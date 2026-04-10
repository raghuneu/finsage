import streamlit as st
from utils.connections import get_snowflake, get_kb, get_ticker
from utils.styles import inject_css
from utils.helpers import page_header

inject_css()
session = get_snowflake()
kb = get_kb()
ticker = get_ticker()

page_header(f"Ask FinSage — {ticker}", "Dual-source Q&A: Snowflake Cortex or Bedrock Knowledge Base")

source = st.radio(
    "Select source:",
    ["Snowflake Cortex (Analytics + Filing)", "Bedrock KB (RAG)"],
    horizontal=True,
)

q = st.text_input("Your question:", placeholder=f"What is {ticker}'s competitive advantage?")

if st.button("Ask", type="primary") and q:
    if source.startswith("Snowflake"):
        if not session:
            st.error("Snowflake not connected.")
            st.stop()
        with st.spinner("Analyzing with Cortex..."):
            from document_agent import ask_question
            answer = ask_question(session, ticker, q)
            st.markdown("---")
            st.markdown(answer)
    else:
        if not kb:
            st.error("Set `BEDROCK_KB_ID` in .env to enable RAG.")
            st.stop()
        with st.spinner("Searching Knowledge Base..."):
            r = kb.ask(q, ticker=ticker)
            st.markdown("---")
            st.markdown(r["answer"])
            if r.get("citations"):
                st.markdown("**Citations:**")
                for c in r["citations"]:
                    source_file = c.get("source", "").split("/")[-1]
                    st.markdown(
                        f'<div class="citation-box">📄 {source_file}</div>',
                        unsafe_allow_html=True,
                    )
