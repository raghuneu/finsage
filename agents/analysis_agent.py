"""
FinSage Analysis Agent

Uses Snowflake Cortex to generate written analysis for each validated chart
and summarize SEC filing text (MD&A + Risk Factors).

Inputs:
    - validated chart list (from validation_agent / mock_data during dev)
    - Snowflake session
    - ticker symbol

Outputs:
    - List of analysis dicts: {chart_id, title, analysis_text}
    - SEC summary dict: {mda_summary, risk_summary}
"""

import logging
from typing import Optional
from snowflake.snowpark import Session

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Cortex model to use
# ──────────────────────────────────────────────────────────────
CORTEX_MODEL = "mistral-large"

# Max characters of SEC text to pass into SUMMARIZE
# Cortex has token limits — keep it under ~8000 words
MAX_SEC_TEXT_CHARS = 40_000


# ──────────────────────────────────────────────────────────────
# Per-chart prompt templates
# ──────────────────────────────────────────────────────────────
CHART_PROMPTS = {
    "price_sma": """
You are a senior equity research analyst writing a section of a professional financial report.
Analyze the following stock price and moving average data for {ticker} and write a concise,
insightful 3-4 sentence analysis. Focus on trend direction, momentum, and what the SMA
crossover signals for near-term price action. Be specific with the numbers provided.

Data:
- Current Price: ${current_price}
- 7-Day SMA: ${sma_7d}
- 30-Day SMA: ${sma_30d}
- 90-Day SMA: ${sma_90d}
- Trend Signal: {trend_signal}
- Date Range: {date_range}

Write the analysis in third person, professional tone. Do not use bullet points.
""",

    "volatility": """
You are a senior equity research analyst writing a section of a professional financial report.
Analyze the following volume and volatility data for {ticker} and write a concise,
insightful 3-4 sentence analysis. Comment on trading activity levels, price stability,
and what this implies about investor sentiment and risk profile.

Data:
- Average Daily Volume: {avg_volume:,}
- 30-Day Volatility: {volatility_30d_pct}%
- Average Daily Range: {daily_range_pct_avg}%

Write the analysis in third person, professional tone. Do not use bullet points.
""",

    "revenue_growth": """
You are a senior equity research analyst writing a section of a professional financial report.
Analyze the following revenue and net income growth data for {ticker} and write a concise,
insightful 3-4 sentence analysis. Comment on revenue trajectory, profitability trends,
and overall fundamental strength.

Data:
- Latest Revenue Growth (YoY): {latest_revenue_growth_yoy}%
- Latest Net Income Growth (YoY): {latest_net_income_growth_yoy}%
- Fundamental Signal: {fundamental_signal}

Write the analysis in third person, professional tone. Do not use bullet points.
""",

    "eps_trend": """
You are a senior equity research analyst writing a section of a professional financial report.
Analyze the following earnings per share data for {ticker} and write a concise,
insightful 3-4 sentence analysis. Comment on earnings quality, growth consistency,
and shareholder value implications.

Data:
- Latest EPS: ${latest_eps}
- EPS Growth (YoY): {eps_growth_yoy_pct}%
- EPS Growth (QoQ): {eps_growth_qoq_pct}%

Write the analysis in third person, professional tone. Do not use bullet points.
""",

    "sentiment": """
You are a senior equity research analyst writing a section of a professional financial report.
Analyze the following news sentiment data for {ticker} and write a concise,
insightful 3-4 sentence analysis. Comment on market perception, sentiment momentum,
and what media coverage implies about near-term investor confidence.

Data:
- 7-Day Average Sentiment Score: {sentiment_score_7d_avg} (scale: -1 bearish to +1 bullish)
- Sentiment Label: {sentiment_label}
- Sentiment Trend: {sentiment_trend}
- Total Articles (Last 30 Days): {total_articles_30d}

Write the analysis in third person, professional tone. Do not use bullet points.
""",

    "financial_health": """
You are a senior equity research analyst writing a section of a professional financial report.
Analyze the following financial health data for {ticker} sourced from SEC filings and write
a concise, insightful 3-4 sentence analysis. Comment on balance sheet strength, profitability,
leverage, and overall financial health rating.

Data:
- Total Revenue: ${total_revenue:,.0f}
- Net Margin: {net_margin_pct}%
- Debt-to-Equity Ratio: {debt_to_equity_ratio}
- Financial Health Rating: {financial_health}

Write the analysis in third person, professional tone. Do not use bullet points.
""",
}


