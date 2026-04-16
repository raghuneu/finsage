"""
FinSage Chart Agent
===================
Pulls data from ANALYTICS layer, generates 6 professional matplotlib charts
using a 3-iteration VLM refinement loop (FinSight Section 2.4).

Produces a list of ChartResult dicts consumed by the orchestrator.

Each chart goes through:
    Iteration 1: Basic chart
    Iteration 2: Improved based on VLM critique
    Iteration 3: Publication-ready final

CLI:
    python agents/chart_agent.py --ticker AAPL
    python agents/chart_agent.py --ticker AAPL --debug
"""

import os
import sys
import json
import time
import base64
import logging
import subprocess
import tempfile
import textwrap
import concurrent.futures
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from snowflake_connection import get_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_fh = logging.FileHandler(_LOG_DIR / "chart_agent.log")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logger.addHandler(_fh)

CORTEX_MODEL_LLM = os.getenv("CORTEX_MODEL_LLM", "claude-opus-4-6")
CORTEX_MODEL_VLM = os.getenv("CORTEX_MODEL_VLM", "claude-sonnet-4-6")
MAX_REFINEMENT_ITERATIONS = 3
MIN_ACCEPTABLE_SCORE = 6.0
VLM_CALL_TIMEOUT_SEC = 120
PER_CHART_BUDGET_SEC = 300

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_BASE = PROJECT_ROOT / "outputs"


# ──────────────────────────────────────────────────────────────
# Data fetchers — one per analytics table
# ──────────────────────────────────────────────────────────────

def fetch_stock_metrics(session, ticker: str) -> pd.DataFrame:
    df = session.sql(f"""
        SELECT DATE, CLOSE, SMA_7D, SMA_30D, SMA_90D,
               VOLUME, VOLATILITY_30D_PCT, DAILY_RANGE_PCT, TREND_SIGNAL
        FROM ANALYTICS.FCT_STOCK_METRICS
        WHERE TICKER = '{ticker.upper()}'
        ORDER BY DATE DESC
        LIMIT 90
    """).to_pandas()
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _fiscal_quarter_sort_key(q: str) -> tuple:
    """Convert 'Q4 2025' -> (2025, 4) for chronological sort."""
    try:
        parts = str(q).strip().split()
        qnum = int(parts[0].lstrip("Q"))
        year = int(parts[1])
        return (year, qnum)
    except Exception:
        return (0, 0)


def fetch_fundamentals_growth(session, ticker: str) -> pd.DataFrame:
    df = session.sql(f"""
        SELECT FISCAL_QUARTER, REVENUE, NET_INCOME, EPS,
               REVENUE_GROWTH_YOY AS REVENUE_GROWTH_YOY_PCT,
               NET_INCOME_GROWTH_YOY AS NET_INCOME_GROWTH_YOY_PCT,
               EPS_GROWTH_YOY AS EPS_GROWTH_YOY_PCT,
               EPS_GROWTH_QOQ AS EPS_GROWTH_QOQ_PCT,
               REVENUE_GROWTH_QOQ AS REVENUE_GROWTH_QOQ_PCT,
               NET_INCOME_GROWTH_QOQ AS NET_INCOME_GROWTH_QOQ_PCT,
               NET_MARGIN,
               FUNDAMENTAL_SIGNAL
        FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
        WHERE TICKER = '{ticker.upper()}'
    """).to_pandas()
    df.columns = [c.lower() for c in df.columns]
    if "fiscal_quarter" in df.columns and not df.empty:
        df["_sort_key"] = df["fiscal_quarter"].map(_fiscal_quarter_sort_key)
        df = df.sort_values("_sort_key").drop(columns="_sort_key").reset_index(drop=True)
    return df


def fetch_news_sentiment(session, ticker: str) -> pd.DataFrame:
    df = session.sql(f"""
        SELECT NEWS_DATE,
               AVG_SENTIMENT_SCORE AS SENTIMENT_SCORE,
               ROLLING_SENTIMENT_7D AS SENTIMENT_SCORE_7D_AVG,
               ARTICLE_COUNT AS TOTAL_ARTICLES,
               SENTIMENT_LABEL, SENTIMENT_TREND,
               VOLUME_MOMENTUM AS NEWS_VOLUME_MOMENTUM
        FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG
        WHERE TICKER = '{ticker.upper()}'
          AND NEWS_DATE >= DATEADD('day', -60, CURRENT_DATE)
        ORDER BY NEWS_DATE DESC
        LIMIT 60
    """).to_pandas()
    df.columns = [c.lower() for c in df.columns]
    df["news_date"] = pd.to_datetime(df["news_date"])
    return df.sort_values("news_date").reset_index(drop=True)


def fetch_sec_financial_summary(session, ticker: str) -> pd.DataFrame:
    """Fetch financial health data, merging SEC and fundamentals tables.

    FCT_SEC_FINANCIAL_SUMMARY has NULL margins for many tickers, so we
    fall back to FCT_FUNDAMENTALS_GROWTH.NET_MARGIN and compute
    operating_margin from SEC OPERATING_INCOME / fundamentals REVENUE.
    """
    # Primary: fundamentals table (has real NET_MARGIN)
    fund_df = session.sql(f"""
        SELECT FISCAL_QUARTER, REVENUE, NET_MARGIN, NET_INCOME
        FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
        WHERE TICKER = '{ticker.upper()}'
        ORDER BY FISCAL_QUARTER
    """).to_pandas()
    fund_df.columns = [c.lower() for c in fund_df.columns]

    # SEC table for debt/equity and operating income
    sec_df = session.sql(f"""
        SELECT FISCAL_YEAR, FISCAL_PERIOD,
               DEBT_TO_EQUITY AS DEBT_TO_EQUITY_RATIO,
               ROE AS RETURN_ON_EQUITY_PCT,
               OPERATING_INCOME,
               FINANCIAL_HEALTH
        FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
        WHERE TICKER = '{ticker.upper()}'
        ORDER BY FISCAL_YEAR DESC, FISCAL_PERIOD
        LIMIT 10
    """).to_pandas()
    sec_df.columns = [c.lower() for c in sec_df.columns]

    # DIM_COMPANY for fallback profit margin
    dim_df = session.sql(f"""
        SELECT PROFIT_MARGIN
        FROM ANALYTICS.DIM_COMPANY
        WHERE TICKER = '{ticker.upper()}'
        LIMIT 1
    """).to_pandas()
    dim_profit_margin = float(dim_df.iloc[0, 0]) * 100 if not dim_df.empty and pd.notna(dim_df.iloc[0, 0]) else None

    # Build merged dataframe from fundamentals as base
    if not fund_df.empty:
        result = fund_df[["fiscal_quarter", "revenue", "net_margin", "net_income"]].copy()
        result.rename(columns={
            "fiscal_quarter": "fiscal_period",
            "revenue": "total_revenue",
            "net_margin": "net_margin_pct",
        }, inplace=True)
        # Add fiscal_year column (extract from fiscal_quarter like "Q4 2025")
        result["fiscal_year"] = result["fiscal_period"].str.extract(r'(\d{4})').astype(float)

        # Operating margin: compute from SEC operating_income / fundamentals revenue
        result["operating_margin_pct"] = None

        # Merge debt_to_equity and operating_income from SEC table
        if not sec_df.empty:
            latest_dte = sec_df["debt_to_equity_ratio"].dropna().iloc[0] if sec_df["debt_to_equity_ratio"].notna().any() else None
            result["debt_to_equity_ratio"] = latest_dte
            latest_health = sec_df["financial_health"].iloc[0] if "financial_health" in sec_df.columns else "FAIR"
            result["financial_health"] = latest_health

            # Compute operating margin from SEC operating_income / fundamentals revenue
            if "operating_income" in sec_df.columns and sec_df["operating_income"].notna().any():
                latest_op_income = sec_df["operating_income"].dropna().iloc[0]
                latest_revenue = result["total_revenue"].dropna().iloc[-1] if result["total_revenue"].notna().any() else None
                if latest_revenue and float(latest_revenue) != 0:
                    result["operating_margin_pct"] = round(float(latest_op_income) / float(latest_revenue) * 100, 1)
        else:
            result["debt_to_equity_ratio"] = None
            result["financial_health"] = "FAIR"

        # Fallback: if net_margin_pct is all NaN, use DIM_COMPANY
        if result["net_margin_pct"].isna().all() and dim_profit_margin is not None:
            result["net_margin_pct"] = dim_profit_margin

        return result
    else:
        # Fallback to SEC-only data with DIM_COMPANY margin
        df = sec_df.copy()
        df["total_revenue"] = None
        df["net_margin_pct"] = dim_profit_margin if dim_profit_margin is not None else 0.0
        df["operating_margin_pct"] = None
        if "operating_income" in df.columns:
            df.drop(columns=["operating_income"], inplace=True)
        return df


