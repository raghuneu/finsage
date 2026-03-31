"""
FinSage Document Reading Agent.

An LLM-powered agent that reads and analyzes extracted SEC filing text
(MD&A and Risk Factors) stored in Snowflake. Uses Snowflake Cortex LLM
functions for in-database AI analysis.

Usage:
    python -m sec_filings.document_agent --ticker AAPL
    python -m sec_filings.document_agent --ticker TSLA --question "What are the main risks?"
    python -m sec_filings.document_agent --ticker MSFT --mode summary
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
    # Escape single quotes in prompt
    escaped_prompt = prompt.replace("'", "''")

    # Truncate prompt if too long (Cortex has token limits)
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
# Document retrieval from Snowflake
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

    # Select columns based on section
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
# Analysis modes
# ──────────────────────────────────────────────────────────────
def summarize_filing(session, ticker: str, form_type: str = "10-K") -> str:
    """Generate an executive summary of the most recent filing."""
    filings = get_filing_text(session, ticker, form_type, section="both", limit=1)

    if not filings:
        return f"No extracted filings found for {ticker} {form_type}"

    filing = filings[0]
    mda = filing.get("mda_text", "")[:20000]
    risk = filing.get("risk_factors_text", "")[:10000]

    prompt = f"""You are a senior financial analyst. Analyze the following SEC {filing['form_type']} filing 
for {filing['company_name']} ({filing['ticker']}) filed on {filing['filing_date']}, 
covering the period ending {filing['period_of_report']}.

MANAGEMENT'S DISCUSSION AND ANALYSIS (MD&A):
{mda}

RISK FACTORS:
{risk}

Provide a concise executive summary covering:
1. KEY FINANCIAL HIGHLIGHTS - Revenue trends, profitability, notable changes
2. STRATEGIC INITIATIVES - What management is focused on
3. RISK ASSESSMENT - Top 3-5 most significant risks
4. OUTLOOK - Management's forward-looking statements and expectations

Keep the summary professional, data-driven, and under 500 words."""

    return cortex_complete(session, prompt)


def analyze_risks(session, ticker: str, form_type: str = "10-K") -> str:
    """Deep analysis of risk factors."""
    filings = get_filing_text(session, ticker, form_type, section="risk", limit=1)

    if not filings:
        return f"No risk factors found for {ticker}"

    filing = filings[0]
    risk = filing.get("risk_factors_text", "")[:30000]

    prompt = f"""You are a risk analyst reviewing {filing['company_name']}'s ({filing['ticker']}) 
{filing['form_type']} filing from {filing['filing_date']}.

RISK FACTORS SECTION:
{risk}

Provide a structured risk analysis:
1. RISK CATEGORIES - Group risks into categories (market, operational, regulatory, financial, technology)
2. TOP 5 CRITICAL RISKS - Most impactful risks with brief explanation
3. NEW OR EMERGING RISKS - Any risks that appear new or escalating
4. RISK MITIGATION - What strategies does the company mention to address key risks?
5. INVESTOR IMPLICATIONS - How should investors weigh these risks?

Be specific and reference details from the filing. Keep under 600 words."""

    return cortex_complete(session, prompt)


def analyze_mda(session, ticker: str, form_type: str = "10-K") -> str:
    """Deep analysis of MD&A section."""
    filings = get_filing_text(session, ticker, form_type, section="mda", limit=1)

    if not filings:
        return f"No MD&A found for {ticker}"

    filing = filings[0]
    mda = filing.get("mda_text", "")[:30000]

    prompt = f"""You are a senior equity research analyst reviewing {filing['company_name']}'s ({filing['ticker']}) 
{filing['form_type']} MD&A section from {filing['filing_date']}.

MANAGEMENT'S DISCUSSION AND ANALYSIS:
{mda}

Provide a detailed MD&A analysis covering:
1. REVENUE ANALYSIS - Key revenue drivers, segment performance, growth trends
2. PROFITABILITY - Margin trends, cost structure changes, efficiency improvements
3. CASH FLOW & LIQUIDITY - Cash generation, capital allocation, debt management
4. STRATEGIC DIRECTION - Management priorities, investments, market positioning
5. FORWARD GUIDANCE - Any outlook statements, expected trends, planned initiatives

