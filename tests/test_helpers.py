"""Tests for frontend helper functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "frontend"))

from utils.helpers import fmt_money, signal_badge


class TestFmtMoney:
    """Test money formatting helper."""

    def test_none_returns_na(self):
        assert fmt_money(None) == "N/A"

    def test_trillions(self):
        assert fmt_money(3_000_000_000_000) == "$3.00T"

    def test_billions(self):
        assert fmt_money(95_000_000_000) == "$95.0B"

    def test_millions(self):
        assert fmt_money(500_000_000) == "$500M"

    def test_thousands(self):
        assert fmt_money(50_000) == "$50,000"

    def test_negative_billions(self):
        assert fmt_money(-2_500_000_000) == "$-2.5B"


class TestSignalBadge:
    """Test signal badge rendering."""

    def test_bullish_signal(self):
        html = signal_badge("BULLISH")
        assert "06d6a0" in html
        assert "BULLISH" in html

    def test_bearish_signal(self):
        html = signal_badge("BEARISH")
        assert "ef476f" in html
        assert "BEARISH" in html

    def test_neutral_signal(self):
        html = signal_badge("MIXED")
        assert "94a3b8" in html
        assert "MIXED" in html

    def test_growth_signal(self):
        html = signal_badge("STRONG_GROWTH")
        assert "06d6a0" in html

    def test_declining_signal(self):
        html = signal_badge("DECLINING")
        assert "ef476f" in html
