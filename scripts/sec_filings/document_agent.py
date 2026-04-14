"""
FinSage Document Reading Agent (v2 — Full Analytics Integration).

An LLM-powered agent that reads and analyzes extracted SEC filing text
(MD&A and Risk Factors) stored in Snowflake, COMBINED with quantitative
data from the analytics layer (stock metrics, fundamentals, sentiment,
SEC financials, company profile).

Uses Snowflake Cortex LLM functions for in-database AI analysis.

Changes from v1:
    - Added get_company_intelligence() to pull ALL analytics data
    - Added format_analytics_context() to build structured data context
    - Updated ALL analysis functions to include analytics data in prompts
    - Added new 'full_report' mode combining all analyses with analytics
    - Added 'data_snapshot' mode to show raw analytics data without LLM
    - Interactive mode updated with new commands

Usage:
    python -m sec_filings.document_agent --ticker AAPL
    python -m sec_filings.document_agent --ticker AAPL --mode full_report
    python -m sec_filings.document_agent --ticker TSLA --mode snapshot
    python -m sec_filings.document_agent --ticker MSFT --question "What are the main risks?"
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from snowflake_connection import get_session

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Snowflake Cortex LLM helper
# ──────────────────────────────────────────────────────────────
def cortex_complete(session, prompt: str, model: str = "llama3.1-70b") -> str:
    """
    Call Snowflake Cortex LLM for text completion.

    Available models: llama3.1-70b, llama3.1-8b, mistral-large2,
                      gemma-7b, mixtral-8x7b
    """
    escaped_prompt = prompt.replace("'", "''")

    max_chars = 50000
    if len(escaped_prompt) > max_chars:
        escaped_prompt = escaped_prompt[:max_chars]
        logger.warning("Prompt truncated to %d characters", max_chars)

    sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{escaped_prompt}') AS response"

    try:
        result = session.sql(sql).collect()
        return result[0]["RESPONSE"]
    except Exception as e:
        logger.error("Cortex LLM call failed: %s", e)
        raise


# ──────────────────────────────────────────────────────────────
# Analytics Intelligence Layer (NEW in v2)
# Pulls ALL quantitative data from dbt analytics models
# ──────────────────────────────────────────────────────────────
def get_company_intelligence(session, ticker: str) -> dict:
    """
    Pull ALL analytics data for a ticker — stock metrics,
    fundamentals growth, news sentiment, SEC financials, and
    company profile from the dbt analytics layer.

    Returns a dict with keys: profile, stock, fundamentals,
    sentiment, sec_financials. Each key may be None if the
    query fails or returns no data.
    """
    ticker = ticker.upper()
    intel = {"ticker": ticker}

    # 1. Company profile from dim_company
    try:
        rows = session.sql(f"""
            SELECT *
            FROM ANALYTICS.DIM_COMPANY
            WHERE TICKER = '{ticker}'
        """).collect()
        if rows:
            r = rows[0]
            intel["profile"] = {
                "market_cap": r["MARKET_CAP"],
                "market_cap_category": r["MARKET_CAP_CATEGORY"],
                "pe_ratio": r["PE_RATIO"],
                "profit_margin": r["PROFIT_MARGIN"],
                "debt_to_equity": r["DEBT_TO_EQUITY"],
                "cik": r["CIK"],
                "latest_form_type": r["LATEST_FORM_TYPE"],
                "price_history_start": str(r["PRICE_HISTORY_START"]),
                "price_history_end": str(r["PRICE_HISTORY_END"]),
                "total_trading_days": r["TOTAL_TRADING_DAYS"],
                "total_news_articles": r["TOTAL_NEWS_ARTICLES"],
                "data_sources_available": r["DATA_SOURCES_AVAILABLE"],
            }
            logger.info("Loaded company profile for %s: %s", ticker, intel["profile"]["market_cap_category"])
    except Exception as e:
        logger.warning("Could not fetch company profile for %s: %s", ticker, e)
        intel["profile"] = None

    # 2. Latest stock metrics from fct_stock_metrics
    try:
        rows = session.sql(f"""
            SELECT *
            FROM ANALYTICS.FCT_STOCK_METRICS
            WHERE TICKER = '{ticker}'
            ORDER BY DATE DESC
            LIMIT 1
        """).collect()
        if rows:
            r = rows[0]
            intel["stock"] = {
                "date": str(r["DATE"]),
                "close": r["CLOSE"],
                "open": r["OPEN"],
                "high": r["HIGH"],
                "low": r["LOW"],
                "volume": r["VOLUME"],
                "daily_return_pct": r["DAILY_RETURN_PCT"],
                "sma_7d": r["SMA_7D"],
                "sma_30d": r["SMA_30D"],
                "sma_90d": r["SMA_90D"],
                "avg_volume_30d": r["AVG_VOLUME_30D"],
                "volatility_30d_pct": r["VOLATILITY_30D_PCT"],
                "daily_range": r["DAILY_RANGE"],
                "daily_range_pct": r["DAILY_RANGE_PCT"],
                "week_52_high": r["WEEK_52_HIGH"],
                "week_52_low": r["WEEK_52_LOW"],
                "price_position_52w_pct": r["PRICE_POSITION_52W_PCT"],
                "trend_signal": r["TREND_SIGNAL"],
            }
            logger.info("Loaded stock metrics for %s: %s @ $%s", ticker, r["TREND_SIGNAL"], r["CLOSE"])
    except Exception as e:
        logger.warning("Could not fetch stock metrics for %s: %s", ticker, e)
        intel["stock"] = None

    # 3. Latest fundamentals growth from fct_fundamentals_growth
    try:
        rows = session.sql(f"""
            SELECT *
            FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
            WHERE TICKER = '{ticker}'
            ORDER BY FISCAL_QUARTER DESC
            LIMIT 1
        """).collect()
        if rows:
            r = rows[0]
            intel["fundamentals"] = {
                "fiscal_quarter": r["FISCAL_QUARTER"],
                "market_cap": r["MARKET_CAP"],
                "revenue": r["REVENUE"],
                "net_income": r["NET_INCOME"],
                "eps": r["EPS"],
                "pe_ratio": r["PE_RATIO"],
                "profit_margin": r["PROFIT_MARGIN"],
                "debt_to_equity": r["DEBT_TO_EQUITY"],
                "total_assets": r["TOTAL_ASSETS"],
                "total_liabilities": r["TOTAL_LIABILITIES"],
                "book_value": r["BOOK_VALUE"],
                "return_on_assets_pct": r["ROA"],
                "net_margin_pct": r["NET_MARGIN"],
                "revenue_growth_qoq_pct": r["REVENUE_GROWTH_QOQ"],
                "revenue_growth_yoy_pct": r["REVENUE_GROWTH_YOY"],
                "net_income_growth_yoy_pct": r["NET_INCOME_GROWTH_YOY"],
                "eps_growth_yoy_pct": r["EPS_GROWTH_YOY"],
                "fundamental_signal": r["FUNDAMENTAL_SIGNAL"],
            }
            logger.info("Loaded fundamentals for %s: %s", ticker, r["FUNDAMENTAL_SIGNAL"])
    except Exception as e:
        logger.warning("Could not fetch fundamentals for %s: %s", ticker, e)
        intel["fundamentals"] = None

    # 4. Latest news sentiment from fct_news_sentiment_agg
    try:
        rows = session.sql(f"""
            SELECT *
            FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG
            WHERE TICKER = '{ticker}'
            ORDER BY NEWS_DATE DESC
            LIMIT 1
        """).collect()
        if rows:
            r = rows[0]
            intel["sentiment"] = {
                "news_date": str(r["NEWS_DATE"]),
                "total_articles": r["ARTICLE_COUNT"],
                "positive_count": r["POSITIVE_COUNT"],
                "negative_count": r["NEGATIVE_COUNT"],
                "neutral_count": r["NEUTRAL_COUNT"],
                "sentiment_score": r["AVG_SENTIMENT_SCORE"],
                "sentiment_score_7d_avg": r["ROLLING_SENTIMENT_7D"],
                "positive_ratio_pct": r["POSITIVE_RATIO"],
                "articles_7d_total": r["ROLLING_VOLUME_7D"],
                "news_volume_momentum": r["VOLUME_MOMENTUM"],
                "sentiment_label": r["SENTIMENT_LABEL"],
                "sentiment_trend": r["SENTIMENT_TREND"],
            }
            logger.info("Loaded sentiment for %s: %s (%s)", ticker, r["SENTIMENT_LABEL"], r["SENTIMENT_TREND"])
    except Exception as e:
        logger.warning("Could not fetch sentiment for %s: %s", ticker, e)
        intel["sentiment"] = None

    # 5. Latest SEC financial summary from fct_sec_financial_summary
    try:
        rows = session.sql(f"""
            SELECT *
            FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
            WHERE TICKER = '{ticker}'
            ORDER BY FISCAL_YEAR DESC, FISCAL_PERIOD DESC
            LIMIT 1
        """).collect()
        if rows:
            r = rows[0]
            intel["sec_financials"] = {
                "fiscal_year": r["FISCAL_YEAR"],
                "fiscal_period": r["FISCAL_PERIOD"],
                "form_type": r["FORM_TYPE"],
                "total_revenue": r["REVENUE"],
                "net_income": r["NET_INCOME"],
                "operating_income": r["OPERATING_INCOME"],
                "total_assets": r["TOTAL_ASSETS"],
                "total_liabilities": r["TOTAL_LIABILITIES"],
                "stockholders_equity": r["STOCKHOLDERS_EQUITY"],
                "cash_and_equivalents": r["CASH_AND_EQUIVALENTS"],
                "eps": r["EPS"],
                "book_value": r["BOOK_VALUE"],
                "net_margin_pct": r["NET_MARGIN"],
                "operating_margin_pct": r["OPERATING_MARGIN"],
                "return_on_assets_pct": r["ROA"],
                "return_on_equity_pct": r["ROE"],
                "debt_to_equity_ratio": r["DEBT_TO_EQUITY"],
                "revenue_growth_yoy_pct": r["REVENUE_GROWTH_YOY"],
                "net_income_growth_yoy_pct": r["NET_INCOME_GROWTH_YOY"],
                "financial_health": r["FINANCIAL_HEALTH"],
            }
            logger.info("Loaded SEC financials for %s: %s", ticker, r["FINANCIAL_HEALTH"])
    except Exception as e:
        logger.warning("Could not fetch SEC financials for %s: %s", ticker, e)
        intel["sec_financials"] = None

    # 6. Recent news headlines (top 5 for context)
    try:
        rows = session.sql(f"""
            SELECT TITLE, PUBLISHED_AT, SENTIMENT
            FROM STAGING.STG_NEWS
            WHERE TICKER = '{ticker}'
              AND TITLE IS NOT NULL
            ORDER BY PUBLISHED_AT DESC
            LIMIT 5
        """).collect()
        if rows:
            intel["recent_headlines"] = [
                {
                    "title": r["TITLE"],
                    "date": str(r["PUBLISHED_AT"]),
                    "sentiment": r["SENTIMENT"],
                }
                for r in rows
            ]
            logger.info("Loaded %d recent headlines for %s", len(rows), ticker)
    except Exception as e:
        logger.warning("Could not fetch headlines for %s: %s", ticker, e)
        intel["recent_headlines"] = []

    return intel


def _safe_fmt(value, fmt=",.0f", prefix="", suffix=""):
    """Safely format a numeric value, returning 'N/A' if None."""
    if value is None:
        return "N/A"
    try:
        return f"{prefix}{value:{fmt}}{suffix}"
    except (ValueError, TypeError):
        return str(value)


def format_analytics_context(intel: dict) -> str:
    """
    Build a human-readable analytics context string from
    the intelligence dict. This gets injected into every prompt
    so the LLM has access to ALL quantitative data.
    """
    sections = []

    # Company profile
    p = intel.get("profile")
    if p:
        sections.append(f"""COMPANY PROFILE:
  Market Cap: {_safe_fmt(p.get('market_cap'), prefix='$')} ({p.get('market_cap_category', 'N/A')})
  P/E Ratio: {_safe_fmt(p.get('pe_ratio'), fmt='.2f')}
  Profit Margin: {_safe_fmt(p.get('profit_margin'), fmt='.2%') if p.get('profit_margin') and p['profit_margin'] < 1 else _safe_fmt(p.get('profit_margin'), fmt='.2f')}
  Debt-to-Equity: {_safe_fmt(p.get('debt_to_equity'), fmt='.2f')}
  Data Sources Available: {p.get('data_sources_available', 'N/A')}/4
  Trading History: {p.get('total_trading_days', 'N/A')} days ({p.get('price_history_start', '?')} to {p.get('price_history_end', '?')})
  News Articles Tracked: {p.get('total_news_articles', 'N/A')}""")

    # Stock metrics
    s = intel.get("stock")
    if s:
        sections.append(f"""STOCK PERFORMANCE (as of {s.get('date', 'N/A')}):
  Close: {_safe_fmt(s.get('close'), fmt='.2f', prefix='$')}
  Daily Return: {_safe_fmt(s.get('daily_return_pct'), fmt='.2f', suffix='%')}
  7-day SMA: {_safe_fmt(s.get('sma_7d'), fmt='.2f', prefix='$')}
  30-day SMA: {_safe_fmt(s.get('sma_30d'), fmt='.2f', prefix='$')}
  90-day SMA: {_safe_fmt(s.get('sma_90d'), fmt='.2f', prefix='$')}
  30-day Volatility: {_safe_fmt(s.get('volatility_30d_pct'), fmt='.2f', suffix='%')}
  52-week High: {_safe_fmt(s.get('week_52_high'), fmt='.2f', prefix='$')}
  52-week Low: {_safe_fmt(s.get('week_52_low'), fmt='.2f', prefix='$')}
  Position in 52-week Range: {_safe_fmt(s.get('price_position_52w_pct'), fmt='.1f', suffix='%')}
  Avg Volume (30d): {_safe_fmt(s.get('avg_volume_30d'), fmt=',.0f')}
  >>> TREND SIGNAL: {s.get('trend_signal', 'N/A')}""")

    # Fundamentals
    f = intel.get("fundamentals")
    if f:
        sections.append(f"""FUNDAMENTALS ({f.get('fiscal_quarter', 'N/A')}):
  Revenue: {_safe_fmt(f.get('revenue'), prefix='$')}
  Net Income: {_safe_fmt(f.get('net_income'), prefix='$')}
  EPS: {_safe_fmt(f.get('eps'), fmt='.2f', prefix='$')}
  Revenue Growth QoQ: {_safe_fmt(f.get('revenue_growth_qoq_pct'), fmt='.2f', suffix='%')}
  Revenue Growth YoY: {_safe_fmt(f.get('revenue_growth_yoy_pct'), fmt='.2f', suffix='%')}
  Net Income Growth YoY: {_safe_fmt(f.get('net_income_growth_yoy_pct'), fmt='.2f', suffix='%')}
  EPS Growth YoY: {_safe_fmt(f.get('eps_growth_yoy_pct'), fmt='.2f', suffix='%')}
  Net Margin: {_safe_fmt(f.get('net_margin_pct'), fmt='.2f', suffix='%')}
  Return on Assets: {_safe_fmt(f.get('return_on_assets_pct'), fmt='.2f', suffix='%')}
  Book Value: {_safe_fmt(f.get('book_value'), prefix='$')}
  >>> FUNDAMENTAL SIGNAL: {f.get('fundamental_signal', 'N/A')}""")

    # SEC financials
    sf = intel.get("sec_financials")
    if sf:
        sections.append(f"""SEC FILING FINANCIALS (Official — FY{sf.get('fiscal_year', '?')} {sf.get('fiscal_period', '?')}):
  Total Revenue: {_safe_fmt(sf.get('total_revenue'), prefix='$')}
  Net Income: {_safe_fmt(sf.get('net_income'), prefix='$')}
  Operating Income: {_safe_fmt(sf.get('operating_income'), prefix='$')}
  Total Assets: {_safe_fmt(sf.get('total_assets'), prefix='$')}
  Stockholders Equity: {_safe_fmt(sf.get('stockholders_equity'), prefix='$')}
  Cash & Equivalents: {_safe_fmt(sf.get('cash_and_equivalents'), prefix='$')}
  EPS (Diluted): {_safe_fmt(sf.get('eps_diluted'), fmt='.2f', prefix='$')}
  Net Margin: {_safe_fmt(sf.get('net_margin_pct'), fmt='.2f', suffix='%')}
  Operating Margin: {_safe_fmt(sf.get('operating_margin_pct'), fmt='.2f', suffix='%')}
  Return on Equity: {_safe_fmt(sf.get('return_on_equity_pct'), fmt='.2f', suffix='%')}
  Return on Assets: {_safe_fmt(sf.get('return_on_assets_pct'), fmt='.2f', suffix='%')}
  Debt-to-Equity Ratio: {_safe_fmt(sf.get('debt_to_equity_ratio'), fmt='.2f')}
  Revenue Growth YoY: {_safe_fmt(sf.get('revenue_growth_yoy_pct'), fmt='.2f', suffix='%')}
  >>> FINANCIAL HEALTH: {sf.get('financial_health', 'N/A')}""")

    # News sentiment
    sent = intel.get("sentiment")
    if sent:
        sections.append(f"""NEWS SENTIMENT (as of {sent.get('news_date', 'N/A')}):
  Sentiment Score: {_safe_fmt(sent.get('sentiment_score'), fmt='.3f')} (range: -1 to +1)
  7-day Avg Score: {_safe_fmt(sent.get('sentiment_score_7d_avg'), fmt='.3f')}
  Articles Today: {sent.get('total_articles', 'N/A')} ({sent.get('positive_count', 0)} positive, {sent.get('negative_count', 0)} negative, {sent.get('neutral_count', 0)} neutral)
  7-day Article Volume: {sent.get('articles_7d_total', 'N/A')}
  Positive Ratio: {_safe_fmt(sent.get('positive_ratio_pct'), fmt='.1f', suffix='%')}
  News Volume Momentum: {_safe_fmt(sent.get('news_volume_momentum'), fmt='.2f')}x
  >>> SENTIMENT LABEL: {sent.get('sentiment_label', 'N/A')}
  >>> SENTIMENT TREND: {sent.get('sentiment_trend', 'N/A')}""")

    # Recent headlines
    headlines = intel.get("recent_headlines", [])
    if headlines:
        hl_lines = []
        for h in headlines:
            emoji = "+" if h["sentiment"] == "positive" else ("-" if h["sentiment"] == "negative" else "~")
            hl_lines.append(f"  [{emoji}] {h['title'][:100]}")
        sections.append("RECENT HEADLINES:\n" + "\n".join(hl_lines))

    if not sections:
        return "(No analytics data available — only SEC filing text will be used)"

    return "\n\n".join(sections)


# ──────────────────────────────────────────────────────────────
# Document retrieval from Snowflake (unchanged from v1)
# ──────────────────────────────────────────────────────────────
def get_filing_text(session, ticker: str, form_type: str = None,
                    section: str = "both", limit: int = 1) -> list:
    """
    Retrieve extracted filing text from Snowflake.

    Args:
        ticker: Stock ticker
        form_type: '10-K', '10-Q', or None for both
        section: 'mda', 'risk', or 'both'
        limit: Number of most recent filings to retrieve

    Returns list of dicts with filing metadata and text.
    """
    where = [
        f"TICKER = '{ticker.upper()}'",
        "EXTRACTION_STATUS = 'extracted'",
    ]
    if form_type:
        where.append(f"FORM_TYPE = '{form_type}'")

    if section == "mda":
        text_cols = "MDA_TEXT, MDA_WORD_COUNT"
    elif section == "risk":
        text_cols = "RISK_FACTORS_TEXT, RISK_WORD_COUNT"
    else:
        text_cols = "MDA_TEXT, MDA_WORD_COUNT, RISK_FACTORS_TEXT, RISK_WORD_COUNT"

    query = f"""
    SELECT FILING_ID, TICKER, FORM_TYPE, FILING_DATE, PERIOD_OF_REPORT,
           COMPANY_NAME, {text_cols}, DATA_QUALITY_SCORE
    FROM RAW.RAW_SEC_FILING_DOCUMENTS
    WHERE {' AND '.join(where)}
    ORDER BY FILING_DATE DESC
    LIMIT {limit}
    """

    rows = session.sql(query).collect()

    filings = []
    for row in rows:
        filing = {
            "filing_id": row["FILING_ID"],
            "ticker": row["TICKER"],
            "form_type": row["FORM_TYPE"],
            "filing_date": str(row["FILING_DATE"]),
            "period_of_report": str(row["PERIOD_OF_REPORT"]),
            "company_name": row["COMPANY_NAME"],
            "quality_score": row["DATA_QUALITY_SCORE"],
        }
        if section in ("mda", "both") and "MDA_TEXT" in row.as_dict():
            filing["mda_text"] = row["MDA_TEXT"] or ""
            filing["mda_word_count"] = row["MDA_WORD_COUNT"] or 0
        if section in ("risk", "both") and "RISK_FACTORS_TEXT" in row.as_dict():
            filing["risk_factors_text"] = row["RISK_FACTORS_TEXT"] or ""
            filing["risk_word_count"] = row["RISK_WORD_COUNT"] or 0

        filings.append(filing)

    return filings


# ──────────────────────────────────────────────────────────────
# Analysis modes (UPDATED in v2 — all use analytics data)
# ──────────────────────────────────────────────────────────────
def summarize_filing(session, ticker: str, form_type: str = "10-K") -> str:
    """Generate a comprehensive executive summary using ALL data sources."""
    filings = get_filing_text(session, ticker, form_type, section="both", limit=1)

    if not filings:
        return f"No extracted filings found for {ticker} {form_type}"

    filing = filings[0]
    mda = filing.get("mda_text", "")[:15000]
    risk = filing.get("risk_factors_text", "")[:8000]

    # NEW: Get ALL analytics data
    intel = get_company_intelligence(session, ticker)
    analytics = format_analytics_context(intel)

    prompt = f"""You are a senior financial analyst at a top-tier investment bank. Generate a
