"""Report API — Quick report and CAVM pipeline."""

import os
import sys
import json
import uuid
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from deps import get_snowpark_session

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logger = logging.getLogger("finsage.report")

STAGE_FQN = "@FINSAGE_DB.PUBLIC.FINSAGE_REPORTS_STAGE"
PRESIGNED_EXPIRY = 3600  # 1 hour


def _upload_to_stage(local_path: str, stage_path: str) -> Optional[str]:
    """Upload a file to FINSAGE_REPORTS_STAGE and return a pre-signed URL.

    Returns None if upload fails (e.g. no Snowflake connection).
    """
    try:
        from snowflake_connection import get_session
        session = get_session()
        try:
            session.file.put(
                f"file://{local_path}",
                f"{STAGE_FQN}/{stage_path}",
                auto_compress=False,
                overwrite=True,
            )
            rows = session.sql(
                f"SELECT GET_PRESIGNED_URL({STAGE_FQN}, '{stage_path}', {PRESIGNED_EXPIRY})"
            ).collect()
            url = rows[0][0] if rows else None
            logger.info("Uploaded %s to stage -> %s", stage_path, url[:80] if url else "N/A")
            return url
        finally:
            session.close()
    except Exception as e:
        logger.warning("Stage upload failed for %s: %s", stage_path, e)
        return None


def _get_presigned_url(stage_path: str) -> Optional[str]:
    """Get a fresh pre-signed URL for an existing file on the stage."""
    try:
        from snowflake_connection import get_session
        session = get_session()
        try:
            rows = session.sql(
                f"SELECT GET_PRESIGNED_URL({STAGE_FQN}, '{stage_path}', {PRESIGNED_EXPIRY})"
            ).collect()
            return rows[0][0] if rows else None
        finally:
            session.close()
    except Exception:
        return None


def _list_stage_reports(ticker: str) -> List[dict]:
    """Query the stage directory table for reports matching a ticker prefix."""
    try:
        from snowflake_connection import get_session
        session = get_session()
        try:
            rows = session.sql(
                f"SELECT RELATIVE_PATH, SIZE, LAST_MODIFIED "
                f"FROM DIRECTORY({STAGE_FQN}) "
                f"WHERE RELATIVE_PATH LIKE '{ticker.upper()}_%' "
                f"AND RELATIVE_PATH LIKE '%.pdf'"
            ).collect()
            results = []
            for row in rows:
                results.append({
                    "relative_path": row["RELATIVE_PATH"],
                    "size": row["SIZE"],
                    "last_modified": str(row["LAST_MODIFIED"]) if row["LAST_MODIFIED"] else None,
                })
            return results
        finally:
            session.close()
    except Exception as e:
        logger.warning("Stage directory listing failed: %s", e)
        return []

router = APIRouter()

# In-memory task store for CAVM pipeline progress
_tasks: Dict[str, dict] = {}


class QuickReportRequest(BaseModel):
    ticker: str


class CAVMRequest(BaseModel):
    ticker: str
    debug: bool = False
    skip_charts: bool = False
    charts_dir: Optional[str] = None
    auto_load: bool = True  # automatically load missing data before pipeline
    detail_level: str = "detailed"  # "detailed" or "summary"


@router.post("/quick")
def quick_report(req: QuickReportRequest, session=Depends(get_snowpark_session)):
    ticker = req.ticker.upper().strip()

    from document_agent import full_report

    try:
        result = full_report(session, ticker)
        return {"result": result or "Report returned no content."}
    except Exception as e:
        return {"error": str(e)}


@router.post("/cavm")
def start_cavm_pipeline(req: CAVMRequest, session=Depends(get_snowpark_session)):
    ticker = req.ticker.upper().strip()

    # Pre-flight readiness check
    from utils.data_readiness import check_data_readiness
    readiness = check_data_readiness(session, ticker)

    if not readiness["min_viable"] and not req.auto_load:
        return {
            "error": "insufficient_data",
            "readiness": readiness,
            "message": f"Required data missing for {ticker}: {', '.join(readiness['missing'])}. "
                       f"Use POST /api/pipeline/load to fetch data first, or set auto_load=true.",
        }

    task_id = str(uuid.uuid4())[:8]

    _tasks[task_id] = {
        "status": "running",
        "stage": 0,
        "ticker": ticker,
        "result": None,
        "error": None,
        "messages": [],
        "auto_load": req.auto_load and not readiness["ready"],
    }

    def _run():
        try:
            # Auto-load missing data if requested
            if req.auto_load and not readiness["ready"]:
                _tasks[task_id]["stage"] = -1  # indicates data loading
                from utils.on_demand_loader import ensure_data_for_ticker
                ensure_data_for_ticker(ticker=ticker)

            from orchestrator import generate_report_pipeline

            def _update_stage(stage: int):
                _tasks[task_id]["stage"] = stage

            def _add_message(msg: str):
                msgs = _tasks[task_id]["messages"]
                msgs.append(msg)
                if len(msgs) > 20:
                    _tasks[task_id]["messages"] = msgs[-20:]

            result = generate_report_pipeline(
                ticker=ticker,
                debug=req.debug,
                skip_charts=req.skip_charts,
                charts_dir=req.charts_dir,
                detail_level=req.detail_level,
                on_stage=_update_stage,
                on_message=_add_message,
            )
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["stage"] = 4

            pdf_path = result.get("pdf_path", "")
            stage_url = None

            # Upload PDF to Snowflake stage for persistent storage
            if pdf_path and Path(pdf_path).exists():
                local_pdf = Path(pdf_path)
                # Stage path mirrors local: TICKER_YYYYMMDD_HHMMSS/filename.pdf
                stage_key = f"{local_pdf.parent.name}/{local_pdf.name}"
                stage_url = _upload_to_stage(str(local_pdf), stage_key)

            _tasks[task_id]["result"] = {
                "pdf_path": pdf_path,
                "stage_url": stage_url,
                "elapsed_seconds": result.get("elapsed_seconds", 0),
                "charts_count": len(result.get("charts", [])),
                "charts_validated": sum(1 for c in result.get("charts", []) if c.get("validated")),
                "charts": [
                    {"chart_id": c.get("chart_id", ""), "file_path": c.get("file_path", ""), "validated": c.get("validated", False)}
                    for c in result.get("charts", [])
                ],
            }
        except Exception as e:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["error"] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"task_id": task_id, "readiness": readiness}


