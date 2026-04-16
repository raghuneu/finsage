"""
FinSage Chart Specifications
============================
Schema-driven chart specifications that replace open-ended prompts.

Each spec defines:
    - chart_type: the visualization type (line, bar, stacked_bar, dual_axis, etc.)
    - required_series: series names that MUST appear in the chart
    - required_visuals: visual elements (legend, gridlines, axis labels, etc.)
    - constraints: hard rules the LLM must follow
    - precomputed_columns: mapping from prep data keys to plot-ready column names

The LLM's job is ONLY to arrange these pre-defined series into a
professional matplotlib chart — NOT to compute, transform, or reorder data.
"""

from typing import Any

# Version tag for reproducibility auditing
CHART_SPECS_VERSION = "1.0.0"

# ──────────────────────────────────────────────────────────────
# Canonical chart order (single source of truth)
# ──────────────────────────────────────────────────────────────

CANONICAL_CHART_ORDER = [
    "price_sma",
    "volatility",
    "revenue_growth",
    "eps_trend",
    "financial_health",
    "margin_trend",
    "balance_sheet",
    "sentiment",
]


# ──────────────────────────────────────────────────────────────
# Chart specifications
# ──────────────────────────────────────────────────────────────

CHART_SPECS: dict[str, dict[str, Any]] = {

    "price_sma": {
        "title": "Price & Moving Averages",
        "chart_type": "line_with_fill",
        "required_series": ["close", "sma_7d", "sma_30d", "sma_90d"],
        "required_visuals": [
            "legend", "gridlines", "axis_labels", "title",
            "fill_under_close", "y_zoom_to_price_range",
        ],
        "constraints": [
            "Data is pre-sorted by date ascending. Do NOT reorder.",
            "All values are in USD. Do NOT apply any unit conversion.",
            "Y-axis must zoom around min/max price (not start at 0).",
            "X-axis shows dates, rotated 30 degrees.",
        ],
        "precomputed_columns": {
            "x": "date",
            "close": "close",
            "sma_7d": "sma_7d",
            "sma_30d": "sma_30d",
            "sma_90d": "sma_90d",
        },
        "style": {
            "close": {"color": "#2563eb", "linewidth": 2, "fill_alpha": 0.15},
            "sma_7d": {"color": "#f59e0b", "linestyle": "--", "linewidth": 1.5},
            "sma_30d": {"color": "#10b981", "linestyle": "--", "linewidth": 1.5},
            "sma_90d": {"color": "#ef4444", "linestyle": "--", "linewidth": 1.5},
        },
        "figsize": (14, 6),
    },

    "volatility": {
        "title": "Volume & 30-Day Volatility",
        "chart_type": "dual_axis_bar_line",
        "required_series": ["volume_millions", "volatility_30d_pct"],
        "required_visuals": [
            "legend", "gridlines", "axis_labels", "title",
            "dual_y_axes", "combined_legend",
        ],
        "constraints": [
            "Data is pre-sorted by date ascending. Do NOT reorder.",
            "Volume is ALREADY in millions. Do NOT divide by 1e6.",
            "Volatility is ALREADY in percent. Do NOT multiply by 100.",
            "Do NOT use scientific notation on any axis.",
            "Left axis: Volume (Millions). Right axis: Volatility %.",
        ],
        "precomputed_columns": {
            "x": "date",
            "volume_millions": "volume_millions",
            "volatility_30d_pct": "volatility_30d_pct",
        },
        "style": {
            "volume_millions": {"color": "#94a3b8", "alpha": 0.6, "type": "bar"},
            "volatility_30d_pct": {"color": "#ef4444", "linewidth": 2, "type": "line"},
        },
        "figsize": (14, 6),
    },

    "revenue_growth": {
        "title": "Revenue & Net Income Growth (YoY %)",
        "chart_type": "grouped_bar",
        "required_series": ["revenue_growth_yoy_pct", "net_income_growth_yoy_pct"],
        "required_visuals": [
            "legend", "gridlines", "axis_labels", "title",
            "zero_reference_line", "data_labels_on_bars",
            "color_negative_bars_red",
        ],
        "constraints": [
            "Data is pre-sorted chronologically. Do NOT reorder.",
            "Values are ALREADY in percent. Do NOT multiply by 100.",
            "Plot ONLY YoY columns. Do NOT use QoQ columns.",
            "Do NOT add a secondary y-axis.",
            "Do NOT plot absolute revenue values.",
            "Do NOT use scientific notation.",
        ],
        "precomputed_columns": {
            "x": "fiscal_quarter",
            "revenue_growth_yoy_pct": "revenue_growth_yoy_pct",
            "net_income_growth_yoy_pct": "net_income_growth_yoy_pct",
        },
        "style": {
            "revenue_growth_yoy_pct": {"color_pos": "#00b4d8", "color_neg": "#ef4444"},
            "net_income_growth_yoy_pct": {"color_pos": "#06d6a0", "color_neg": "#ef4444"},
        },
        "figsize": (14, 6),
    },

    "eps_trend": {
        "title": "Earnings Per Share (EPS) Trend",
        "chart_type": "dual_axis_line_bar",
        "required_series": ["eps", "eps_growth_yoy_pct"],
        "required_visuals": [
            "legend", "gridlines", "axis_labels", "title",
            "data_labels_on_eps_points", "combined_legend",
        ],
        "constraints": [
            "Data is pre-sorted chronologically. Do NOT reorder.",
            "EPS is in USD. Growth is ALREADY in percent.",
            "Do NOT apply any unit conversion.",
        ],
        "precomputed_columns": {
            "x": "fiscal_quarter",
            "eps": "eps",
            "eps_growth_yoy_pct": "eps_growth_yoy_pct",
        },
        "style": {
            "eps": {"color": "#2563eb", "linewidth": 2.5, "marker": "o", "markersize": 8},
            "eps_growth_yoy_pct": {"color_pos": "#10b981", "color_neg": "#ef4444", "alpha": 0.4, "type": "bar"},
        },
        "figsize": (14, 6),
    },

    "sentiment": {
        "title": "News Sentiment Trend (7-Day Average)",
        "chart_type": "line_with_fill_zones",
        "required_series": ["sentiment_score_7d_avg"],
        "required_visuals": [
            "legend", "gridlines", "axis_labels", "title",
            "zero_reference_line", "positive_fill_green",
            "negative_fill_red",
        ],
        "constraints": [
            "Data is pre-sorted by date ascending. Do NOT reorder.",
            "Sentiment scores are ALREADY in range -1 to +1. Do NOT scale.",
            "Y-axis range must be -1 to +1.",
        ],
        "precomputed_columns": {
            "x": "news_date",
            "sentiment_score": "sentiment_score",
            "sentiment_score_7d_avg": "sentiment_score_7d_avg",
        },
        "style": {
            "sentiment_score_7d_avg": {"color": "#2563eb", "linewidth": 2},
            "positive_fill": {"color": "#10b981", "alpha": 0.2},
            "negative_fill": {"color": "#ef4444", "alpha": 0.2},
        },
        "figsize": (14, 6),
    },

    "financial_health": {
        "title": "Financial Health \u2014 Margins & Leverage",
        "chart_type": "dual_axis_grouped_bar_line",
        "required_series": ["net_margin_pct", "operating_margin_pct", "debt_to_equity_ratio"],
        "required_visuals": [
            "legend", "gridlines", "axis_labels", "title",
            "dual_y_axes", "combined_legend", "data_labels_on_bars",
        ],
        "constraints": [
            "Data is pre-sorted chronologically. Do NOT reorder.",
            "Margins are ALREADY in percent. Do NOT multiply by 100.",
            "Debt/Equity is ALREADY a ratio. Do NOT transform.",
            "Left axis: Margin %. Right axis: Debt/Equity Ratio.",
        ],
        "precomputed_columns": {
            "x": "fiscal_period",
            "net_margin_pct": "net_margin_pct",
            "operating_margin_pct": "operating_margin_pct",
            "debt_to_equity_ratio": "debt_to_equity_ratio",
        },
        "style": {
            "net_margin_pct": {"color": "#00b4d8", "alpha": 0.8, "type": "bar"},
            "operating_margin_pct": {"color": "#06d6a0", "alpha": 0.8, "type": "bar"},
            "debt_to_equity_ratio": {"color": "#ef4444", "linewidth": 2, "marker": "D", "type": "line"},
        },
        "figsize": (14, 6),
    },

    "margin_trend": {
        "title": "Profitability Margin Trend",
        "chart_type": "line_with_fill",
        "required_series": ["net_margin_pct", "operating_margin_pct"],
        "required_visuals": [
            "legend", "gridlines", "axis_labels", "title",
            "fill_under_net_margin", "data_labels_on_points",
        ],
        "constraints": [
            "Data is pre-sorted chronologically. Do NOT reorder.",
            "Margins are ALREADY in percent. Do NOT multiply by 100.",
            "Handle NaN gracefully with forward fill.",
        ],
        "precomputed_columns": {
            "x": "fiscal_period",
            "net_margin_pct": "net_margin_pct",
            "operating_margin_pct": "operating_margin_pct",
        },
        "style": {
            "net_margin_pct": {"color": "#00b4d8", "linewidth": 2, "marker": "o", "fill_alpha": 0.15},
            "operating_margin_pct": {"color": "#06d6a0", "linewidth": 2, "marker": "s", "linestyle": "--"},
        },
        "figsize": (14, 6),
    },

    "balance_sheet": {
        "title": "Balance Sheet Composition",
        "chart_type": "stacked_bar_with_line",
        "required_series": [
            "total_liabilities_billions",
            "stockholders_equity_billions",
            "total_assets_billions",
        ],
        "required_visuals": [
            "legend", "gridlines", "axis_labels", "title",
            "data_labels_on_assets_line",
        ],
        "constraints": [
            "Data is pre-sorted chronologically. Do NOT reorder.",
            "All values are ALREADY in billions ($B). Do NOT divide by 1e9.",
            "Stacked bars: liabilities on bottom, equity on top.",
            "Total assets as line overlay.",
            "Y-axis label: 'Amount ($B)'.",
        ],
        "precomputed_columns": {
            "x": "fiscal_period",
            "total_liabilities_billions": "total_liabilities_billions",
            "stockholders_equity_billions": "stockholders_equity_billions",
            "total_assets_billions": "total_assets_billions",
        },
        "style": {
            "total_liabilities_billions": {"color": "#ef4444", "alpha": 0.7, "type": "bar"},
            "stockholders_equity_billions": {"color": "#06d6a0", "alpha": 0.7, "type": "bar"},
            "total_assets_billions": {"color": "#00b4d8", "linewidth": 2, "marker": "D", "type": "line"},
        },
        "figsize": (14, 6),
    },
}


def get_spec(chart_id: str) -> dict[str, Any]:
    """Get chart specification by ID. Raises KeyError if not found."""
    return CHART_SPECS[chart_id]


def get_constraint_text(chart_id: str) -> str:
    """Format constraints as a prompt-ready string for the LLM."""
    spec = CHART_SPECS[chart_id]
    lines = [f"CHART SPEC CONSTRAINTS (v{CHART_SPECS_VERSION}):"]
    lines.append(f"  Chart type: {spec['chart_type']}")
    lines.append(f"  Required series: {', '.join(spec['required_series'])}")
    lines.append(f"  Required visuals: {', '.join(spec['required_visuals'])}")
    lines.append("  Rules:")
    for i, c in enumerate(spec["constraints"], 1):
        lines.append(f"    {i}. {c}")
    return "\n".join(lines)