# ──────────────────────────────────────────────────────────────
# Data summary builders — feed into analysis agent prompts
# ──────────────────────────────────────────────────────────────

def build_price_summary(df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]
    return {
        "current_price": round(float(latest["close"]), 2),
        "sma_7d": round(float(latest["sma_7d"]) if pd.notna(latest["sma_7d"]) else 0, 2),
        "sma_30d": round(float(latest["sma_30d"]) if pd.notna(latest["sma_30d"]) else 0, 2),
        "sma_90d": round(float(latest["sma_90d"]) if pd.notna(latest["sma_90d"]) else 0, 2),
        "trend_signal": str(latest["trend_signal"]),
        "date_range": f"{df['date'].iloc[0].strftime('%Y-%m-%d')} to {df['date'].iloc[-1].strftime('%Y-%m-%d')}",
    }


def build_volatility_summary(df: pd.DataFrame) -> dict:
    vol_series = df["volatility_30d_pct"].dropna()
    return {
        "avg_volume": int(df["volume"].mean()),
        "volatility_30d_pct": round(float(vol_series.iloc[-1]), 2) if not vol_series.empty else 0.0,
        "daily_range_pct_avg": round(float(df["daily_range_pct"].dropna().mean()), 2) if not df["daily_range_pct"].dropna().empty else 0.0,
    }


def build_revenue_summary(df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]
    # Prefer YoY, fall back to QoQ if YoY is all NaN
    yoy_rev = latest.get("revenue_growth_yoy_pct")
    qoq_rev = latest.get("revenue_growth_qoq_pct")
    yoy_ni = latest.get("net_income_growth_yoy_pct")
    qoq_ni = latest.get("net_income_growth_qoq_pct")
    return {
        "latest_revenue_growth_yoy": round(float(yoy_rev) if pd.notna(yoy_rev) else (float(qoq_rev) if pd.notna(qoq_rev) else 0), 1),
        "latest_net_income_growth_yoy": round(float(yoy_ni) if pd.notna(yoy_ni) else (float(qoq_ni) if pd.notna(qoq_ni) else 0), 1),
        "growth_type": "YoY" if pd.notna(yoy_rev) else "QoQ",
        "fundamental_signal": str(latest["fundamental_signal"]),
    }


def build_eps_summary(df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]
    return {
        "latest_eps": round(float(latest["eps"]) if pd.notna(latest["eps"]) else 0, 2),
        "eps_growth_yoy_pct": round(float(latest["eps_growth_yoy_pct"]) if pd.notna(latest["eps_growth_yoy_pct"]) else 0, 1),
        "eps_growth_qoq_pct": round(float(latest["eps_growth_qoq_pct"]) if pd.notna(latest["eps_growth_qoq_pct"]) else 0, 1),
    }


def build_sentiment_summary(df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]
    return {
        "sentiment_score_7d_avg": round(float(latest["sentiment_score_7d_avg"]) if pd.notna(latest["sentiment_score_7d_avg"]) else 0, 2),
        "sentiment_label": str(latest["sentiment_label"]),
        "sentiment_trend": str(latest["sentiment_trend"]),
        "total_articles_30d": int(df.tail(30)["total_articles"].fillna(0).sum()),
    }


def build_financial_health_summary(df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]  # last row = most recent quarter
    op_margin = None
    if "operating_margin_pct" in df.columns:
        op_vals = df["operating_margin_pct"].dropna()
        if not op_vals.empty:
            op_margin = round(float(op_vals.iloc[-1]), 1)
    return {
        "total_revenue": float(latest["total_revenue"]) if pd.notna(latest.get("total_revenue")) else 0,
        "net_margin_pct": round(float(latest["net_margin_pct"]) if pd.notna(latest.get("net_margin_pct")) else 0, 1),
        "operating_margin_pct": op_margin,
        "debt_to_equity_ratio": round(float(latest["debt_to_equity_ratio"]) if pd.notna(latest.get("debt_to_equity_ratio")) else 0, 2),
        "financial_health": str(latest.get("financial_health", "FAIR")),
    }


def build_margin_trend_summary(df: pd.DataFrame) -> dict:
    """Build data summary for margin trend chart (SEC data)."""
    periods = df["fiscal_period"].tolist() if "fiscal_period" in df.columns else []
    net_margins = df["net_margin"].dropna().tolist() if "net_margin" in df.columns else []
    op_margins = df["operating_margin"].dropna().tolist() if "operating_margin" in df.columns else []
    latest_net = round(float(net_margins[-1]) * 100, 1) if net_margins else None
    latest_op = round(float(op_margins[-1]) * 100, 1) if op_margins else None
    # Trend direction
    if len(net_margins) >= 2:
        margin_trend = "expanding" if net_margins[-1] > net_margins[-2] else "compressing"
    else:
        margin_trend = "insufficient data"
    return {
        "num_quarters": len(df),
        "latest_net_margin_pct": latest_net,
        "latest_operating_margin_pct": latest_op,
        "margin_trend": margin_trend,
    }


def build_balance_sheet_summary(df: pd.DataFrame) -> dict:
    """Build data summary for balance sheet composition chart (SEC data)."""
    latest = df.iloc[-1]
    total_assets = float(latest["total_assets"]) if pd.notna(latest.get("total_assets")) else 0
    total_liab = float(latest["total_liabilities"]) if pd.notna(latest.get("total_liabilities")) else 0
    equity = float(latest["stockholders_equity"]) if pd.notna(latest.get("stockholders_equity")) else 0
    equity_pct = round(equity / total_assets * 100, 1) if total_assets else 0
    return {
        "total_assets_b": round(total_assets / 1e9, 1),
        "total_liabilities_b": round(total_liab / 1e9, 1),
        "stockholders_equity_b": round(equity / 1e9, 1),
        "equity_pct": equity_pct,
        "num_quarters": len(df),
    }


