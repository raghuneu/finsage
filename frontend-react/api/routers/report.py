"""Report API — Quick report and CAVM pipeline."""

import os
import sys
import json
import uuid
import threading
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from deps import get_snowpark_session

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

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
            _tasks[task_id]["result"] = {
                "pdf_path": result.get("pdf_path", ""),
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
    """Return previously generated reports for a ticker, newest first."""
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        return []

    prefix = ticker.upper() + "_"
    results: List[ReportHistoryItem] = []

    for folder in outputs_dir.iterdir():
        if not folder.is_dir() or not folder.name.startswith(prefix):
            continue

        # Look for PDF files in this folder
        pdfs = list(folder.glob("*.pdf"))
        if not pdfs:
            continue

        # Try to read pipeline_result.json for metadata
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

        # Infer run_at from folder name if not in metadata (TICKER_YYYYMMDD_HHMMSS)
        if not run_at:
            parts = folder.name.split("_")
            if len(parts) >= 3:
                try:
                    dt = datetime.strptime(f"{parts[-2]}_{parts[-1]}", "%Y%m%d_%H%M%S")
                    run_at = dt.isoformat()
                except ValueError:
                    pass

        for pdf in pdfs:
            detail = "summary" if "Summary" in pdf.name else "full"
            results.append(ReportHistoryItem(
                folder_name=folder.name,
                pdf_filename=pdf.name,
                run_at=run_at,
                elapsed_seconds=elapsed,
                detail_level=detail,
                pdf_path=f"{folder.name}/{pdf.name}",
            ))

    # Sort newest first by run_at
    results.sort(key=lambda r: r.run_at or "", reverse=True)
    return results


@router.get("/download/{filename:path}")
def download_report(filename: str):
    """Download a PDF report from the outputs directory."""
    filepath = PROJECT_ROOT / "outputs" / filename

    if not filepath.exists():
        filepath = Path(filename)

    if filepath.exists() and filepath.suffix == ".pdf":
        return FileResponse(str(filepath), media_type="application/pdf", filename=filepath.name)

    return {"error": "File not found"}
