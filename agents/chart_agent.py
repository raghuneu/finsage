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
FIXED_REFINEMENT_ITERATIONS = 2   # Deterministic: always exactly 2 iterations
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
               REVENUE_GROWTH_YOY_PCT,
               NET_INCOME_GROWTH_YOY_PCT,
               EPS_GROWTH_YOY_PCT,
               EPS_GROWTH_QOQ_PCT,
               REVENUE_GROWTH_QOQ_PCT,
               NET_INCOME_GROWTH_QOQ_PCT,
               NET_MARGIN_PCT,
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
               SENTIMENT_SCORE,
               SENTIMENT_SCORE_7D_AVG,
               TOTAL_ARTICLES,
               SENTIMENT_LABEL, SENTIMENT_TREND,
               NEWS_VOLUME_MOMENTUM
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
    """Fetch financial health data directly from dbt-materialized FCT_SEC_FINANCIAL_SUMMARY.

    This table already has ALL precomputed columns: total_revenue, net_income,
    total_assets, total_liabilities, stockholders_equity, operating_income,
    net_margin_pct, operating_margin_pct, debt_to_equity_ratio, financial_health, etc.

    No runtime merges or computations needed — deterministic single-table query.
    """
    df = session.sql(f"""
        SELECT FISCAL_YEAR, FISCAL_PERIOD,
               TOTAL_REVENUE,
               NET_INCOME,
               OPERATING_INCOME,
               TOTAL_ASSETS,
               TOTAL_LIABILITIES,
               STOCKHOLDERS_EQUITY,
               NET_MARGIN_PCT,
               OPERATING_MARGIN_PCT,
               DEBT_TO_EQUITY_RATIO,
               RETURN_ON_EQUITY_PCT,
               FINANCIAL_HEALTH
        FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
        WHERE TICKER = '{ticker.upper()}'
          AND REPORTING_FREQUENCY = 'quarterly'
        ORDER BY FISCAL_YEAR DESC, FISCAL_PERIOD DESC
        LIMIT 12
    """).to_pandas()
    df.columns = [c.lower() for c in df.columns]
    # Reverse so oldest quarter is first (chronological order for charting)
    return df.iloc[::-1].reset_index(drop=True)


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
    # Use _pct columns from dbt (already in percentage form)
    net_margins = df["net_margin_pct"].dropna().tolist() if "net_margin_pct" in df.columns else []
    op_margins = df["operating_margin_pct"].dropna().tolist() if "operating_margin_pct" in df.columns else []
    latest_net = round(float(net_margins[-1]), 1) if net_margins else None
    latest_op = round(float(op_margins[-1]), 1) if op_margins else None
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
from agents.chart_data_prep import PREPARE_FUNCTIONS
from agents.chart_specs import CANONICAL_CHART_ORDER, get_constraint_text
from agents.chart_validation import validate_chart_data, ChartDataValidationError


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
    "Do NOT redefine df. "
    "ALL data values are PRECOMPUTED — do NOT perform any arithmetic "
    "(no dividing by 1e9, no multiplying by 100, no unit conversions). "
    "Plot the columns exactly as provided. Do NOT reorder rows."
)

