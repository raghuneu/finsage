"""
Tests for the FinSage report evaluation system.

All tests use in-memory fixture data — no Snowflake, no filesystem writes.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from evaluator.rubric import get_verdict, SCORE_WEIGHTS
from evaluator.checks.completeness import check_completeness
from evaluator.checks.data_quality import check_data_quality
from evaluator.checks.chart_quality import check_chart_quality
from evaluator.checks.consistency import check_consistency, _signal_polarity, _text_polarity
from evaluator.checks.text_quality import check_text_quality, _rule_score_text


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def minimal_chart():
    return {
        "chart_id": "price_sma",
        "title": "AAPL Price & Moving Averages",
        "file_path": "",  # no real file
        "validated": True,
        "refinement_count": 1,
        "data_summary": {
            "current_price": 185.50,
            "sma_7d": 184.20,
            "sma_30d": 180.10,
            "sma_90d": 175.00,
            "trend_signal": "BULLISH",
            "date_range": "2024-01-01 to 2024-03-31",
        },
        "validation_notes": [
            {"check": "file_exists",    "passed": True,  "message": "File exists"},
            {"check": "file_size",      "passed": True,  "message": "OK"},
            {"check": "dimensions",     "passed": True,  "message": "OK"},
            {"check": "data_summary",   "passed": True,  "message": "6 keys"},
            {"check": "data_plausibility", "passed": True, "message": "OK"},
            {"check": "vlm_review",     "passed": True,  "score": 8.5, "feedback": "Looks great"},
        ],
    }


@pytest.fixture
def full_manifest(minimal_chart):
    chart_ids = [
        "price_sma", "volatility", "revenue_growth", "eps_trend",
        "financial_health", "margin_trend", "balance_sheet", "sentiment",
    ]
    charts = []
    for cid in chart_ids:
        c = dict(minimal_chart)
        c["chart_id"] = cid
        # give each chart appropriate data_summary keys
        c["data_summary"] = {
            "current_price": 185.0, "sma_7d": 184.0, "sma_30d": 180.0,
            "sma_90d": 175.0, "trend_signal": "BULLISH",
            "avg_volume": 50000000, "volatility_30d_pct": 2.5,
            "daily_range_pct_avg": 1.2,
            "latest_revenue_growth_yoy": 8.5, "latest_net_income_growth_yoy": 12.3,
            "fundamental_signal": "STRONG_GROWTH",
            "latest_eps": 1.53, "eps_growth_yoy_pct": 15.2, "eps_growth_qoq_pct": 3.1,
            "financial_health": "EXCELLENT",
            "net_margin_pct": 25.3, "operating_margin_pct": 30.1, "total_revenue": 120e9,
            "num_quarters": 4, "latest_net_margin_pct": 25.3,
            "latest_operating_margin_pct": 30.1, "margin_trend": "IMPROVING",
            "total_assets_b": 335.0, "total_liabilities_b": 270.0,
            "stockholders_equity_b": 65.0, "equity_pct": 19.4,
            "sentiment_score_7d_avg": 0.45, "sentiment_label": "BULLISH",
            "sentiment_trend": "IMPROVING", "total_articles_30d": 78,
            "debt_to_equity_ratio": 1.5,
        }
        charts.append(c)
    return charts


@pytest.fixture
def pipeline_result(tmp_path):
    """Minimal valid pipeline_result.json content (no real PDF)."""
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%" + b"PDF-1.4" + b"\x00" * 150_000)

    # Chart-specific texts that reference the relevant numeric values from data_summary
    _chart_texts = {
        "price_sma": (
            "Apple trades at $185.00, with the 30-day SMA at $180.10 and the 90-day SMA "
            "at $175.00 confirming a sustained uptrend. The 7-day SMA of $184.00 reflects "
            "near-term positive momentum, and price action 5.7% above the 90-day average "
            "indicates strong bullish conviction. The current trend signal is BULLISH across "
            "all three key moving average horizons, supporting a constructive technical view."
        ),
        "volatility": (
            "Apple exhibits a 30-day volatility of 2.5%, below the large-cap technology "
            "sector median, indicating a relatively stable price environment. The average "
            "daily range of 1.2% implies moderate intraday risk suitable for institutional "
            "participation. Average daily volume of 50,000,000 shares confirms deep liquidity "
            "and efficient price discovery. The low volatility profile positions Apple as a "
            "lower-risk holding within a diversified technology portfolio."
        ),
        "revenue_growth": (
            "Apple reported revenue growth of 8.5% year-over-year, reflecting sustained "
            "top-line momentum across its product and services portfolio. Net income growth "
            "of 12.3% outpaced revenue, indicating meaningful margin expansion. The "
            "STRONG_GROWTH fundamental signal confirms accelerating earnings quality. "
            "This pattern of net income growing faster than revenue is typically "
            "associated with durable competitive advantages and pricing power."
        ),
        "eps_trend": (
            "Earnings per share of $1.53 grew 15.2% year-over-year and 3.1% sequentially, "
            "indicating robust and broad-based earnings expansion. The dual-horizon growth "
            "trajectory suggests both cyclical recovery and structural improvement. "
            "At $1.53, EPS represents a meaningful increase from prior-year levels and "
            "positions the company ahead of consensus estimates for the current fiscal year. "
            "Continued EPS growth at this rate would support premium valuation multiples."
        ),
        "financial_health": (
            "Apple's financial health is rated EXCELLENT, supported by a net margin of "
            "25.3% and total revenue of approximately $120 billion in the most recent period. "
            "Operating margin of 30.1% reflects the leverage inherent in the services "
            "business model. The combination of high margins and large absolute revenue "
            "base generates exceptional free cash flow conversion. Balance sheet strength "
            "further reinforces the EXCELLENT financial health designation."
        ),
        "margin_trend": (
            "Net margin of 25.3% and operating margin of 30.1% represent the latest "
            "quarterly readings across four reporting periods. The IMPROVING margin trend "
            "indicates that services revenue — which carries higher margins than hardware — "
            "is accounting for a growing share of the total revenue mix. Continued margin "
            "expansion at this pace would be structurally positive for long-term earnings "
            "power and return on equity."
        ),
        "balance_sheet": (
            "Stockholders' equity represents 19.4% of total assets, reflecting the "
            "company's disciplined capital return program via buybacks and dividends. "
            "Total assets of $335B and total liabilities of $270B result in a balance "
            "sheet that is highly liquid and investment-grade in all material respects. "
            "The 19.4% equity ratio, while lower than many peers, is supported by "
            "exceptional free cash flow generation and a long history of debt service."
        ),
        "sentiment": (
            "A 7-day average sentiment score of 0.45 on the -1 to +1 scale indicates "
            "moderately positive media sentiment, classified as BULLISH. Coverage of "
            "78 articles over the past 30 days reflects active institutional and retail "
            "attention. The IMPROVING sentiment trend suggests positive newsflow momentum "
            "that is reinforcing the constructive fundamental and technical picture. "
            "High article count combined with a 0.45 sentiment score is atypical for "
            "periods of market stress and supports a risk-on positioning stance."
        ),
    }
    chart_analyses = [
        {"chart_id": cid, "analysis_text": _chart_texts[cid]}
        for cid in [
            "price_sma", "volatility", "revenue_growth", "eps_trend",
            "financial_health", "margin_trend", "balance_sheet", "sentiment",
        ]
    ]

    return {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "pdf_path": str(pdf),
        "analysis": {
            "chart_analyses": chart_analyses,
            "investment_thesis": (
                "Apple Inc. demonstrates robust financial health, with revenue growth of 8.5% "
                "year-over-year and exceptional profit margins of 25.3%. The company continues "
                "to outperform sector peers on multiple fundamental metrics, supported by a "
                "strong balance sheet and improving sentiment indicators. The technical picture "
                "reinforces the constructive fundamental view, with price action sustaining above "
                "all three key moving averages. Valuation remains reasonable relative to peers."
            ),
            "mda_summary": (
                "Management discussion highlights sustained revenue momentum and expanding "
                "operating margins driven by services segment growth. Capital allocation "
                "priorities include share buybacks and dividend increases."
            ),
            "risk_summary": (
                "Key risks include macroeconomic headwinds, supply chain concentration, "
                "and regulatory scrutiny in major markets. Currency fluctuations may impact "
                "international revenue contribution."
            ),
        },
        "company_overview": {
            "company_description": (
                "Apple Inc. is a multinational technology company headquartered in Cupertino, "
                "California, designing and selling consumer electronics, software, and services. "
                "The company generated $120 billion in revenue during the most recent quarter "
                "with a net margin of 25.3%. Apple's ecosystem of hardware and services creates "
                "high switching costs and recurring revenue streams. The company maintains one "
                "of the strongest balance sheets in the technology sector."
            ),
        },
        "peer_comparison": {
            "comparison_summary": (
                "Relative to peers, Apple trades at a premium valuation justified by its "
                "superior margin profile and services growth trajectory. Microsoft and Google "
                "present comparable growth profiles at similar multiples."
            ),
        },
    }


@pytest.fixture
def good_artifacts(tmp_path, full_manifest, pipeline_result):
    return {
        "output_dir":      str(tmp_path),
        "pipeline_result": pipeline_result,
        "chart_manifest":  full_manifest,
    }


# ── Rubric tests ───────────────────────────────────────────────────────────

class TestGetVerdict:
    def test_golden(self):
        assert get_verdict(95.0) == "GOLDEN"

    def test_publication_ready(self):
        assert get_verdict(80.0) == "PUBLICATION_READY"

    def test_needs_revision(self):
        assert get_verdict(60.0) == "NEEDS_REVISION"

    def test_rejected(self):
        assert get_verdict(40.0) == "REJECTED"

    def test_boundary_golden(self):
        assert get_verdict(90.0) == "GOLDEN"

    def test_weights_sum_to_one(self):
        total = sum(SCORE_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9


# ── Completeness tests ─────────────────────────────────────────────────────

class TestCheckCompleteness:
    def test_good_artifacts_high_score(self, good_artifacts):
        # Charts have no real file_path — expect some deductions for PNGs missing
        score, issues = check_completeness(good_artifacts)
        # Should score high for text/JSON completeness despite missing PNGs
        assert score >= 50

    def test_missing_pipeline_result(self, good_artifacts):
        good_artifacts["pipeline_result"] = None
        score, issues = check_completeness(good_artifacts)
        assert score < 90
        assert any("pipeline_result.json" in i for i in issues)

    def test_missing_chart_manifest(self, good_artifacts):
        good_artifacts["chart_manifest"] = None
        score, issues = check_completeness(good_artifacts)
        assert any("chart_manifest.json" in i for i in issues)

    def test_empty_analysis_text_flagged(self, good_artifacts):
        good_artifacts["pipeline_result"]["analysis"]["chart_analyses"][0]["analysis_text"] = ""
        _, issues = check_completeness(good_artifacts)
        assert any("price_sma" in i and "empty" in i.lower() for i in issues)

    def test_guardrail_text_flagged(self, good_artifacts):
        good_artifacts["pipeline_result"]["analysis"]["chart_analyses"][0]["analysis_text"] = (
            "This analysis section has been withheld because it did not pass "
            "content safety validation."
        )
        _, issues = check_completeness(good_artifacts)
        assert any("guardrail" in i.lower() or "fallback" in i.lower() for i in issues)

    def test_short_text_flagged(self, good_artifacts):
        good_artifacts["pipeline_result"]["analysis"]["chart_analyses"][0]["analysis_text"] = (
            "Too short."
        )
        _, issues = check_completeness(good_artifacts)
        assert any("price_sma" in i and "short" in i.lower() for i in issues)


# ── Data quality tests ─────────────────────────────────────────────────────

class TestCheckDataQuality:
    def test_clean_data_high_score(self, good_artifacts):
        score, issues = check_data_quality(good_artifacts)
        assert score >= 80

    def test_margin_out_of_bounds(self, good_artifacts):
        good_artifacts["chart_manifest"][0]["data_summary"]["net_margin_pct"] = 150.0
        _, issues = check_data_quality(good_artifacts)
        assert any("net_margin_pct" in i for i in issues)

    def test_negative_price_flagged(self, good_artifacts):
        good_artifacts["chart_manifest"][0]["data_summary"]["current_price"] = -5.0
        _, issues = check_data_quality(good_artifacts)
        assert any("current_price" in i for i in issues)

    def test_sentiment_out_of_range(self, good_artifacts):
        good_artifacts["chart_manifest"][0]["data_summary"]["sentiment_score_7d_avg"] = 2.5
        _, issues = check_data_quality(good_artifacts)
        assert any("sentiment_score_7d_avg" in i for i in issues)

    def test_invalid_categorical_signal(self, good_artifacts):
        good_artifacts["chart_manifest"][0]["data_summary"]["trend_signal"] = "VERY_BULLISH"
        _, issues = check_data_quality(good_artifacts)
        assert any("trend_signal" in i for i in issues)

    def test_empty_manifest_zero_score(self):
        score, _ = check_data_quality({"chart_manifest": []})
        assert score == 0.0


# ── Chart quality tests ────────────────────────────────────────────────────

class TestCheckChartQuality:
    def test_high_vlm_scores_give_high_score(self, good_artifacts):
        score, _ = check_chart_quality(good_artifacts)
        assert score >= 70

    def test_low_vlm_score_triggers_issue(self, good_artifacts):
        good_artifacts["chart_manifest"][0]["validation_notes"][-1]["score"] = 4.0
        good_artifacts["chart_manifest"][0]["validation_notes"][-1]["passed"] = False
        _, issues = check_chart_quality(good_artifacts)
        assert any("VLM score" in i for i in issues)

    def test_missing_vlm_note_uses_default(self, good_artifacts):
        # Remove vlm_review note — should default to 7.0 and not crash
        for note in good_artifacts["chart_manifest"][0]["validation_notes"]:
            if note.get("check") == "vlm_review":
                good_artifacts["chart_manifest"][0]["validation_notes"].remove(note)
                break
        score, _ = check_chart_quality(good_artifacts)
        assert score > 0

    def test_failed_validation_flag_flagged(self, good_artifacts):
        good_artifacts["chart_manifest"][0]["validated"] = False
        _, issues = check_chart_quality(good_artifacts)
        assert any("did not pass" in i for i in issues)


# ── Consistency tests ──────────────────────────────────────────────────────

class TestConsistency:
    def test_signal_polarity_bullish(self):
        assert _signal_polarity("BULLISH") == "bullish"
        assert _signal_polarity("BULLISH_STRONG") == "bullish"
        assert _signal_polarity("STRONG_GROWTH") == "bullish"

    def test_signal_polarity_bearish(self):
        assert _signal_polarity("BEARISH") == "bearish"
        assert _signal_polarity("DECLINING") == "bearish"

    def test_signal_polarity_neutral(self):
        assert _signal_polarity("NEUTRAL") == "neutral"
        assert _signal_polarity("MIXED") == "neutral"

    def test_text_polarity_bullish(self):
        assert _text_polarity("The stock shows strong uptrend and bullish momentum.") == "bullish"

    def test_text_polarity_bearish(self):
        assert _text_polarity("The stock is in downtrend with bearish signals and declining revenue.") == "bearish"

    def test_consistent_artifacts_high_score(self, good_artifacts):
        score, _ = check_consistency(good_artifacts)
        assert score >= 50  # good fixtures reference data values

    def test_number_not_cited_triggers_issue(self, good_artifacts):
        # Replace analysis text with one that mentions no numbers
        good_artifacts["pipeline_result"]["analysis"]["chart_analyses"][0]["analysis_text"] = (
            "The stock appears to be in an uptrend based on moving average analysis. "
            "Momentum looks positive across all time frames. Investors may find this "
            "trajectory encouraging as the company executes on its strategic priorities."
        )
        _, issues = check_consistency(good_artifacts)
        assert any("price_sma" in i and "not referenced" in i for i in issues)


# ── Text quality tests ─────────────────────────────────────────────────────

class TestTextQuality:
    def test_rule_score_good_text(self):
        text = (
            "Apple reported revenue of $120B, representing 8.5% year-over-year growth. "
            "Net margin improved to 25.3%, reflecting effective cost management and "
            "disciplined expense control across all business segments. "
            "EPS of $1.53 beat consensus by 3.1% and grew 15.2% on an annual basis. "
            "The balance sheet shows debt-to-equity of 1.5x, well within sector norms, "
            "and the company generated $28B in operating cash flow during the quarter. "
            "Overall the financial profile remains robust with continued shareholder returns."
        )
        score, issues = _rule_score_text(text, "test")
        assert score >= 7
        assert not issues

    def test_rule_score_markdown_detected(self):
        text = "The stock is **very bullish** with `strong` indicators. " * 5
        score, issues = _rule_score_text(text, "test")
        assert any("markdown" in i.lower() for i in issues)
        assert score < 8

    def test_rule_score_no_numbers(self):
        text = (
            "The company demonstrates strong growth trajectory and improving margins. "
            "Momentum appears positive with favorable market conditions. "
            "Management continues to execute on strategic priorities effectively. "
            "The overall outlook remains constructive for long-term investors."
        )
        score, issues = _rule_score_text(text, "test")
        assert any("numeric" in i.lower() for i in issues)

    def test_rule_score_fallback_text(self):
        text = "This analysis section has been withheld because it did not pass content safety validation."
        score, issues = _rule_score_text(text, "test")
        assert score == 0.0
        assert issues

    def test_rule_score_too_short(self):
        score, issues = _rule_score_text("Short.", "test")
        assert any("short" in i.lower() for i in issues)

    def test_check_text_quality_no_session(self, good_artifacts):
        score, _ = check_text_quality(good_artifacts, session=None)
        assert 0 <= score <= 100
