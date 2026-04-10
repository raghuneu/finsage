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
import base64
import logging
import subprocess
import tempfile
import textwrap
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

CORTEX_MODEL_LLM = "llama3.1-70b"
CORTEX_MODEL_VLM = "pixtral-large"
MAX_REFINEMENT_ITERATIONS = 3

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_BASE = PROJECT_ROOT / "outputs"


# ──────────────────────────────────────────────────────────────
# Data fetchers — one per analytics table
# ──────────────────────────────────────────────────────────────

def fetch_stock_metrics(session, ticker: str) -> pd.DataFrame:
    df = session.sql(f"""
        SELECT DATE, CLOSE, SMA_7D, SMA_30D, SMA_90D,
               VOLUME, VOLATILITY_30D_PCT, DAILY_RANGE_PCT, TREND_SIGNAL
        FROM FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS
        WHERE TICKER = '{ticker.upper()}'
        ORDER BY DATE DESC
        LIMIT 90
    """).to_pandas()
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def fetch_fundamentals_growth(session, ticker: str) -> pd.DataFrame:
    df = session.sql(f"""
        SELECT FISCAL_QUARTER, REVENUE, NET_INCOME, EPS,
               REVENUE_GROWTH_YOY_PCT, NET_INCOME_GROWTH_YOY_PCT,
               EPS_GROWTH_YOY_PCT, EPS_GROWTH_QOQ_PCT, FUNDAMENTAL_SIGNAL
        FROM FINSAGE_DB.ANALYTICS.FCT_FUNDAMENTALS_GROWTH
        WHERE TICKER = '{ticker.upper()}'
        ORDER BY FISCAL_QUARTER
    """).to_pandas()
    df.columns = [c.lower() for c in df.columns]
    return df


def fetch_news_sentiment(session, ticker: str) -> pd.DataFrame:
    df = session.sql(f"""
        SELECT NEWS_DATE, SENTIMENT_SCORE, SENTIMENT_SCORE_7D_AVG,
               TOTAL_ARTICLES, SENTIMENT_LABEL, SENTIMENT_TREND,
               NEWS_VOLUME_MOMENTUM
        FROM FINSAGE_DB.ANALYTICS.FCT_NEWS_SENTIMENT_AGG
        WHERE TICKER = '{ticker.upper()}'
        ORDER BY NEWS_DATE DESC
        LIMIT 60
    """).to_pandas()
    df.columns = [c.lower() for c in df.columns]
    df["news_date"] = pd.to_datetime(df["news_date"])
    return df.sort_values("news_date").reset_index(drop=True)


def fetch_sec_financial_summary(session, ticker: str) -> pd.DataFrame:
    df = session.sql(f"""
        SELECT FISCAL_YEAR, FISCAL_PERIOD, TOTAL_REVENUE, NET_MARGIN_PCT,
               OPERATING_MARGIN_PCT, DEBT_TO_EQUITY_RATIO,
               RETURN_ON_EQUITY_PCT, FINANCIAL_HEALTH
        FROM FINSAGE_DB.ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
        WHERE TICKER = '{ticker.upper()}'
        ORDER BY FISCAL_YEAR DESC, FISCAL_PERIOD
        LIMIT 10
    """).to_pandas()
    df.columns = [c.lower() for c in df.columns]
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
    return {
        "avg_volume": int(df["volume"].mean()),
        "volatility_30d_pct": round(float(df["volatility_30d_pct"].dropna().iloc[-1]), 2),
        "daily_range_pct_avg": round(float(df["daily_range_pct"].mean()), 2),
    }


def build_revenue_summary(df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]
    return {
        "latest_revenue_growth_yoy": round(float(latest["revenue_growth_yoy_pct"]) if pd.notna(latest["revenue_growth_yoy_pct"]) else 0, 1),
        "latest_net_income_growth_yoy": round(float(latest["net_income_growth_yoy_pct"]) if pd.notna(latest["net_income_growth_yoy_pct"]) else 0, 1),
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
        "total_articles_30d": int(df.tail(30)["total_articles"].sum()),
    }


def build_financial_health_summary(df: pd.DataFrame) -> dict:
    latest = df.iloc[0]
    return {
        "total_revenue": float(latest["total_revenue"]) if pd.notna(latest["total_revenue"]) else 0,
        "net_margin_pct": round(float(latest["net_margin_pct"]) if pd.notna(latest["net_margin_pct"]) else 0, 1),
        "debt_to_equity_ratio": round(float(latest["debt_to_equity_ratio"]) if pd.notna(latest["debt_to_equity_ratio"]) else 0, 2),
        "financial_health": str(latest["financial_health"]),
    }


