"""
S3 helper utilities for FinSage SEC filing storage.

Bucket layout:
    filings/raw/{ticker}/{form_type}/{filing_id}.html
    filings/extracted/{ticker}/{form_type}/{filing_id}_mda.txt
    filings/extracted/{ticker}/{form_type}/{filing_id}_risk.txt
    filings/metadata/download_manifest.json

Environment variables required:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
    (or use an IAM role / AWS profile)
    FINSAGE_S3_BUCKET  — bucket name (default: finsage-sec-filings)
"""

import os
import json
import logging
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("FINSAGE_S3_BUCKET", "finsage-sec-filings")


def _client():
    """Return a reusable S3 client."""
    return boto3.client("s3", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))


# ──────────────────────────────────────────────────────────────
# Key builders
# ──────────────────────────────────────────────────────────────
def raw_key(ticker: str, form_type: str, filing_id: str, ext: str = "html") -> str:
    """Build S3 key for a raw filing document."""
    return f"filings/raw/{ticker.upper()}/{form_type}/{filing_id}.{ext}"


def extracted_key(ticker: str, form_type: str, filing_id: str, section: str) -> str:
    """Build S3 key for extracted text (section = 'mda' or 'risk')."""
    return f"filings/extracted/{ticker.upper()}/{form_type}/{filing_id}_{section}.txt"


# ──────────────────────────────────────────────────────────────
# Upload helpers
# ──────────────────────────────────────────────────────────────
def upload_filing(local_path: str, ticker: str, form_type: str,
                  filing_id: str, ext: str = "html") -> dict:
    """
    Upload a raw filing document to S3.
    Returns dict with s3_key and file_size_bytes.
    """
    s3 = _client()
    key = raw_key(ticker, form_type, filing_id, ext)
    file_size = os.path.getsize(local_path)

    try:
        s3.upload_file(
            Filename=local_path,
            Bucket=BUCKET_NAME,
            Key=key,
            ExtraArgs={
                "Metadata": {
                    "ticker": ticker.upper(),
                    "form_type": form_type,
                    "filing_id": filing_id,
                    "uploaded_at": datetime.utcnow().isoformat(),
                },
                "ContentType": "text/html" if ext == "html" else "application/pdf",
            },
        )
        logger.info("Uploaded %s → s3://%s/%s (%d bytes)", local_path, BUCKET_NAME, key, file_size)
        return {"s3_key": key, "file_size_bytes": file_size}
    except ClientError as e:
        logger.error("S3 upload failed for %s: %s", key, e)
        raise


def upload_extracted_text(text: str, ticker: str, form_type: str,
                          filing_id: str, section: str) -> str:
    """
    Upload extracted section text to S3.
    section: 'mda' or 'risk'
    Returns the S3 key.
    """
    s3 = _client()
    key = extracted_key(ticker, form_type, filing_id, section)

    try:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=text.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
            Metadata={
                "ticker": ticker.upper(),
                "section": section,
                "word_count": str(len(text.split())),
                "extracted_at": datetime.utcnow().isoformat(),
            },
        )
        logger.info("Uploaded extracted %s text → s3://%s/%s", section, BUCKET_NAME, key)
        return key
    except ClientError as e:
        logger.error("S3 upload failed for extracted text %s: %s", key, e)
        raise


# ──────────────────────────────────────────────────────────────
# Download / read helpers
# ──────────────────────────────────────────────────────────────
def download_filing(s3_key: str, local_path: str) -> str:
    """Download a raw filing from S3 to a local path."""
    s3 = _client()
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    s3.download_file(BUCKET_NAME, s3_key, local_path)
    logger.info("Downloaded s3://%s/%s → %s", BUCKET_NAME, s3_key, local_path)
    return local_path


def read_extracted_text(s3_key: str) -> str:
    """Read extracted text content directly from S3."""
    s3 = _client()
    resp = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
    return resp["Body"].read().decode("utf-8")


# ──────────────────────────────────────────────────────────────
# Listing helpers
# ──────────────────────────────────────────────────────────────
def list_filings(ticker: str = None, form_type: str = None,
                 prefix: str = "filings/raw/") -> list:
    """
    List filing keys in S3 under the given prefix.
    Optionally filter by ticker and/or form_type.
    """
    s3 = _client()

    if ticker:
        prefix = f"filings/raw/{ticker.upper()}/"
        if form_type:
            prefix = f"filings/raw/{ticker.upper()}/{form_type}/"

    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith("/"):
                continue
            keys.append(obj["Key"])

    return keys


def filing_exists(ticker: str, form_type: str, filing_id: str, ext: str = "html") -> bool:
    """Check if a specific filing already exists in S3."""
    s3 = _client()
    key = raw_key(ticker, form_type, filing_id, ext)
    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=key)
        return True
    except ClientError:
        return False


# ──────────────────────────────────────────────────────────────
# Manifest helpers (for tracking download batches)
# ──────────────────────────────────────────────────────────────
def save_download_manifest(manifest: dict):
    """Save a download manifest JSON to S3 metadata folder."""
    s3 = _client()
    key = f"filings/metadata/manifest_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps(manifest, indent=2, default=str).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Saved download manifest → s3://%s/%s", BUCKET_NAME, key)
    return key
