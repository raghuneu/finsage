"""Tests for clean_llm_text and render_badge."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "agents"))
sys.path.insert(0, str(PROJECT_ROOT / "frontend"))


class TestCleanLLMText:
    def _load(self):
        from agents.report_agent import clean_llm_text
        return clean_llm_text

    def test_empty_returns_empty(self):
        assert self._load()("") == ""
        assert self._load()(None) == ""

    def test_strips_bold(self):
        assert self._load()("This is **important** text") == "This is important text"

    def test_strips_header(self):
        assert self._load()("# Title here") == "Title here"
        assert self._load()("### Sub") == "Sub"

    def test_bullet_conversion(self):
        out = self._load()("- first\n- second")
        assert "• first" in out
        assert "• second" in out

    def test_preserves_inline_dollar_symbol(self):
        assert "$100" in self._load()("Revenue is $100M")


class TestRenderBadge:
    def _load(self):
        import streamlit  # noqa: F401  (ensure importable for helpers)
        from frontend.utils.helpers import render_badge
        return render_badge

    def test_bullish_color(self):
        try:
            render_badge = self._load()
        except Exception:
            # Streamlit may not be installed; skip.
            import pytest
            pytest.skip("streamlit unavailable")
        html = render_badge("BUY", "BULLISH")
        assert "#06d6a0" in html
        assert "BUY" in html

    def test_bearish_color(self):
        try:
            render_badge = self._load()
        except Exception:
            import pytest
            pytest.skip("streamlit unavailable")
        html = render_badge("SELL", "BEARISH")
        assert "#ef476f" in html

    def test_neutral_color(self):
        try:
            render_badge = self._load()
        except Exception:
            import pytest
            pytest.skip("streamlit unavailable")
        html = render_badge("HOLD", "NEUTRAL")
        assert "#888888" in html

    def test_unknown_is_neutral(self):
        try:
            render_badge = self._load()
        except Exception:
            import pytest
            pytest.skip("streamlit unavailable")
        html = render_badge("x", "ZZZ")
        assert "#888888" in html

    def test_escapes_html(self):
        try:
            render_badge = self._load()
        except Exception:
            import pytest
            pytest.skip("streamlit unavailable")
        html = render_badge("<script>", "NEUTRAL")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
