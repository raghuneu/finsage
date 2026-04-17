"""Chat API — Ask FinSage (Cortex only)."""

import re
import sys
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from deps import get_snowpark_session

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "sec_filings"))

router = APIRouter()


class ChatRequest(BaseModel):
    ticker: str
    question: str


def _get_available_report_tickers() -> set[str]:
    """Return tickers that have at least one output folder with a PDF."""
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        return set()
    tickers: set[str] = set()
    for folder in outputs_dir.iterdir():
        if not folder.is_dir():
            continue
        parts = folder.name.split("_")
        if len(parts) < 3:
            continue
        ticker_parts: list[str] = []
        for p in parts:
            if len(p) == 8 and p.isdigit():
                break
            ticker_parts.append(p)
        if ticker_parts and list(folder.glob("*.pdf")):
            tickers.add("_".join(ticker_parts))
    return tickers


def _get_known_tickers() -> set[str]:
    """Load configured tickers from tickers.yaml."""
    config_path = PROJECT_ROOT / "config" / "tickers.yaml"
    if not config_path.exists():
        return set()
    try:
        import yaml
        with open(config_path) as f:
            data = yaml.safe_load(f)
        tickers: set[str] = set()
        if isinstance(data, dict) and "tickers" in data:
            for sector_tickers in data["tickers"].values():
                if isinstance(sector_tickers, list):
                    tickers.update(t.upper() for t in sector_tickers)
        return tickers
    except Exception:
        return set()


_COMMON_WORDS = {
    "A", "I", "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IF",
    "IN", "IS", "IT", "ME", "MY", "NO", "OF", "OK", "ON", "OR", "SO", "TO",
    "UP", "US", "WE", "VS", "THE", "AND", "ARE", "BUT", "CAN", "DID", "FOR",
    "GET", "GOT", "HAS", "HAD", "HER", "HIM", "HIS", "HOW", "ITS", "LET",
    "MAY", "NEW", "NOT", "NOW", "OLD", "OUR", "OUT", "OWN", "SAY", "SHE",
    "TOO", "USE", "WAY", "WHO", "WHY", "ALL", "ANY", "BIG", "DAY", "END",
    "FAR", "FEW", "KEY", "MAN", "RUN", "SET", "TOP", "TRY", "TWO",
    "ALSO", "BACK", "BEEN", "BOTH", "CALL", "COME", "EACH", "FIND", "GIVE",
    "GOOD", "HAVE", "HERE", "HIGH", "JUST", "KEEP", "KNOW", "LAST", "LIKE",
    "LONG", "LOOK", "MADE", "MAKE", "MORE", "MOST", "MUCH", "MUST", "NAME",
    "NEXT", "ONLY", "OVER", "PART", "SAME", "SHOW", "SUCH", "TAKE", "TELL",
    "THAN", "THAT", "THEM", "THEN", "THEY", "THIS", "TIME", "TURN", "VERY",
    "WANT", "WELL", "WHAT", "WHEN", "WILL", "WITH", "WORK", "YEAR",
    "ABOUT", "AFTER", "BEING", "COULD", "EVERY", "FIRST", "FOUND", "GREAT",
    "THEIR", "THERE", "THESE", "THINK", "THREE", "UNDER", "WHERE", "WHICH",
    "WHILE", "WOULD", "RISK", "BEAR", "BULL", "STOCK",
    "COMPARE", "REVENUE", "GROWTH", "PRICE", "MARKET", "SHARE",
}


def _extract_tickers_from_question(question: str, known: set[str]) -> list[str]:
    """Extract ticker symbols mentioned in the question from known tickers."""
    found: list[str] = []
    q_upper = question.upper()
    for t in sorted(known):
        if re.search(rf'\b{re.escape(t)}\b', q_upper):
            found.append(t)
    return found


@router.post("/ask")
def ask_finsage(req: ChatRequest, session=Depends(get_snowpark_session)):
    primary_ticker = req.ticker.upper().strip()

    from document_agent import ask_question, get_company_intelligence, format_analytics_context, cortex_complete, get_filing_text

    # Detect additional tickers in the question
    known = _get_known_tickers()
    available_reports = _get_available_report_tickers()
    mentioned = _extract_tickers_from_question(req.question, known)

    # Build full ticker list (primary + mentioned), deduplicated
    all_tickers = list(dict.fromkeys([primary_ticker] + mentioned))

    # Detect missing report tickers
    all_raw = set(re.findall(r'\b[A-Z]{1,5}\b', req.question.upper()))
    missing_tickers: list[str] = []
    for raw_t in all_raw:
        if raw_t in _COMMON_WORDS or raw_t in available_reports:
            continue
        if raw_t in known:
            missing_tickers.append(raw_t)

    if len(all_tickers) <= 1:
        # Single-ticker mode — original behavior
        try:
            answer = ask_question(session, primary_ticker, req.question)
            return {
                "answer": answer or "No answer was generated.",
                "missing_tickers": missing_tickers,
            }
        except Exception as e:
            return {"error": str(e)}

    # Multi-ticker comparison mode
    try:
        sections: list[str] = []
        for t in all_tickers:
            intel = get_company_intelligence(session, t)
            analytics = format_analytics_context(intel)
            if analytics:
                sections.append(f"=== {t} ===\n{analytics}")

        combined_context = "\n\n".join(sections)
        # Cap at 35k chars to leave room for prompt
        combined_context = combined_context[:35000]

        missing_note = ""
        if missing_tickers:
            missing_note = (
                f"\nNote: The following tickers were mentioned but may not have full data: "
                f"{', '.join(missing_tickers)}. The user should generate reports for these tickers."
            )

        prompt = f"""You are a financial analyst comparing multiple stocks.

You have quantitative analytics data for the following stocks: {', '.join(all_tickers)}.
{missing_note}

QUANTITATIVE DATA:
{combined_context}

QUESTION: {req.question}

Compare the stocks using the data above. Structure your comparison clearly with
sections or key differences highlighted. Be specific with numbers.
If data is missing for any stock, note that clearly.
Do NOT give investment advice. Present facts and let the user draw conclusions.
Keep your answer under 600 words."""

        answer = cortex_complete(session, prompt)
        return {
            "answer": answer or "No answer was generated.",
            "missing_tickers": missing_tickers,
        }
    except Exception as e:
        return {"error": str(e)}