comprehensive research summary for {filing['company_name']} ({filing['ticker']}).

You have TWO types of data:
1. QUANTITATIVE analytics data from our data pipeline (numbers, metrics, signals)
2. QUALITATIVE text from the SEC {filing['form_type']} filing dated {filing['filing_date']}

QUANTITATIVE DATA:
{analytics}

MANAGEMENT'S DISCUSSION AND ANALYSIS (MD&A):
{mda}

RISK FACTORS:
{risk}

Generate a professional research summary covering:

1. COMPANY SNAPSHOT — Use the quantitative data to paint the picture: market cap category,
   current price vs 52-week range, trend signal, and financial health rating.

2. FINANCIAL PERFORMANCE — Cross-reference the analytics numbers (revenue growth, margins,
   ROE) with what management says in the MD&A. If the numbers contradict management's
   narrative, flag it explicitly.

3. MARKET SIGNALS — Combine the stock trend signal with news sentiment. Is the market
   confirming or diverging from fundamentals? Note the sentiment trend direction.

4. KEY RISKS — List the top 3-5 risks from the filing, but weight them using the
   quantitative data. A "debt risk" matters more if debt-to-equity is high.

5. OUTLOOK & ASSESSMENT — Synthesize everything: fundamental signal + trend signal +
   sentiment label + financial health into a coherent forward-looking view.