@router.get("/cavm/status/{task_id}")
def cavm_status(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        return {"error": "Task not found"}
    return task


class ReportHistoryItem(BaseModel):
    folder_name: str
    pdf_filename: str
    run_at: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    detail_level: str  # "summary" or "full"
    pdf_path: str  # relative path for download endpoint


@router.get("/history/{ticker}", response_model=List[ReportHistoryItem])
def report_history(ticker: str):
    """Return previously generated reports for a ticker, newest first.

    Merges local filesystem results with Snowflake stage directory listing
    so reports survive ephemeral filesystem resets on free hosting tiers.
    """
    seen_paths: set = set()
    results: List[ReportHistoryItem] = []

    # --- 1. Local filesystem scan (works in local dev, may be empty on Render) ---
    outputs_dir = PROJECT_ROOT / "outputs"
    if outputs_dir.exists():
        prefix = ticker.upper() + "_"
        for folder in outputs_dir.iterdir():
            if not folder.is_dir() or not folder.name.startswith(prefix):
                continue

            pdfs = list(folder.glob("*.pdf"))
            if not pdfs:
                continue

            run_at = None
            elapsed = None
            result_file = folder / "pipeline_result.json"
            if result_file.exists():
                try:
                    meta = json.loads(result_file.read_text())
                    run_at = meta.get("run_at")
                    elapsed = meta.get("elapsed_seconds")
                except (json.JSONDecodeError, OSError):
                    pass

            if not run_at:
                parts = folder.name.split("_")
                if len(parts) >= 3:
                    try:
                        dt = datetime.strptime(f"{parts[-2]}_{parts[-1]}", "%Y%m%d_%H%M%S")
                        run_at = dt.isoformat()
                    except ValueError:
                        pass

            for pdf in pdfs:
                pdf_path = f"{folder.name}/{pdf.name}"
                seen_paths.add(pdf_path)
                detail = "summary" if "Summary" in pdf.name else "full"
                results.append(ReportHistoryItem(
                    folder_name=folder.name,
                    pdf_filename=pdf.name,
                    run_at=run_at,
                    elapsed_seconds=elapsed,
                    detail_level=detail,
                    pdf_path=pdf_path,
                ))

    # --- 2. Snowflake stage directory listing (catches reports not on local FS) ---
    stage_reports = _list_stage_reports(ticker)
    for sr in stage_reports:
        rel = sr["relative_path"]  # e.g. "AAPL_20260420_120000/report.pdf"
        if rel in seen_paths:
            continue
        parts = rel.split("/")
        if len(parts) != 2:
            continue
        folder_name, pdf_name = parts[0], parts[1]

        # Infer run_at from folder name
        run_at = None
        folder_parts = folder_name.split("_")
        if len(folder_parts) >= 3:
            try:
                dt = datetime.strptime(f"{folder_parts[-2]}_{folder_parts[-1]}", "%Y%m%d_%H%M%S")
                run_at = dt.isoformat()
            except ValueError:
                pass
        if not run_at and sr["last_modified"]:
            run_at = sr["last_modified"]

        detail = "summary" if "Summary" in pdf_name else "full"
        results.append(ReportHistoryItem(
            folder_name=folder_name,
            pdf_filename=pdf_name,
            run_at=run_at,
            elapsed_seconds=None,
            detail_level=detail,
            pdf_path=rel,
        ))

    results.sort(key=lambda r: r.run_at or "", reverse=True)
    return results


@router.get("/available-tickers")
def available_report_tickers() -> List[str]:
    """Return tickers that have at least one completed report (folder with a PDF)."""
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        return []

    tickers: set = set()
    for folder in outputs_dir.iterdir():
        if not folder.is_dir():
            continue
        parts = folder.name.split("_")
        if len(parts) < 3:
            continue
        # Ticker is everything before the date segment (8-digit YYYYMMDD)
        ticker_parts: list = []
        for p in parts:
            if len(p) == 8 and p.isdigit():
                break
            ticker_parts.append(p)
        if not ticker_parts:
            continue
        candidate = "_".join(ticker_parts)
        if list(folder.glob("*.pdf")):
            tickers.add(candidate)

    return sorted(tickers)


@router.get("/download/{filename:path}")
def download_report(filename: str):
    """Download a PDF report — serves from local FS or redirects to Snowflake stage URL."""
    # 1. Try local filesystem first (works in local dev and when file is cached)
    filepath = PROJECT_ROOT / "outputs" / filename
    if not filepath.exists():
        filepath = Path(filename)

    if filepath.exists() and filepath.suffix == ".pdf":
        return FileResponse(str(filepath), media_type="application/pdf", filename=filepath.name)

    # 2. Fall back to Snowflake stage pre-signed URL (production / ephemeral FS)
    url = _get_presigned_url(filename)
    if url:
        return RedirectResponse(url=url, status_code=302)

    return {"error": "File not found"}
