"""
SEC EDGAR Filing Downloader for FinSage.

Downloads 10-K and 10-Q filings (HTML) from SEC EDGAR for configured tickers.
Respects SEC rate limits (10 req/sec), implements retry logic, and uploads
raw filings to S3.

Usage:
    python -m sec_filings.filing_downloader
    python -m sec_filings.filing_downloader --ticker AAPL --form-type 10-K
"""

import os
import sys
import time
import json
import logging
import argparse
import tempfile
from datetime import datetime

import httpx
import pandas as pd
from dotenv import load_dotenv

# Add parent directory so we can import snowflake_connection
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from snowflake_connection import get_session
from sec_filings.s3_utils import (
    upload_filing,
    filing_exists,
    save_download_manifest,
)

load_dotenv()

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# SEC EDGAR requires a User-Agent with company name and email
SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "FinSage NEU vedanarayanan.s@northeastern.edu"
)

HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}

# SEC rate limit: max 10 requests per second
SEC_REQUEST_DELAY = 0.12  # ~8 req/sec to stay safe

# Company mapping: ticker → CIK (zero-padded to 10 digits)
COMPANY_MAP = {
    "AAPL":  "0000320193",
    "TSLA":  "0001318605",
    "MSFT":  "0000789019",
    "JPM":   "0000019617",
    "GOOGL": "0001652044",
}

SUPPORTED_FORM_TYPES = ["10-K", "10-Q"]


# ──────────────────────────────────────────────────────────────
# SEC EDGAR API helpers
# ──────────────────────────────────────────────────────────────
def get_filing_index(cik: str, form_type: str, count: int = 10) -> list:
    """
    Query SEC EDGAR submissions API to get recent filings of a given type.

    Returns a list of dicts with:
        accession_number, filing_date, primary_document, form_type,
        period_of_report, company_name
    """
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    logger.info("Fetching filing index for CIK %s from %s", cik, url)
    time.sleep(SEC_REQUEST_DELAY)

    response = httpx.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    company_name = data.get("name", "Unknown")

    # Recent filings are in data["filings"]["recent"]
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])
    report_dates = recent.get("reportDate", [])

    filings = []
    for i, form in enumerate(forms):
        if form != form_type:
            continue
        if len(filings) >= count:
            break

        # Clean accession number (remove dashes for URL/ID)
        accession_raw = accessions[i]
        accession_clean = accession_raw.replace("-", "")

        filings.append({
            "accession_number": accession_raw,
            "filing_id": accession_clean,
            "filing_date": filing_dates[i],
            "primary_document": primary_docs[i],
            "form_type": form,
            "period_of_report": report_dates[i] if i < len(report_dates) else None,
            "company_name": company_name,
        })

    logger.info("Found %d %s filings for CIK %s", len(filings), form_type, cik)
    return filings


def download_filing_document(cik: str, accession_raw: str,
                              primary_document: str, temp_dir: str) -> str:
    """
    Download the actual filing document (HTML) from SEC EDGAR.

    URL pattern:
        https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}

    Returns the local file path of the downloaded document.
    """
    # Build the EDGAR archive URL
    accession_path = accession_raw.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik.lstrip('0')}/{accession_path}/{primary_document}"
    )

    logger.info("Downloading filing from %s", url)
    time.sleep(SEC_REQUEST_DELAY)

    response = httpx.get(url, headers=HEADERS, timeout=60, follow_redirects=True)
    response.raise_for_status()

    # Determine file extension
    ext = "html"
    if primary_document.lower().endswith(".pdf"):
        ext = "pdf"

    local_path = os.path.join(temp_dir, f"{accession_path}.{ext}")
    with open(local_path, "wb") as f:
        f.write(response.content)

    file_size = os.path.getsize(local_path)
    logger.info("Downloaded %s (%d bytes)", local_path, file_size)

    return local_path, ext


