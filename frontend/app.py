"""
FinSage - AI-Powered Financial Research Platform
Main entry point for the multi-page Streamlit application.

Usage:
    cd frontend
    streamlit run app.py
"""

import streamlit as st
from utils.connections import get_snowflake, load_tickers, render_sidebar
from utils.styles import inject_css
from utils.helpers import metric_card, section_header

st.set_page_config(
    page_title="FinSage",
    page_icon="https://img.icons8.com/color/48/combo-chart.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ── Shared sidebar (ticker selector + connection indicators) ──
render_sidebar()
session = get_snowflake()
tickers = load_tickers()

# ── Landing page ─────────────────────────────────────────────
st.markdown(
    '<div style="text-align:center;padding:40px 0 20px 0">'
    '<div style="font-size:3rem;font-weight:800;line-height:1.1">'
    '<span style="color:#f9fafb">Fin</span>'
    '<span style="color:#00d4ff">Sage</span>'
    '</div>'
    '<div style="color:#6b7280;font-size:1.1rem;margin-top:8px">'
    'AI-Powered Financial Research Report Generator for U.S. Public Companies'
    '</div>'
    '<div style="height:2px;max-width:200px;margin:20px auto 0;'
    'background:linear-gradient(90deg,transparent,#00d4ff,transparent)"></div>'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown("")

# Architecture overview cards
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        '<div class="fs-card fs-card-accent">'
        '<h4>Data Pipeline</h4>'
        '<div class="value" style="font-size:1.3rem">4 Sources</div>'
        '<p style="color:#6b7280;font-size:0.85rem;margin-top:8px">'
        'Yahoo Finance, NewsAPI, SEC EDGAR, AWS S3 &mdash; ingested into Snowflake '
        'with dbt transformations across RAW, STAGING, and ANALYTICS layers.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        '<div class="fs-card fs-card-accent">'
        '<h4>AI Analysis</h4>'
        '<div class="value" style="font-size:1.3rem">CAVM Pipeline</div>'
        '<p style="color:#6b7280;font-size:0.85rem;margin-top:8px">'
        'Chart generation with VLM refinement, Chain-of-Analysis, '
        'multi-model consensus, and Bedrock Guardrails for content safety.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        '<div class="fs-card fs-card-accent">'
        '<h4>Report Generation</h4>'
        '<div class="value" style="font-size:1.3rem">Branded PDF</div>'
        '<p style="color:#6b7280;font-size:0.85rem;margin-top:8px">'
        '15-20 page professional equity research report with charts, '
        'investment thesis, risk factors, and SEC filing analysis.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)

# Quick stats if Snowflake is connected
if session:
    section_header("Platform Overview", "Live data from Snowflake warehouse")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        try:
            cnt = session.sql("SELECT COUNT(DISTINCT TICKER) AS c FROM ANALYTICS.DIM_COMPANY").collect()[0]["C"]
            metric_card("Companies Tracked", str(cnt))
        except Exception:
            metric_card("Companies Tracked", str(len(tickers)))
    with c2:
        try:
            cnt = session.sql("SELECT COUNT(*) AS c FROM RAW.RAW_STOCK_PRICES").collect()[0]["C"]
            metric_card("Stock Prices", f"{cnt:,}")
        except Exception:
            metric_card("Stock Prices", "N/A")
    with c3:
        try:
            cnt = session.sql("SELECT COUNT(*) AS c FROM RAW.RAW_SEC_FILINGS").collect()[0]["C"]
            metric_card("SEC Records", f"{cnt:,}")
        except Exception:
            metric_card("SEC Records", "N/A")
    with c4:
        try:
            cnt = session.sql("SELECT COUNT(*) AS c FROM RAW.RAW_NEWS").collect()[0]["C"]
            metric_card("News Articles", f"{cnt:,}")
        except Exception:
            metric_card("News Articles", "N/A")
else:
    st.markdown(
        '<div class="fs-card" style="border-left:3px solid #ffaa00">'
        '<div style="color:#ffaa00;font-weight:600;margin-bottom:4px">Snowflake Not Connected</div>'
        '<div style="color:#6b7280;font-size:0.85rem">'
        'Check your .env credentials to enable full functionality. '
        'Navigate to System Status for diagnostics.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown("")
st.markdown(
    '<div style="text-align:center;color:#4b5563;font-size:0.85rem;padding:20px 0">'
    'Select a page from the sidebar to get started</div>',
    unsafe_allow_html=True,
)
