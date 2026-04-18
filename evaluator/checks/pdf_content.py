"""
PDF Content Check
=================
Opens the generated PDF with pdfplumber and validates:

1. PDF is readable / text-extractable
2. Page count is within expected range (>= MIN_PAGES)
3. Required section headers are present
4. Ticker symbol appears in the document
5. No $0 financial values (data governance — catches $0 revenue, $0 price)
6. N/A saturation: too many "N/A" cells signals missing upstream data
7. Key figures cross-validation: current_price and latest_eps from data_summary
   must appear approximately in the PDF text
"""

import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MIN_PAGES = 10

# Section headers that must appear somewhere in the PDF (case-insensitive)
_REQUIRED_SECTIONS: list[str] = [
    "executive summary",
    "company overview",
    "risk",
    "investment",
]

# Maximum tolerated N/A count in financial metric tables before we flag it.
# A handful is fine (some optional fields); a flood means the data pull failed.
_NA_SATURATION_THRESHOLD = 20

# Regex for standalone $0 or $0.00 — these should never appear for price/revenue
_DOLLAR_ZERO_RE = re.compile(r"\$0(?:\.0+)?\b")

# Regex for extracting all dollar amounts from text (e.g. $185.00, $1.53)
_DOLLAR_AMOUNT_RE = re.compile(r"\$(\d{1,6}(?:\.\d{1,4})?)")


def _extract_pdf_text(pdf_path: str) -> Optional[str]:
    """Return full extracted text from all PDF pages, or None on failure."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed — skipping PDF content check")
        return None

    try:
        full_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text.append(text)
        return "\n".join(full_text)
    except Exception as e:
        logger.warning("Could not extract PDF text from %s: %s", pdf_path, e)
        return None


def _count_pages(pdf_path: str) -> Optional[int]:
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)
    except Exception:
        return None


def _approx_present(value: float, text_numbers: list[float], tolerance: float = 0.05) -> bool:
    """Return True if value appears within tolerance in the extracted text numbers."""
    if abs(value) < 0.01:
        return True
    for n in text_numbers:
        if abs(value) > 0 and abs(n - value) / abs(value) <= tolerance:
            return True
    return False


def check_pdf_content(artifacts: dict) -> tuple[float, list[str]]:
    """
    Args:
        artifacts: dict with 'pipeline_result' and 'chart_manifest'

    Returns:
        (score 0-100, list of issue strings)
    """
    issues: list[str] = []
    pipeline = artifacts.get("pipeline_result") or {}
    manifest = artifacts.get("chart_manifest") or []

    pdf_path = pipeline.get("pdf_path", "")
    ticker = pipeline.get("ticker", "")

    # ── Guard: no PDF path ────────────────────────────────────────────────
    if not pdf_path or not Path(pdf_path).exists():
        return 0.0, ["PDF not found — cannot run content check"]

    # ── Extract text ──────────────────────────────────────────────────────
    text = _extract_pdf_text(pdf_path)
    if text is None:
        # pdfplumber not installed or extraction failed — skip gracefully
        return 50.0, ["PDF text extraction unavailable — install pdfplumber for full check"]

    total_checks = 0
    passed_checks = 0

    # ── 1. Page count ─────────────────────────────────────────────────────
    total_checks += 1
    page_count = _count_pages(pdf_path)
    if page_count is None:
        issues.append("Could not determine PDF page count")
    elif page_count < MIN_PAGES:
        issues.append(
            f"PDF has only {page_count} page(s) — expected ≥ {MIN_PAGES}; "
            "report may be incomplete"
        )
    else:
        passed_checks += 1

    # ── 2. Required sections present ─────────────────────────────────────
    text_lower = text.lower()
    for section in _REQUIRED_SECTIONS:
        total_checks += 1
        if section in text_lower:
            passed_checks += 1
        else:
            issues.append(f"PDF missing expected section: '{section}'")

    # ── 3. Ticker appears in document ─────────────────────────────────────
    if ticker:
        total_checks += 1
        if ticker.upper() in text.upper():
            passed_checks += 1
        else:
            issues.append(f"Ticker '{ticker}' not found in PDF text")

    # ── 4. $0 financial values (data governance) ──────────────────────────
    total_checks += 1
    zero_matches = _DOLLAR_ZERO_RE.findall(text)
    if zero_matches:
        issues.append(
            f"PDF contains {len(zero_matches)} '$0' value(s) — "
            "likely indicates $0 revenue, price, or EPS from bad upstream data "
            f"(e.g. {zero_matches[:3]})"
        )
    else:
        passed_checks += 1

    # ── 5. N/A saturation ─────────────────────────────────────────────────
    total_checks += 1
    na_count = text.count("N/A")
    if na_count > _NA_SATURATION_THRESHOLD:
        issues.append(
            f"PDF contains {na_count} 'N/A' values (threshold {_NA_SATURATION_THRESHOLD}) — "
            "indicates widespread missing data from upstream pipeline"
        )
    else:
        passed_checks += 1

    # ── 6. Key figure cross-validation ────────────────────────────────────
    # Extract dollar amounts from PDF text and cross-check price and EPS
    charts_by_id = {c.get("chart_id"): c for c in manifest}
    text_dollar_values = [
        float(m) for m in _DOLLAR_AMOUNT_RE.findall(text)
        if _is_safe_float(m)
    ]

    for chart_id, field, label in (
        ("price_sma",  "current_price", "current price"),
        ("eps_trend",  "latest_eps",    "latest EPS"),
    ):
        ds = (charts_by_id.get(chart_id) or {}).get("data_summary") or {}
        value = ds.get(field)
        if value is None:
            continue
        try:
            fval = float(value)
        except (TypeError, ValueError):
            continue
        if fval <= 0:
            continue  # already caught by data_quality check

        total_checks += 1
        if _approx_present(fval, text_dollar_values):
            passed_checks += 1
        else:
            issues.append(
                f"PDF cross-validation: {label} {fval} from data_summary "
                "not found in PDF text — value may have been incorrectly rendered"
            )

    score = (passed_checks / total_checks * 100.0) if total_checks else 0.0
    logger.info(
        "PDF content: %d/%d checks passed, %d issues → %.1f",
        passed_checks, total_checks, len(issues), score,
    )
    return round(score, 1), issues


def _is_safe_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False