# ──────────────────────────────────────────────────────────────
# Cortex / Vision helpers (shared via vision_utils)
# ──────────────────────────────────────────────────────────────

from agents.vision_utils import cortex_complete, vision_critique


# ──────────────────────────────────────────────────────────────
# Chart code executor
# ──────────────────────────────────────────────────────────────

def execute_chart_code(code: str, df: pd.DataFrame, output_path: str) -> bool:
    """
    Write df to temp CSV, wrap LLM code in runner script,
    execute in subprocess, save chart to output_path.
    Returns True on success, False on failure.
    """

    # Sanitize known bad kwargs and methods Cortex sometimes generates
    code = code.replace("fillalpha=", "alpha=")
    code = code.replace("fill_alpha=", "alpha=")
    code = code.replace(
        ".legend(lines1 + lines2)",
        ".legend(lines1 + lines2, labels1 + labels2)"
    )
    code = code.replace("lineStyle=", "linestyle=")
    code = code.replace("lambdax:", "lambda x:")

    # Remove hallucinated matplotlib methods that don't exist
    code = code.replace("ax1.semi_logy()", "ax1.set_yscale('log')")
    code = code.replace("ax2.semi_logy()", "ax2.set_yscale('log')")
    code = code.replace("ax.semi_logy()", "ax.set_yscale('log')")
    # Fix common xticklabels mismatch — wrap in try/except
    code = code.replace(
        "ax1.set_xticklabels(",
        "ax1.set_xticks(range(len(df))); ax1.set_xticklabels("
    )
    code = code.replace(
        "ax.set_xticklabels(",
        "ax.set_xticks(range(len(df))); ax.set_xticklabels("
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as f:
        df.to_csv(f, index=False)
        csv_path = f.name

    indented_code = textwrap.indent(code, "    ")
    runner = textwrap.dedent(f"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import numpy as np
import traceback
import warnings
warnings.filterwarnings("ignore")

df = pd.read_csv(r"{csv_path}")

# Auto-convert date/datetime columns so LLM code never sees raw epoch values
for _col in df.columns:
    if any(kw in _col for kw in ('date', 'DATE', 'Date')):
        try:
            # Try standard parsing first (handles ISO strings)
            df[_col] = pd.to_datetime(df[_col], errors='coerce')
            # If all NaT, try epoch seconds/milliseconds
            if df[_col].isna().all():
                raw = pd.read_csv(r"{csv_path}")[_col]
                if raw.dtype in ('int64', 'float64'):
                    if raw.mean() > 1e10:
                        df[_col] = pd.to_datetime(raw, unit='ms', errors='coerce')
                    else:
                        df[_col] = pd.to_datetime(raw, unit='s', errors='coerce')
        except Exception:
            pass

try:
{indented_code}
except Exception as _e:
    print(f"CHART_ERROR: {{type(_e).__name__}}: {{_e}}")
    traceback.print_exc()
    raise SystemExit(1)

try:
    plt.tight_layout()
except Exception:
    pass
plt.savefig(r"{output_path}", dpi=150, bbox_inches="tight", facecolor="white")
plt.close("all")
""")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(runner)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            logger.error("Chart render failed (exit=%d):\nSTDERR:\n%s\nSTDOUT:\n%s",
                         result.returncode, result.stderr[-2000:], result.stdout[-500:])
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("Chart render timed out")
        return False
    finally:
        os.unlink(script_path)
        os.unlink(csv_path)


# ──────────────────────────────────────────────────────────────
# Chart definitions
# ──────────────────────────────────────────────────────────────

CHART_CODE_SYSTEM = (
    "Return ONLY executable Python matplotlib code. "
    "No markdown fences, no explanations, no import statements, no plt.show(), no plt.savefig(). "
    "DataFrame `df` is already loaded with lowercase column names. "
    "Do NOT redefine df."
)

CHART_DEFINITIONS = {
    "price_sma": {
        "title": "Price & Moving Averages",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a basic matplotlib chart for {ticker} stock price. "
            f"df has columns: date (datetime), close, sma_7d, sma_30d, sma_90d. "
            f"Plot close price as a line. figsize=(12,5). "
            f"Title: '{ticker} Stock Price'. x-axis: date, rotate 45 degrees."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} chart. Previous code:\n{code}\n\n"
            f"Critique:\n{critique}\n\n"
            f"Add: sma_7d (orange dashed), sma_30d (green dashed), sma_90d (red dashed), "
            f"gridlines (alpha=0.3), legend, axis labels 'Price (USD)' and 'Date'."
        ),
        "iter3_prompt": lambda ticker, df, code, critique: (
            f"Create a PROFESSIONAL publication-ready {ticker} price chart. Previous:\n{code}\n\n"
            f"Critique:\n{critique}\n\n"
            f"Requirements: close as filled area (#2563eb alpha=0.15) with line, "
            f"sma_7d (#f59e0b dashed), sma_30d (#10b981 dashed), sma_90d (#ef4444 dashed), "
            f"ax.set_facecolor('#f8f9fa'), gridlines (#e0e0e0), "
            f"title fontsize=14 bold, axis labels fontsize=11, "
            f"legend upper left framealpha=0.9, x-ticks rotate 30deg, figsize=(14,6)."
        ),
        "fallback_code": """
import matplotlib.dates as mdates
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
df['date'] = pd.to_datetime(df['date'])
ax.fill_between(df['date'], df['close'].min(), df['close'], alpha=0.15, color='#00b4d8')
ax.plot(df['date'], df['close'], color='#00b4d8', linewidth=2, label='Close Price')
if df['sma_7d'].notna().any():
    ax.plot(df['date'], df['sma_7d'], color='#f59e0b', linewidth=1.5, linestyle='--', label='SMA 7D')
if df['sma_30d'].notna().any():
    ax.plot(df['date'], df['sma_30d'], color='#06d6a0', linewidth=1.5, linestyle='--', label='SMA 30D')
if df['sma_90d'].notna().any():
    ax.plot(df['date'], df['sma_90d'], color='#ef476f', linewidth=1.5, linestyle='--', label='SMA 90D')
ax.set_title('Price & Moving Averages', fontsize=14, fontweight='bold')
ax.set_xlabel('Date', fontsize=11)
ax.set_ylabel('Price (USD)', fontsize=11)
ax.grid(True, color='#e0e0e0', alpha=0.7, linestyle='--', linewidth=0.5)
ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
plt.xticks(rotation=45, ha='right', fontsize=9)
# Tighten y-axis around price range (avoid large empty space below)
price_min = float(df['close'].min())
price_max = float(df['close'].max())
padding = (price_max - price_min) * 0.1
ax.set_ylim(price_min - padding, price_max + padding)
""",
    },

    "volatility": {
        "title": "Volume & 30-Day Volatility",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a basic matplotlib chart for {ticker} volume. "
            f"df has columns: date (datetime), volume, volatility_30d_pct. "
            f"Plot volume as bar chart. figsize=(12,5). Title: '{ticker} Volume'."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} volume chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Add: volatility_30d_pct as line on right axis (twinx), "
            f"axis labels, legend, gridlines."
        ),
        "iter3_prompt": lambda ticker, df, code, critique: (
            f"Create PROFESSIONAL {ticker} volume/volatility chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Requirements: volume bars (#94a3b8 alpha=0.6) on left axis, "
            f"volatility_30d_pct line (#ef4444 linewidth=2) on right axis, "
            f"ax.set_facecolor('#f8f9fa'), gridlines, both axes labeled, "
            f"title fontsize=14 bold, combined legend, figsize=(14,6). "
            f"MUST show dual axes: left=Volume in Millions (divide raw volume by 1e6), "
            f"right=Volatility %. MUST NOT use scientific notation. "
            f"MUST show both bar chart (volume) and line chart (volatility) on same figure. "
            f"Use FuncFormatter to format left y-axis as 'Xm' and right y-axis as 'X.X%'."
        ),
        "fallback_code": """
from matplotlib.ticker import MaxNLocator, FuncFormatter
fig, ax1 = plt.subplots(figsize=(14, 6))
ax1.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
df['date'] = pd.to_datetime(df['date'])
ax2 = ax1.twinx()
vol_m = df['volume'] / 1e6
ax1.bar(df['date'], vol_m, color='#94a3b8', alpha=0.6, width=1.5, label='Volume (M)')
if df['volatility_30d_pct'].notna().any():
    ax2.plot(df['date'], df['volatility_30d_pct'], color='#ef476f', linewidth=2, label='Volatility 30D %')
ax1.set_title('Volume & 30-Day Volatility', fontsize=14, fontweight='bold')
ax1.set_xlabel('Date', fontsize=11)
ax1.set_ylabel('Volume (Millions)', fontsize=11)
ax2.set_ylabel('Volatility 30D %', fontsize=11)
# Explicit y-limits + formatters (no scientific notation)
ax1.set_ylim(0, float(vol_m.max()) * 1.15)
ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.0f}M'))
vol_series = df['volatility_30d_pct'].dropna()
if not vol_series.empty:
    ax2.set_ylim(0, float(vol_series.max()) * 1.2)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.1f}%'))
