"""Analytics API — Stock metrics, fundamentals, sentiment, SEC financials."""

from fastapi import APIRouter, Depends, Query
from deps import get_snowpark_session

router = APIRouter()


def _rows_to_dicts(rows, float_cols=None):
    """Convert Snowpark Row objects to JSON-safe dicts."""
    float_cols = float_cols or []
    result = []
    for r in rows:
        d = r.as_dict()
        for k in d:
            if k in float_cols and d[k] is not None:
                d[k] = float(d[k])
            elif hasattr(d[k], "isoformat"):
                d[k] = str(d[k])
        result.append(d)
    return result


@router.get("/stock-metrics")
def get_stock_metrics(
    ticker: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(90, ge=1, le=365),
    session=Depends(get_snowpark_session),
):
    ticker = ticker.upper().strip()
    rows = session.sql(f"""
        SELECT DATE, OPEN, HIGH, LOW, CLOSE, SMA_7D, SMA_30D, SMA_90D, VOLUME,
               DAILY_RETURN_PCT, VOLATILITY_30D_PCT, TREND_SIGNAL
        FROM ANALYTICS.FCT_STOCK_METRICS
        WHERE TICKER='{ticker}' ORDER BY DATE DESC LIMIT {limit}
    """).collect()
    return _rows_to_dicts(rows, float_cols=[
        "OPEN", "HIGH", "LOW", "CLOSE", "SMA_7D", "SMA_30D", "SMA_90D",
        "VOLUME", "DAILY_RETURN_PCT", "VOLATILITY_30D_PCT",
    ])


@router.get("/fundamentals")
def get_fundamentals(
    ticker: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(12, ge=1, le=40),
    session=Depends(get_snowpark_session),
):
    ticker = ticker.upper().strip()
    rows = session.sql(f"""
        SELECT FISCAL_QUARTER, REVENUE, NET_INCOME, EPS,
               REVENUE_GROWTH_QOQ_PCT,
               REVENUE_GROWTH_YOY_PCT,
               NET_MARGIN_PCT,
               FUNDAMENTAL_SIGNAL
        FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
        WHERE TICKER='{ticker}' ORDER BY SUBSTRING(FISCAL_QUARTER, 4) DESC, SUBSTRING(FISCAL_QUARTER, 1, 2) DESC LIMIT {limit}
    """).collect()
    return _rows_to_dicts(rows, float_cols=[
        "REVENUE", "NET_INCOME", "EPS", "REVENUE_GROWTH_QOQ_PCT",
        "REVENUE_GROWTH_YOY_PCT", "NET_MARGIN_PCT",
    ])


@router.get("/sentiment")
def get_sentiment(
    ticker: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(30, ge=1, le=90),
    session=Depends(get_snowpark_session),
):
    ticker = ticker.upper().strip()
    rows = session.sql(f"""
        SELECT NEWS_DATE, TOTAL_ARTICLES,
               POSITIVE_COUNT, NEGATIVE_COUNT,
               SENTIMENT_SCORE,
               SENTIMENT_SCORE_7D_AVG,
               SENTIMENT_LABEL, SENTIMENT_TREND
        FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG
        WHERE TICKER='{ticker}' ORDER BY NEWS_DATE DESC LIMIT {limit}
    """).collect()
    return _rows_to_dicts(rows, float_cols=[
        "TOTAL_ARTICLES", "POSITIVE_COUNT", "NEGATIVE_COUNT",
        "SENTIMENT_SCORE", "SENTIMENT_SCORE_7D_AVG",
    ])


@router.get("/sec-financials")
def get_sec_financials(
    ticker: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(10, ge=1, le=40),
    session=Depends(get_snowpark_session),
):
    ticker = ticker.upper().strip()
    rows = session.sql(f"""
        SELECT FISCAL_YEAR, FISCAL_PERIOD,
               TOTAL_REVENUE, NET_INCOME,
               OPERATING_MARGIN_PCT,
               NET_MARGIN_PCT,
               RETURN_ON_EQUITY_PCT,
               DEBT_TO_EQUITY_RATIO,
               REVENUE_GROWTH_YOY_PCT,
               FINANCIAL_HEALTH
        FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
        WHERE TICKER='{ticker}' ORDER BY FISCAL_YEAR DESC, CASE FISCAL_PERIOD WHEN 'FY' THEN 0 WHEN 'Q4' THEN 1 WHEN 'Q3' THEN 2 WHEN 'Q2' THEN 3 WHEN 'Q1' THEN 4 ELSE 5 END LIMIT {limit}
    """).collect()
    return _rows_to_dicts(rows, float_cols=[
        "TOTAL_REVENUE", "NET_INCOME", "OPERATING_MARGIN_PCT", "NET_MARGIN_PCT",
        "RETURN_ON_EQUITY_PCT", "DEBT_TO_EQUITY_RATIO", "REVENUE_GROWTH_YOY_PCT",
    ])
