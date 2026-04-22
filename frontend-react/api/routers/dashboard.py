"""Dashboard API — KPIs, price history, headlines."""

import time
from cachetools import TTLCache
from fastapi import APIRouter, Depends, Query
from deps import get_snowpark_session

router = APIRouter()

# Cache KPIs for 5 minutes — data changes at most daily
_kpi_cache: TTLCache = TTLCache(maxsize=100, ttl=300)
_price_cache: TTLCache = TTLCache(maxsize=100, ttl=300)
_headlines_cache: TTLCache = TTLCache(maxsize=100, ttl=300)


@router.get("/kpis")
def get_kpis(ticker: str = Query(..., min_length=1, max_length=10), session=Depends(get_snowpark_session)):
    ticker = ticker.upper().strip()

    if ticker in _kpi_cache:
        return _kpi_cache[ticker]

    # Single CTE query combining all 5 data sources
    rows = session.sql("""
        WITH company AS (
            SELECT MARKET_CAP, PE_RATIO, PROFIT_MARGIN
            FROM ANALYTICS.DIM_COMPANY WHERE TICKER = ?
        ),
        stock AS (
            SELECT CLOSE, DAILY_RETURN_PCT, TREND_SIGNAL
            FROM ANALYTICS.FCT_STOCK_METRICS
            WHERE TICKER = ? ORDER BY DATE DESC LIMIT 1
        ),
        fundamentals AS (
            SELECT REVENUE, REVENUE_GROWTH_YOY_PCT, FUNDAMENTAL_SIGNAL
            FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
            WHERE TICKER = ? ORDER BY FISCAL_QUARTER DESC LIMIT 1
        ),
        sentiment AS (
            SELECT SENTIMENT_SCORE, SENTIMENT_LABEL, SENTIMENT_TREND
            FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG
            WHERE TICKER = ? ORDER BY NEWS_DATE DESC LIMIT 1
        ),
        sec_fin AS (
            SELECT FINANCIAL_HEALTH
            FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
            WHERE TICKER = ? ORDER BY FISCAL_YEAR DESC, FISCAL_PERIOD DESC LIMIT 1
        )
        SELECT
            c.MARKET_CAP, c.PE_RATIO, c.PROFIT_MARGIN,
            s.CLOSE, s.DAILY_RETURN_PCT, s.TREND_SIGNAL,
            f.REVENUE, f.REVENUE_GROWTH_YOY_PCT, f.FUNDAMENTAL_SIGNAL,
            snt.SENTIMENT_SCORE, snt.SENTIMENT_LABEL, snt.SENTIMENT_TREND,
            sf.FINANCIAL_HEALTH
        FROM (SELECT 1 AS _join) AS d
        LEFT JOIN company c ON TRUE
        LEFT JOIN stock s ON TRUE
        LEFT JOIN fundamentals f ON TRUE
        LEFT JOIN sentiment snt ON TRUE
        LEFT JOIN sec_fin sf ON TRUE
    """, params=[ticker, ticker, ticker, ticker, ticker]).collect()

    profile = {}
    stock = {}
    fundamentals = {}
    sentiment = {}
    sec_fin = {}

    if rows:
        r = rows[0]
        if r["MARKET_CAP"] is not None or r["PE_RATIO"] is not None:
            profile = {"market_cap": r["MARKET_CAP"], "pe_ratio": r["PE_RATIO"], "profit_margin": r["PROFIT_MARGIN"]}
        if r["CLOSE"] is not None:
            stock = {"close": r["CLOSE"], "daily_return_pct": r["DAILY_RETURN_PCT"], "trend_signal": r["TREND_SIGNAL"]}
        if r["REVENUE"] is not None:
            fundamentals = {
                "revenue": r["REVENUE"],
                "revenue_growth_yoy_pct": r["REVENUE_GROWTH_YOY_PCT"],
                "fundamental_signal": r["FUNDAMENTAL_SIGNAL"],
            }
        if r["SENTIMENT_SCORE"] is not None:
            sentiment = {
                "sentiment_score": r["SENTIMENT_SCORE"],
                "sentiment_label": r["SENTIMENT_LABEL"],
                "sentiment_trend": r["SENTIMENT_TREND"],
            }
        if r["FINANCIAL_HEALTH"] is not None:
            sec_fin = {"financial_health": r["FINANCIAL_HEALTH"]}

    result = {
        "ticker": ticker,
        "profile": profile,
        "stock": stock,
        "fundamentals": fundamentals,
        "sentiment": sentiment,
        "sec_financials": sec_fin,
    }
    _kpi_cache[ticker] = result
    return result


@router.get("/price-history")
def get_price_history(
    ticker: str = Query(..., min_length=1, max_length=10),
    days: int = Query(90, ge=1, le=365),
    session=Depends(get_snowpark_session),
):
    ticker = ticker.upper().strip()
    cache_key = f"{ticker}:{days}"

    if cache_key in _price_cache:
        return _price_cache[cache_key]

    rows = session.sql("""
        SELECT DATE, OPEN, HIGH, LOW, CLOSE, VOLUME, SMA_7D, SMA_30D, SMA_90D
        FROM ANALYTICS.FCT_STOCK_METRICS
        WHERE TICKER = ?
        ORDER BY DATE DESC LIMIT ?
    """, params=[ticker, days]).collect()

    result = [
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
    _price_cache[cache_key] = result
    return result


@router.get("/headlines")
def get_headlines(
    ticker: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(10, ge=1, le=50),
    session=Depends(get_snowpark_session),
):
    ticker = ticker.upper().strip()
    cache_key = f"{ticker}:{limit}"

    if cache_key in _headlines_cache:
        return _headlines_cache[cache_key]

    rows = session.sql("""
        SELECT TITLE, PUBLISHED_AT, SOURCE_NAME
        FROM RAW.RAW_NEWS
        WHERE TICKER = ? AND TITLE IS NOT NULL
        ORDER BY PUBLISHED_AT DESC LIMIT ?
    """, params=[ticker, limit]).collect()

    result = [
        {
            "title": r["TITLE"],
            "published_at": str(r["PUBLISHED_AT"]) if r["PUBLISHED_AT"] else None,
            "source_name": r["SOURCE_NAME"],
        }
        for r in rows
    ]
    _headlines_cache[cache_key] = result
    return result