ax1.grid(True, color='#e0e0e0', alpha=0.7, linestyle='--', linewidth=0.5)
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)
ax1.xaxis.set_major_locator(MaxNLocator(8))
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha='right', fontsize=9)
""",
    },

    "revenue_growth": {
        "title": "Revenue & Net Income Growth",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a grouped bar chart for {ticker} YoY growth. "
            f"df has columns: fiscal_quarter, revenue_growth_yoy_pct, net_income_growth_yoy_pct. "
            f"Plot revenue_growth_yoy_pct and net_income_growth_yoy_pct as grouped bars. "
            f"DO NOT use any _qoq_ columns. DO NOT use a secondary axis. figsize=(12,5). "
            f"Title: 'Revenue & Net Income Growth (YoY %)'. "
            f"y-axis label: 'Growth (YoY %)'. x-axis: fiscal_quarter."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} YoY growth chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Keep using revenue_growth_yoy_pct and net_income_growth_yoy_pct ONLY. "
            f"Add: color coding (green=#06d6a0 positive, red=#ef476f negative), legend, axis labels. "
            f"DO NOT switch to QoQ columns. DO NOT add a secondary y-axis."
        ),
        "iter3_prompt": lambda ticker, df, code, critique: (
            f"Create PROFESSIONAL {ticker} revenue/income growth chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Requirements: grouped bars ONLY (revenue_growth=#00b4d8, net_income_growth=#06d6a0), "
            f"color bars #ef476f if negative, zero reference line, "
            f"ax.set_facecolor('#f8f9fa'), data labels on top of each bar showing the %, "
            f"title fontsize=14 bold, figsize=(14,6). "
            f"MUST plot revenue_growth_yoy_pct and net_income_growth_yoy_pct (NOT the QoQ columns). "
            f"Title MUST be 'Revenue & Net Income Growth (YoY %)'. y-axis label MUST be 'Growth (YoY %)'. "
            f"MUST show only percentage values on single y-axis. "
            f"MUST NOT plot absolute revenue values. MUST NOT use a secondary y-axis. "
            f"MUST NOT use scientific notation. Use FormatStrFormatter('%.1f%%') on y-axis."
        ),
        "fallback_code": """
from matplotlib.ticker import FormatStrFormatter
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')

# Always use YoY growth
growth_col = 'revenue_growth_yoy_pct'
ni_col = 'net_income_growth_yoy_pct'

x = list(range(len(df)))
width = 0.35
rev_vals = df[growth_col].fillna(0)
ni_vals = df[ni_col].fillna(0)
rev_colors = ['#00b4d8' if v >= 0 else '#ef476f' for v in rev_vals]
inc_colors = ['#06d6a0' if v >= 0 else '#ef476f' for v in ni_vals]
bars1 = ax.bar([i - width/2 for i in x], rev_vals, width, color=rev_colors, alpha=0.85,
               label='Revenue Growth YoY %')
bars2 = ax.bar([i + width/2 for i in x], ni_vals, width, color=inc_colors, alpha=0.85,
               label='Net Income Growth YoY %')
ax.axhline(y=0, color='black', linewidth=0.8, linestyle='-')

# Data labels on top of bars
for bar, v in zip(bars1, rev_vals):
    ax.annotate(f'{v:.1f}%', (bar.get_x() + bar.get_width()/2, v),
                textcoords='offset points', xytext=(0, 4 if v >= 0 else -12),
                ha='center', fontsize=8, color='#0f172a')
for bar, v in zip(bars2, ni_vals):
    ax.annotate(f'{v:.1f}%', (bar.get_x() + bar.get_width()/2, v),
                textcoords='offset points', xytext=(0, 4 if v >= 0 else -12),
                ha='center', fontsize=8, color='#0f172a')

ax.set_xticks(x)
ax.set_xticklabels(df['fiscal_quarter'].tolist(), rotation=30, fontsize=9, ha='right')
ax.set_title('Revenue & Net Income Growth (YoY %)', fontsize=14, fontweight='bold')
ax.set_ylabel('Growth (YoY %)', fontsize=11)
ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f%%'))
ax.grid(True, axis='y', color='#e0e0e0', alpha=0.7, linestyle='--')
ax.legend(fontsize=9, framealpha=0.9, loc='upper left')
""",
    },

    "eps_trend": {
        "title": "EPS Trend",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a basic line chart for {ticker} EPS. "
            f"df has columns: fiscal_quarter, eps, eps_growth_yoy_pct. "
            f"Plot eps as a line. figsize=(12,5). Title: '{ticker} EPS Trend'."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} EPS chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Add: eps_growth_yoy_pct as bars on right axis (twinx), "
            f"data point markers on EPS line, axis labels, legend."
        ),
        "iter3_prompt": lambda ticker, df, code, critique: (
            f"Create PROFESSIONAL {ticker} EPS trend chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Requirements: eps line (#2563eb linewidth=2.5 with circle markers), "
            f"eps_growth_yoy_pct bars (#10b981/#ef4444 based on sign) on right axis, "
            f"data labels on EPS points, ax.set_facecolor('#f8f9fa'), "
            f"title fontsize=14 bold, figsize=(14,6)."
        ),
        "fallback_code": """
fig, ax1 = plt.subplots(figsize=(14, 6))
ax1.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
ax2 = ax1.twinx()
x = range(len(df))
growth_colors = ['#06d6a0' if v >= 0 else '#ef476f'
                 for v in df['eps_growth_yoy_pct'].fillna(0)]
ax2.bar(x, df['eps_growth_yoy_pct'].fillna(0), color=growth_colors,
        alpha=0.4, label='EPS Growth YoY %')
