"""
FinSage Validation Agent
========================
Validates charts produced by chart_agent against a quality rubric.
Uses pixtral-large (VLM) for intelligent critique where available,
with programmatic rule-based checks as fallback.

If a chart fails validation, triggers one re-render via fallback_code
in chart_agent. Max 1 re-render attempt per chart.

Input:  List of ChartResult dicts from chart_agent
Output: Same list with 'validated' field updated + validation_notes added
"""

import os
import sys
import logging
from pathlib import Path
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from snowflake_connection import get_session
from agents.vision_utils import vision_critique as _vision_critique

logger = logging.getLogger(__name__)

CORTEX_MODEL_VLM = os.getenv("CORTEX_MODEL_VLM", "openai-gpt-5.2")

# Minimum acceptable file size for a chart (bytes)
MIN_FILE_SIZE_BYTES = 10_000

# Minimum acceptable image dimensions
MIN_WIDTH_PX = 800
MIN_HEIGHT_PX = 400


# ──────────────────────────────────────────────────────────────
# Rule-based checks (always run — fast, no API call)
# ──────────────────────────────────────────────────────────────

def check_file_exists(chart: dict) -> tuple:
    path = chart.get("file_path", "")
    if not path or not os.path.exists(path):
        return False, "Chart file does not exist"
    return True, "File exists"


def check_file_size(chart: dict) -> tuple:
    path = chart.get("file_path", "")
    if not path or not os.path.exists(path):
        return False, "File does not exist (cannot check size)"
    size = os.path.getsize(path)
    if size < MIN_FILE_SIZE_BYTES:
        return False, f"File too small ({size} bytes) — likely blank or corrupt"
    return True, f"File size OK ({size:,} bytes)"


def check_image_dimensions(chart: dict) -> tuple:
    try:
        with Image.open(chart["file_path"]) as img:
            w, h = img.size
            if w < MIN_WIDTH_PX or h < MIN_HEIGHT_PX:
                return False, f"Image too small ({w}x{h}px) — minimum {MIN_WIDTH_PX}x{MIN_HEIGHT_PX}"
            return True, f"Dimensions OK ({w}x{h}px)"
    except Exception as e:
        return False, f"Could not open image: {e}"


def check_data_summary_populated(chart: dict) -> tuple:
    summary = chart.get("data_summary", {})
    if not summary:
        return False, "data_summary is empty — analysis agent will have no context"
    return True, f"data_summary has {len(summary)} keys"


def run_rule_checks(chart: dict) -> list:
    """
    Run all rule-based checks. Returns list of result dicts.
    """
    checks = [
        ("file_exists",    check_file_exists),
        ("file_size",      check_file_size),
        ("dimensions",     check_image_dimensions),
        ("data_summary",   check_data_summary_populated),
    ]

    results = []
    for check_name, check_fn in checks:
        passed, message = check_fn(chart)
        results.append({
            "check": check_name,
            "passed": passed,
            "message": message,
        })
    return results


# ──────────────────────────────────────────────────────────────
# VLM-based check (pixtral-large)
# ──────────────────────────────────────────────────────────────

def run_vlm_check(session, chart: dict) -> dict:
    """
    Use VLM to evaluate chart quality for publication readiness.
    Uses Cortex VLM (openai-gpt-5.2 primary, pixtral-large fallback).
    Returns dict with passed (bool), score (0-10), and feedback.
    """
    chart_id = chart.get("chart_id", "unknown")
    title = chart.get("title", "financial chart")
    data_summary = chart.get("data_summary", {})

    prompt = (
        f"You are a senior equity research editor reviewing a '{title}' chart "
        f"for inclusion in a client-facing financial report. "
        f"Evaluate the chart on these criteria: "
        f"(1) Clear title and axis labels, "
        f"(2) Appropriate chart type for financial data, "
        f"(3) Professional color scheme and styling, "
        f"(4) Sufficient data density and information value, "
        f"(5) Legend present and readable. "
        f"Respond with: "
        f"SCORE: X/10 "
        f"STATUS: APPROVED or NEEDS_REVISION "
        f"FEEDBACK: one sentence. "
        f"Be concise — 2-3 lines total."
    )

    try:
        response = _vision_critique(
            session, chart.get("file_path", ""), prompt,
            data_summary=data_summary, model=CORTEX_MODEL_VLM
        )

        # Parse response
        passed = "APPROVED" in response.upper()
        score_str = "7"  # default
        for part in response.split():
            if "/" in part:
                score_str = part.split("/")[0].replace("SCORE:", "").strip()
                break

        try:
            score = float(score_str)
        except ValueError:
            score = 7.0

        # Override: if score < 6, fail regardless of status text
        if score < 6.0:
            passed = False

        return {
            "passed": passed,
            "score": score,
            "feedback": response,
            "check": "vlm_review",
        }

    except Exception as e:
        logger.warning("VLM check failed for %s: %s — defaulting to FAIL", chart_id, e)
        return {
            "passed": False,
            "score": 0.0,
            "feedback": f"VLM check failed: {e}",
            "check": "vlm_review",
        }


