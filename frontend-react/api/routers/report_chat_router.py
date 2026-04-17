"""Report Chat Router — conversational Q&A about generated reports via Snowflake Cortex."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_snowpark_session
from routers.report_chat import ask, reset_session

router = APIRouter()


class AskRequest(BaseModel):
    session_id: str
    ticker: str
    question: str
    folder_name: Optional[str] = None


class ResetRequest(BaseModel):
    session_id: str


@router.post("/ask")
def report_chat_ask(req: AskRequest, session=Depends(get_snowpark_session)):
    try:
        result = ask(session, req.session_id, req.ticker, req.question, req.folder_name)
        return result  # {answer: str, missing_tickers: list[str]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
def report_chat_reset(req: ResetRequest):
    cleared = reset_session(req.session_id)
    return {"ok": True, "cleared": cleared}
