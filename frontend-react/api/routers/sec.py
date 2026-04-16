"""SEC Filing API — Filing inventory and Cortex analysis."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from deps import get_snowpark_session

router = APIRouter()


@router.get("/filings")
def get_filings(
    ticker: str = Query(..., min_length=1, max_length=10),
    session=Depends(get_snowpark_session),
):
    ticker = ticker.upper().strip()

    # Try document-level filings first
    rows = session.sql(f"""
        SELECT FILING_ID, FORM_TYPE, FILING_DATE, PERIOD_OF_REPORT,
               COMPANY_NAME, MDA_WORD_COUNT, RISK_WORD_COUNT,
               EXTRACTION_STATUS, DATA_QUALITY_SCORE
        FROM RAW.RAW_SEC_FILING_DOCUMENTS
        WHERE TICKER='{ticker}' ORDER BY FILING_DATE DESC
    """).collect()

    if rows:
        return {
            "source": "documents",
            "filings": [
                {k: (str(v) if hasattr(v, "isoformat") else (float(v) if isinstance(v, (int, float)) and v is not None else v))
                 for k, v in r.as_dict().items()}
                for r in rows
            ],
        }

    # Fallback to XBRL filings
    rows = session.sql(f"""
        SELECT DISTINCT CONCEPT, FORM_TYPE, FILED_DATE AS FILING_DATE,
               FISCAL_YEAR, FISCAL_PERIOD, VALUE, DATA_QUALITY_SCORE
        FROM RAW.RAW_SEC_FILINGS
        WHERE TICKER='{ticker}' ORDER BY FILED_DATE DESC LIMIT 50
    """).collect()

    return {
        "source": "filings" if rows else "none",
        "filings": [
            {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in r.as_dict().items()}
            for r in rows
        ],
    }


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
