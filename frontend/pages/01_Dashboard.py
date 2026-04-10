import streamlit as st
from utils.connections import get_snowflake, get_ticker
from utils.styles import inject_css
from utils.helpers import page_header, signal_html, fmt_money, metric_card, require_snowflake

inject_css()
session = get_snowflake()
ticker = get_ticker()

page_header(f"Dashboard — {ticker}", "Real-time company metrics and market signals")
require_snowflake(session)

from document_agent import get_company_intelligence

intel = get_company_intelligence(session, ticker)
p = intel.get("profile", {})
s = intel.get("stock", {})
f = intel.get("fundamentals", {})
sent = intel.get("sentiment", {})
sf = intel.get("sec_financials", {})

# ── Key Metrics ──────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    metric_card("Market Cap", fmt_money(p.get("market_cap")))
with c2:
    price = s.get("close", 0)
    ret = s.get("daily_return_pct", 0)
    metric_card("Price", f"${price:.2f}", f"{ret:+.2f}%")
with c3:
    rev = f.get("revenue")
    yoy = f.get("revenue_growth_yoy_pct", 0)
    metric_card("Revenue", fmt_money(rev), f"{yoy:+.1f}% YoY" if yoy else None)
with c4:
    score = sent.get("sentiment_score", 0)
    trend = sent.get("sentiment_trend", "")
    metric_card("Sentiment", f"{score:.3f}", trend)
with c5:
    pe = p.get("pe_ratio")
    metric_card("P/E Ratio", f"{pe:.1f}" if pe else "N/A")

st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)

# ── Signals ──────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown("**Stock Trend**")
    st.markdown(signal_html(s.get("trend_signal", "N/A")), unsafe_allow_html=True)
with c2:
    st.markdown("**Fundamentals**")
    st.markdown(signal_html(f.get("fundamental_signal", "N/A")), unsafe_allow_html=True)
with c3:
    st.markdown("**Sentiment**")
    st.markdown(signal_html(sent.get("sentiment_label", "N/A")), unsafe_allow_html=True)
with c4:
    st.markdown("**Financial Health**")
    st.markdown(signal_html(sf.get("financial_health", "N/A")), unsafe_allow_html=True)

# ── Headlines ────────────────────────────────────────────────
headlines = intel.get("recent_headlines", [])
if headlines:
    st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
    st.markdown("#### Recent Headlines")
    for h in headlines[:8]:
        emoji = {"positive": "🟢", "negative": "🔴"}.get(h.get("sentiment"), "🟡")
        st.markdown(f"{emoji} {h['title'][:140]}")
