"""Dashboard API — KPIs, price history, headlines."""

from fastapi import APIRouter, Depends, Query
from deps import get_snowpark_session

router = APIRouter()


@router.get("/kpis")
def get_kpis(ticker: str = Query(..., min_length=1, max_length=10), session=Depends(get_snowpark_session)):
    ticker = ticker.upper().strip()

    profile = {}
    try:
        rows = session.sql(f"""
            SELECT MARKET_CAP, PE_RATIO, PROFIT_MARGIN
            FROM ANALYTICS.DIM_COMPANY WHERE TICKER = '{ticker}'
        """).collect()
        if rows:
            r = rows[0]
            profile = {"market_cap": r["MARKET_CAP"], "pe_ratio": r["PE_RATIO"], "profit_margin": r["PROFIT_MARGIN"]}
    except Exception:
        pass

    stock = {}
    try:
        rows = session.sql(f"""
            SELECT CLOSE, DAILY_RETURN_PCT, TREND_SIGNAL
            FROM ANALYTICS.FCT_STOCK_METRICS
            WHERE TICKER = '{ticker}' ORDER BY DATE DESC LIMIT 1
        """).collect()
        if rows:
            r = rows[0]
            stock = {"close": r["CLOSE"], "daily_return_pct": r["DAILY_RETURN_PCT"], "trend_signal": r["TREND_SIGNAL"]}
    except Exception:
        pass

    fundamentals = {}
    try:
        rows = session.sql(f"""
            SELECT REVENUE, REVENUE_GROWTH_YOY_PCT,
                   NET_INCOME, EPS, FUNDAMENTAL_SIGNAL
            FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
            WHERE TICKER = '{ticker}' ORDER BY FISCAL_QUARTER DESC LIMIT 1
        """).collect()
        if rows:
            r = rows[0]
            fundamentals = {
                "revenue": r["REVENUE"],
                "revenue_growth_yoy_pct": r["REVENUE_GROWTH_YOY_PCT"],
                "fundamental_signal": r["FUNDAMENTAL_SIGNAL"],
            }
    except Exception:
        pass

    sentiment = {}
    try:
        rows = session.sql(f"""
            SELECT SENTIMENT_SCORE, SENTIMENT_LABEL, SENTIMENT_TREND
            FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG
            WHERE TICKER = '{ticker}' ORDER BY NEWS_DATE DESC LIMIT 1
        """).collect()
        if rows:
            r = rows[0]
            sentiment = {
                "sentiment_score": r["SENTIMENT_SCORE"],
                "sentiment_label": r["SENTIMENT_LABEL"],
                "sentiment_trend": r["SENTIMENT_TREND"],
            }
    except Exception:
        pass

    sec_fin = {}
    try:
        rows = session.sql(f"""
            SELECT FINANCIAL_HEALTH
            FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
            WHERE TICKER = '{ticker}' ORDER BY FISCAL_YEAR DESC, FISCAL_PERIOD DESC LIMIT 1
        """).collect()
        if rows:
            sec_fin = {"financial_health": rows[0]["FINANCIAL_HEALTH"]}
    except Exception:
        pass

    return {
        "ticker": ticker,
        "profile": profile,
        "stock": stock,
        "fundamentals": fundamentals,
        "sentiment": sentiment,
        "sec_financials": sec_fin,
    }


@router.get("/price-history")
def get_price_history(
    ticker: str = Query(..., min_length=1, max_length=10),
    days: int = Query(90, ge=1, le=365),
    session=Depends(get_snowpark_session),
):
    ticker = ticker.upper().strip()
    rows = session.sql(f"""
        SELECT DATE, OPEN, HIGH, LOW, CLOSE, VOLUME, SMA_7D, SMA_30D, SMA_90D
        FROM ANALYTICS.FCT_STOCK_METRICS
        WHERE TICKER = '{ticker}'
        ORDER BY DATE DESC LIMIT {days}
    """).collect()

    return [
        {
            "date": str(r["DATE"]),
            "open": float(r["OPEN"]) if r["OPEN"] is not None else None,
            "high": float(r["HIGH"]) if r["HIGH"] is not None else None,
            "low": float(r["LOW"]) if r["LOW"] is not None else None,
            "close": float(r["CLOSE"]) if r["CLOSE"] is not None else None,
            "volume": float(r["VOLUME"]) if r["VOLUME"] is not None else None,
            "sma_7d": float(r["SMA_7D"]) if r["SMA_7D"] is not None else None,
            "sma_30d": float(r["SMA_30D"]) if r["SMA_30D"] is not None else None,
            "sma_90d": float(r["SMA_90D"]) if r["SMA_90D"] is not None else None,
        }
        for r in rows
    ]


@router.get("/headlines")
def get_headlines(
    ticker: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(10, ge=1, le=50),
    session=Depends(get_snowpark_session),
):
    ticker = ticker.upper().strip()
    rows = session.sql(f"""
        SELECT TITLE, PUBLISHED_AT, SOURCE_NAME
        FROM RAW.RAW_NEWS
        WHERE TICKER = '{ticker}' AND TITLE IS NOT NULL
        ORDER BY PUBLISHED_AT DESC LIMIT {limit}
    """).collect()

    return [
        {
            "title": r["TITLE"],
            "published_at": str(r["PUBLISHED_AT"]) if r["PUBLISHED_AT"] else None,
            "source_name": r["SOURCE_NAME"],
        }
        for r in rows
    ]
