import time
import streamlit as st
from utils.connections import get_snowflake, get_ticker
from utils.styles import inject_css
from utils.helpers import page_header, require_snowflake

inject_css()
session = get_snowflake()
ticker = get_ticker()

page_header(f"Research Report — {ticker}", "Generate a comprehensive 7-section financial research report")
require_snowflake(session)

st.markdown(
    '<div class="fs-card">'
    "<h4>Report Sections</h4>"
    "<p style='color:#0f172a;font-size:0.9rem;line-height:1.8'>"
    "1. Executive Summary &nbsp;&bull;&nbsp; "
    "2. Financial Performance &nbsp;&bull;&nbsp; "
    "3. Stock Analysis &nbsp;&bull;&nbsp; "
    "4. Sentiment &nbsp;&bull;&nbsp; "
    "5. Risk Factors &nbsp;&bull;&nbsp; "
    "6. Management Credibility &nbsp;&bull;&nbsp; "
    "7. Forward Outlook"
    "</p></div>",
    unsafe_allow_html=True,
)

st.markdown("")

if st.button("Generate Full Report", type="primary"):
    with st.spinner(f"Generating report for {ticker}... this may take 30-60 seconds."):
        from document_agent import full_report
        start = time.time()
        result = full_report(session, ticker)
        elapsed = time.time() - start

    st.success(f"Report generated in {elapsed:.1f}s")
    st.markdown("---")
    st.markdown(result)

    st.download_button(
        label="Download as Markdown",
        data=result,
        file_name=f"{ticker}_research_report.md",
        mime="text/markdown",
    )
