"""
Consistency Check
=================
Rule-based checks that the LLM analysis text is consistent with the
structured data it was supposed to describe.

Two types of consistency are checked:
1. Signal tone — does the text sentiment match the categorical signal?
2. Numeric grounding — do key figures from data_summary appear in the text?
"""

import re
import logging

from evaluator.rubric import REQUIRED_CHART_IDS

logger = logging.getLogger(__name__)

# ── Tone keywords for signal matching ──────────────────────────────────────
_BULLISH_WORDS = frozenset([
    "bullish", "uptrend", "outperform", "strong growth", "positive momentum",
    "above", "exceeds", "surpasses", "gains", "rally", "improvement",
    "acceleration", "robust", "favorable", "healthy",
])
_BEARISH_WORDS = frozenset([
    "bearish", "downtrend", "underperform", "declining", "negative",
    "below", "falls", "drops", "weakness", "deterioration", "contraction",
    "compression", "risk", "concern", "unfavorable",
])


def _signal_polarity(signal: str) -> str:
    """Return 'bullish', 'bearish', or 'neutral' for a signal string."""
    s = signal.upper()
    if "BULLISH" in s or "STRONG_GROWTH" in s or "EXCELLENT" in s or "HEALTHY" in s:
        return "bullish"
    if "BEARISH" in s or "DECLINING" in s or "UNPROFITABLE" in s:
        return "bearish"
    return "neutral"


def _text_polarity(text: str) -> str:
    """Heuristic: count bullish vs bearish words in the text."""
    lower = text.lower()
    b_count = sum(1 for w in _BULLISH_WORDS if w in lower)
    n_count = sum(1 for w in _BEARISH_WORDS if w in lower)
    if b_count > n_count + 1:
        return "bullish"
    if n_count > b_count + 1:
        return "bearish"
    return "neutral"


def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values from text (handles $1.2B, 3.4%, -5.6, etc.)."""
    raw = re.findall(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    result = []
    for r in raw:
        try:
            result.append(float(r))
        except ValueError:
            pass
    return result


def _approx_in_text(value: float, text_numbers: list[float], tolerance: float = 0.15) -> bool:
    """Return True if `value` appears approximately in the text numbers."""
    if abs(value) < 0.01:
        return True  # near-zero values are trivially present
    for n in text_numbers:
        if abs(value) > 0:
            if abs(n - value) / abs(value) <= tolerance:
                return True
        elif abs(n - value) < 0.01:
            return True
    return False


# ── Per-chart key values to verify are cited ──────────────────────────────
_NUMERIC_KEYS_TO_CHECK: dict[str, list[str]] = {
    "price_sma":       ["current_price", "sma_30d", "sma_90d"],
    "volatility":      ["volatility_30d_pct"],
    "revenue_growth":  ["latest_revenue_growth_yoy"],
    "eps_trend":       ["latest_eps", "eps_growth_yoy_pct"],
    "financial_health":["net_margin_pct", "total_revenue"],
    "margin_trend":    ["latest_net_margin_pct"],
    "balance_sheet":   ["equity_pct"],
    "sentiment":       ["sentiment_score_7d_avg", "total_articles_30d"],
}

_SIGNAL_KEYS: dict[str, str] = {
    "price_sma":       "trend_signal",
    "revenue_growth":  "fundamental_signal",
    "financial_health":"financial_health",
    "sentiment":       "sentiment_label",
}


def _check_chart_consistency(
    chart_id: str,
    analysis_text: str,
    data_summary: dict,
) -> list[str]:
    """Return consistency issues for a single chart."""
    issues = []

    if not analysis_text or not data_summary:
        return issues

    text_numbers = _extract_numbers(analysis_text)

    # 1. Numeric grounding
    for key in _NUMERIC_KEYS_TO_CHECK.get(chart_id, []):
        val = data_summary.get(key)
        if val is None:
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        if not _approx_in_text(fval, text_numbers):
            issues.append(
                f"{chart_id}: key figure '{key}' = {val} not referenced in analysis text"
            )

    # 2. Signal tone consistency
    signal_key = _SIGNAL_KEYS.get(chart_id)
    if signal_key:
        signal = str(data_summary.get(signal_key, ""))
        if signal:
            data_polarity = _signal_polarity(signal)
            text_polarity = _text_polarity(analysis_text)
            if (
                data_polarity != "neutral"
                and text_polarity != "neutral"
                and data_polarity != text_polarity
            ):
                issues.append(
                    f"{chart_id}: signal '{signal}' ({data_polarity}) conflicts with "
                    f"text tone ({text_polarity})"
                )

    return issues


def check_consistency(artifacts: dict) -> tuple[float, list[str]]:
    """
    Args:
        artifacts: dict with 'pipeline_result' and 'chart_manifest'

    Returns:
        (score 0-100, list of issue strings)
    """
    pipeline = artifacts.get("pipeline_result") or {}
    manifest = artifacts.get("chart_manifest") or []

    charts_by_id = {c.get("chart_id"): c for c in manifest}
    chart_analyses = {
        a.get("chart_id"): a.get("analysis_text", "")
        for a in (pipeline.get("analysis", {}).get("chart_analyses") or [])
    }

    all_issues: list[str] = []
    total = len(REQUIRED_CHART_IDS)
    consistent = 0

    for chart_id in REQUIRED_CHART_IDS:
        analysis = chart_analyses.get(chart_id, "")
        data_summary = (charts_by_id.get(chart_id) or {}).get("data_summary") or {}

        chart_issues = _check_chart_consistency(chart_id, analysis, data_summary)
        all_issues.extend(chart_issues)
        if not chart_issues:
            consistent += 1

    score = (consistent / total * 100.0) if total else 0.0
    # Light penalty per issue beyond the per-chart failures already captured
    extra_penalty = max(0.0, len(all_issues) - (total - consistent)) * 2.0
    score = max(0.0, score - extra_penalty)

    logger.info(
        "Consistency: %d/%d charts consistent, %d issues → %.1f",
        consistent, total, len(all_issues), score,
    )
    return round(score, 1), all_issues