CHART_DEFINITIONS = {
    "price_sma": {
        "title": "Price & Moving Averages",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a professional matplotlib chart for {ticker} stock price.\n"
            f"df columns: date (datetime), close, sma_7d, sma_30d, sma_90d.\n"
            f"All values are in USD. Data is pre-sorted by date ascending.\n"
            f"Plot close as filled area (#2563eb alpha=0.15) with line, "
            f"sma_7d (#f59e0b dashed), sma_30d (#10b981 dashed), sma_90d (#ef4444 dashed).\n"
            f"ax.set_facecolor('#f8f9fa'), gridlines (#e0e0e0), legend upper left, "
            f"title fontsize=14 bold, axis labels fontsize=11, figsize=(14,6).\n"
            f"Y-axis must zoom around min/max price (not start at 0).\n"
            f"X-ticks rotate 30deg."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} price chart based on critique.\nPrevious code:\n{code}\n\n"
            f"Critique:\n{critique}\n\n"
            f"Data is pre-sorted. All values in USD. Do NOT reorder or transform data.\n"
            f"Fix the issues mentioned while keeping: filled area under close, "
            f"all 4 SMAs, professional styling, legend, gridlines."
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
price_min = float(df['close'].min())
price_max = float(df['close'].max())
padding = (price_max - price_min) * 0.1
ax.set_ylim(price_min - padding, price_max + padding)
""",
    },

    "volatility": {
        "title": "Volume & 30-Day Volatility",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a professional dual-axis chart for {ticker} volume and volatility.\n"
            f"df columns: date (datetime), volume_millions (ALREADY in millions), "
            f"volatility_30d_pct (ALREADY in %).\n"
            f"Data is pre-sorted by date ascending. Do NOT divide volume or multiply volatility.\n"
            f"Left axis: volume bars (#94a3b8 alpha=0.6). Right axis: volatility line (#ef4444).\n"
            f"ax.set_facecolor('#f8f9fa'), combined legend, title fontsize=14 bold, figsize=(14,6).\n"
            f"Use FuncFormatter: left 'X.0fM', right 'X.1f%'. No scientific notation."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} volume/volatility chart based on critique.\n"
            f"Previous code:\n{code}\n\nCritique:\n{critique}\n\n"
            f"volume_millions is ALREADY in millions. volatility_30d_pct is ALREADY in %.\n"
            f"Do NOT divide or multiply any values. Fix the critique issues."
        ),
        "fallback_code": """
from matplotlib.ticker import MaxNLocator, FuncFormatter
fig, ax1 = plt.subplots(figsize=(14, 6))
ax1.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
df['date'] = pd.to_datetime(df['date'])
ax2 = ax1.twinx()
ax1.bar(df['date'], df['volume_millions'], color='#94a3b8', alpha=0.6, width=1.5, label='Volume (M)')
if df['volatility_30d_pct'].notna().any():
    ax2.plot(df['date'], df['volatility_30d_pct'], color='#ef476f', linewidth=2, label='Volatility 30D %')
ax1.set_title('Volume & 30-Day Volatility', fontsize=14, fontweight='bold')
ax1.set_xlabel('Date', fontsize=11)
ax1.set_ylabel('Volume (Millions)', fontsize=11)
ax2.set_ylabel('Volatility 30D %', fontsize=11)
ax1.set_ylim(0, float(df['volume_millions'].max()) * 1.15)
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
        "title": "Revenue & Net Income Growth (YoY %)",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a professional grouped bar chart for {ticker} YoY growth.\n"
            f"df columns: fiscal_quarter, revenue_growth_yoy_pct, net_income_growth_yoy_pct.\n"
            f"Values are ALREADY in percent. Do NOT multiply by 100. Data is pre-sorted.\n"
            f"Grouped bars: revenue (#00b4d8), net_income (#06d6a0), negative bars in #ef476f.\n"
            f"Zero reference line, data labels on bars, ax.set_facecolor('#f8f9fa'),\n"
            f"title fontsize=14 bold, figsize=(14,6). y-axis: 'Growth (YoY %)'.\n"
            f"Do NOT add a secondary y-axis. Do NOT plot absolute values."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} growth chart based on critique.\n"
            f"Previous code:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Values are ALREADY in percent. Do NOT multiply or transform.\n"
            f"Keep using revenue_growth_yoy_pct and net_income_growth_yoy_pct ONLY."
        ),
        "fallback_code": """
from matplotlib.ticker import FormatStrFormatter
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
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
            f"Generate a professional dual-axis chart for {ticker} EPS trend.\n"
            f"df columns: fiscal_quarter, eps (USD), eps_growth_yoy_pct (ALREADY in %).\n"
            f"Data is pre-sorted chronologically. Do NOT transform values.\n"
            f"EPS line (#2563eb linewidth=2.5 circle markers) on left axis.\n"
            f"eps_growth_yoy_pct bars (green/red by sign, alpha=0.4) on right axis.\n"
            f"Data labels on EPS points, ax.set_facecolor('#f8f9fa'), "
            f"title fontsize=14 bold, figsize=(14,6)."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} EPS chart based on critique.\n"
            f"Previous code:\n{code}\n\nCritique:\n{critique}\n\n"
            f"EPS in USD, growth ALREADY in %. Do NOT transform. Fix the critique issues."
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
            f"Generate a professional sentiment chart for {ticker}.\n"
            f"df columns: news_date (datetime), sentiment_score, sentiment_score_7d_avg.\n"
            f"Scores are ALREADY in range -1 to +1. Data is pre-sorted by date.\n"
            f"fill_between positive (#10b981 alpha=0.2), negative (#ef4444 alpha=0.2),\n"
            f"7d avg line (#2563eb linewidth=2), zero reference line (black dashed),\n"
            f"y-axis -1 to 1, ax.set_facecolor('#f8f9fa'), title fontsize=14 bold, figsize=(14,6)."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} sentiment chart based on critique.\n"
            f"Previous code:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Scores ALREADY in -1 to +1. Do NOT scale. Fix the critique issues."
        ),
        "fallback_code": """
