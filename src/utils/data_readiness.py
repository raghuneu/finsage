"""
Data readiness checker for FinSage.

Queries the ANALYTICS layer to determine if sufficient data exists
for a given ticker to generate a meaningful research report.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum row counts for each data source to be considered "ready"
MIN_ROWS = {
    "stock": 1,
    "fundamentals": 1,
    "news": 0,       # soft requirement — report can degrade without it
    "sec": 0,        # soft requirement — report can degrade without it
}

# Tables queried for each data source
TABLE_MAP = {
    "stock": "ANALYTICS.FCT_STOCK_METRICS",
    "fundamentals": "ANALYTICS.FCT_FUNDAMENTALS_GROWTH",
    "news": "ANALYTICS.FCT_NEWS_SENTIMENT_AGG",
    "sec": "ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY",
}

# Sources that MUST have data for a viable (even degraded) report
HARD_REQUIREMENTS = {"stock"}


def check_data_readiness(session, ticker: str) -> dict:
    """Check whether the ANALYTICS layer has enough data for a ticker.

    Args:
        session: Snowpark Session (from ``get_session()``).
        ticker: Uppercase ticker symbol (e.g. ``"AAPL"``).

    Returns:
        dict with keys:
            ticker          – the ticker checked
            ready           – True if all sources have data
            min_viable      – True if hard-requirement sources have data
            missing         – list of source names with 0 rows
            counts          – {source: row_count} for each source
            details         – per-source dicts with table name and count
    """
    ticker = ticker.upper().strip()
    counts: dict[str, int] = {}
    details: dict[str, dict] = {}

    for source, table in TABLE_MAP.items():
        try:
            rows = session.sql(
                f"SELECT COUNT(*) AS C FROM {table} WHERE TICKER = '{ticker}'"
            ).collect()
            count = rows[0]["C"] if rows else 0
        except Exception as exc:
            logger.warning("Readiness check failed for %s.%s: %s", table, ticker, exc)
            count = 0

        counts[source] = count
        details[source] = {"table": table, "count": count}

    missing = [src for src, cnt in counts.items() if cnt == 0]
    hard_missing = [src for src in HARD_REQUIREMENTS if counts.get(src, 0) == 0]

    return {
        "ticker": ticker,
        "ready": len(missing) == 0,
        "min_viable": len(hard_missing) == 0,
        "missing": missing,
        "counts": counts,
        "details": details,
    }


def check_raw_data_exists(session, ticker: str) -> dict:
    """Check the RAW layer for a ticker (useful before running dbt).

    Returns:
        dict mapping source names to row counts in RAW tables.
    """
    raw_tables = {
        "stock": "RAW.RAW_STOCK_PRICES",
        "fundamentals": "RAW.RAW_FUNDAMENTALS",
        "news": "RAW.RAW_NEWS",
        "sec_text": "RAW.RAW_SEC_FILING_TEXT",
        "sec_xbrl": "RAW.RAW_SEC_FILINGS",
        "sec_docs": "RAW.RAW_SEC_FILING_DOCUMENTS",
    }

    ticker = ticker.upper().strip()
    counts: dict[str, int] = {}

    for source, table in raw_tables.items():
        try:
            rows = session.sql(
                f"SELECT COUNT(*) AS C FROM {table} WHERE TICKER = '{ticker}'"
            ).collect()
            counts[source] = rows[0]["C"] if rows else 0
        except Exception as exc:
            logger.warning("RAW check failed for %s.%s: %s", table, ticker, exc)
            counts[source] = 0

    return counts
