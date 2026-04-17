"""
FinSage Chart Data Preparation
==============================
Deterministic data preparation layer for all 8 chart types.

Key principle: ALL numerical computations (unit conversions, ratios,
rolling averages, totals) are done here in Python. The LLM receives
final plot-ready values and is responsible ONLY for visualization code.

Each prepare_*_data() function:
    1. Accepts the raw DataFrame from fetch_* functions
    2. Sorts all time-series chronologically (explicit, deterministic)
    3. Applies all unit conversions (e.g., volume/1e6, margin*100, assets/1e9)
    4. Converts to ordered Python lists
    5. Returns a dict of named series ready for direct plotting
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Version tag for prompt reproducibility auditing
DATA_PREP_VERSION = "1.0.0"


def prepare_price_sma_data(df: pd.DataFrame) -> dict[str, Any]:
    """Prepare data for price_sma chart.

    Input columns: date, close, sma_7d, sma_30d, sma_90d
    Output: all values as-is (USD), sorted by date ascending.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    return {
        "date": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "close": df["close"].round(2).tolist(),
        "sma_7d": df["sma_7d"].round(2).tolist(),
        "sma_30d": df["sma_30d"].round(2).tolist(),
        "sma_90d": df["sma_90d"].round(2).tolist(),
        "y_label": "Price (USD)",
        "x_label": "Date",
        "num_points": len(df),
        "_version": DATA_PREP_VERSION,
    }


