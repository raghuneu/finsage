import streamlit as st
from utils.connections import get_snowflake, get_ticker
from utils.styles import inject_css
from utils.helpers import page_header, require_snowflake, section_header

inject_css()
session = get_snowflake()
ticker = get_ticker()

page_header(f"SEC Filing Analysis — {ticker}", "Document-level analysis of 10-K and 10-Q filings")
require_snowflake(session)

try:
    df = session.sql(f"""
        SELECT FILING_ID, FORM_TYPE, FILING_DATE, PERIOD_OF_REPORT,
               COMPANY_NAME, MDA_WORD_COUNT, RISK_WORD_COUNT,
               EXTRACTION_STATUS, DATA_QUALITY_SCORE
        FROM RAW.RAW_SEC_FILING_DOCUMENTS
        WHERE TICKER='{ticker}' ORDER BY FILING_DATE DESC
    """).to_pandas()

    if df.empty:
        st.info(f"No SEC filing documents found for {ticker}.")
        st.stop()

    st.markdown(f"**{len(df)} filings** found for {ticker}")
    st.dataframe(df, use_container_width=True)

    st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
    section_header("Run Analysis")

    c1, c2 = st.columns([1, 3])
    with c1:
        mode = st.selectbox("Analysis Mode", [
            "Executive Summary",
            "Risk Analysis",
            "MD&A Analysis",
            "Filing Comparison",
        ])
    with c2:
        st.markdown("")  # spacing
        if st.button("Run Analysis", type="primary"):
            with st.spinner(f"Running {mode} for {ticker}..."):
                from document_agent import summarize_filing, analyze_risks, analyze_mda, compare_filings
                fn_map = {
                    "Executive Summary": summarize_filing,
                    "Risk Analysis": analyze_risks,
                    "MD&A Analysis": analyze_mda,
                    "Filing Comparison": compare_filings,
                }
                result = fn_map[mode](session, ticker)
                st.markdown("---")
                st.markdown(result)

except Exception as e:
    st.error(f"Error loading filings: {e}")