CRITICAL INSTRUCTIONS:
- Reference SPECIFIC numbers from the analytics data (e.g., "Revenue grew 8.2% YoY")
- Cross-reference qualitative claims with quantitative evidence
- If management claims strong growth but the numbers show otherwise, explicitly note it
- Include the signal labels (BULLISH/BEARISH, HEALTHY/DECLINING, etc.) naturally in your text

Keep the report professional, data-driven, and under 700 words."""

    return cortex_complete(session, prompt)


def analyze_risks(session, ticker: str, form_type: str = "10-K") -> str:
    """Deep risk analysis enhanced with quantitative context."""
    filings = get_filing_text(session, ticker, form_type, section="risk", limit=1)

    if not filings:
        return f"No risk factors found for {ticker}"

    filing = filings[0]
    risk = filing.get("risk_factors_text", "")[:25000]

    # NEW: Get analytics data for risk context
    intel = get_company_intelligence(session, ticker)
    analytics = format_analytics_context(intel)

    prompt = f"""You are a risk analyst reviewing {filing['company_name']}'s ({filing['ticker']})
{filing['form_type']} filing from {filing['filing_date']}.

You have quantitative data to WEIGHT each risk by its actual impact:

QUANTITATIVE CONTEXT:
{analytics}

RISK FACTORS SECTION FROM FILING:
{risk}

