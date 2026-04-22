"""SEC Filing API — Filing inventory and Cortex analysis."""

from cachetools import TTLCache
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from deps import get_snowpark_session

router = APIRouter()

_sec_cache: TTLCache = TTLCache(maxsize=100, ttl=300)


@router.get("/filings")
def get_filings(
    ticker: str = Query(..., min_length=1, max_length=10),
    session=Depends(get_snowpark_session),
):
    ticker = ticker.upper().strip()

    if ticker in _sec_cache:
        return _sec_cache[ticker]

    # Try document-level filings first
    rows = session.sql("""
        SELECT FILING_ID, FORM_TYPE, FILING_DATE, PERIOD_OF_REPORT,
               COMPANY_NAME, MDA_WORD_COUNT, RISK_WORD_COUNT,
               EXTRACTION_STATUS, DATA_QUALITY_SCORE
        FROM RAW.RAW_SEC_FILING_DOCUMENTS
        WHERE TICKER = ? ORDER BY FILING_DATE DESC
    """, params=[ticker]).collect()

    if rows:
        result = {
            "source": "documents",
            "filings": [
                {k: (str(v) if hasattr(v, "isoformat") else (float(v) if isinstance(v, (int, float)) and v is not None else v))
                 for k, v in r.as_dict().items()}
                for r in rows
            ],
        }
        _sec_cache[ticker] = result
        return result

    # Fallback to XBRL filings
    rows = session.sql("""
        SELECT DISTINCT CONCEPT, FORM_TYPE, FILED_DATE AS FILING_DATE,
               FISCAL_YEAR, FISCAL_PERIOD, VALUE, DATA_QUALITY_SCORE
        FROM RAW.RAW_SEC_FILINGS
        WHERE TICKER = ? ORDER BY FILED_DATE DESC LIMIT 50
    """, params=[ticker]).collect()

    result = {
        "source": "filings" if rows else "none",
        "filings": [
            {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in r.as_dict().items()}
            for r in rows
        ],
    }
    _sec_cache[ticker] = result
    return result


class AnalyzeRequest(BaseModel):
    ticker: str
    mode: str  # summary | risks | mda | compare


@router.post("/analyze")
def analyze_filing(req: AnalyzeRequest, session=Depends(get_snowpark_session)):
    ticker = req.ticker.upper().strip()

    from document_agent import summarize_filing, analyze_risks, analyze_mda, compare_filings

    fn_map = {
        "summary": summarize_filing,
        "risks": analyze_risks,
        "mda": analyze_mda,
        "compare": compare_filings,
    }

    fn = fn_map.get(req.mode)
    if fn is None:
        return {"error": f"Unknown mode: {req.mode}"}

    try:
        result = fn(session, ticker)
        return {"result": result or "Analysis returned no results."}
    except Exception as e:
        return {"error": str(e)}
