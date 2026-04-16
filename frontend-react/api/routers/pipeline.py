"""Pipeline API — Data readiness checks and on-demand loading."""

import sys
import uuid
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from deps import get_snowpark_session

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

router = APIRouter()

# In-memory task store for async data-loading jobs
_load_tasks: dict[str, dict] = {}


class ReadinessRequest(BaseModel):
    ticker: str


class LoadDataRequest(BaseModel):
    ticker: str
    include_news: bool = True
    include_sec: bool = True
    include_s3_filings: bool = False
    run_dbt: bool = True


@router.post("/readiness")
def check_readiness(req: ReadinessRequest, session=Depends(get_snowpark_session)):
    """Check whether sufficient data exists for a ticker."""
    from utils.data_readiness import check_data_readiness, check_raw_data_exists

    ticker = req.ticker.upper().strip()
    readiness = check_data_readiness(session, ticker)
    raw_counts = check_raw_data_exists(session, ticker)

    return {
        "readiness": readiness,
        "raw_counts": raw_counts,
    }


@router.post("/load")
def start_data_load(req: LoadDataRequest):
    """Start an async data-loading job for a ticker.

    Returns a task_id that can be polled via GET /load/status/{task_id}.
    """
    ticker = req.ticker.upper().strip()
    task_id = str(uuid.uuid4())[:8]

    _load_tasks[task_id] = {
        "status": "running",
        "stage": "starting",
        "ticker": ticker,
        "result": None,
        "error": None,
    }

    def _run():
        try:
            from utils.on_demand_loader import ensure_data_for_ticker

            def _progress(stage, detail=""):
                _load_tasks[task_id]["stage"] = stage

            result = ensure_data_for_ticker(
                ticker=ticker,
                include_news=req.include_news,
                include_sec=req.include_sec,
                include_s3_filings=req.include_s3_filings,
                run_dbt=req.run_dbt,
                progress_callback=_progress,
            )

            _load_tasks[task_id]["status"] = "completed"
            _load_tasks[task_id]["result"] = {
                "readiness": result["readiness"],
                "loaded": result["loaded"],
                "dbt_success": result["dbt_success"],
            }
        except Exception as e:
            _load_tasks[task_id]["status"] = "failed"
            _load_tasks[task_id]["error"] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"task_id": task_id}


@router.get("/load/status/{task_id}")
def load_status(task_id: str):
    """Poll the status of a data-loading job."""
    task = _load_tasks.get(task_id)
    if not task:
        return {"error": "Task not found"}
    return task