Provide a data-enhanced risk analysis:

1. RISK CATEGORIES — Group risks into categories (market, operational, regulatory,
   financial, technology). For each category, note the relevant metric that measures
   exposure (e.g., financial risk → debt-to-equity ratio is X.XX).

2. TOP 5 CRITICAL RISKS — Rank by actual quantitative impact, not just by how much
   text the company devotes to them. A debt risk with D/E ratio of 3.0 is more critical
   than a regulatory risk mentioned in one paragraph.

3. RISK-METRIC ALIGNMENT — For each top risk, cite the specific metric that either
   confirms or mitigates it:
   - If filing mentions "revenue concentration risk" and revenue_growth_yoy is negative → HIGH concern
   - If filing mentions "debt risk" but D/E is 0.5 → LOW actual exposure

4. SENTIMENT CROSS-CHECK — Do recent news headlines confirm any of these risks?
   What does the sentiment trend tell us about market perception of risk?

5. RISK SCORE — Rate overall risk as LOW / MODERATE / HIGH / CRITICAL based on the
   combination of qualitative risks and quantitative evidence.

Be specific with numbers. Keep under 600 words."""

    return cortex_complete(session, prompt)


def analyze_mda(session, ticker: str, form_type: str = "10-K") -> str:
    """Deep MD&A analysis cross-referenced with analytics data."""
    filings = get_filing_text(session, ticker, form_type, section="mda", limit=1)

    if not filings:
        return f"No MD&A found for {ticker}"

    filing = filings[0]
    mda = filing.get("mda_text", "")[:25000]

    # NEW: Get analytics data
    intel = get_company_intelligence(session, ticker)
    analytics = format_analytics_context(intel)

    prompt = f"""You are a senior equity research analyst reviewing {filing['company_name']}'s ({filing['ticker']})
{filing['form_type']} MD&A section from {filing['filing_date']}.

