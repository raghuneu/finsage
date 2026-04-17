"""
Data Quality Check
==================
Validates that financial values in each chart's data_summary are within
plausible bounds and contain no None/NaN values in critical fields.
No API calls — purely rule-based.
"""

import math
import logging

from evaluator.rubric import (
    REQUIRED_CHART_IDS,
    DATA_BOUNDS,
    MUST_BE_POSITIVE_KEYS,
)

logger = logging.getLogger(__name__)

# Keys that must be present (non-None) for each chart
_REQUIRED_KEYS_PER_CHART: dict[str, list[str]] = {
    "price_sma":       ["current_price", "sma_7d", "sma_30d", "sma_90d", "trend_signal"],
    "volatility":      ["avg_volume", "volatility_30d_pct"],
    "revenue_growth":  ["latest_revenue_growth_yoy", "fundamental_signal"],
    "eps_trend":       ["latest_eps"],
    "financial_health":["financial_health"],
    "margin_trend":    ["latest_net_margin_pct"],
    "balance_sheet":   ["equity_pct"],
    "sentiment":       ["sentiment_score_7d_avg", "sentiment_label"],
}

_VALID_CATEGORICAL: dict[str, set[str]] = {
    "trend_signal":      {"BULLISH", "BULLISH_STRONG", "BEARISH", "BEARISH_STRONG", "NEUTRAL"},
    "fundamental_signal":{"STRONG_GROWTH", "MODERATE_GROWTH", "DECLINING", "MIXED"},
    "sentiment_label":   {"BULLISH", "BEARISH", "NEUTRAL", "NO_COVERAGE"},
    "financial_health":  {"EXCELLENT", "HEALTHY", "FAIR", "UNPROFITABLE"},
    "sentiment_trend":   {"IMPROVING", "DETERIORATING", "STABLE"},
}


def _is_nan_or_none(value) -> bool:
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _check_chart_data(chart_id: str, data_summary: dict) -> list[str]:
    """Return list of issue strings for a single chart's data_summary."""
    issues = []

    # Required keys present
    for key in _REQUIRED_KEYS_PER_CHART.get(chart_id, []):
        if _is_nan_or_none(data_summary.get(key)):
            issues.append(f"{chart_id}: required key '{key}' is None/NaN")

    for key, value in data_summary.items():
        if _is_nan_or_none(value):
            continue  # already caught above or non-critical

        # Categorical validation
        if key in _VALID_CATEGORICAL:
            if str(value) not in _VALID_CATEGORICAL[key]:
                issues.append(
                    f"{chart_id}: '{key}' has unexpected value '{value}' "
                    f"(expected one of {sorted(_VALID_CATEGORICAL[key])})"
                )
            continue

        # Numeric bounds
        if key in DATA_BOUNDS:
            try:
                v = float(value)
                lo, hi = DATA_BOUNDS[key]
                if not (lo <= v <= hi):
                    issues.append(
                        f"{chart_id}: '{key}' = {v} is outside expected range [{lo}, {hi}]"
                    )
            except (TypeError, ValueError):
                pass

        # Must-be-positive keys
        if key in MUST_BE_POSITIVE_KEYS:
            try:
                if float(value) < 0:
                    issues.append(f"{chart_id}: '{key}' = {value} should be positive")
            except (TypeError, ValueError):
                pass

    return issues


def check_data_quality(artifacts: dict) -> tuple[float, list[str]]:
    """
    Args:
        artifacts: dict with 'chart_manifest' key

    Returns:
        (score 0-100, list of issue strings)
    """
    manifest = artifacts.get("chart_manifest") or []
    charts_by_id = {c.get("chart_id"): c for c in manifest}

    all_issues: list[str] = []
    total_charts = len(REQUIRED_CHART_IDS)
    clean_charts = 0

    for chart_id in REQUIRED_CHART_IDS:
        chart = charts_by_id.get(chart_id, {})
        data_summary = chart.get("data_summary") or {}

        if not data_summary:
            all_issues.append(f"{chart_id}: data_summary is empty")
            continue

        chart_issues = _check_chart_data(chart_id, data_summary)
        all_issues.extend(chart_issues)
        if not chart_issues:
            clean_charts += 1

    # Score: proportion of charts with zero data issues, scaled 0-100
    score = (clean_charts / total_charts * 100.0) if total_charts else 0.0

    # Partial credit: reduce score by 5 per issue on charts that have issues
    penalty = min(len(all_issues) * 3.0, score)
    score = max(0.0, score - penalty)

    logger.info(
        "Data quality: %d/%d charts clean, %d issues → %.1f",
        clean_charts, total_charts, len(all_issues), score,
    )
    return round(score, 1), all_issues
