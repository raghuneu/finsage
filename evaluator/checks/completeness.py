"""
Completeness Check
==================
Verifies that every required artifact and text field is present and non-empty
in the pipeline output directory.  No API calls — purely deterministic.
"""

import os
import logging
from pathlib import Path

from evaluator.rubric import (
    REQUIRED_CHART_IDS,
    REQUIRED_TEXT_FIELDS,
    ANALYSIS_MIN_WORDS,
    MIN_PDF_SIZE_BYTES,
    FALLBACK_SUBSTRINGS,
)

logger = logging.getLogger(__name__)


def _get_nested(obj: dict, dot_path: str):
    """Retrieve a value from a nested dict using dot notation."""
    keys = dot_path.split(".")
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _is_fallback(text: str) -> bool:
    lower = text.lower()
    return any(sub in lower for sub in FALLBACK_SUBSTRINGS)


def check_completeness(artifacts: dict) -> tuple[float, list[str]]:
    """
    Args:
        artifacts: dict with keys 'pipeline_result', 'chart_manifest', 'output_dir'

    Returns:
        (score 0-100, list of issue strings)
    """
    issues: list[str] = []
    total_checks = 0
    passed_checks = 0

    pipeline = artifacts.get("pipeline_result") or {}
    manifest = artifacts.get("chart_manifest") or []
    output_dir = Path(artifacts.get("output_dir", "."))

    # ── 1. Core JSON files loaded ──────────────────────────────────────────
    for key, label in (("pipeline_result", "pipeline_result.json"),
                       ("chart_manifest",  "chart_manifest.json")):
        total_checks += 1
        if artifacts.get(key) is not None:
            passed_checks += 1
        else:
            issues.append(f"Missing artifact: {label}")

    # ── 2. PDF file ────────────────────────────────────────────────────────
    total_checks += 1
    pdf_path = pipeline.get("pdf_path", "")
    if pdf_path and os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path)
        if size >= MIN_PDF_SIZE_BYTES:
            passed_checks += 1
        else:
            issues.append(
                f"PDF too small ({size:,} bytes < {MIN_PDF_SIZE_BYTES:,}) — "
                "likely incomplete render"
            )
    else:
        issues.append(f"PDF file not found: {pdf_path or '(path missing from pipeline_result)'}")

    # ── 3. All 8 chart IDs present in manifest ────────────────────────────
    manifest_ids = {c.get("chart_id") for c in manifest}
    for chart_id in REQUIRED_CHART_IDS:
        total_checks += 1
        if chart_id in manifest_ids:
            passed_checks += 1
        else:
            issues.append(f"Chart missing from manifest: {chart_id}")

    # ── 4. Chart PNG files exist ──────────────────────────────────────────
    charts_by_id = {c.get("chart_id"): c for c in manifest}
    for chart_id in REQUIRED_CHART_IDS:
        total_checks += 1
        chart = charts_by_id.get(chart_id, {})
        file_path = chart.get("file_path", "")
        if file_path and os.path.exists(file_path):
            passed_checks += 1
        else:
            issues.append(f"Chart PNG missing on disk: {chart_id} ({file_path})")

    # ── 5. Per-chart analysis texts ────────────────────────────────────────
    chart_analyses = {
        a.get("chart_id"): a.get("analysis_text", "")
        for a in (pipeline.get("analysis", {}).get("chart_analyses") or [])
    }
    for chart_id in REQUIRED_CHART_IDS:
        total_checks += 1
        text = chart_analyses.get(chart_id, "")
        if not text:
            issues.append(f"Analysis text empty or missing: {chart_id}")
        elif _is_fallback(text):
            issues.append(f"Analysis text is guardrail/fallback placeholder: {chart_id}")
        elif len(text.split()) < ANALYSIS_MIN_WORDS:
            issues.append(
                f"Analysis text too short ({len(text.split())} words): {chart_id}"
            )
        else:
            passed_checks += 1

    # ── 6. Section-level text fields ─────────────────────────────────────
    for dot_path, min_words in REQUIRED_TEXT_FIELDS.items():
        total_checks += 1
        text = _get_nested(pipeline, dot_path) or ""
        if not text:
            issues.append(f"Text field empty: {dot_path}")
        elif _is_fallback(text):
            issues.append(f"Text field is fallback placeholder: {dot_path}")
        elif len(text.split()) < min_words:
            issues.append(
                f"Text field too short ({len(text.split())} words, need {min_words}): {dot_path}"
            )
        else:
            passed_checks += 1

    score = (passed_checks / total_checks * 100.0) if total_checks else 0.0
    logger.info(
        "Completeness: %d/%d checks passed → %.1f",
        passed_checks, total_checks, score,
    )
    return round(score, 1), issues
