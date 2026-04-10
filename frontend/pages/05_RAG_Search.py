import streamlit as st
from utils.connections import get_kb, get_ticker
from utils.styles import inject_css
from utils.helpers import page_header, require_kb

inject_css()
kb = get_kb()
ticker = get_ticker()

page_header("RAG Search", "Semantic search over SEC filings via Bedrock Knowledge Base")
require_kb(kb)

t1, t2, t3 = st.tabs(["Ask", "Cross-Ticker", "Raw Chunks"])

with t1:
    q = st.text_input("Ask about SEC filings:", placeholder=f"What are {ticker}'s main risk factors?", key="rag_ask")
    if q:
        with st.spinner("Searching Knowledge Base..."):
            r = kb.ask(q, ticker=ticker)
            st.markdown(r["answer"])
            if r.get("citations"):
                st.markdown("**Citations:**")
                for c in r["citations"]:
                    source = c.get("source", "").split("/")[-1]
                    st.markdown(f'<div class="citation-box">📄 {source}</div>', unsafe_allow_html=True)

with t2:
    q = st.text_input("Compare companies:", placeholder="How do companies discuss AI strategy?", key="rag_cross")
    if q:
        with st.spinner("Analyzing across tickers..."):
            r = kb.cross_ticker_analysis(q)
            st.markdown(f"**Tickers found:** {', '.join(r.get('tickers_found', []))}")
            st.markdown(r.get("analysis", ""))

with t3:
    q = st.text_input("Retrieve raw chunks:", placeholder="revenue growth drivers", key="rag_chunks")
    if q:
        with st.spinner("Retrieving..."):
            chunks = kb.retrieve(q, ticker=ticker)
            if not chunks:
                st.info("No matching chunks found.")
            for i, c in enumerate(chunks, 1):
                with st.expander(f"Chunk {i} — {c.get('ticker', '')} {c.get('section', '')} (score: {c.get('score', 0):.3f})"):
                    st.markdown(f"**Source:** `{c.get('source', '').split('/')[-1]}`")
                    st.text(c.get("text", "")[:1000])