CRITICAL: You have both management's narrative AND independent quantitative data.
Your job is to verify management's claims against the numbers.

QUANTITATIVE DATA (from our analytics pipeline):
{analytics}

MANAGEMENT'S DISCUSSION AND ANALYSIS:
{mda}

Provide a verification-focused MD&A analysis:

1. REVENUE ANALYSIS — What does management say about revenue? Does our
   revenue_growth_yoy_pct and revenue_growth_qoq_pct confirm their claims?
   Note any discrepancies.

2. PROFITABILITY — Management's margin discussion vs our calculated
   net_margin_pct, operating_margin_pct, and return_on_equity_pct.
   Are margins actually improving as they claim?

3. BALANCE SHEET HEALTH — Management's liquidity claims vs our
   debt_to_equity_ratio, cash_and_equivalents, and book_value.
   Is the company actually in a strong position?

4. MANAGEMENT CREDIBILITY CHECK — List 2-3 specific claims from the MD&A
   and verify each against the quantitative data:
   ✓ Confirmed: "Management claims strong growth" → revenue_growth_yoy = +12%
   ✗ Contradicted: "Management claims improving margins" → net_margin declined 2%
   ~ Unverifiable: "Management claims market leadership" → no direct metric

5. FORWARD OUTLOOK — What is management's guidance, and does the trend
   data (fundamental_signal, trend_signal) support their optimism?