# ──────────────────────────────────────────────────────────────
# Cortex helpers
# ──────────────────────────────────────────────────────────────
def _cortex_complete(session: Session, prompt: str) -> str:
    """
    Call Snowflake Cortex COMPLETE() with the given prompt.
    Returns the generated text string.
    """
    # Escape single quotes in prompt for SQL safety
    safe_prompt = prompt.replace("'", "\\'")

    sql = f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            '{CORTEX_MODEL}',
            '{safe_prompt}'
        ) AS response
    """
    result = session.sql(sql).collect()
    if result and result[0]["RESPONSE"]:
        return result[0]["RESPONSE"].strip()
    return ""


def _cortex_summarize(session: Session, text: str) -> str:
    """
    Call Snowflake Cortex SUMMARIZE() on the given text.
    Returns a condensed summary string.
    """
    if not text or len(text.strip()) < 100:
        return ""

    # Truncate if too long
    truncated = text[:MAX_SEC_TEXT_CHARS]
    safe_text = truncated.replace("'", "\\'")

    sql = f"""
        SELECT SNOWFLAKE.CORTEX.SUMMARIZE(
            '{safe_text}'
        ) AS summary
    """
    result = session.sql(sql).collect()
    if result and result[0]["SUMMARY"]:
        return result[0]["SUMMARY"].strip()
    return ""


# ──────────────────────────────────────────────────────────────
# Chart analysis
# ──────────────────────────────────────────────────────────────
def analyze_chart(session: Session, chart: dict, ticker: str) -> dict:
    """
    Generate a written analysis paragraph for a single validated chart.

    Args:
        session: Snowflake session
        chart: ChartResult dict from chart_agent / mock_data
        ticker: Stock ticker symbol

    Returns:
        dict with chart_id, title, analysis_text
    """
    chart_id = chart["chart_id"]
    data_summary = chart.get("data_summary", {})

    prompt_template = CHART_PROMPTS.get(chart_id)
    if not prompt_template:
        logger.warning("No prompt template for chart_id '%s', skipping", chart_id)
        return {
            "chart_id": chart_id,
            "title": chart.get("title", ""),
            "analysis_text": "Analysis not available for this chart.",
        }

    try:
        # Fill in the prompt template with actual data values
        prompt = prompt_template.format(ticker=ticker, **data_summary)
        logger.info("Generating analysis for chart: %s", chart_id)

        analysis_text = _cortex_complete(session, prompt)

        if not analysis_text:
            logger.warning("Cortex returned empty response for chart '%s'", chart_id)
            analysis_text = "Insufficient data to generate analysis for this chart."

        logger.info("✅ Analysis generated for %s (%d chars)", chart_id, len(analysis_text))

        return {
            "chart_id": chart_id,
            "title": chart.get("title", ""),
            "analysis_text": analysis_text,
        }

    except Exception as e:
        logger.error("Failed to analyze chart '%s': %s", chart_id, e)
        return {
            "chart_id": chart_id,
            "title": chart.get("title", ""),
            "analysis_text": "Analysis could not be generated due to a processing error.",
        }


def analyze_all_charts(session: Session, charts: list, ticker: str) -> list:
    """
    Generate analysis for all validated charts.

    Args:
        session: Snowflake session
        charts: List of ChartResult dicts
        ticker: Stock ticker symbol

    Returns:
        List of analysis dicts [{chart_id, title, analysis_text}, ...]
    """
    logger.info("Starting chart analysis for %s (%d charts)", ticker, len(charts))
    analyses = []

    for chart in charts:
        if not chart.get("validated", True):
            logger.warning("Skipping unvalidated chart: %s", chart.get("chart_id"))
            continue
        analysis = analyze_chart(session, chart, ticker)
        analyses.append(analysis)

    logger.info("✅ Completed analysis for %d/%d charts", len(analyses), len(charts))
    return analyses


# ──────────────────────────────────────────────────────────────
# SEC filing summarization
# ──────────────────────────────────────────────────────────────
def fetch_sec_text(session: Session, ticker: str) -> dict:
    """
    Fetch the most recent MD&A and Risk Factors text from Snowflake
    for the given ticker (from RAW.RAW_SEC_FILING_DOCUMENTS).

    Returns dict with mda_text and risk_text (empty strings if not found).
    """
    sql = f"""
        SELECT MDA_TEXT, RISK_FACTORS_TEXT
        FROM RAW.RAW_SEC_FILING_DOCUMENTS
        WHERE TICKER = '{ticker.upper()}'
          AND EXTRACTION_STATUS = 'extracted'
          AND MDA_TEXT IS NOT NULL
        ORDER BY FILING_DATE DESC
        LIMIT 1
    """
    try:
        rows = session.sql(sql).collect()
        if rows:
            return {
                "mda_text": rows[0]["MDA_TEXT"] or "",
                "risk_text": rows[0]["RISK_FACTORS_TEXT"] or "",
            }
    except Exception as e:
        logger.warning("Could not fetch SEC text for %s: %s", ticker, e)

    return {"mda_text": "", "risk_text": ""}


def summarize_sec_filings(session: Session, ticker: str) -> dict:
    """
    Fetch and summarize SEC filing text (MD&A + Risk Factors) using Cortex.

    Returns:
        dict with mda_summary and risk_summary strings.
        Falls back to empty strings if no SEC data available.
    """
    logger.info("Fetching SEC filing text for %s", ticker)
    sec_text = fetch_sec_text(session, ticker)

    mda_summary = ""
    risk_summary = ""

    if sec_text["mda_text"]:
        logger.info("Summarizing MD&A text (%d chars)", len(sec_text["mda_text"]))
        mda_summary = _cortex_summarize(session, sec_text["mda_text"])
        if mda_summary:
            logger.info("✅ MD&A summary generated (%d chars)", len(mda_summary))
        else:
            logger.warning("Cortex returned empty MD&A summary for %s", ticker)
    else:
        logger.warning("No extracted MD&A text found for %s", ticker)

    if sec_text["risk_text"]:
        logger.info("Summarizing Risk Factors text (%d chars)", len(sec_text["risk_text"]))
        risk_summary = _cortex_summarize(session, sec_text["risk_text"])
        if risk_summary:
            logger.info("✅ Risk summary generated (%d chars)", len(risk_summary))
        else:
            logger.warning("Cortex returned empty risk summary for %s", ticker)
    else:
        logger.warning("No extracted Risk Factors text found for %s", ticker)

    return {
        "mda_summary": mda_summary or f"MD&A summary not available for {ticker}.",
        "risk_summary": risk_summary or f"Risk factors summary not available for {ticker}.",
    }


# ──────────────────────────────────────────────────────────────
# Main entry point (called by orchestrator)
# ──────────────────────────────────────────────────────────────
def run_analysis(session: Session, charts: list, ticker: str) -> dict:
    """
    Full analysis pipeline:
        1. Generate written analysis for each validated chart
        2. Summarize SEC filing MD&A and Risk Factors

    Args:
        session: Snowflake session
        charts: List of validated ChartResult dicts
        ticker: Stock ticker symbol

    Returns:
        {
            "chart_analyses": [...],   # list of {chart_id, title, analysis_text}
            "mda_summary": "...",      # Cortex summary of MD&A section
            "risk_summary": "...",     # Cortex summary of Risk Factors
        }
    """
    logger.info("═" * 50)
    logger.info("Analysis Agent starting for %s", ticker)
    logger.info("═" * 50)

    chart_analyses = analyze_all_charts(session, charts, ticker)
    sec_summaries = summarize_sec_filings(session, ticker)

    result = {
        "chart_analyses": chart_analyses,
        "mda_summary": sec_summaries["mda_summary"],
        "risk_summary": sec_summaries["risk_summary"],
    }

    logger.info("Analysis Agent complete for %s", ticker)
    return result


# ──────────────────────────────────────────────────────────────
# Dev test (uses mock data — remove before production)
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os
    import logging

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

    from snowflake_connection import get_session
    from mock_data import MOCK_CHARTS

    session = get_session()
    result = run_analysis(session, MOCK_CHARTS, "AAPL")

    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    for a in result["chart_analyses"]:
        print(f"\n📊 {a['title']}")
        print(f"{a['analysis_text']}")
        print("-" * 40)

    print(f"\n📄 MD&A Summary:\n{result['mda_summary']}")
    print(f"\n⚠️  Risk Summary:\n{result['risk_summary']}")

    session.close()