from matplotlib.ticker import MaxNLocator
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
if df['news_date'].dtype in ('int64', 'float64'):
    if df['news_date'].mean() > 1e10:
        df['news_date'] = pd.to_datetime(df['news_date'], unit='ms')
    else:
        df['news_date'] = pd.to_datetime(df['news_date'], unit='s')
else:
    df['news_date'] = pd.to_datetime(df['news_date'])
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
            f"Generate a professional financial health chart for {ticker}.\n"
            f"df columns: fiscal_period, net_margin_pct (ALREADY in %), "
            f"operating_margin_pct (ALREADY in %), debt_to_equity_ratio (ratio).\n"
            f"Data is pre-sorted chronologically. Do NOT multiply or transform values.\n"
            f"Grouped bars: net_margin_pct (#00b4d8), operating_margin_pct (#06d6a0).\n"
            f"debt_to_equity_ratio line (#ef4444) on right axis.\n"
            f"Value labels on bars, ax.set_facecolor('#f8f9fa'), "
            f"combined legend, title fontsize=14 bold, figsize=(14,6)."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} financial health chart based on critique.\n"
            f"Previous code:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Margins ALREADY in %. Debt/equity ALREADY a ratio. Do NOT transform."
        ),
        "fallback_code": """
fig, ax1 = plt.subplots(figsize=(14, 6))
ax1.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
ax2 = ax1.twinx()
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
            f"Generate a professional margin trend chart for {ticker}.\n"
            f"df columns: fiscal_period, net_margin_pct (ALREADY in %), "
            f"operating_margin_pct (ALREADY in %).\n"
            f"Data is pre-sorted chronologically. Do NOT multiply by 100.\n"
            f"Net margin: filled area (#00b4d8 alpha=0.15) + line (#00b4d8 linewidth=2, marker='o').\n"
            f"Operating margin: dashed line (#06d6a0 linewidth=2, marker='s').\n"
            f"Value labels on points, ax.set_facecolor('#f8f9fa'), "
            f"title fontsize=14 bold, figsize=(14,6). y-axis: 'Margin %'."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} margin trend chart based on critique.\n"
            f"Previous code:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Margins ALREADY in %. Do NOT multiply by 100. Fix the critique issues."
        ),
        "fallback_code": """
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
labels = df['fiscal_period'].tolist()
x = range(len(df))
net_m = df['net_margin_pct'].fillna(0)
op_m = df['operating_margin_pct'].fillna(0)
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
            f"Generate a professional balance sheet chart for {ticker}.\n"
            f"df columns: fiscal_period, total_assets_billions, total_liabilities_billions, "
            f"stockholders_equity_billions.\n"
            f"ALL values are ALREADY in billions ($B). Do NOT divide by 1e9.\n"
            f"Data is pre-sorted chronologically.\n"
            f"Stacked bars: liabilities (#ef476f alpha=0.7) bottom, equity (#06d6a0 alpha=0.7) top.\n"
            f"Total assets line overlay (#00b4d8 linewidth=2, marker='D').\n"
            f"Data labels on assets line, ax.set_facecolor('#f8f9fa'), "
            f"y-axis: 'Amount ($B)', title fontsize=14 bold, figsize=(14,6)."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} balance sheet chart based on critique.\n"
            f"Previous code:\n{code}\n\nCritique:\n{critique}\n\n"
            f"ALL values ALREADY in billions. Do NOT divide by 1e9. Fix the critique issues."
        ),
        "fallback_code": """
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
labels = df['fiscal_period'].tolist()
x = range(len(df))
liab_b = df['total_liabilities_billions'].fillna(0)
eq_b = df['stockholders_equity_billions'].fillna(0)
assets_b = df['total_assets_billions'].fillna(0)
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
    Generate one chart through exactly FIXED_REFINEMENT_ITERATIONS (2) LLM+VLM
    refinement iterations. Deterministic — no budget-based or score-based
    early stopping.

    Iteration 1: Generate professional chart from spec-driven prompt.
    Iteration 2: Refine based on VLM critique of iteration 1.

    Falls back to hardcoded professional chart if both iterations fail.

    Returns a ChartResult dict.
    """
    defn = CHART_DEFINITIONS[chart_id]
    title = f"{ticker} {defn['title']}"
    final_path = str(output_dir / f"{chart_id}.png")

    logger.info("Generating chart: %s", chart_id)

    # Hard constraints injected into every prompt
    cols_list = ", ".join(df.columns.tolist())
    spec_constraints = get_constraint_text(chart_id)
    hard_constraints = (
        f"{spec_constraints}\n\n"
        "HARD CONSTRAINTS:\n"
        f"- Use only columns that exist in df: [{cols_list}]\n"
        "- ALL data values are PRECOMPUTED — do NOT perform any arithmetic.\n"
        "- Modules pd, np, plt, mdates are already imported — do NOT re-import.\n"
        "- DO NOT call plt.savefig or plt.show — the runner handles saving.\n"
        "- DO NOT call ax.ticklabel_format or set_scientific (breaks date/category axes).\n"
        "- DO NOT pass tz= to DateFormatter or WeekdayLocator.\n"
        "- DO NOT use constrained_layout together with tight_layout.\n"
        "- For price charts: set ax.set_ylim to zoom around min/max (not starting at 0)."
    )

    iter_prompt_keys = {1: "iter1_prompt", 2: "iter2_prompt"}

    try:
        import shutil as _shutil
        best_path = None
        prev_code = None
        prev_critique = None
        refinement_count = 0

        for iteration in range(1, FIXED_REFINEMENT_ITERATIONS + 1):
            iter_tag = f"iter{iteration}"
            logger.info("Chart %s: starting %s (of %d fixed)",
                        chart_id, iter_tag, FIXED_REFINEMENT_ITERATIONS)

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
                ) if prev_critique else "No critique available."
                prompt = (
                    f"{CHART_CODE_SYSTEM}\n\n"
                    f"{defn[prompt_key](ticker, df, prev_code, feedback)}\n\n"
                    f"{hard_constraints}"
                )
                # On final iteration, include fallback code as reference
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
                if best_path and iteration == FIXED_REFINEMENT_ITERATIONS:
                    # Final iteration failed — retry once with simplified prompt
                    logger.info("Chart %s: retrying iter%d with simplified prompt",
                                chart_id, iteration)
                    simple_prompt = (
                        f"{CHART_CODE_SYSTEM}\n\n"
                        f"The previous code for this {ticker} {chart_id} chart works correctly. "
                        f"Make only MINIMAL styling improvements. Do NOT restructure.\n"
                        f"Working code:\n{prev_code}\n\n"
                        f"{hard_constraints}"
                    )
                    retry_code = cortex_complete_with_timeout(session, simple_prompt)
                    if retry_code and execute_chart_code(retry_code, df, iter_path):
                        _shutil.copyfile(iter_path, final_path)
                        best_path = final_path
                        refinement_count = iteration
                        prev_code = retry_code
                        logger.info("Chart %s: simplified retry succeeded", chart_id)
                    else:
                        logger.warning("Chart %s: simplified retry also failed, keeping iter%d",
                                       chart_id, iteration - 1)
                    continue
                elif best_path:
                    continue
                else:
                    raise RuntimeError(f"Iteration {iteration} render failed (no prior version)")

            # Keep latest successful render
            _shutil.copyfile(iter_path, final_path)
            best_path = final_path
            refinement_count = iteration
            prev_code = code

            # ── VLM critique (skip on final iteration — no more refinements) ──
            if iteration < FIXED_REFINEMENT_ITERATIONS:
                crit_text = vision_critique_with_timeout(
                    session, iter_path, CRITIQUE_PROMPT, data_summary
                )
                if crit_text is not None:
                    prev_critique = parse_vlm_critique(crit_text)
                    logger.info(
                        "VLM critique %s %s: score=%.1f",
                        chart_id, iter_tag, prev_critique["score"],
                    )
                else:
                    logger.info("VLM critique %s %s: TIMEOUT — proceeding to next iteration",
                                chart_id, iter_tag)
                    prev_critique = None

        # All fixed iterations done
        logger.info("Chart %s: completed %d deterministic iterations",
                    chart_id, refinement_count)

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
    Generate all 8 charts for the given ticker with deterministic ordering.

    Pipeline:
        1. Fetch raw data from ANALYTICS layer
        2. Run data through chart_data_prep (precompute all values)
        3. Generate charts in parallel (ThreadPoolExecutor)
        4. Re-sort results by CANONICAL_CHART_ORDER (deterministic)
        5. Save manifest

    Args:
        session:    Snowflake session
        ticker:     Stock ticker symbol
        output_dir: Directory to save charts (created if not exists)
        debug:      If True, saves all iteration PNGs per chart

    Returns:
        List of ChartResult dicts in CANONICAL order (contract for orchestrator)
    """
    ticker = ticker.upper()

    if output_dir is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = OUTPUT_BASE / f"{ticker}_{ts}"
    else:
        out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if debug:
        logger.info("DEBUG MODE ON — all iteration charts will be saved")

    logger.info("=" * 50)
    logger.info("Chart Agent starting for %s -> %s", ticker, out)
    logger.info("=" * 50)

    # ── 1. Fetch all raw data upfront ─────────────────────────
    logger.info("Fetching data from ANALYTICS layer...")
    stock_df = fetch_stock_metrics(session, ticker)
    fund_df = fetch_fundamentals_growth(session, ticker)
    news_df = fetch_news_sentiment(session, ticker)
    sec_df = fetch_sec_financial_summary(session, ticker)

    # Map chart_id -> (raw_dataframe, data_summary_builder)
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
        "sentiment": 5,
    }

    # ── 2. Precompute chart-ready data via data prep layer ────
    chart_tasks = []
    for chart_id, (raw_df, summary_fn) in chart_data_map.items():
        if raw_df.empty:
            logger.warning("No data for chart '%s', skipping", chart_id)
            continue

        min_rows = MIN_ROWS.get(chart_id, 1)
        if len(raw_df) < min_rows:
            logger.warning(
                "Insufficient data for chart '%s' (%d rows, need %d), skipping",
                chart_id, len(raw_df), min_rows,
            )
            continue

        # Run through deterministic data preparation
        prep_fn = PREPARE_FUNCTIONS.get(chart_id)
        if prep_fn is not None:
            prepped = prep_fn(raw_df)

            # ── Pre-render validation ─────────────────────────
            try:
                warnings = validate_chart_data(chart_id, prepped)
                if warnings:
                    logger.info("Chart '%s' validation warnings: %s", chart_id, warnings)
            except ChartDataValidationError as e:
                logger.error("Chart '%s' failed pre-render validation: %s", chart_id, e)
                continue

            # Convert precomputed dict back to DataFrame for chart execution
            # (the execute_chart_code function writes df to CSV)
            prep_df = pd.DataFrame(prepped)
        else:
            prep_df = raw_df.copy()

        data_summary = summary_fn(raw_df)
        chart_tasks.append((chart_id, prep_df, data_summary))

    # ── 3. Generate charts in parallel ────────────────────────
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

    # Collect results into dict keyed by chart_id (order-independent)
    results_by_id = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CHART_WORKERS) as executor:
        futures = {
            executor.submit(_generate_one, task): task[0]
            for task in chart_tasks
        }
        for future in concurrent.futures.as_completed(futures):
            chart_id = futures[future]
            try:
                result = future.result()
                results_by_id[chart_id] = result
            except Exception:
                logger.exception("Chart '%s' failed in parallel generation", chart_id)

    # ── 4. Restore canonical ordering ─────────────────────────
    results = []
    for chart_id in CANONICAL_CHART_ORDER:
        if chart_id in results_by_id:
            results.append(results_by_id[chart_id])

    logger.info(
        "Chart Agent complete: %d/%d charts generated (canonical order)",
        len(results), len(chart_data_map)
    )

    # ── 5. Save manifest ──────────────────────────────────────
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
    """Re-run chart generation for one chart_id (used by orchestrator retry loop).

    Uses the data preparation layer for deterministic precomputed values.
    """
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
    raw_df = fetch_fn(session, ticker)
    if raw_df.empty:
        raise RuntimeError(f"No data available for chart '{chart_id}'")

    # Run through deterministic data preparation
    prep_fn = PREPARE_FUNCTIONS.get(chart_id)
    if prep_fn is not None:
        prepped = prep_fn(raw_df)

        # Pre-render validation
        try:
            warnings = validate_chart_data(chart_id, prepped)
            if warnings:
                logger.info("Regen chart '%s' validation warnings: %s", chart_id, warnings)
        except ChartDataValidationError as e:
            raise RuntimeError(f"Chart '{chart_id}' failed pre-render validation: {e}") from e

        prep_df = pd.DataFrame(prepped)
    else:
        prep_df = raw_df.copy()

    data_summary = summary_fn(raw_df)
    chart_result = generate_single_chart(
        session, chart_id, ticker, prep_df, out, debug=debug,
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
        help="Save all iteration charts per chart + print VLM critiques to logs"
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
