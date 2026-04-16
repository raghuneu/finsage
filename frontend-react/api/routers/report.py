"""Report API — Quick report and CAVM pipeline."""

import os
import uuid
import threading
from typing import Dict, Optional
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from deps import get_snowpark_session

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
def start_cavm_pipeline(req: CAVMRequest):
    ticker = req.ticker.upper().strip()
    task_id = str(uuid.uuid4())[:8]

    _tasks[task_id] = {
        "status": "running",
        "stage": 0,
        "ticker": ticker,
        "result": None,
        "error": None,
    }

    def _run():
        try:
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

    return {"task_id": task_id}


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
