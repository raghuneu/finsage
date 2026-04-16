"""Chat API — Ask FinSage (Cortex only)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from deps import get_snowpark_session

router = APIRouter()


class ChatRequest(BaseModel):
    ticker: str
    question: str


@router.post("/ask")
def ask_finsage(req: ChatRequest, session=Depends(get_snowpark_session)):
    ticker = req.ticker.upper().strip()

    from document_agent import ask_question

    try:
        answer = ask_question(session, ticker, req.question)
        return {"answer": answer or "No answer was generated."}
    except Exception as e:
        return {"error": str(e)}
