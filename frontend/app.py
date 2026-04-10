"""
FinSage - AI-Powered Financial Research Platform
Main entry point for the multi-page Streamlit application.

Usage:
    cd frontend
    streamlit run app.py
"""

import streamlit as st
from utils.connections import get_snowflake, get_kb, get_guardrail, get_multi_model
from utils.styles import inject_css

st.set_page_config(
    page_title="FinSage",
    page_icon="https://img.icons8.com/color/48/combo-chart.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ── Sidebar (appears on every page) ─────────────────────────
session = get_snowflake()
kb = get_kb()
guardrail = get_guardrail()
mm = get_multi_model()

with st.sidebar:
    st.markdown("### FinSage")
    st.caption("AI-Powered Financial Research")
    st.markdown("---")

    st.selectbox(
        "Ticker",
        ["AAPL", "MSFT", "GOOGL", "TSLA", "JPM"],
        key="ticker",
    )

    st.markdown("---")
    st.markdown("##### Connections")
    dot_g = '<span class="status-dot green"></span>'
    dot_r = '<span class="status-dot red"></span>'
    st.markdown(f"{dot_g if session else dot_r} Snowflake", unsafe_allow_html=True)
    st.markdown(f"{dot_g if kb else dot_r} Bedrock KB", unsafe_allow_html=True)
    st.markdown(f"{dot_g if guardrail else dot_r} Guardrails", unsafe_allow_html=True)
    st.markdown(f"{dot_g if mm else dot_r} Multi-Model", unsafe_allow_html=True)

    st.markdown("---")
    st.caption("DAMG 7374 - Spring 2026")
    st.caption("Shrirangesh | Raghu | Omkar")

# ── Landing page ─────────────────────────────────────────────
st.markdown('<div class="fs-title">Welcome to FinSage</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="fs-subtitle">AI-Powered Financial Research Report Generator for U.S. Public Companies</div>',
    unsafe_allow_html=True,
)

st.markdown("---")

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        '<div class="fs-card fs-card-accent">'
        "<h4>Data Pipeline</h4>"
        '<div class="value" style="font-size:1.1rem">4 Sources</div>'
        "<p style='color:#64748b;font-size:0.85rem;margin-top:8px'>"
        "Yahoo Finance, NewsAPI, SEC EDGAR, AWS S3 — ingested into Snowflake "
        "with dbt transformations.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        '<div class="fs-card fs-card-accent">'
        "<h4>AI Analysis</h4>"
        '<div class="value" style="font-size:1.1rem">CAVM Pipeline</div>'
        "<p style='color:#64748b;font-size:0.85rem;margin-top:8px'>"
        "Chart generation with VLM refinement, Chain-of-Analysis, "
        "multi-model consensus, and Bedrock Guardrails.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        '<div class="fs-card fs-card-accent">'
        "<h4>Report Generation</h4>"
        '<div class="value" style="font-size:1.1rem">Branded PDF</div>'
        "<p style='color:#64748b;font-size:0.85rem;margin-top:8px'>"
        "15-20 page professional equity research report with charts, "
        "analysis, investment thesis, and risk factors.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

st.markdown("---")
st.info("Use the sidebar to navigate between pages.")