ax1.plot(list(x), df['eps'].fillna(0), color='#00b4d8', linewidth=2.5,
         marker='o', markersize=8, label='EPS', zorder=5)
for i, (xi, yi) in enumerate(zip(x, df['eps'].fillna(0))):
    ax1.annotate(f'${yi:.2f}', (xi, yi), textcoords="offset points",
                 xytext=(0, 10), ha='center', fontsize=8)
ax1.set_xticks(list(x))
ax1.set_xticklabels(df['fiscal_quarter'].tolist(), rotation=30, fontsize=9)
ax1.set_title('Earnings Per Share (EPS) Trend', fontsize=14, fontweight='bold')
ax1.set_ylabel('EPS (USD)', fontsize=11)
ax2.set_ylabel('EPS Growth YoY %', fontsize=11)
ax1.grid(True, color='#e0e0e0', alpha=0.7, linestyle='--')
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)
""",
    },

    "sentiment": {
        "title": "News Sentiment Trend",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a basic line chart for {ticker} sentiment. "
            f"df has columns: news_date (datetime), sentiment_score, sentiment_score_7d_avg. "
            f"Plot sentiment_score as a line. figsize=(12,5). Title: '{ticker} News Sentiment'."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} sentiment chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Add: sentiment_score_7d_avg as smoother line, "
            f"zero reference line, color positive area green and negative red, "
            f"axis labels, legend."
        ),
        "iter3_prompt": lambda ticker, df, code, critique: (
            f"Create PROFESSIONAL {ticker} sentiment chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Requirements: fill_between positive sentiment (#10b981 alpha=0.2), "
            f"fill_between negative sentiment (#ef4444 alpha=0.2), "
            f"sentiment_score_7d_avg line (#2563eb linewidth=2), "
            f"zero reference line (black dashed), ax.set_facecolor('#f8f9fa'), "
            f"y-axis range -1 to 1, title fontsize=14 bold, figsize=(14,6). "
            f"MUST show dates from 2025-2026 only. If x-axis shows 1969 or 1970, "
            f"timestamps are in milliseconds — use pd.to_datetime(df['news_date'], unit='ms'). "
            f"MUST filter to last 60 days: cutoff = pd.Timestamp.now() - pd.Timedelta(days=60); "
            f"df = df[df['news_date'] >= cutoff]."
        ),
        "fallback_code": """
from matplotlib.ticker import MaxNLocator
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
# Robust date parsing — guard against epoch (seconds or ms) stored as int/float
if df['news_date'].dtype in ('int64', 'float64'):
    if df['news_date'].mean() > 1e10:
        df['news_date'] = pd.to_datetime(df['news_date'], unit='ms')
    else:
        df['news_date'] = pd.to_datetime(df['news_date'], unit='s')
else:
    df['news_date'] = pd.to_datetime(df['news_date'])
# Filter to last 60 days relative to now
cutoff = pd.Timestamp.now() - pd.Timedelta(days=60)
df = df[df['news_date'] >= cutoff].sort_values('news_date').reset_index(drop=True)
ax.fill_between(df['news_date'], 0, df['sentiment_score_7d_avg'].fillna(0),
                where=df['sentiment_score_7d_avg'].fillna(0) >= 0,
                alpha=0.2, color='#10b981', label='Positive')
ax.fill_between(df['news_date'], 0, df['sentiment_score_7d_avg'].fillna(0),
                where=df['sentiment_score_7d_avg'].fillna(0) < 0,
                alpha=0.2, color='#ef4444', label='Negative')
ax.plot(df['news_date'], df['sentiment_score_7d_avg'].fillna(0),
        color='#2563eb', linewidth=2, label='7D Avg Sentiment')
ax.axhline(y=0, color='black', linewidth=0.8, linestyle='--')
ax.set_ylim(-1, 1)
ax.set_title('News Sentiment Trend (7-Day Average, last 60 days)', fontsize=14, fontweight='bold')
ax.set_xlabel('Date', fontsize=11)
ax.set_ylabel('Sentiment Score (-1 to +1)', fontsize=11)
ax.grid(True, color='#e0e0e0', alpha=0.7, linestyle='--')
ax.legend(fontsize=9, framealpha=0.9)
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
ax.xaxis.set_major_locator(MaxNLocator(10))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
plt.xticks(rotation=30, ha='right', fontsize=9)
""",
    },

    "financial_health": {
        "title": "SEC Financial Health Snapshot",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a basic bar chart for {ticker} financial margins. "
            f"df has columns: fiscal_year, fiscal_period, net_margin_pct, operating_margin_pct. "
            f"Plot net_margin_pct as bars. figsize=(12,5). Title: '{ticker} Financial Health'."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} financial health chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Add: operating_margin_pct as second grouped bar, "
            f"debt_to_equity_ratio as line on right axis, axis labels, legend."
        ),
        "iter3_prompt": lambda ticker, df, code, critique: (
            f"Create PROFESSIONAL {ticker} financial health chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Requirements: net_margin_pct bars (#2563eb), operating_margin_pct bars (#10b981), "
            f"debt_to_equity_ratio line (#ef4444) on right axis, "
            f"period labels as 'YYYY FP' on x-axis, "
            f"ax.set_facecolor('#f8f9fa'), value labels on bars, "
            f"title fontsize=14 bold, figsize=(14,6)."
        ),
        "fallback_code": """
fig, ax1 = plt.subplots(figsize=(14, 6))
ax1.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
ax2 = ax1.twinx()
# Use fiscal_period directly — it already contains the year (e.g. "Q4 2025")
labels = df['fiscal_period'].tolist()
x = range(len(df))
width = 0.35
ax1.bar([i - width/2 for i in x], df['net_margin_pct'].fillna(0),
        width, color='#00b4d8', alpha=0.8, label='Net Margin %')
if 'operating_margin_pct' in df.columns:
    ax1.bar([i + width/2 for i in x], df['operating_margin_pct'].fillna(0),
            width, color='#06d6a0', alpha=0.8, label='Operating Margin %')
if df['debt_to_equity_ratio'].notna().any():
    ax2.plot(list(x), df['debt_to_equity_ratio'].fillna(0),
             color='#ef476f', linewidth=2, marker='D', markersize=6,
             label='Debt/Equity Ratio')
# Add value labels on margin bars
for i, v in enumerate(df['net_margin_pct'].fillna(0)):
    if v != 0:
        ax1.annotate(f'{v:.1f}%', (i - width/2, v), textcoords='offset points',
                     xytext=(0, 5), ha='center', fontsize=8, color='#00b4d8')