Be specific. Cite exact numbers. Keep under 600 words."""

    return cortex_complete(session, prompt)


def compare_filings(session, ticker: str) -> str:
    """Compare filings enhanced with trend data showing trajectory."""
    filings = get_filing_text(session, ticker, form_type=None, section="both", limit=2)

    if len(filings) < 2:
        return f"Need at least 2 filings for comparison. Found {len(filings)} for {ticker}"

    newer = filings[0]
    older = filings[1]

    newer_mda = newer.get("mda_text", "")[:12000]
    older_mda = older.get("mda_text", "")[:12000]
    newer_risk = newer.get("risk_factors_text", "")[:6000]
    older_risk = older.get("risk_factors_text", "")[:6000]

    # NEW: Get current analytics for trajectory context
    intel = get_company_intelligence(session, ticker)
    analytics = format_analytics_context(intel)

    prompt = f"""You are a financial analyst comparing two filings for {newer['company_name']} ({newer['ticker']}).

CURRENT QUANTITATIVE STATE (from analytics pipeline):
{analytics}

RECENT FILING ({newer['form_type']} — {newer['filing_date']}):
MD&A: {newer_mda}
Risk Factors: {newer_risk}

PREVIOUS FILING ({older['form_type']} — {older['filing_date']}):
MD&A: {older_mda}
Risk Factors: {older_risk}

Provide a trend-aware comparison:

1. NARRATIVE CHANGES — What materially changed in management's story?

2. QUANTITATIVE TRAJECTORY — Use the analytics data to show where the company
   is headed. Are the current numbers (fundamental_signal, financial_health,
   trend_signal) consistent with the direction from older → newer filing?

3. RISK EVOLUTION — New risks added? Old risks removed? Cross-reference with
   current sentiment_label and sentiment_trend.

4. MANAGEMENT TONE SHIFT — More optimistic or cautious? Does sentiment data
   from news coverage align with the tone change?

5. VERDICT — Is the company improving, stable, or deteriorating? Support with
   both filing text changes AND quantitative signals.

