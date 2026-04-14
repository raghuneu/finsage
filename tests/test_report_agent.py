"""Tests for report agent signal derivation logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from report_agent import get_signal, overall_signal, C_BULLISH, C_BEARISH, C_NEUTRAL


class TestGetSignal:
    """Test per-chart signal derivation."""

    def test_price_sma_bullish(self):
        label, color = get_signal("price_sma", {"trend_signal": "BULLISH"})
        assert "BULLISH" in label
        assert color == C_BULLISH

    def test_price_sma_bearish(self):
        label, color = get_signal("price_sma", {"trend_signal": "BEARISH"})
        assert "BEARISH" in label
        assert color == C_BEARISH

    def test_price_sma_neutral(self):
        label, color = get_signal("price_sma", {"trend_signal": "NEUTRAL"})
        assert "NEUTRAL" in label
        assert color == C_NEUTRAL

    def test_volatility_low(self):
        label, color = get_signal("volatility", {"volatility_30d_pct": 1.0})
        assert "LOW VOL" in label
        assert color == C_BULLISH

    def test_volatility_high(self):
        label, color = get_signal("volatility", {"volatility_30d_pct": 4.0})
        assert "HIGH VOL" in label
        assert color == C_BEARISH

    def test_sentiment_bullish(self):
        label, color = get_signal("sentiment", {"sentiment_label": "BULLISH"})
        assert "BULLISH" in label
        assert color == C_BULLISH

    def test_financial_health_excellent(self):
        label, color = get_signal("financial_health", {"financial_health": "EXCELLENT"})
        assert "HEALTHY" in label
        assert color == C_BULLISH

    def test_financial_health_unprofitable(self):
        label, color = get_signal("financial_health", {"financial_health": "UNPROFITABLE"})
        assert "WEAK" in label
        assert color == C_BEARISH

    def test_unknown_chart_id(self):
        label, color = get_signal("unknown_chart", {})
        assert "NEUTRAL" in label


class TestOverallSignal:
    """Test overall report signal from chart votes."""

    def test_mostly_bullish(self):
        charts = [
            {"chart_id": "price_sma", "data_summary": {"trend_signal": "BULLISH"}},
            {"chart_id": "volatility", "data_summary": {"volatility_30d_pct": 1.0}},
            {"chart_id": "sentiment", "data_summary": {"sentiment_label": "BULLISH"}},
            {"chart_id": "financial_health", "data_summary": {"financial_health": "EXCELLENT"}},
        ]
        label, color = overall_signal(charts)
        assert "BULLISH" in label

    def test_mostly_bearish(self):
        charts = [
            {"chart_id": "price_sma", "data_summary": {"trend_signal": "BEARISH"}},
            {"chart_id": "volatility", "data_summary": {"volatility_30d_pct": 4.0}},
            {"chart_id": "sentiment", "data_summary": {"sentiment_label": "BEARISH"}},
            {"chart_id": "financial_health", "data_summary": {"financial_health": "UNPROFITABLE"}},
        ]
        label, color = overall_signal(charts)
        assert "BEARISH" in label

    def test_mixed_returns_neutral(self):
        charts = [
            {"chart_id": "price_sma", "data_summary": {"trend_signal": "BULLISH"}},
            {"chart_id": "volatility", "data_summary": {"volatility_30d_pct": 4.0}},
            {"chart_id": "sentiment", "data_summary": {"sentiment_label": "NEUTRAL"}},
        ]
        label, color = overall_signal(charts)
        assert "NEUTRAL" in label

    def test_empty_charts(self):
        label, color = overall_signal([])
        assert "NEUTRAL" in label
