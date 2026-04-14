"""
FinSage SEC Filing Analysis - Document-level analysis of 10-K and 10-Q filings.

Queries RAW.RAW_SEC_FILING_DOCUMENTS for filing inventory. Falls back to
RAW.RAW_SEC_FILINGS (XBRL data) if no documents are found.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from utils.connections import get_snowflake, render_sidebar
from utils.styles import inject_css, create_plotly_template
from utils.helpers import page_header, require_snowflake, section_header, safe_query, sanitize_ticker, escape_latex, cached_query

inject_css()
ticker = sanitize_ticker(render_sidebar())
session = get_snowflake()
TPL = create_plotly_template()

page_header(f"SEC Filing Analysis -- {ticker}", "Document-level analysis of 10-K and 10-Q filings")
require_snowflake(session)

# ── Try to import document_agent functions ─────────────────────
_agent_available = False
try:
    from document_agent import summarize_filing, analyze_risks, analyze_mda, compare_filings
    _agent_available = True
except ImportError:
    pass
except Exception:
    pass

# ── Load filing documents ──────────────────────────────────────
filing_source = None
df = None

df = cached_query(f"""
    SELECT FILING_ID, FORM_TYPE, FILING_DATE, PERIOD_OF_REPORT,
           COMPANY_NAME, MDA_WORD_COUNT, RISK_WORD_COUNT,
           EXTRACTION_STATUS, DATA_QUALITY_SCORE
    FROM RAW.RAW_SEC_FILING_DOCUMENTS
    WHERE TICKER='{ticker}' ORDER BY FILING_DATE DESC
""")
if df is not None and not df.empty:
    filing_source = "documents"

if df is None or df.empty:
    df = cached_query(f"""
        SELECT DISTINCT CONCEPT, FORM_TYPE, FILED_DATE AS FILING_DATE,
               FISCAL_YEAR, FISCAL_PERIOD, VALUE,
               DATA_QUALITY_SCORE
        FROM RAW.RAW_SEC_FILINGS
        WHERE TICKER='{ticker}' ORDER BY FILED_DATE DESC
        LIMIT 50
    """)
    if df is not None and not df.empty:
        filing_source = "filings"

# ── Display filing inventory ───────────────────────────────────
if df is None or df.empty:
    st.markdown(
        f'<div class="fs-card" style="text-align:center;color:#6b7280">'
        f'No SEC filing data found for {ticker}. Run the data pipeline to load SEC filings.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

if filing_source == "documents":
    st.markdown(
        f'<div class="fs-card fs-card-accent">'
        f'<h4>Filing Documents</h4>'
        f'<div style="color:#f9fafb;font-size:1rem;font-weight:600">{len(df)} document(s)</div>'
        f'<div style="color:#6b7280;font-size:0.8rem">from RAW_SEC_FILING_DOCUMENTS</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Filing timeline visualization
    if "FILING_DATE" in df.columns and "MDA_WORD_COUNT" in df.columns:
        timeline_df = df.dropna(subset=["FILING_DATE"])
        if not timeline_df.empty:
            fig = go.Figure()
            for form_type, color in [("10-K", "#00d4ff"), ("10-Q", "#ffaa00")]:
                mask = timeline_df["FORM_TYPE"] == form_type
                subset = timeline_df[mask]
                if not subset.empty:
                    fig.add_trace(go.Scatter(
                        x=subset["FILING_DATE"],
                        y=subset.get("MDA_WORD_COUNT", [0] * len(subset)),
                        mode="markers",
                        name=form_type,
                        marker=dict(color=color, size=12, line=dict(width=1, color="#1f2937")),
                        hovertemplate="%{x}<br>Words: %{y:,}<extra>" + form_type + "</extra>",
                    ))
            fig.update_layout(**TPL, height=250, title="Filing Timeline (sized by MD&A word count)",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            bgcolor="rgba(0,0,0,0)", font=dict(color="#e5e7eb"), bordercolor="rgba(0,0,0,0)"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.markdown(
        f'<div class="fs-card fs-card-accent">'
        f'<h4>XBRL Filings</h4>'
        f'<div style="color:#f9fafb;font-size:1rem;font-weight:600">{len(df)} record(s)</div>'
        f'<div style="color:#6b7280;font-size:0.8rem">from RAW_SEC_FILINGS (no extracted documents)</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.dataframe(df, use_container_width=True)

# ── Analysis Controls ──────────────────────────────────────────
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("Run Analysis", "Use Snowflake Cortex to analyze filing content")

if not _agent_available:
    st.markdown(
        '<div class="fs-card" style="border-left:3px solid #ffaa00">'
        '<div style="color:#ffaa00;font-weight:600">Document Agent Unavailable</div>'
        '<div style="color:#6b7280;font-size:0.85rem">'
        'Missing dependencies or Snowflake Cortex not available. Filing data is displayed above.'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.stop()

if filing_source == "filings":
    st.markdown(
        '<div class="fs-card" style="border-left:3px solid #00d4ff">'
        '<div style="color:#6b7280;font-size:0.85rem">'
        'Document-level analysis requires extracted filing text (RAW_SEC_FILING_DOCUMENTS). '
        'Only XBRL financial data is available. Run the SEC extraction pipeline to enable full analysis.'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.stop()

c1, c2 = st.columns([1, 3])
with c1:
    mode = st.selectbox("Analysis Mode", [
        "Executive Summary", "Risk Analysis", "MD&A Analysis", "Filing Comparison",
    ])
with c2:
    descriptions = {
        "Executive Summary": "Generate a concise summary of the latest filing.",
        "Risk Analysis": "Analyze risk factors disclosed in the filing.",
        "MD&A Analysis": "Analyze the Management Discussion & Analysis section.",
        "Filing Comparison": "Compare the two most recent filings for changes.",
    }
    st.markdown("")
    st.markdown(f'<div style="color:#6b7280;font-size:0.85rem">{descriptions.get(mode, "")}</div>', unsafe_allow_html=True)

if st.button("Run Analysis", type="primary"):
    fn_map = {
        "Executive Summary": summarize_filing,
        "Risk Analysis": analyze_risks,
        "MD&A Analysis": analyze_mda,
        "Filing Comparison": compare_filings,
    }
    fn = fn_map.get(mode)
    if fn is None:
        st.error(f"Unknown analysis mode: {mode}")
    else:
        with st.spinner(f"Running {mode} for {ticker} via Snowflake Cortex..."):
            try:
                result = fn(session, ticker)
                if result:
                    st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
                    section_header(f"{mode} Results")
                    st.markdown(escape_latex(result))
                else:
                    st.markdown(
                        '<div style="color:#ffaa00;font-size:0.85rem">'
                        'Analysis returned no results. The filing text may be empty or too short.</div>',
                        unsafe_allow_html=True,
                    )
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                st.markdown(
                    '<div style="color:#6b7280;font-size:0.8rem">'
                    'This typically happens when Snowflake Cortex LLM functions are not available '
                    'or the filing text is missing.</div>',
                    unsafe_allow_html=True,
                )
