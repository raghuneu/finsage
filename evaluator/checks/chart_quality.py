"""
Chart Quality Check
===================
Aggregates the VLM review scores already stored in chart_manifest.json
(written by validation_agent during the pipeline run).
No new API calls needed.
"""

import logging

from evaluator.rubric import REQUIRED_CHART_IDS, CHART_VLM_PASS_THRESHOLD

logger = logging.getLogger(__name__)


def _extract_vlm_score(chart: dict) -> float | None:
    """Pull the VLM score (0-10) from a chart's validation_notes list."""
    for note in chart.get("validation_notes") or []:
        if note.get("check") == "vlm_review":
            raw = note.get("score")
            try:
                return float(raw)
            except (TypeError, ValueError):
                return None
    return None


def check_chart_quality(artifacts: dict) -> tuple[float, list[str]]:
    """
    Args:
        artifacts: dict with 'chart_manifest' key

    Returns:
        (score 0-100, list of issue strings)
    """
    manifest = artifacts.get("chart_manifest") or []
    charts_by_id = {c.get("chart_id"): c for c in manifest}

    issues: list[str] = []
    scores: list[float] = []
    per_chart_scores: dict[str, float] = {}

    for chart_id in REQUIRED_CHART_IDS:
        chart = charts_by_id.get(chart_id, {})

        # Check validation passed flag
        if not chart.get("validated", False):
            issues.append(f"{chart_id}: chart did not pass validation_agent checks")

        # Pull VLM score
        vlm_score = _extract_vlm_score(chart)
        if vlm_score is None:
            # No VLM score recorded — treat as neutral (7/10)
            vlm_score = 7.0
            logger.debug("%s: no VLM score in manifest — using default 7.0", chart_id)

        per_chart_scores[chart_id] = vlm_score
        scores.append(vlm_score)

        if vlm_score < CHART_VLM_PASS_THRESHOLD:
            issues.append(
                f"{chart_id}: VLM score {vlm_score:.1f}/10 is below "
                f"threshold {CHART_VLM_PASS_THRESHOLD}"
            )

        # Refinement count — a chart that needed 3 refinements may still be suboptimal
        refinements = chart.get("refinement_count", 0)
        if refinements >= 3:
            issues.append(
                f"{chart_id}: required maximum ({refinements}) VLM refinement iterations"
            )

    # Score = mean VLM score normalised to 0-100
    if scores:
        mean_vlm = sum(scores) / len(scores)
        score = mean_vlm * 10.0  # 0-10 → 0-100
    else:
        score = 0.0

    logger.info(
        "Chart quality: avg VLM %.2f/10, %d issues → %.1f",
        (sum(scores) / len(scores)) if scores else 0.0,
        len(issues),
        score,
    )
    return round(score, 1), issues