Be specific about differences. Keep under 600 words."""

    return cortex_complete(session, prompt)


def ask_question(session, ticker: str, question: str,
                 form_type: str = "10-K") -> str:
    """Ask a question with full analytics context."""
    filings = get_filing_text(session, ticker, form_type, section="both", limit=1)

    if not filings:
        return f"No filings found for {ticker}"

    filing = filings[0]
    mda = filing.get("mda_text", "")[:15000]
    risk = filing.get("risk_factors_text", "")[:8000]

    # NEW: Get analytics data
    intel = get_company_intelligence(session, ticker)
    analytics = format_analytics_context(intel)

    prompt = f"""You are a financial analyst answering questions about {filing['company_name']}'s ({filing['ticker']}).

You have access to TWO data sources:
1. Quantitative analytics data (numbers, metrics, computed signals)
2. SEC {filing['form_type']} filing text from {filing['filing_date']}

QUANTITATIVE DATA:
{analytics}

MANAGEMENT'S DISCUSSION AND ANALYSIS:
{mda}

RISK FACTORS:
{risk}

QUESTION: {question}

Answer using BOTH the quantitative data and filing text. If the question is about
numbers, prioritize the analytics data. If about strategy or plans, prioritize the
filing text. Always cross-reference when possible.

If the answer is not in either source, say so clearly.
Keep your answer under 400 words."""

    return cortex_complete(session, prompt)


# ──────────────────────────────────────────────────────────────
# NEW in v2: Full comprehensive report
# ──────────────────────────────────────────────────────────────
def full_report(session, ticker: str, form_type: str = "10-K") -> str:
    """
    Generate a comprehensive multi-section research report.
    Runs multiple analyses and combines them into one output.
    """
    logger.info("Generating full report for %s", ticker)

    filings = get_filing_text(session, ticker, form_type, section="both", limit=1)
    if not filings:
        return f"No extracted filings found for {ticker} {form_type}"

    filing = filings[0]
    mda = filing.get("mda_text", "")[:15000]
    risk = filing.get("risk_factors_text", "")[:8000]

    intel = get_company_intelligence(session, ticker)
    analytics = format_analytics_context(intel)

    prompt = f"""You are the lead analyst at a top investment research firm. Generate a
comprehensive equity research report for {filing['company_name']} ({filing['ticker']}).

This report must integrate BOTH quantitative analytics and qualitative SEC filing analysis.

═══ QUANTITATIVE DATA FROM ANALYTICS PIPELINE ═══
{analytics}

═══ SEC {filing['form_type']} FILING (dated {filing['filing_date']}) ═══

MANAGEMENT'S DISCUSSION AND ANALYSIS:
{mda}

RISK FACTORS:
{risk}

═══ REPORT STRUCTURE ═══

Generate the following sections:

## 1. EXECUTIVE SUMMARY (100 words)
One-paragraph snapshot: what this company is, its current state, and the key takeaway.
Include: market cap category, financial health rating, trend signal, sentiment label.

## 2. FINANCIAL PERFORMANCE (150 words)
Revenue and profitability analysis with specific numbers from both analytics and filing.
Include: revenue growth YoY, net margin, operating margin, ROE. Flag any contradictions
between management narrative and actual numbers.

## 3. STOCK & MARKET ANALYSIS (100 words)
Current price context: position in 52-week range, moving averages, volatility,
trend signal. How does the market price reflect (or diverge from) fundamentals?

## 4. NEWS SENTIMENT ANALYSIS (100 words)
What is the market saying? Sentiment score, trend direction, key positive and
negative themes from recent headlines. Compare market mood vs actual performance.

## 5. RISK ASSESSMENT (150 words)
Top 3-5 risks ranked by quantitative impact. For each risk: the qualitative
description from the filing + the quantitative metric that measures actual exposure.
Overall risk rating: LOW / MODERATE / HIGH / CRITICAL.

## 6. MANAGEMENT CREDIBILITY (100 words)
Pick 2-3 specific management claims from the MD&A and verify against analytics data.
Rate management credibility: HIGH / MODERATE / LOW.

## 7. INVESTMENT OUTLOOK (100 words)
Synthesis of all signals: fundamental_signal + trend_signal + sentiment_label +
financial_health. Forward-looking view with specific data-backed reasoning.

CRITICAL RULES:
- Every section MUST cite at least 2 specific numbers from the analytics data
- Use signal labels naturally (e.g., "The BULLISH trend signal aligns with...")
- Flag contradictions between management claims and quantitative data
- This is a professional report — no hedging language like "it seems" or "possibly"

Total length: ~800 words."""

    return cortex_complete(session, prompt)


# ──────────────────────────────────────────────────────────────
# NEW in v2: Data snapshot (no LLM — raw analytics display)
# ──────────────────────────────────────────────────────────────
def data_snapshot(session, ticker: str) -> str:
    """
    Display all analytics data without LLM analysis.
    Useful for debugging and verifying data pipeline output.
    """
    intel = get_company_intelligence(session, ticker)
    analytics = format_analytics_context(intel)

    header = f"""
{'='*60}
  FinSage Data Snapshot — {ticker.upper()}
  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
{'='*60}