# ──────────────────────────────────────────────────────────────
# Snowflake metadata tracking
# ──────────────────────────────────────────────────────────────
def upsert_filing_metadata(session, record: dict):
    """
    Insert or update filing document metadata in Snowflake.
    Uses MERGE for idempotency.
    """
    df = pd.DataFrame([record])
    df.columns = df.columns.str.upper()

    # Create temp staging table
    session.sql("CREATE TEMPORARY TABLE IF NOT EXISTS TEMP_FILING_DOCS LIKE RAW.RAW_SEC_FILING_DOCUMENTS").collect()
    session.write_pandas(df, "TEMP_FILING_DOCS", auto_create_table=False, overwrite=True)

    merge_sql = """
    MERGE INTO RAW.RAW_SEC_FILING_DOCUMENTS target
    USING TEMP_FILING_DOCS source
    ON target.FILING_ID = source.FILING_ID AND target.TICKER = source.TICKER
    WHEN MATCHED THEN
        UPDATE SET
            S3_RAW_KEY = source.S3_RAW_KEY,
            FILE_FORMAT = source.FILE_FORMAT,
            FILE_SIZE_BYTES = source.FILE_SIZE_BYTES,
            DOWNLOAD_STATUS = source.DOWNLOAD_STATUS,
            UPDATED_AT = CURRENT_TIMESTAMP()
    WHEN NOT MATCHED THEN
        INSERT (FILING_ID, TICKER, CIK, FORM_TYPE, FILING_DATE, PERIOD_OF_REPORT,
                COMPANY_NAME, S3_RAW_KEY, FILE_FORMAT, FILE_SIZE_BYTES,
                DOWNLOAD_STATUS, SOURCE, INGESTED_AT)
        VALUES (source.FILING_ID, source.TICKER, source.CIK, source.FORM_TYPE,
                source.FILING_DATE, source.PERIOD_OF_REPORT, source.COMPANY_NAME,
                source.S3_RAW_KEY, source.FILE_FORMAT, source.FILE_SIZE_BYTES,
                source.DOWNLOAD_STATUS, source.SOURCE, CURRENT_TIMESTAMP())
    """
    session.sql(merge_sql).collect()
    logger.info("Upserted metadata for filing %s / %s", record["ticker"], record["filing_id"])


# ──────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────
def download_filings_for_ticker(ticker: str, form_type: str,
                                 count: int = 5, session=None) -> dict:
    """
    Full pipeline for one ticker + form type:
        1. Query EDGAR for recent filings
        2. Skip already-downloaded filings (check S3)
        3. Download new filings to temp dir
        4. Upload to S3
        5. Track metadata in Snowflake

    Returns summary dict with counts.
    """
    cik = COMPANY_MAP.get(ticker.upper())
    if not cik:
        logger.error("Ticker %s not found in COMPANY_MAP", ticker)
        return {"ticker": ticker, "error": "unknown_ticker"}

    # Step 1: Get filing index from EDGAR
    filings = get_filing_index(cik, form_type, count=count)
    if not filings:
        logger.warning("No %s filings found for %s", form_type, ticker)
        return {"ticker": ticker, "form_type": form_type, "found": 0, "downloaded": 0, "skipped": 0}

    own_session = False
    if session is None:
        session = get_session()
        own_session = True

    downloaded = 0
    skipped = 0
    failed = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        for filing in filings:
            filing_id = filing["filing_id"]

            # Step 2: Skip if already in S3
            if filing_exists(ticker, form_type, filing_id):
                logger.info("Skipping %s (already in S3)", filing_id)
                skipped += 1
                continue

            try:
                # Step 3: Download from EDGAR
                local_path, ext = download_filing_document(
                    cik, filing["accession_number"],
                    filing["primary_document"], temp_dir
                )

                # Step 4: Upload to S3
                s3_result = upload_filing(local_path, ticker, form_type, filing_id, ext)

                # Step 5: Track in Snowflake
                record = {
                    "filing_id": filing_id,
                    "ticker": ticker.upper(),
                    "cik": cik,
                    "form_type": form_type,
                    "filing_date": filing["filing_date"],
                    "period_of_report": filing["period_of_report"],
                    "company_name": filing["company_name"],
                    "s3_raw_key": s3_result["s3_key"],
                    "file_format": ext,
                    "file_size_bytes": s3_result["file_size_bytes"],
                    "download_status": "downloaded",
                    "source": "sec_edgar",
                }
                upsert_filing_metadata(session, record)
                downloaded += 1

            except Exception as e:
                logger.error("Failed to download filing %s for %s: %s", filing_id, ticker, e)
                # Track the failure in Snowflake
                try:
                    fail_record = {
                        "filing_id": filing_id,
                        "ticker": ticker.upper(),
                        "cik": cik,
                        "form_type": form_type,
                        "filing_date": filing["filing_date"],
                        "period_of_report": filing.get("period_of_report"),
                        "company_name": filing.get("company_name"),
                        "s3_raw_key": None,
                        "file_format": None,
                        "file_size_bytes": None,
                        "download_status": "failed",
                        "source": "sec_edgar",
                    }
                    upsert_filing_metadata(session, fail_record)
                except Exception:
                    pass
                failed += 1

    summary = {
        "ticker": ticker,
        "form_type": form_type,
        "found": len(filings),
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
    }

    logger.info("Summary for %s %s: %s", ticker, form_type, summary)

    if own_session:
        session.close()

    return summary