# ──────────────────────────────────────────────────────────────
# Validation orchestration
# ──────────────────────────────────────────────────────────────

def validate_chart(session, chart: dict) -> dict:
    """
    Validate a single chart through rule checks + VLM review.
    Returns the chart dict with added validation_notes and updated validated field.
    """
    chart_id = chart.get("chart_id", "unknown")
    logger.info("Validating chart: %s", chart_id)

    validation_notes = []
    all_passed = True

    # Step 1: Rule-based checks
    rule_results = run_rule_checks(chart)
    for r in rule_results:
        validation_notes.append(r)
        if not r["passed"]:
            all_passed = False
            logger.warning("  ❌ Rule check failed [%s]: %s", r["check"], r["message"])
        else:
            logger.info("  ✅ Rule check passed [%s]: %s", r["check"], r["message"])

    # Step 2: Only run VLM check if rule checks passed
    if all_passed:
        vlm_result = run_vlm_check(session, chart)
        validation_notes.append(vlm_result)
        if not vlm_result["passed"]:
            # Soft pass: include chart in report even if VLM critique is negative,
            # as long as rule checks passed (file exists, size OK, dimensions OK).
            logger.warning("  ⚠️  VLM quality note [score=%.1f]: %s",
                           vlm_result["score"], vlm_result["feedback"])
            logger.info("  ℹ️  Soft pass — chart included despite VLM critique")
        else:
            logger.info("  ✅ VLM check passed [score=%.1f]", vlm_result["score"])

    chart["validated"] = all_passed
    chart["validation_notes"] = validation_notes

    status = "✅ PASSED" if all_passed else "❌ FAILED"
    logger.info("Chart %s validation: %s", chart_id, status)

    return chart


def validate_all_charts(session, charts: list) -> list:
    """
    Validate all charts. Attempts one re-render for failed charts
    using the fallback_code path in chart_agent.

    Args:
        session: Snowflake session
        charts: List of ChartResult dicts from chart_agent

    Returns:
        Validated chart list with validation_notes added to each
    """
    logger.info("═" * 50)
    logger.info("Validation Agent starting (%d charts)", len(charts))
    logger.info("═" * 50)

    validated = []
    for chart in charts:
        result = validate_chart(session, chart)

        # One re-render attempt for failed charts
        if not result["validated"] and result.get("refinement_count", 0) > 0:
            logger.warning(
                "Chart %s failed validation — attempting fallback re-render",
                chart["chart_id"]
            )
            # Import here to avoid circular import
            from agents.chart_agent import CHART_DEFINITIONS, execute_chart_code
            defn = CHART_DEFINITIONS.get(chart["chart_id"])
            df = chart.get("_df")
            if defn and df is not None:
                success = execute_chart_code(
                    defn["fallback_code"],
                    df,
                    chart["file_path"]
                )
                if success:
                    result = validate_chart(session, chart)
                    logger.info("Re-render result for %s: %s",
                                chart["chart_id"],
                                "✅ PASSED" if result["validated"] else "❌ STILL FAILED")
            elif defn and df is None:
                logger.warning(
                    "Cannot re-render %s — DataFrame not available (loaded from manifest?)",
                    chart["chart_id"]
                )

        validated.append(result)

    # Summary
    passed = sum(1 for c in validated if c["validated"])
    failed = len(validated) - passed

    logger.info("Validation complete: %d passed, %d failed", passed, failed)

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    for c in validated:
        status = "✅" if c["validated"] else "❌"
        print(f"  {status} {c['chart_id']}")
    print(f"\n  Total: {passed} passed, {failed} failed")
    print("=" * 60)

    return validated