"""
    return header + analytics


# ──────────────────────────────────────────────────────────────
# Interactive mode (UPDATED with new commands)
# ──────────────────────────────────────────────────────────────
def interactive_mode(session, ticker: str):
    """Interactive Q&A session with full analytics context."""
    print(f"\n{'='*60}")
    print(f"  FinSage Document Agent v2 — {ticker.upper()}")
    print(f"  (Now with full analytics integration!)")
    print(f"{'='*60}")
    print(f"  Commands:")
    print(f"    summary    — Executive summary (analytics + filing)")
    print(f"    risks      — Risk analysis weighted by metrics")
    print(f"    mda        — MD&A with management credibility check")
    print(f"    compare    — Compare filings with trend data")
    print(f"    report     — Full comprehensive research report")
    print(f"    snapshot   — Raw analytics data (no LLM)")
    print(f"    quit       — Exit")
    print(f"    Or type any question about the company")
    print(f"{'='*60}\n")

    while True:
        try:
            user_input = input(f"[{ticker.upper()}] Ask > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        print("\nAnalyzing...\n")

        try:
            if user_input.lower() == "summary":
                result = summarize_filing(session, ticker)
            elif user_input.lower() == "risks":
                result = analyze_risks(session, ticker)
            elif user_input.lower() == "mda":
                result = analyze_mda(session, ticker)
            elif user_input.lower() == "compare":
                result = compare_filings(session, ticker)
            elif user_input.lower() == "report":
                result = full_report(session, ticker)
            elif user_input.lower() == "snapshot":
                result = data_snapshot(session, ticker)
            else:
                result = ask_question(session, ticker, user_input)

            print(f"\n{result}\n")
            print("-" * 60)

        except Exception as e:
            print(f"\nError: {e}\n")


# ──────────────────────────────────────────────────────────────
# Batch analysis (UPDATED to include full_report)
# ──────────────────────────────────────────────────────────────
def batch_analysis(session, tickers: list = None, output_dir: str = None) -> dict:
    """
    Run full analysis on multiple tickers and save results.
    Now includes analytics data snapshot with each ticker.
    """
    if tickers is None:
        rows = session.sql("""
            SELECT DISTINCT TICKER FROM RAW.RAW_SEC_FILING_DOCUMENTS
            WHERE EXTRACTION_STATUS = 'extracted'
            ORDER BY TICKER
        """).collect()
        tickers = [r["TICKER"] for r in rows]

    results = {}

    for ticker in tickers:
        logger.info("Running full analysis for %s", ticker)

        try:
            # Get analytics snapshot
            intel = get_company_intelligence(session, ticker)

            analysis = {
                "ticker": ticker,
                "timestamp": datetime.utcnow().isoformat(),
                "analytics_data": intel,
                "full_report": full_report(session, ticker),
                "summary": summarize_filing(session, ticker),
                "risk_analysis": analyze_risks(session, ticker),
                "mda_analysis": analyze_mda(session, ticker),
            }

            # Try comparison if multiple filings exist
            try:
                analysis["comparison"] = compare_filings(session, ticker)
            except Exception:
                analysis["comparison"] = "Insufficient filings for comparison"

            results[ticker] = analysis
            logger.info("Full analysis complete for %s", ticker)

        except Exception as e:
            logger.error("Analysis failed for %s: %s", ticker, e)
            results[ticker] = {"ticker": ticker, "error": str(e)}

    # Save results if output directory specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir,
            f"analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info("Results saved to %s", output_path)

    return results


# ──────────────────────────────────────────────────────────────
# CLI entrypoint (UPDATED with new modes)
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinSage Document Reading Agent v2")
    parser.add_argument("--ticker", type=str, required=True,
                        help="Stock ticker (e.g. AAPL)")
    parser.add_argument("--mode", type=str,
                        choices=["summary", "risks", "mda", "compare",
                                 "full_report", "snapshot",
                                 "interactive", "batch"],
                        default="interactive",
                        help="Analysis mode (default: interactive)")
    parser.add_argument("--question", type=str,
                        help="Ask a specific question (skips interactive mode)")
    parser.add_argument("--form-type", type=str, choices=["10-K", "10-Q"],
                        default="10-K",
                        help="Filing type (default: 10-K)")
    parser.add_argument("--output-dir", type=str,
                        help="Output directory for batch results")
    args = parser.parse_args()

    session = get_session()

    try:
        if args.question:
            result = ask_question(session, args.ticker, args.question, args.form_type)
            print(f"\n{result}\n")

        elif args.mode == "summary":
            result = summarize_filing(session, args.ticker, args.form_type)
            print(f"\n{result}\n")

        elif args.mode == "risks":
            result = analyze_risks(session, args.ticker, args.form_type)
            print(f"\n{result}\n")

        elif args.mode == "mda":
            result = analyze_mda(session, args.ticker, args.form_type)
            print(f"\n{result}\n")

        elif args.mode == "compare":
            result = compare_filings(session, args.ticker)
            print(f"\n{result}\n")

        elif args.mode == "full_report":
            result = full_report(session, args.ticker, args.form_type)
            print(f"\n{result}\n")

        elif args.mode == "snapshot":
            result = data_snapshot(session, args.ticker)
            print(result)

        elif args.mode == "batch":
            tickers = [args.ticker] if args.ticker != "ALL" else None
            batch_analysis(session, tickers=tickers, output_dir=args.output_dir)

        else:
            interactive_mode(session, args.ticker)

    finally:
        session.close()