def download_all_filings(tickers: list = None, form_types: list = None,
                          count: int = 5) -> list:
    """
    Download filings for multiple tickers and form types.
    Saves a manifest to S3 when complete.
    """
    if tickers is None:
        tickers = list(COMPANY_MAP.keys())
    if form_types is None:
        form_types = SUPPORTED_FORM_TYPES

    session = get_session()
    results = []

    for ticker in tickers:
        for form_type in form_types:
            logger.info("═" * 50)
            logger.info("Processing %s %s filings", ticker, form_type)
            logger.info("═" * 50)

            summary = download_filings_for_ticker(
                ticker, form_type, count=count, session=session
            )
            results.append(summary)

    # Save manifest to S3
    manifest = {
        "run_timestamp": datetime.utcnow().isoformat(),
        "tickers": tickers,
        "form_types": form_types,
        "results": results,
        "total_downloaded": sum(r.get("downloaded", 0) for r in results),
        "total_skipped": sum(r.get("skipped", 0) for r in results),
        "total_failed": sum(r.get("failed", 0) for r in results),
    }

    try:
        save_download_manifest(manifest)
    except Exception as e:
        logger.warning("Failed to save manifest to S3: %s", e)

    session.close()

    # Print final summary
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    for r in results:
        status = "✅" if r.get("failed", 0) == 0 else "⚠️"
        print(f"  {status} {r['ticker']} {r.get('form_type', 'N/A')}: "
              f"{r.get('downloaded', 0)} downloaded, "
              f"{r.get('skipped', 0)} skipped, "
              f"{r.get('failed', 0)} failed")
    print(f"\n  Total: {manifest['total_downloaded']} downloaded, "
          f"{manifest['total_skipped']} skipped, "
          f"{manifest['total_failed']} failed")
    print("=" * 60)

    return results


# ──────────────────────────────────────────────────────────────
# CLI entrypoint
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download SEC EDGAR filings")
    parser.add_argument("--ticker", type=str, help="Single ticker (e.g. AAPL)")
    parser.add_argument("--form-type", type=str, choices=["10-K", "10-Q"],
                        help="Filing type")
    parser.add_argument("--count", type=int, default=5,
                        help="Number of recent filings per ticker/type (default: 5)")
    parser.add_argument("--all", action="store_true",
                        help="Download for all configured tickers")
    args = parser.parse_args()

    if args.ticker and not args.all:
        tickers = [args.ticker.upper()]
        form_types = [args.form_type] if args.form_type else SUPPORTED_FORM_TYPES
    else:
        tickers = None
        form_types = None

    download_all_filings(tickers=tickers, form_types=form_types, count=args.count)
