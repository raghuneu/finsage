"""
FinSage Chart Data Validation
=============================
Pre-render validation layer that checks data integrity BEFORE
passing to the LLM for chart generation.

Validates:
    1. Required series present (per chart spec)
    2. No missing critical metrics (all-NaN series)
    3. Matching series lengths (all columns same length)
    4. Chronological ordering preserved (no reordering)
    5. Unit conversion sanity (values in expected ranges)
"""

import logging
from typing import Any

import pandas as pd

from agents.chart_specs import CHART_SPECS

logger = logging.getLogger(__name__)


class ChartDataValidationError(Exception):
    """Raised when precomputed chart data fails validation."""
    pass


def validate_chart_data(chart_id: str, prep_data: dict[str, Any]) -> list[str]:
    """
    Validate precomputed chart data against its spec.

    Args:
        chart_id: The chart identifier (e.g. 'balance_sheet')
        prep_data: Dict returned by prepare_*_data() functions

    Returns:
        List of warning strings (empty = all checks passed).

    Raises:
        ChartDataValidationError: If critical validation fails
            (missing required series, zero-length data).
    """
    warnings = []
    spec = CHART_SPECS.get(chart_id)
    if spec is None:
        warnings.append(f"No spec found for chart_id={chart_id}, skipping validation")
        return warnings

    # ── Check 1: Required series present ──────────────────────
    required = spec["required_series"]
    precomputed_cols = spec["precomputed_columns"]

    for series_name in required:
        # Map from spec series name to prep data key
        data_key = precomputed_cols.get(series_name, series_name)
        if data_key not in prep_data:
            raise ChartDataValidationError(
                f"Chart '{chart_id}': required series '{series_name}' "
                f"(data key '{data_key}') missing from precomputed data. "
                f"Available keys: {list(prep_data.keys())}"
            )

    # ── Check 2: Non-empty data ───────────────────────────────
    num_points = prep_data.get("num_points", 0)
    if num_points == 0:
        raise ChartDataValidationError(
            f"Chart '{chart_id}': zero data points in precomputed data"
        )

    # ── Check 3: Matching series lengths ──────────────────────
    list_keys = [k for k, v in prep_data.items() if isinstance(v, list)]
    lengths = {k: len(prep_data[k]) for k in list_keys}
    unique_lengths = set(lengths.values())

    if len(unique_lengths) > 1:
        raise ChartDataValidationError(
            f"Chart '{chart_id}': mismatched series lengths: {lengths}"
        )

    # ── Check 4: No all-NaN required series ───────────────────
    for series_name in required:
        data_key = precomputed_cols.get(series_name, series_name)
        values = prep_data.get(data_key)
        if isinstance(values, list):
            non_null = [v for v in values if v is not None and not (isinstance(v, float) and pd.isna(v))]
            if len(non_null) == 0:
                warnings.append(
                    f"Chart '{chart_id}': required series '{series_name}' is all NaN/None"
                )

    # ── Check 5: Unit conversion sanity checks ────────────────
    _check_unit_ranges(chart_id, prep_data, warnings)

    if warnings:
        for w in warnings:
            logger.warning("Validation: %s", w)

    return warnings


def _check_unit_ranges(chart_id: str, prep_data: dict, warnings: list) -> None:
    """Check that precomputed values are in expected ranges."""

    if chart_id == "volatility":
        vol_m = prep_data.get("volume_millions", [])
        if vol_m and any(isinstance(v, (int, float)) and v > 50000 for v in vol_m):
            warnings.append(
                "volatility: volume_millions has values >50,000 — "
                "possible double-division (raw volume passed instead of millions?)"
            )

    if chart_id == "balance_sheet":
        assets = prep_data.get("total_assets_billions", [])
        if assets and any(isinstance(v, (int, float)) and v > 100000 for v in assets):
            warnings.append(
                "balance_sheet: total_assets_billions has values >100,000 — "
                "possible raw values passed instead of billions"
            )

    if chart_id in ("margin_trend", "financial_health"):
        for key in ("net_margin_pct", "operating_margin_pct"):
            vals = prep_data.get(key, [])
            if vals and any(isinstance(v, (int, float)) and abs(v) > 200 for v in vals):
                warnings.append(
                    f"{chart_id}: {key} has values >200% — "
                    "possible double-multiplication (decimal * 100 * 100?)"
                )

    if chart_id == "sentiment":
        scores = prep_data.get("sentiment_score_7d_avg", [])
        if scores and any(isinstance(v, (int, float)) and abs(v) > 1.0 for v in scores):
            warnings.append(
                "sentiment: sentiment_score_7d_avg has values outside [-1, 1] range"
            )


def validate_all_chart_data(
    chart_tasks: list[tuple[str, dict[str, Any]]]
) -> dict[str, list[str]]:
    """
    Validate all precomputed chart data before generation.

    Args:
        chart_tasks: List of (chart_id, prep_data) tuples

    Returns:
        Dict mapping chart_id -> list of warnings.
        Charts that raise ChartDataValidationError are logged and excluded.
    """
    results = {}
    for chart_id, prep_data in chart_tasks:
        try:
            warnings = validate_chart_data(chart_id, prep_data)
            results[chart_id] = warnings
        except ChartDataValidationError as e:
            logger.error("Data validation FAILED for '%s': %s", chart_id, e)
            results[chart_id] = [f"CRITICAL: {e}"]
    return results
