"""
SEC Filing Text Extractor for FinSage.

Extracts key sections from 10-K and 10-Q HTML filings:
    - MD&A (Management's Discussion and Analysis)
    - Risk Factors

Downloads raw HTML from S3, parses sections, uploads extracted text
back to S3, and updates Snowflake metadata.

Usage:
    python -m sec_filings.text_extractor
    python -m sec_filings.text_extractor --ticker AAPL --form-type 10-K
"""

import os
import re
import sys
import logging
import argparse
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from snowflake_connection import get_session
from sec_filings.s3_utils import (
    read_extracted_text,
    upload_extracted_text,
    download_filing,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# HTML Cleaning
# ──────────────────────────────────────────────────────────────
def clean_html_to_text(html_content: str) -> str:
    """
    Convert raw HTML to clean readable text.
    Removes tags, scripts, styles, and normalizes whitespace.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for tag in soup(["script", "style", "meta", "link", "header", "footer"]):
        tag.decompose()

    # Get text
    text = soup.get_text(separator="\n")

    # Normalize whitespace
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)

    text = "\n".join(lines)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


# ──────────────────────────────────────────────────────────────
# Section Extraction — Pattern Matching
# ──────────────────────────────────────────────────────────────

# 10-K item patterns (annual filings)
SECTION_PATTERNS_10K = {
    "mda": {
        "start": [
            r"item\s*7[\.\s]*[-–—]?\s*management.s\s+discussion\s+and\s+analysis",
            r"item\s*7[\.\s]*management.s\s+discussion",
            r"item\s*7[\.\s]*md\s*&\s*a",
            r"management.s\s+discussion\s+and\s+analysis\s+of\s+financial\s+condition",
        ],
        "end": [
            r"item\s*7a[\.\s]*[-–—]?\s*quantitative\s+and\s+qualitative",
            r"item\s*8[\.\s]*[-–—]?\s*financial\s+statements",
            r"item\s*8[\.\s]",
        ],
    },
    "risk": {
        "start": [
            r"item\s*1a[\.\s]*[-–—]?\s*risk\s+factors",
            r"item\s*1a[\.\s]*risk\s+factors",
            r"risk\s+factors",
        ],
        "end": [
            r"item\s*1b[\.\s]*[-–—]?\s*unresolved\s+staff\s+comments",
            r"item\s*1c[\.\s]*[-–—]?\s*cybersecurity",
            r"item\s*2[\.\s]*[-–—]?\s*properties",
            r"item\s*2[\.\s]",
        ],
    },
}

# 10-Q item patterns (quarterly filings)
SECTION_PATTERNS_10Q = {
    "mda": {
        "start": [
            r"item\s*2[\.\s]*[-–—]?\s*management.s\s+discussion\s+and\s+analysis",
            r"item\s*2[\.\s]*management.s\s+discussion",
            r"management.s\s+discussion\s+and\s+analysis\s+of\s+financial\s+condition",
        ],
        "end": [
            r"item\s*3[\.\s]*[-–—]?\s*quantitative\s+and\s+qualitative",
            r"item\s*4[\.\s]*[-–—]?\s*controls\s+and\s+procedures",
            r"item\s*3[\.\s]",
        ],
    },
    "risk": {
        "start": [
            r"item\s*1a[\.\s]*[-–—]?\s*risk\s+factors",
            r"risk\s+factors",
        ],
        "end": [
            r"item\s*2[\.\s]*[-–—]?\s*unregistered\s+sales",
            r"item\s*3[\.\s]*[-–—]?\s*defaults",
            r"item\s*2[\.\s]",
        ],
    },
}


def extract_section(text: str, section: str, form_type: str) -> str:
    """
    Extract a specific section from the filing text using regex patterns.

    Args:
        text: Full cleaned text of the filing
        section: 'mda' or 'risk'
        form_type: '10-K' or '10-Q'

    Returns:
        Extracted section text, or empty string if not found.
    """
    if form_type == "10-K":
        patterns = SECTION_PATTERNS_10K.get(section, {})
    else:
        patterns = SECTION_PATTERNS_10Q.get(section, {})

    start_patterns = patterns.get("start", [])
    end_patterns = patterns.get("end", [])

    text_lower = text.lower()

    # Find the START of the section
    start_pos = None
    for pattern in start_patterns:
        match = re.search(pattern, text_lower)
        if match:
            start_pos = match.start()
            logger.debug("Section '%s' start matched at position %d with pattern: %s",
                         section, start_pos, pattern)
            break

    if start_pos is None:
        logger.warning("Could not find start of section '%s' in %s filing", section, form_type)
        return ""

    # Find the END of the section (search after start position)
    end_pos = None
    search_from = start_pos + 100  # skip past the header itself
    for pattern in end_patterns:
        match = re.search(pattern, text_lower[search_from:])
        if match:
            end_pos = search_from + match.start()
            logger.debug("Section '%s' end matched at position %d with pattern: %s",
                         section, end_pos, pattern)
            break

    if end_pos is None:
        # If no end marker found, take next 50,000 characters as a fallback
        end_pos = min(start_pos + 50000, len(text))
        logger.warning("Could not find end of section '%s', using fallback length", section)

    extracted = text[start_pos:end_pos].strip()

    # Basic validation: section should have meaningful content
    if len(extracted) < 200:
        logger.warning("Extracted section '%s' is suspiciously short (%d chars)", section, len(extracted))
        return ""

    logger.info("Extracted section '%s': %d chars, ~%d words",
                section, len(extracted), len(extracted.split()))

    return extracted


# ──────────────────────────────────────────────────────────────
# Quality scoring for extracted text
# ──────────────────────────────────────────────────────────────
def calculate_extraction_quality(mda_text: str, risk_text: str) -> float:
    """
    Score the quality of extraction on a 0-100 scale.

    Deductions:
        - No MD&A extracted: -40
        - No Risk Factors extracted: -30
        - MD&A too short (< 1000 words): -15
        - Risk Factors too short (< 500 words): -10
        - Either section suspiciously long (> 100k words): -5
    """
    score = 100.0

    mda_words = len(mda_text.split()) if mda_text else 0
    risk_words = len(risk_text.split()) if risk_text else 0

    if mda_words == 0:
        score -= 40
    elif mda_words < 1000:
        score -= 15

    if risk_words == 0:
        score -= 30
    elif risk_words < 500:
        score -= 10

    if mda_words > 100000:
        score -= 5
    if risk_words > 100000:
        score -= 5

    return max(score, 0.0)


# ──────────────────────────────────────────────────────────────
# Snowflake update
# ──────────────────────────────────────────────────────────────
def update_extraction_metadata(session, filing_id: str, ticker: str,
                                mda_text: str, risk_text: str,
                                s3_mda_key: str, s3_risk_key: str,
                                quality_score: float,
                                error: str = None):
    """Update the filing document record with extraction results."""

    mda_word_count = len(mda_text.split()) if mda_text else 0
    risk_word_count = len(risk_text.split()) if risk_text else 0
    status = "extracted" if (mda_text or risk_text) else "failed"

    # Escape single quotes in text for SQL
    mda_escaped = mda_text.replace("'", "''") if mda_text else ""
    risk_escaped = risk_text.replace("'", "''") if risk_text else ""
    error_escaped = error.replace("'", "''") if error else ""

    # Truncate text if extremely long (Snowflake TEXT max = 16MB, but keep reasonable)
    max_text_len = 2_000_000  # 2M chars
    if len(mda_escaped) > max_text_len:
        mda_escaped = mda_escaped[:max_text_len]
        logger.warning("Truncated MD&A text for %s/%s to %d chars", ticker, filing_id, max_text_len)
    if len(risk_escaped) > max_text_len:
        risk_escaped = risk_escaped[:max_text_len]

    update_sql = f"""
    UPDATE RAW.RAW_SEC_FILING_DOCUMENTS
    SET
        MDA_TEXT = '{mda_escaped}',
        RISK_FACTORS_TEXT = '{risk_escaped}',
        MDA_WORD_COUNT = {mda_word_count},
        RISK_WORD_COUNT = {risk_word_count},
        S3_MDA_KEY = '{s3_mda_key or ""}',
        S3_RISK_KEY = '{s3_risk_key or ""}',
        EXTRACTION_STATUS = '{status}',
        EXTRACTION_ERROR = '{error_escaped}',
        DATA_QUALITY_SCORE = {quality_score},
        UPDATED_AT = CURRENT_TIMESTAMP()
    WHERE FILING_ID = '{filing_id}' AND TICKER = '{ticker}'
    """

    session.sql(update_sql).collect()
    logger.info("Updated extraction metadata for %s/%s (status=%s, quality=%.0f)",
                ticker, filing_id, status, quality_score)


# ──────────────────────────────────────────────────────────────
# Main extraction pipeline
# ──────────────────────────────────────────────────────────────
def extract_filing(session, filing_id: str, ticker: str, form_type: str,
                    s3_raw_key: str) -> dict:
    """
    Full extraction pipeline for a single filing:
        1. Download raw HTML from S3
        2. Clean HTML → plain text
        3. Extract MD&A section
        4. Extract Risk Factors section
        5. Upload extracted text to S3
        6. Store extracted text + metadata in Snowflake

    Returns summary dict.
    """
    import tempfile

    logger.info("Extracting sections from %s %s filing %s", ticker, form_type, filing_id)

    try:
        # Step 1: Download raw filing from S3
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = os.path.join(temp_dir, f"{filing_id}.html")
            download_filing(s3_raw_key, local_path)

            with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
                html_content = f.read()

        # Step 2: Clean HTML to text
        clean_text = clean_html_to_text(html_content)
        logger.info("Cleaned text: %d chars from HTML", len(clean_text))

        # Step 3: Extract MD&A
        mda_text = extract_section(clean_text, "mda", form_type)

        # Step 4: Extract Risk Factors
        risk_text = extract_section(clean_text, "risk", form_type)

        # Step 5: Upload extracted text to S3
        s3_mda_key = None
        s3_risk_key = None

        if mda_text:
            s3_mda_key = upload_extracted_text(mda_text, ticker, form_type, filing_id, "mda")

        if risk_text:
            s3_risk_key = upload_extracted_text(risk_text, ticker, form_type, filing_id, "risk")

        # Step 6: Quality score + update Snowflake
        quality = calculate_extraction_quality(mda_text, risk_text)

        update_extraction_metadata(
            session, filing_id, ticker,
            mda_text, risk_text,
            s3_mda_key, s3_risk_key,
            quality
        )

        return {
            "filing_id": filing_id,
            "ticker": ticker,
            "status": "extracted",
            "mda_words": len(mda_text.split()) if mda_text else 0,
            "risk_words": len(risk_text.split()) if risk_text else 0,
            "quality_score": quality,
        }

    except Exception as e:
        logger.error("Extraction failed for %s/%s: %s", ticker, filing_id, e)

        try:
            update_extraction_metadata(
                session, filing_id, ticker,
                "", "", None, None,
                quality_score=0.0,
                error=str(e)
            )
        except Exception:
            pass

        return {
            "filing_id": filing_id,
            "ticker": ticker,
            "status": "failed",
            "error": str(e),
        }


def extract_pending_filings(ticker: str = None, form_type: str = None):
    """
    Find all downloaded-but-not-extracted filings in Snowflake and extract them.
    """
    session = get_session()

    # Build query to find pending filings
    where_clauses = ["DOWNLOAD_STATUS = 'downloaded'", "EXTRACTION_STATUS = 'pending'"]
    if ticker:
        where_clauses.append(f"TICKER = '{ticker.upper()}'")
    if form_type:
        where_clauses.append(f"FORM_TYPE = '{form_type}'")

    query = f"""
    SELECT FILING_ID, TICKER, FORM_TYPE, S3_RAW_KEY
    FROM RAW.RAW_SEC_FILING_DOCUMENTS
    WHERE {' AND '.join(where_clauses)}
    ORDER BY FILING_DATE DESC
    """

    rows = session.sql(query).collect()

    if not rows:
        print("No pending filings found for extraction.")
        session.close()
        return []

    print(f"Found {len(rows)} filings pending extraction\n")

    results = []
    for row in rows:
        result = extract_filing(
            session,
            row["FILING_ID"],
            row["TICKER"],
            row["FORM_TYPE"],
            row["S3_RAW_KEY"],
        )
        results.append(result)

    # Print summary
    extracted = sum(1 for r in results if r["status"] == "extracted")
    failed = sum(1 for r in results if r["status"] == "failed")

    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    for r in results:
        if r["status"] == "extracted":
            print(f"  ✅ {r['ticker']} {r['filing_id']}: "
                  f"MD&A={r['mda_words']} words, "
                  f"Risk={r['risk_words']} words, "
                  f"Quality={r['quality_score']:.0f}")
        else:
            print(f"  ❌ {r['ticker']} {r['filing_id']}: {r.get('error', 'unknown')}")
    print(f"\n  Total: {extracted} extracted, {failed} failed")
    print("=" * 60)

    session.close()
    return results


# ──────────────────────────────────────────────────────────────
# CLI entrypoint
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract text from SEC filings")
    parser.add_argument("--ticker", type=str, help="Filter by ticker (e.g. AAPL)")
    parser.add_argument("--form-type", type=str, choices=["10-K", "10-Q"],
                        help="Filter by filing type")
    args = parser.parse_args()

    extract_pending_filings(ticker=args.ticker, form_type=args.form_type)