ax1.set_xticks(list(x))
ax1.set_xticklabels(labels, rotation=30, fontsize=9, ha='right')
ax1.set_title('Financial Health — Margins & Leverage', fontsize=14, fontweight='bold')
ax1.set_ylabel('Margin %', fontsize=11)
ax2.set_ylabel('Debt/Equity Ratio', fontsize=11)
ax1.grid(True, axis='y', color='#e0e0e0', alpha=0.7, linestyle='--')
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)
""",
    },

    "margin_trend": {
        "title": "Profitability Margin Trend",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a line chart for {ticker} margin trends. "
            f"df has columns: fiscal_period, net_margin, operating_margin (as decimals 0-1). "
            f"Multiply by 100 to show as percentages. Plot both as lines. "
            f"figsize=(12,5). Title: '{ticker} Margin Trend'."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} margin trend chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Add: area fill under net_margin line, markers on data points, "
            f"gridlines, y-axis label as 'Margin %', legend."
        ),
        "iter3_prompt": lambda ticker, df, code, critique: (
            f"Create PROFESSIONAL {ticker} margin trend chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Requirements: net_margin*100 as filled area (#00b4d8 alpha=0.15) with solid line (#00b4d8 linewidth=2), "
            f"operating_margin*100 as line (#06d6a0 linewidth=2 dashed), "
            f"markers (o, s) on data points, ax.set_facecolor('#f8f9fa'), "
            f"value labels on each point, gridlines, title fontsize=14 bold, figsize=(14,6). "
            f"x-axis: fiscal_period labels. y-axis: 'Margin %'. "
            f"Handle NaN gracefully with .fillna(method='ffill')."
        ),
        "fallback_code": """
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
labels = df['fiscal_period'].tolist()
x = range(len(df))
net_m = df['net_margin'].fillna(0) * 100
op_m = df['operating_margin'].fillna(0) * 100
ax.fill_between(list(x), 0, net_m, alpha=0.15, color='#00b4d8')
ax.plot(list(x), net_m, color='#00b4d8', linewidth=2, marker='o', markersize=6, label='Net Margin %')
ax.plot(list(x), op_m, color='#06d6a0', linewidth=2, marker='s', markersize=6, linestyle='--', label='Operating Margin %')
for i, (n, o) in enumerate(zip(net_m, op_m)):
    if n != 0:
        ax.annotate(f'{n:.1f}%', (i, n), textcoords='offset points', xytext=(0, 8), ha='center', fontsize=8, color='#00b4d8')
    if o != 0:
        ax.annotate(f'{o:.1f}%', (i, o), textcoords='offset points', xytext=(0, -12), ha='center', fontsize=8, color='#06d6a0')
ax.set_xticks(list(x))
ax.set_xticklabels(labels, rotation=30, fontsize=9, ha='right')
ax.set_title('Profitability Margin Trend', fontsize=14, fontweight='bold')
ax.set_ylabel('Margin %', fontsize=11)
ax.set_xlabel('Fiscal Period', fontsize=11)
ax.grid(True, color='#e0e0e0', alpha=0.7, linestyle='--', linewidth=0.5)
ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
""",
    },

    "balance_sheet": {
        "title": "Balance Sheet Composition",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a stacked bar chart for {ticker} balance sheet. "
            f"df has columns: fiscal_period, total_assets, total_liabilities, stockholders_equity. "
            f"Values are large numbers — divide by 1e9 to show in billions. "
            f"figsize=(12,5). Title: '{ticker} Balance Sheet'."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} balance sheet chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Show liabilities and equity as stacked bars (should sum to ~total_assets). "
            f"Add total_assets as a line overlay, axis labels in $B, legend."
        ),
        "iter3_prompt": lambda ticker, df, code, critique: (
            f"Create PROFESSIONAL {ticker} balance sheet chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Requirements: stacked bars with total_liabilities (#ef476f alpha=0.7) on bottom "
            f"and stockholders_equity (#06d6a0 alpha=0.7) stacked on top, "
            f"total_assets as line (#00b4d8 linewidth=2, marker='D'), "
            f"all values divided by 1e9 (show as $B), ax.set_facecolor('#f8f9fa'), "
            f"y-axis: 'Amount ($B)', x-axis: fiscal_period labels, "
            f"title fontsize=14 bold, figsize=(14,6), gridlines."
        ),
        "fallback_code": """
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
labels = df['fiscal_period'].tolist()
x = range(len(df))
liab_b = df['total_liabilities'].fillna(0) / 1e9
eq_b = df['stockholders_equity'].fillna(0) / 1e9
assets_b = df['total_assets'].fillna(0) / 1e9
ax.bar(list(x), liab_b, color='#ef476f', alpha=0.7, label='Total Liabilities')
ax.bar(list(x), eq_b, bottom=liab_b, color='#06d6a0', alpha=0.7, label="Stockholders' Equity")
ax.plot(list(x), assets_b, color='#00b4d8', linewidth=2, marker='D', markersize=7, label='Total Assets')
for i, v in enumerate(assets_b):
    ax.annotate(f'${v:.0f}B', (i, v), textcoords='offset points', xytext=(0, 8), ha='center', fontsize=8, fontweight='bold')
ax.set_xticks(list(x))
ax.set_xticklabels(labels, rotation=30, fontsize=9, ha='right')
ax.set_title('Balance Sheet Composition', fontsize=14, fontweight='bold')
ax.set_ylabel('Amount ($B)', fontsize=11)
ax.set_xlabel('Fiscal Period', fontsize=11)
ax.grid(True, axis='y', color='#e0e0e0', alpha=0.7, linestyle='--', linewidth=0.5)
ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
""",
    },
}


# ──────────────────────────────────────────────────────────────
# Structured VLM critique
# ──────────────────────────────────────────────────────────────

CRITIQUE_PROMPT = """You are a financial chart quality reviewer. Examine this chart image carefully and evaluate:

1. AXIS LABELS: Are all axes labeled clearly? Are units shown?
2. SCALE: Does the y-axis start at an appropriate value (not 0 for price charts)? No scientific notation?
3. READABILITY: Is the x-axis readable? No overlapping dates?
4. DATA INTEGRITY: Does the chart show meaningful variation? (not a flat line due to wrong scale)
5. LEGEND: Is a legend present and readable?
6. TITLE: Is there a clear descriptive title?

Respond in this EXACT format (no markdown, no extra text):
SCORE: X/10
ISSUES: [list each issue found, or "None"]
IMPROVEMENTS: [specific matplotlib code changes needed]
ACCEPT: YES or NO (YES if score >= 7)
"""


def vision_critique_with_timeout(session, image_path, prompt, data_summary=None,
                                   timeout=VLM_CALL_TIMEOUT_SEC):
    """Wrap vision_critique with a hard timeout. Returns None on timeout."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(vision_critique, session, image_path, prompt, data_summary)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning("VLM call timed out after %ds", timeout)
            return None


