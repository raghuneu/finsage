"""Report API — Quick report and CAVM pipeline."""

import os
import sys
import uuid
import threading
from typing import Dict, Optional
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

            result = generate_report_pipeline(
                ticker=ticker,
                debug=req.debug,
                skip_charts=req.skip_charts,
                charts_dir=req.charts_dir,
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


@router.get("/download/{filename:path}")
def download_report(filename: str):
    # Look in the outputs directory
    project_root = Path(__file__).resolve().parent.parent.parent
    filepath = project_root / "outputs" / filename

    if not filepath.exists():
        # Try as absolute path
        filepath = Path(filename)

    if filepath.exists() and filepath.suffix == ".pdf":
        return FileResponse(str(filepath), media_type="application/pdf", filename=filepath.name)

    return {"error": "File not found"}
