"""
FinSage Report Evaluation Rubric
=================================
Centralised constants — thresholds, weights, required fields, data bounds.
All check modules import from here so the scoring model stays in one place.
"""

# ── Dimension weights (must sum to 1.0) ────────────────────────────────────
SCORE_WEIGHTS: dict[str, float] = {
    "completeness":  0.15,
    "data_quality":  0.20,
    "text_quality":  0.30,
    "chart_quality": 0.15,
    "consistency":   0.10,
    "pdf_content":   0.10,
}

# ── Verdict thresholds (lower-bound inclusive) ─────────────────────────────
VERDICT_THRESHOLDS: dict[str, float] = {
    "GOLDEN":             90.0,
    "PUBLICATION_READY":  75.0,
    "NEEDS_REVISION":     50.0,
    "REJECTED":            0.0,
}

# ── Charts ──────────────────────────────────────────────────────────────────
REQUIRED_CHART_IDS: list[str] = [
    "price_sma",
    "volatility",
    "revenue_growth",
    "eps_trend",
    "financial_health",
    "margin_trend",
    "balance_sheet",
    "sentiment",
]

# ── LLM text fields: (dot-path into analysis_result.json, min word count) ──
# Top-level keys match _save_analysis_result() in orchestrator.py.
REQUIRED_TEXT_FIELDS: dict[str, int] = {
    "investment_thesis":                       50,
    "mda_summary":                             30,
    "risk_summary":                            30,
    "company_overview.company_description":    50,
    "peer_comparison.comparison_summary":      20,
}

# Min / max word counts for per-chart analysis paragraphs
ANALYSIS_MIN_WORDS: int = 50
ANALYSIS_MAX_WORDS: int = 300

# Minimum chart VLM score to pass
CHART_VLM_PASS_THRESHOLD: float = 6.0

# Minimum PDF size (bytes) — a real report is always several hundred KB
MIN_PDF_SIZE_BYTES: int = 100_000

# Text that signals a guardrails block
GUARDRAIL_FALLBACK_SUBSTRING: str = "withheld because it did not pass"

# Fallback / missing-data sentinel substrings (case-insensitive)
FALLBACK_SUBSTRINGS: list[str] = [
    "not available",
    "analysis not available",
    "could not be generated",
    "failed to generate",
    GUARDRAIL_FALLBACK_SUBSTRING,
]

# ── Financial data bounds ───────────────────────────────────────────────────
# key: (min, max).  Values outside this range are flagged as suspect.
DATA_BOUNDS: dict[str, tuple[float, float]] = {
    # Margin fields (percent)
    "net_margin_pct":              (-100.0, 100.0),
    "operating_margin_pct":        (-100.0, 100.0),
    "gross_margin_pct":            (-100.0, 100.0),
    "latest_net_margin_pct":       (-100.0, 100.0),
    "latest_operating_margin_pct": (-100.0, 100.0),
    "profit_margin":               (-100.0, 100.0),
    # Leverage
    "debt_to_equity_ratio":        (0.0, 50.0),
    "debt_to_equity":              (0.0, 50.0),
    # Sentiment (-1 bearish → +1 bullish)
    "sentiment_score_7d_avg":      (-1.0,  1.0),
    # Volatility (percent)
    "volatility_30d_pct":          (0.0, 200.0),
    "daily_range_pct_avg":         (0.0, 100.0),
    # EPS growth rates (percent) — allow wide range for small-cap swings
    "eps_growth_yoy_pct":          (-500.0, 1000.0),
    "eps_growth_qoq_pct":          (-500.0, 1000.0),
    # Revenue growth (percent)
    "latest_revenue_growth_yoy":   (-100.0, 500.0),
    "latest_net_income_growth_yoy":(-200.0, 1000.0),
}

# Keys that must be positive (revenue, price, volume, etc.)
MUST_BE_POSITIVE_KEYS: set[str] = {
    "current_price",
    "sma_7d", "sma_30d", "sma_90d",
    "latest_eps",
    "avg_volume",
    "total_revenue",
    "total_articles_30d",
}

# Subset that must be strictly > 0 (zero is also a data error, e.g. $0 revenue)
MUST_BE_STRICTLY_POSITIVE_KEYS: set[str] = {
    "current_price",
    "total_revenue",
    "avg_volume",
}


def get_verdict(score: float) -> str:
    """Map overall score to a verdict string."""
    for label, threshold in sorted(
        VERDICT_THRESHOLDS.items(), key=lambda kv: kv[1], reverse=True
    ):
        if score >= threshold:
            return label
    return "REJECTED"