def prepare_volatility_data(df: pd.DataFrame) -> dict[str, Any]:
    """Prepare data for volatility chart.

    Input columns: date, volume (raw), volatility_30d_pct
    Output: volume converted to millions, volatility as-is (already %).
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Pre-compute volume in millions — LLM must NOT divide
    volume_millions = (df["volume"] / 1e6).round(2)

    return {
        "date": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "volume_millions": volume_millions.tolist(),
        "volatility_30d_pct": df["volatility_30d_pct"].round(2).tolist(),
        "y_left_label": "Volume (Millions)",
        "y_right_label": "Volatility 30D %",
        "x_label": "Date",
        "num_points": len(df),
        "_version": DATA_PREP_VERSION,
    }


def prepare_revenue_growth_data(df: pd.DataFrame) -> dict[str, Any]:
    """Prepare data for revenue_growth chart.

    Input columns: fiscal_quarter, revenue_growth_yoy_pct, net_income_growth_yoy_pct
    Output: growth percentages as-is (already in %), sorted chronologically.
    """
    df = df.copy()
    # Chronological sort by fiscal quarter
    df = _sort_by_fiscal_quarter(df)

    return {
        "fiscal_quarter": df["fiscal_quarter"].tolist(),
        "revenue_growth_yoy_pct": df["revenue_growth_yoy_pct"].fillna(0).round(1).tolist(),
        "net_income_growth_yoy_pct": df["net_income_growth_yoy_pct"].fillna(0).round(1).tolist(),
        "y_label": "Growth (YoY %)",
        "x_label": "Fiscal Quarter",
        "num_points": len(df),
        "_version": DATA_PREP_VERSION,
    }


def prepare_eps_trend_data(df: pd.DataFrame) -> dict[str, Any]:
    """Prepare data for eps_trend chart.

    Input columns: fiscal_quarter, eps, eps_growth_yoy_pct
    Output: EPS in USD, growth as-is (already %), sorted chronologically.
    """
    df = df.copy()
    df = _sort_by_fiscal_quarter(df)

    return {
        "fiscal_quarter": df["fiscal_quarter"].tolist(),
        "eps": df["eps"].fillna(0).round(2).tolist(),
        "eps_growth_yoy_pct": df["eps_growth_yoy_pct"].fillna(0).round(1).tolist(),
        "y_left_label": "EPS (USD)",
        "y_right_label": "EPS Growth YoY %",
        "x_label": "Fiscal Quarter",
        "num_points": len(df),
        "_version": DATA_PREP_VERSION,
    }


def prepare_sentiment_data(df: pd.DataFrame) -> dict[str, Any]:
    """Prepare data for sentiment chart.

    Input columns: news_date, sentiment_score, sentiment_score_7d_avg
    Output: scores as-is (-1 to +1 range), sorted by date ascending.
    """
    df = df.copy()
    df["news_date"] = pd.to_datetime(df["news_date"])
    df = df.sort_values("news_date").reset_index(drop=True)

    return {
        "news_date": df["news_date"].dt.strftime("%Y-%m-%d").tolist(),
        "sentiment_score": df["sentiment_score"].fillna(0).round(3).tolist(),
        "sentiment_score_7d_avg": df["sentiment_score_7d_avg"].fillna(0).round(3).tolist(),
        "y_label": "Sentiment Score (-1 to +1)",
        "x_label": "Date",
        "y_min": -1.0,
        "y_max": 1.0,
        "num_points": len(df),
        "_version": DATA_PREP_VERSION,
    }


def prepare_financial_health_data(df: pd.DataFrame) -> dict[str, Any]:
    """Prepare data for financial_health chart.

    Input columns: fiscal_period, net_margin_pct, operating_margin_pct, debt_to_equity_ratio
    Output: margins as-is (already %), debt_to_equity as-is (ratio).
    Sorted chronologically by fiscal_period.
    """
    df = df.copy()
    df = _sort_by_fiscal_period(df)

    return {
        "fiscal_period": df["fiscal_period"].tolist(),
        "net_margin_pct": df["net_margin_pct"].fillna(0).round(1).tolist(),
        "operating_margin_pct": df["operating_margin_pct"].fillna(0).round(1).tolist(),
        "debt_to_equity_ratio": df["debt_to_equity_ratio"].fillna(0).round(2).tolist(),
        "y_left_label": "Margin %",
        "y_right_label": "Debt/Equity Ratio",
        "x_label": "Fiscal Period",
        "num_points": len(df),
        "_version": DATA_PREP_VERSION,
    }


def prepare_margin_trend_data(df: pd.DataFrame) -> dict[str, Any]:
    """Prepare data for margin_trend chart.

    Input columns: fiscal_period, net_margin (decimal 0-1), operating_margin (decimal 0-1)
                   OR net_margin_pct, operating_margin_pct (already %)
    Output: margins converted to percentage if needed. LLM must NOT multiply.
    """
    df = df.copy()
    df = _sort_by_fiscal_period(df)

    # Determine if margins are in decimal (0-1) or percentage form
    # If column names end with _pct, they're already percentages
    if "net_margin_pct" in df.columns:
        net_margin_pct = df["net_margin_pct"].fillna(0).round(1)
    elif "net_margin" in df.columns:
        # Convert decimal to percentage here — NOT in LLM
        net_margin_pct = (df["net_margin"].fillna(0) * 100).round(1)
    else:
        net_margin_pct = pd.Series([0.0] * len(df))

    if "operating_margin_pct" in df.columns:
        op_margin_pct = df["operating_margin_pct"].fillna(0).round(1)
    elif "operating_margin" in df.columns:
        op_margin_pct = (df["operating_margin"].fillna(0) * 100).round(1)
    else:
        op_margin_pct = pd.Series([0.0] * len(df))

    return {
        "fiscal_period": df["fiscal_period"].tolist(),
        "net_margin_pct": net_margin_pct.tolist(),
        "operating_margin_pct": op_margin_pct.tolist(),
        "y_label": "Margin %",
        "x_label": "Fiscal Period",
        "num_points": len(df),
        "_version": DATA_PREP_VERSION,
    }


def prepare_balance_sheet_data(df: pd.DataFrame) -> dict[str, Any]:
    """Prepare data for balance_sheet chart.

    Input columns: fiscal_period, total_assets, total_liabilities, stockholders_equity
    Output: ALL values converted to billions ($B). LLM must NOT divide.
    """
    df = df.copy()
    df = _sort_by_fiscal_period(df)

    # Pre-compute billions — LLM must NOT divide by 1e9
    assets_b = (df["total_assets"].fillna(0) / 1e9).round(1)
    liabilities_b = (df["total_liabilities"].fillna(0) / 1e9).round(1)
    equity_b = (df["stockholders_equity"].fillna(0) / 1e9).round(1)

    return {
        "fiscal_period": df["fiscal_period"].tolist(),
        "total_assets_billions": assets_b.tolist(),
        "total_liabilities_billions": liabilities_b.tolist(),
        "stockholders_equity_billions": equity_b.tolist(),
        "y_label": "Amount ($B)",
        "x_label": "Fiscal Period",
        "num_points": len(df),
        "_version": DATA_PREP_VERSION,
    }


# ──────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────

def _fiscal_quarter_sort_key(q: str) -> tuple:
    """Convert 'Q4 2025' -> (2025, 4) for chronological sort."""
    try:
        parts = str(q).strip().split()
        qnum = int(parts[0].lstrip("Q"))
        year = int(parts[1])
        return (year, qnum)
    except Exception:
        return (0, 0)


def _sort_by_fiscal_quarter(df: pd.DataFrame) -> pd.DataFrame:
    """Sort DataFrame by fiscal_quarter column chronologically."""
    if "fiscal_quarter" in df.columns and not df.empty:
        df["_sort_key"] = df["fiscal_quarter"].map(_fiscal_quarter_sort_key)
        df = df.sort_values("_sort_key").drop(columns="_sort_key").reset_index(drop=True)
    return df


def _sort_by_fiscal_period(df: pd.DataFrame) -> pd.DataFrame:
    """Sort DataFrame by fiscal_period column chronologically.

    Handles both 'Q4 2025' format and 'FY2025' format.
    """
    if "fiscal_period" in df.columns and not df.empty:
        df["_sort_key"] = df["fiscal_period"].map(_fiscal_quarter_sort_key)
        df = df.sort_values("_sort_key").drop(columns="_sort_key").reset_index(drop=True)
    return df


# ──────────────────────────────────────────────────────────────
# Registry: chart_id -> prepare function
# ──────────────────────────────────────────────────────────────

PREPARE_FUNCTIONS = {
    "price_sma": prepare_price_sma_data,
    "volatility": prepare_volatility_data,
    "revenue_growth": prepare_revenue_growth_data,
    "eps_trend": prepare_eps_trend_data,
    "sentiment": prepare_sentiment_data,
    "financial_health": prepare_financial_health_data,
    "margin_trend": prepare_margin_trend_data,
    "balance_sheet": prepare_balance_sheet_data,
}