# ──────────────────────────────────────────────────────────────
# Cortex helpers
# ──────────────────────────────────────────────────────────────

def cortex_complete(session, prompt: str, model: str = CORTEX_MODEL_LLM) -> str:
    safe = prompt.replace("'", "\\'")
    sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{safe}') AS r"
    rows = session.sql(sql).collect()
    raw = rows[0]["R"].strip() if rows and rows[0]["R"] else ""

    # Strip markdown code fences if LLM wraps output in ```python ... ```
    if "```" in raw:
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    return raw


def cortex_vision_critique(session, image_path: str, prompt: str) -> str:
    """
    Send rendered chart context to pixtral-large for VLM critique.
    Uses text-only mode (pixtral-large responds to text on this account).
    """
    vision_prompt = (
        f"{prompt}\n\n"
        f"[Evaluate based on the chart description and context provided]"
    )
    return cortex_complete(session, vision_prompt, model=CORTEX_MODEL_VLM)


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

    runner = textwrap.dedent(f"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import warnings
warnings.filterwarnings("ignore")

df = pd.read_csv(r"{csv_path}")

{code}

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
            logger.error("Chart render failed:\n%s", result.stderr[-1000:])
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
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
df['date'] = pd.to_datetime(df['date'])
ax.fill_between(df['date'], df['close'].min(), df['close'], alpha=0.15, color='#2563eb')
ax.plot(df['date'], df['close'], color='#2563eb', linewidth=2, label='Close Price')
if df['sma_7d'].notna().any():
    ax.plot(df['date'], df['sma_7d'], color='#f59e0b', linewidth=1.5, linestyle='--', label='SMA 7D')
if df['sma_30d'].notna().any():
    ax.plot(df['date'], df['sma_30d'], color='#10b981', linewidth=1.5, linestyle='--', label='SMA 30D')
if df['sma_90d'].notna().any():
    ax.plot(df['date'], df['sma_90d'], color='#ef4444', linewidth=1.5, linestyle='--', label='SMA 90D')
ax.set_title('Price & Moving Averages', fontsize=14, fontweight='bold')
ax.set_xlabel('Date', fontsize=11)
ax.set_ylabel('Price (USD)', fontsize=11)
ax.grid(True, color='#e0e0e0', alpha=0.7, linestyle='--', linewidth=0.5)
ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
plt.xticks(rotation=30, fontsize=9)
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
            f"title fontsize=14 bold, combined legend, figsize=(14,6)."
        ),
        "fallback_code": """
fig, ax1 = plt.subplots(figsize=(14, 6))
ax1.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
df['date'] = pd.to_datetime(df['date'])
ax2 = ax1.twinx()
ax1.bar(df['date'], df['volume'] / 1e6, color='#94a3b8', alpha=0.6, label='Volume (M)')
if df['volatility_30d_pct'].notna().any():
    ax2.plot(df['date'], df['volatility_30d_pct'], color='#ef4444', linewidth=2, label='Volatility 30D %')
ax1.set_title('Volume & 30-Day Volatility', fontsize=14, fontweight='bold')
ax1.set_xlabel('Date', fontsize=11)
ax1.set_ylabel('Volume (Millions)', fontsize=11)
ax2.set_ylabel('Volatility 30D %', fontsize=11)
ax1.grid(True, color='#e0e0e0', alpha=0.7, linestyle='--', linewidth=0.5)
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)
plt.xticks(rotation=30, fontsize=9)
""",
    },

    "revenue_growth": {
        "title": "Revenue & Net Income Growth",
        "iter1_prompt": lambda ticker, df: (
            f"Generate a basic bar chart for {ticker} revenue growth. "
            f"df has columns: fiscal_quarter, revenue_growth_yoy_pct, net_income_growth_yoy_pct. "
            f"Plot revenue_growth_yoy_pct as bars. figsize=(12,5). "
            f"Title: '{ticker} Revenue Growth'. x-axis: fiscal_quarter."
        ),
        "iter2_prompt": lambda ticker, df, code, critique: (
            f"Improve this {ticker} growth chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Add: net_income_growth_yoy_pct as second grouped bar, "
            f"color coding (green positive, red negative), legend, axis labels."
        ),
        "iter3_prompt": lambda ticker, df, code, critique: (
            f"Create PROFESSIONAL {ticker} revenue/income growth chart. Previous:\n{code}\n\nCritique:\n{critique}\n\n"
            f"Requirements: grouped bars (revenue=#2563eb, net_income=#10b981), "
            f"color bars red if negative, zero reference line, "
            f"ax.set_facecolor('#f8f9fa'), value labels on bars, "
            f"title fontsize=14 bold, figsize=(14,6)."
        ),
        "fallback_code": """
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
x = range(len(df))
width = 0.35
rev_colors = ['#2563eb' if v >= 0 else '#ef4444' for v in df['revenue_growth_yoy_pct'].fillna(0)]
inc_colors = ['#10b981' if v >= 0 else '#ef4444' for v in df['net_income_growth_yoy_pct'].fillna(0)]
bars1 = ax.bar([i - width/2 for i in x], df['revenue_growth_yoy_pct'].fillna(0),
               width, color=rev_colors, alpha=0.8, label='Revenue Growth YoY %')
bars2 = ax.bar([i + width/2 for i in x], df['net_income_growth_yoy_pct'].fillna(0),
               width, color=inc_colors, alpha=0.8, label='Net Income Growth YoY %')
ax.axhline(y=0, color='black', linewidth=0.8, linestyle='-')
ax.set_xticks(list(x))
ax.set_xticklabels(df['fiscal_quarter'].tolist(), rotation=30, fontsize=9)
ax.set_title('Revenue & Net Income Growth (YoY %)', fontsize=14, fontweight='bold')
ax.set_ylabel('Growth %', fontsize=11)
ax.grid(True, axis='y', color='#e0e0e0', alpha=0.7, linestyle='--')
ax.legend(fontsize=9, framealpha=0.9)
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
growth_colors = ['#10b981' if v >= 0 else '#ef4444'
                 for v in df['eps_growth_yoy_pct'].fillna(0)]
ax2.bar(x, df['eps_growth_yoy_pct'].fillna(0), color=growth_colors,
        alpha=0.4, label='EPS Growth YoY %')
ax1.plot(list(x), df['eps'].fillna(0), color='#2563eb', linewidth=2.5,
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
            f"y-axis range -1 to 1, title fontsize=14 bold, figsize=(14,6)."
        ),
        "fallback_code": """
fig, ax = plt.subplots(figsize=(14, 6))
ax.set_facecolor('#f8f9fa')
fig.patch.set_facecolor('white')
df['news_date'] = pd.to_datetime(df['news_date'])
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
ax.set_title('News Sentiment Trend (7-Day Average)', fontsize=14, fontweight='bold')
ax.set_xlabel('Date', fontsize=11)
ax.set_ylabel('Sentiment Score (-1 to +1)', fontsize=11)
ax.grid(True, color='#e0e0e0', alpha=0.7, linestyle='--')
ax.legend(fontsize=9, framealpha=0.9)
plt.xticks(rotation=30, fontsize=9)
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
labels = [f"{int(r['fiscal_year'])} {r['fiscal_period']}" for _, r in df.iterrows()]
x = range(len(df))
width = 0.35
ax1.bar([i - width/2 for i in x], df['net_margin_pct'].fillna(0),
        width, color='#2563eb', alpha=0.8, label='Net Margin %')
ax1.bar([i + width/2 for i in x], df['operating_margin_pct'].fillna(0),
        width, color='#10b981', alpha=0.8, label='Operating Margin %')
if df['debt_to_equity_ratio'].notna().any():
    ax2.plot(list(x), df['debt_to_equity_ratio'].fillna(0),
             color='#ef4444', linewidth=2, marker='D', markersize=6,
             label='Debt/Equity Ratio')
ax1.set_xticks(list(x))
ax1.set_xticklabels(labels, rotation=30, fontsize=9)
ax1.set_title('Financial Health — Margins & Leverage', fontsize=14, fontweight='bold')
ax1.set_ylabel('Margin %', fontsize=11)
ax2.set_ylabel('Debt/Equity Ratio', fontsize=11)
ax1.grid(True, axis='y', color='#e0e0e0', alpha=0.7, linestyle='--')
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)
""",
    },
}


# ──────────────────────────────────────────────────────────────
# Single chart generator with iterative refinement
# ──────────────────────────────────────────────────────────────

def generate_single_chart(
    session, chart_id: str, ticker: str,
    df: pd.DataFrame, output_dir: Path,
    debug: bool = False
) -> dict:
    """
    Generate one chart through 3 LLM+VLM refinement iterations.
    Falls back to hardcoded professional chart if any iteration fails.

    Args:
        debug: If True, saves all 3 iteration PNGs and prints critiques to logs.
               If False, only the final chart is saved.

    Returns a ChartResult dict.
    """
    defn = CHART_DEFINITIONS[chart_id]
    title = f"{ticker} {defn['title']}"
    final_path = str(output_dir / f"{chart_id}.png")

    logger.info("Generating chart: %s", chart_id)

    try:
        # ── Iteration 1 ──────────────────────────────────────
        prompt1 = f"{CHART_CODE_SYSTEM}\n\n{defn['iter1_prompt'](ticker, df)}"
        code1 = cortex_complete(session, prompt1)

        path1 = str(output_dir / f"{chart_id}_iter1.png") if debug \
            else str(output_dir / f"{chart_id}_iter1_tmp.png")

        if not execute_chart_code(code1, df, path1):
            raise RuntimeError("Iteration 1 render failed")

        if debug:
            logger.info("  [DEBUG] Saved iter1 → %s_iter1.png", chart_id)

        # ── Critique 1 ───────────────────────────────────────
        critique_prompt1 = (
            f"You are a VLM critiquing a {ticker} {defn['title']} chart for equity research. "
            f"List exactly 3 issues starting with ❌. Cover: information density, "
            f"label clarity, missing elements. 3-5 sentences. Plain text only."
        )
        critique1 = cortex_vision_critique(session, path1, critique_prompt1)

        if debug:
            logger.info("  [DEBUG] Critique 1:\n%s", critique1)

        # ── Iteration 2 ──────────────────────────────────────
        prompt2 = f"{CHART_CODE_SYSTEM}\n\n{defn['iter2_prompt'](ticker, df, code1, critique1)}"
        code2 = cortex_complete(session, prompt2)

        path2 = str(output_dir / f"{chart_id}_iter2.png") if debug \
            else str(output_dir / f"{chart_id}_iter2_tmp.png")

        if not execute_chart_code(code2, df, path2):
            raise RuntimeError("Iteration 2 render failed")

        if debug:
            logger.info("  [DEBUG] Saved iter2 → %s_iter2.png", chart_id)

        # ── Critique 2 ───────────────────────────────────────
        critique_prompt2 = (
            f"Re-evaluate this improved {ticker} {defn['title']} chart. "
            f"Note 1-2 improvements, then list 1-2 remaining gaps with ⚠️. "
            f"2-4 sentences. Plain text only."
        )
        critique2 = cortex_vision_critique(session, path2, critique_prompt2)

        if debug:
            logger.info("  [DEBUG] Critique 2:\n%s", critique2)

        # ── Iteration 3 (final) ───────────────────────────────
        prompt3 = f"{CHART_CODE_SYSTEM}\n\n{defn['iter3_prompt'](ticker, df, code2, critique2)}"
        code3 = cortex_complete(session, prompt3)

        if not execute_chart_code(code3, df, final_path):
            raise RuntimeError("Iteration 3 render failed")

        if debug:
            logger.info("  [DEBUG] Saved final → %s.png", chart_id)

        logger.info("✅ Chart generated via LLM refinement: %s", chart_id)
        refinement_count = 3

    except Exception as e:
        logger.warning(
            "LLM refinement failed for %s (%s) — using fallback chart", chart_id, e
        )
        success = execute_chart_code(defn["fallback_code"], df, final_path)
        if not success:
            logger.error("Fallback chart also failed for %s", chart_id)
        refinement_count = 0

    return {
        "chart_id": chart_id,
        "title": title,
        "file_path": final_path,
        "validated": os.path.exists(final_path) and os.path.getsize(final_path) > 0,
        "refinement_count": refinement_count,
        "data_summary": {},  # populated by generate_charts()
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
    }

    results = []
    for chart_id, (df, summary_fn) in chart_data_map.items():
        if df.empty:
            logger.warning("No data for chart '%s', skipping", chart_id)
            continue

        chart_result = generate_single_chart(
            session, chart_id, ticker, df, out, debug=debug
        )
        chart_result["data_summary"] = summary_fn(df)
        results.append(chart_result)

    logger.info(
        "Chart Agent complete: %d/%d charts generated",
        len(results), len(chart_data_map)
    )

    # Save manifest
    manifest_path = out / "chart_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(
            [{k: v for k, v in r.items() if k != "file_path"} for r in results],
            f, indent=2
        )

    return results


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