Be specific with numbers and percentages where available. Keep under 600 words."""

    return cortex_complete(session, prompt)


def compare_filings(session, ticker: str) -> str:
    """Compare the two most recent filings for trend analysis."""
    filings = get_filing_text(session, ticker, form_type=None, section="both", limit=2)

    if len(filings) < 2:
        return f"Need at least 2 filings for comparison. Found {len(filings)} for {ticker}"

    newer = filings[0]
    older = filings[1]

    newer_mda = newer.get("mda_text", "")[:15000]
    older_mda = older.get("mda_text", "")[:15000]
    newer_risk = newer.get("risk_factors_text", "")[:8000]
    older_risk = older.get("risk_factors_text", "")[:8000]

    prompt = f"""You are a financial analyst comparing two consecutive filings for {newer['company_name']} ({newer['ticker']}).

RECENT FILING ({newer['form_type']} - {newer['filing_date']}):
MD&A: {newer_mda}
Risk Factors: {newer_risk}

PREVIOUS FILING ({older['form_type']} - {older['filing_date']}):
MD&A: {older_mda}
Risk Factors: {older_risk}

Compare these filings and provide:
1. KEY CHANGES - What materially changed between the two periods?
2. PERFORMANCE TRENDS - Is the company improving or deteriorating?
3. NEW RISKS - Any new risks appearing in the more recent filing?
4. REMOVED RISKS - Any risks from the older filing no longer mentioned?
5. STRATEGIC SHIFTS - Changes in management priorities or strategy
6. SENTIMENT CHANGE - Has management tone become more optimistic or cautious?

Be specific about differences. Keep under 600 words."""

    return cortex_complete(session, prompt)


def ask_question(session, ticker: str, question: str,
                 form_type: str = "10-K") -> str:
    """Ask a custom question about a company's filing."""
    filings = get_filing_text(session, ticker, form_type, section="both", limit=1)

    if not filings:
        return f"No filings found for {ticker}"

    filing = filings[0]
    mda = filing.get("mda_text", "")[:20000]
    risk = filing.get("risk_factors_text", "")[:10000]

    prompt = f"""You are a financial analyst answering questions about {filing['company_name']}'s ({filing['ticker']}) 
{filing['form_type']} filing from {filing['filing_date']}.

MANAGEMENT'S DISCUSSION AND ANALYSIS:
{mda}

RISK FACTORS:
{risk}

QUESTION: {question}

Answer the question based ONLY on the filing text above. Be specific and cite 
details from the filing. If the answer is not in the filing, say so.
Keep your answer under 400 words."""

    return cortex_complete(session, prompt)


# ──────────────────────────────────────────────────────────────
# Interactive mode
# ──────────────────────────────────────────────────────────────
def interactive_mode(session, ticker: str):
    """Interactive Q&A session about a company's filings."""
    print(f"\n{'='*60}")
    print(f"  FinSage Document Agent — {ticker.upper()}")
    print(f"{'='*60}")
    print(f"  Commands:")
    print(f"    summary  — Executive summary of latest filing")
    print(f"    risks    — Deep risk analysis")
    print(f"    mda      — MD&A analysis")
    print(f"    compare  — Compare two most recent filings")
    print(f"    quit     — Exit")
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
            else:
                result = ask_question(session, ticker, user_input)

            print(f"\n{result}\n")
            print("-" * 60)

        except Exception as e:
            print(f"\nError: {e}\n")


# ──────────────────────────────────────────────────────────────
# Batch analysis — generate reports for all tickers
# ──────────────────────────────────────────────────────────────
def batch_analysis(session, tickers: list = None, output_dir: str = None) -> dict:
    """
    Run analysis on multiple tickers and save results.
    Used by the report generation pipeline.
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
        logger.info("Running analysis for %s", ticker)

        try:
            analysis = {
                "ticker": ticker,
                "timestamp": datetime.utcnow().isoformat(),
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
            logger.info("Analysis complete for %s", ticker)

        except Exception as e:
            logger.error("Analysis failed for %s: %s", ticker, e)
            results[ticker] = {"ticker": ticker, "error": str(e)}

    # Save results if output directory specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info("Results saved to %s", output_path)

    return results


# ──────────────────────────────────────────────────────────────
# CLI entrypoint
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinSage Document Reading Agent")
    parser.add_argument("--ticker", type=str, required=True,
                        help="Stock ticker (e.g. AAPL)")
    parser.add_argument("--mode", type=str,
                        choices=["summary", "risks", "mda", "compare", "interactive", "batch"],
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

        elif args.mode == "batch":
            tickers = [args.ticker] if args.ticker != "ALL" else None
            batch_analysis(session, tickers=tickers, output_dir=args.output_dir)

        else:
            interactive_mode(session, args.ticker)

    finally:
        session.close()