def cortex_complete_with_timeout(session, prompt, timeout=VLM_CALL_TIMEOUT_SEC):
    """Wrap cortex_complete with a hard timeout. Returns None on timeout."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(cortex_complete, session, prompt)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning("Cortex LLM call timed out after %ds", timeout)
            return None


def parse_vlm_critique(text: str) -> dict:
    """Parse structured VLM response into {score, issues, improvements, accept, raw}."""
    import re
    out = {"score": 0.0, "issues": "", "improvements": "", "accept": False, "raw": text or ""}
    if not text:
        return out
    m = re.search(r"SCORE:\s*([\d.]+)\s*/?\s*10", text, re.IGNORECASE)
    if m:
        try:
            out["score"] = float(m.group(1))
        except ValueError:
            pass
    m = re.search(r"ISSUES:\s*(.+?)(?=IMPROVEMENTS:|ACCEPT:|\Z)", text, re.IGNORECASE | re.DOTALL)
    if m:
        out["issues"] = m.group(1).strip()
    m = re.search(r"IMPROVEMENTS:\s*(.+?)(?=ACCEPT:|\Z)", text, re.IGNORECASE | re.DOTALL)
    if m:
        out["improvements"] = m.group(1).strip()
    m = re.search(r"ACCEPT:\s*(YES|NO)", text, re.IGNORECASE)
    if m:
        out["accept"] = m.group(1).upper() == "YES"
    else:
        out["accept"] = out["score"] >= 7.0
    return out


# ──────────────────────────────────────────────────────────────
# Single chart generator with iterative refinement
# ──────────────────────────────────────────────────────────────

def _make_chart_result(chart_id, title, final_path, refinement_count, df):
    return {
        "chart_id": chart_id,
        "title": title,
        "file_path": final_path,
        "validated": os.path.exists(final_path) and os.path.getsize(final_path) > 0,
        "refinement_count": refinement_count,
        "data_summary": {},
        "_df": df,
    }


def generate_single_chart(
    session, chart_id: str, ticker: str,
    df: pd.DataFrame, output_dir: Path,
    debug: bool = False,
    data_summary: dict = None,
) -> dict:
    """
    Generate one chart through up to 3 LLM+VLM refinement iterations.

    After each iteration the chart PNG is uploaded to a Snowflake stage and
    critiqued by the VLM via true multimodal COMPLETE (TO_FILE).

    - If the VLM score >= 7 (ACCEPT), the chart is kept immediately.
    - If the score < MIN_ACCEPTABLE_SCORE after an iteration, the chart is
      regenerated in the next iteration.
    - After 3 iterations (or budget exhaustion), the best-scoring version is kept.
    - Falls back to hardcoded professional chart if all iterations fail.

    Args:
        debug: If True, saves all iteration PNGs.
        data_summary: Pre-computed chart metrics for VLM critique enrichment.

    Returns a ChartResult dict.
    """
    defn = CHART_DEFINITIONS[chart_id]
    title = f"{ticker} {defn['title']}"
    final_path = str(output_dir / f"{chart_id}.png")

    logger.info("Generating chart: %s", chart_id)

    # Hard constraints injected into every regen prompt
    cols_list = ", ".join(df.columns.tolist())
    hard_constraints = (
        "HARD CONSTRAINTS:\n"
        f"- Use only columns that exist in df: [{cols_list}]\n"
        "- Modules pd, np, plt, mdates are already imported — do NOT re-import.\n"
        "- DO NOT call plt.savefig or plt.show — the runner handles saving.\n"
        "- DO NOT call ax.ticklabel_format or set_scientific (breaks date/category axes).\n"
        "- DO NOT pass tz= to DateFormatter or WeekdayLocator.\n"
        "- DO NOT use constrained_layout together with tight_layout.\n"
        "- For price charts: set ax.set_ylim to zoom around min/max (not starting at 0)."
    )

    chart_start = time.time()

    def budget_left():
        return PER_CHART_BUDGET_SEC - (time.time() - chart_start)

    # Map iteration number -> prompt key in CHART_DEFINITIONS
    iter_prompt_keys = {1: "iter1_prompt", 2: "iter2_prompt", 3: "iter3_prompt"}

    try:
        import shutil as _shutil
        best_score = -1.0
        best_path = None
        prev_code = None
        prev_critique = None
        refinement_count = 0

        for iteration in range(1, MAX_REFINEMENT_ITERATIONS + 1):
            iter_tag = f"iter{iteration}"
            logger.info("Chart %s: starting %s", chart_id, iter_tag)

            # ── Build prompt ──────────────────────────────────
            prompt_key = iter_prompt_keys[iteration]
            if iteration == 1:
                prompt = (
                    f"{CHART_CODE_SYSTEM}\n\n"
                    f"{defn[prompt_key](ticker, df)}\n\n"
                    f"{hard_constraints}"
                )
            else:
                feedback = (
                    f"VLM SCORE: {prev_critique['score']}/10\n"
                    f"ISSUES: {prev_critique['issues']}\n"
                    f"IMPROVEMENTS: {prev_critique['improvements']}"
                )
                prompt = (
                    f"{CHART_CODE_SYSTEM}\n\n"
                    f"{defn[prompt_key](ticker, df, prev_code, feedback)}\n\n"
                    f"{hard_constraints}"
                )
                # On final iteration, include fallback code as reference
                if iteration == MAX_REFINEMENT_ITERATIONS:
                    prompt += f"\n\nReference working fallback:\n{defn['fallback_code'][:800]}"

            # ── Generate code ─────────────────────────────────
            code = cortex_complete_with_timeout(session, prompt)
            if code is None:
                raise RuntimeError(f"Iteration {iteration} LLM timed out")

            iter_path = str(output_dir / f"{chart_id}_{iter_tag}.png") if debug \
                else str(output_dir / f"{chart_id}_{iter_tag}_tmp.png")

            # ── Render chart ──────────────────────────────────
            if not execute_chart_code(code, df, iter_path):
                logger.warning("Chart %s: %s render failed", chart_id, iter_tag)
                if best_path:
                    # Keep previous best
                    continue
                else:
                    raise RuntimeError(f"Iteration {iteration} render failed (no prior version)")

            # Update best so far if this is the first successful render
            if best_path is None:
                _shutil.copyfile(iter_path, final_path)
                best_path = final_path
                best_score = 0.0

            refinement_count = iteration
            prev_code = code

            # ── Budget check before critique ──────────────────
            if budget_left() < 30:
                logger.warning("Chart %s: budget exhausted after %s (%.1fs left)",
                               chart_id, iter_tag, budget_left())
                # Keep the latest successful render
                _shutil.copyfile(iter_path, final_path)
                logger.info("Chart %s accepted at %s (budget)", chart_id, iter_tag)
                return _make_chart_result(chart_id, title, final_path, refinement_count, df)

            # ── VLM critique (multimodal — image is uploaded to stage) ──
            crit_text = vision_critique_with_timeout(
                session, iter_path, CRITIQUE_PROMPT, data_summary
            )
            if crit_text is None:
                logger.info("VLM critique %s %s: TIMEOUT — keeping current", chart_id, iter_tag)
                _shutil.copyfile(iter_path, final_path)
                return _make_chart_result(chart_id, title, final_path, refinement_count, df)

            crit = parse_vlm_critique(crit_text)
            prev_critique = crit
            logger.info(
                "VLM critique %s %s: score=%.1f accept=%s",
                chart_id, iter_tag, crit["score"],
                "YES" if crit["accept"] else "NO"
            )

            # Track best version by score
            if crit["score"] > best_score:
                best_score = crit["score"]
                best_path = iter_path
                _shutil.copyfile(iter_path, final_path)

            # ── Accept if score is good enough ────────────────
            if crit["accept"]:
                logger.info("Chart %s accepted at %s (score %.1f)",
                            chart_id, iter_tag, crit["score"])
                return _make_chart_result(chart_id, title, final_path, refinement_count, df)

            # ── Score below threshold: force regeneration ─────
            if crit["score"] < MIN_ACCEPTABLE_SCORE:
                logger.warning(
                    "Chart %s %s: score %.1f < %.1f threshold — will regenerate",
                    chart_id, iter_tag, crit["score"], MIN_ACCEPTABLE_SCORE
                )

            # ── Budget check before next iteration ────────────
            if budget_left() < 60:
                logger.warning("Chart %s: skipping further iterations, budget %.1fs left",
                               chart_id, budget_left())
                break

        # Loop exhausted — use best version
        logger.info("Chart %s: all %d iterations done, best score=%.1f",
                    chart_id, refinement_count, best_score)

    except Exception as e:
        logger.warning(
            "LLM refinement failed for %s — FALLBACK REASON: %s: %s",
            chart_id, type(e).__name__, e
        )
        success = execute_chart_code(defn["fallback_code"], df, final_path)
        if not success:
            logger.error("Fallback chart also failed for %s", chart_id)
        else:
            logger.info("Fallback chart rendered for %s", chart_id)
        refinement_count = 0

    return {
        "chart_id": chart_id,
        "title": title,
        "file_path": final_path,
        "validated": os.path.exists(final_path) and os.path.getsize(final_path) > 0,
        "refinement_count": refinement_count,
        "data_summary": {},  # populated by generate_charts()
        "_df": df,           # DataFrame for validation re-render (excluded from JSON)
    }


# ──────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────

def generate_charts(
    session, ticker: str,
    output_dir: str = None,
    debug: bool = False
) -> list:
    """
    Generate all 6 charts for the given ticker.

    Args:
        session:    Snowflake session
        ticker:     Stock ticker symbol
        output_dir: Directory to save charts (created if not exists)
        debug:      If True, saves all 3 iteration PNGs per chart

    Returns:
        List of ChartResult dicts (contract for orchestrator)
    """
    ticker = ticker.upper()

    if output_dir is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = OUTPUT_BASE / f"{ticker}_{ts}"
    else:
        out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if debug:
        logger.info("🐛 DEBUG MODE ON — all 3 iteration charts will be saved")

    logger.info("═" * 50)
    logger.info("Chart Agent starting for %s → %s", ticker, out)
    logger.info("═" * 50)

    # Fetch all data upfront
    logger.info("Fetching data from ANALYTICS layer...")
    stock_df = fetch_stock_metrics(session, ticker)
    fund_df = fetch_fundamentals_growth(session, ticker)
    news_df = fetch_news_sentiment(session, ticker)
    sec_df = fetch_sec_financial_summary(session, ticker)

    # Map chart_id → (dataframe, data_summary_builder)
    chart_data_map = {
        "price_sma":        (stock_df, build_price_summary),
        "volatility":       (stock_df, build_volatility_summary),
        "revenue_growth":   (fund_df,  build_revenue_summary),
        "eps_trend":        (fund_df,  build_eps_summary),
        "sentiment":        (news_df,  build_sentiment_summary),
        "financial_health": (sec_df,   build_financial_health_summary),
        "margin_trend":     (sec_df,   build_margin_trend_summary),
        "balance_sheet":    (sec_df,   build_balance_sheet_summary),
    }

    # Minimum data rows required per chart for meaningful visualization
    MIN_ROWS = {
        "margin_trend": 3,
        "balance_sheet": 3,
    }

    results = []

    # Build list of charts to generate (pre-filter empty/insufficient data)
    chart_tasks = []
    for chart_id, (df, summary_fn) in chart_data_map.items():
        if df.empty:
            logger.warning("No data for chart '%s', skipping", chart_id)
            continue

        min_rows = MIN_ROWS.get(chart_id, 1)
        if len(df) < min_rows:
            logger.warning(
                "Insufficient data for chart '%s' (%d rows, need %d), skipping",
                chart_id, len(df), min_rows,
            )
            continue

        data_summary = summary_fn(df)
        chart_tasks.append((chart_id, df, data_summary))

    # Generate charts in parallel (each worker gets its own Snowflake session)
    MAX_CHART_WORKERS = min(4, len(chart_tasks)) if chart_tasks else 1
    logger.info(
        "Generating %d charts in parallel (max_workers=%d)",
        len(chart_tasks), MAX_CHART_WORKERS,
    )

    def _generate_one(task_tuple):
        cid, cdf, csummary = task_tuple
        worker_session = get_session()
        try:
            chart_result = generate_single_chart(
                worker_session, cid, ticker, cdf, out, debug=debug,
                data_summary=csummary,
            )
            chart_result["data_summary"] = csummary
            return chart_result
        finally:
            try:
                worker_session.close()
            except Exception:
                pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CHART_WORKERS) as executor:
        futures = {
            executor.submit(_generate_one, task): task[0]
            for task in chart_tasks
        }
        for future in concurrent.futures.as_completed(futures):
            chart_id = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception:
                logger.exception("Chart '%s' failed in parallel generation", chart_id)

    logger.info(
        "Chart Agent complete: %d/%d charts generated",
        len(results), len(chart_data_map)
    )

    # Save manifest
    manifest_path = out / "chart_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(
            [{k: v for k, v in r.items() if k not in ("file_path", "_df")} for r in results],
            f, indent=2
        )

    return results


def regenerate_single_chart(
    session, ticker: str, chart_id: str,
    output_dir: str, debug: bool = False,
) -> dict:
    """Re-run chart generation for one chart_id (used by orchestrator retry loop)."""
    ticker = ticker.upper()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    data_fetchers = {
        "price_sma":        (fetch_stock_metrics,          build_price_summary),
        "volatility":       (fetch_stock_metrics,          build_volatility_summary),
        "revenue_growth":   (fetch_fundamentals_growth,    build_revenue_summary),
        "eps_trend":        (fetch_fundamentals_growth,    build_eps_summary),
        "sentiment":        (fetch_news_sentiment,         build_sentiment_summary),
        "financial_health": (fetch_sec_financial_summary,  build_financial_health_summary),
        "margin_trend":     (fetch_sec_financial_summary,  build_margin_trend_summary),
        "balance_sheet":    (fetch_sec_financial_summary,  build_balance_sheet_summary),
    }
    if chart_id not in data_fetchers:
        raise ValueError(f"Unknown chart_id: {chart_id}")

    fetch_fn, summary_fn = data_fetchers[chart_id]
    df = fetch_fn(session, ticker)
    if df.empty:
        raise RuntimeError(f"No data available for chart '{chart_id}'")

    data_summary = summary_fn(df)
    chart_result = generate_single_chart(
        session, chart_id, ticker, df, out, debug=debug,
        data_summary=data_summary,
    )
    chart_result["data_summary"] = data_summary
    return chart_result


# ──────────────────────────────────────────────────────────────
# CLI entrypoint
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="FinSage Chart Agent")
    parser.add_argument("--ticker", default="AAPL", help="Stock ticker (default: AAPL)")
    parser.add_argument(
        "--debug", action="store_true",
        help="Save all 3 iteration charts per chart + print VLM critiques to logs"
    )
    args = parser.parse_args()

    session = get_session()
    charts = generate_charts(session, args.ticker, debug=args.debug)
    session.close()

    print("\n" + "=" * 60)
    print(f"CHART AGENT RESULTS — {args.ticker}")
    print("=" * 60)
    for c in charts:
        status = "✅" if c["validated"] else "❌"
        mode = f"LLM ({c['refinement_count']} iters)" if c["refinement_count"] > 0 else "fallback"
        print(f"  {status} {c['chart_id']:20s} [{mode}]")
        print(f"       → {c['file_path']}")
        print(f"       data_summary keys: {list(c['data_summary'].keys())}")
    print("=" * 60)

    if args.debug:
        print("\n  [DEBUG] Check output folder for _iter1, _iter2 PNG files")
        print(f"  open \"{Path(charts[0]['file_path']).parent}\"")
