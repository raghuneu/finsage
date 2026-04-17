"""
FinSage RAG Search - Semantic search over SEC filings via Bedrock Knowledge Base.

Three tabs: Ask (chat-style Q&A with citations), Cross-Ticker (comparative analysis),
and Raw Chunks (direct vector retrieval).
"""

import streamlit as st

from utils.connections import get_kb, render_sidebar
from utils.styles import inject_css
from utils.helpers import page_header, section_header, sanitize_ticker, esc, escape_latex

inject_css()
ticker = sanitize_ticker(render_sidebar())
kb = get_kb()

page_header("RAG Search", "Semantic search over SEC filings via Bedrock Knowledge Base")

# ── Check KB availability ───────────────────────────────────
if kb is None:
    st.markdown(
        '<div class="fs-card fs-card-accent">'
        '<h4>Bedrock Knowledge Base Not Configured</h4>'
        '<div style="color:#6b7280;font-size:0.9rem;margin-top:8px">'
        '<p>To enable RAG Search, configure the following in your <code>.env</code> file:</p>'
        '<ul style="line-height:2">'
        '<li><code>BEDROCK_KB_ID</code> -- Your Bedrock Knowledge Base ID</li>'
        '<li><code>AWS_ACCESS_KEY_ID</code> / <code>AWS_SECRET_ACCESS_KEY</code></li>'
        '<li><code>AWS_DEFAULT_REGION</code> -- e.g., us-east-1</li>'
        '</ul>'
        '<p>Restart the Streamlit app after configuring.</p>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Tabs ───────────────────────────────────────────────────────
t1, t2, t3 = st.tabs(["Ask", "Cross-Ticker", "Raw Chunks"])

# ── Tab 1: Ask (Chat interface) ───────────────────────────────
with t1:
    section_header("Ask about SEC Filings", "AI-powered answers with citations from filing documents")

    # Initialize chat history
    if "rag_chat" not in st.session_state:
        st.session_state["rag_chat"] = []

    # Display chat history
    for msg in st.session_state["rag_chat"]:
        with st.chat_message(msg["role"]):
            st.markdown(escape_latex(msg["content"]))
            if msg.get("citations"):
                with st.expander("Citations", expanded=False):
                    for c in msg["citations"]:
                        source = c.get("source", "")
                        source_name = source.split("/")[-1] if source else "Unknown source"
                        text_snippet = c.get("text", "")[:200]
                        snippet_html = f'<br><span style="color:#6b7280;font-size:0.8rem">{esc(text_snippet)}...</span>' if text_snippet else ""
                        st.markdown(
                            f'<div class="citation-box">'
                            f'<strong style="color:#00d4ff">{esc(source_name)}</strong>'
                            f'{snippet_html}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

    # Chat input (handle prefill from suggestion pills)
    _prefill = st.session_state.pop("_rag_prefill", None)
    q = st.chat_input(f"Ask about {ticker}'s SEC filings...")
    if _prefill:
        q = _prefill
    if q:
        # Add user message
        st.session_state["rag_chat"].append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)

        # Get response
        with st.chat_message("assistant"):
            with st.spinner("Searching Knowledge Base..."):
                try:
                    r = kb.ask(q, ticker=ticker)
                    answer = r.get("answer", "No answer was generated. Try rephrasing your question.")
                    citations = r.get("citations", [])

                    st.markdown(escape_latex(answer))

                    if citations:
                        with st.expander("Citations", expanded=False):
                            for c in citations:
                                source = c.get("source", "")
                                source_name = source.split("/")[-1] if source else "Unknown source"
                                text_snippet = c.get("text", "")[:200]
                                snippet_html = f'<br><span style="color:#6b7280;font-size:0.8rem">{esc(text_snippet)}...</span>' if text_snippet else ""
                                st.markdown(
                                    f'<div class="citation-box">'
                                    f'<strong style="color:#00d4ff">{esc(source_name)}</strong>'
                                    f'{snippet_html}'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )

                    st.session_state["rag_chat"].append({
                        "role": "assistant",
                        "content": answer,
                        "citations": citations,
                    })
                except Exception as e:
                    err = f"Knowledge Base query failed: {e}"
                    st.error(err)
                    st.session_state["rag_chat"].append({"role": "assistant", "content": err})

    if not st.session_state["rag_chat"]:
        st.markdown(
            '<div style="text-align:center;color:#4b5563;padding:24px 0 8px">'
            f'Ask a question about {esc(ticker)}\'s SEC filings to get started</div>',
            unsafe_allow_html=True,
        )
        # Clickable suggestion pills
        suggestions = [
            f"What are {ticker}'s key risk factors?",
            f"Summarize {ticker}'s revenue growth",
            f"What does {ticker}'s MD&A discuss?",
        ]
        pill_cols = st.columns(len(suggestions))
        for i, (col, s) in enumerate(zip(pill_cols, suggestions)):
            with col:
                if st.button(s, key=f"rag_suggest_{i}", use_container_width=True):
                    st.session_state["_rag_prefill"] = s
                    st.rerun()

    # Clear chat button
    if st.session_state["rag_chat"]:
        if st.button("Clear Chat", key="clear_rag"):
            st.session_state["rag_chat"] = []
            st.rerun()

# ── Tab 2: Cross-Ticker ───────────────────────────────────────
with t2:
    section_header("Cross-Ticker Analysis", "Compare disclosures across multiple companies")

    q = st.text_input(
        "Comparison question:",
        placeholder="How do companies discuss AI strategy?",
        key="rag_cross",
    )
    if q:
        with st.spinner("Analyzing across tickers..."):
            try:
                r = kb.cross_ticker_analysis(q)
                tickers_found = r.get("tickers_found", [])
                analysis = r.get("analysis", "")

                if tickers_found:
                    pills = " ".join(f'<span class="pill-btn" style="cursor:default">{esc(t)}</span>' for t in tickers_found)
                    st.markdown(f'<div style="margin-bottom:12px">Tickers found: {pills}</div>', unsafe_allow_html=True)

                if analysis:
                    st.markdown(escape_latex(analysis))
                else:
                    st.markdown('<div style="color:#6b7280">No cross-ticker analysis was generated.</div>', unsafe_allow_html=True)

                per_ticker = r.get("per_ticker", {})
                if per_ticker:
                    st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
                    for t, detail in per_ticker.items():
                        with st.expander(f"Details for {t}"):
                            st.markdown(detail if isinstance(detail, str) else str(detail))

            except Exception as e:
                st.error(f"Cross-ticker analysis failed: {e}")

# ── Tab 3: Raw Chunks ─────────────────────────────────────────
with t3:
    section_header("Raw Chunk Retrieval", "Retrieve matching text chunks from the vector store")

    q = st.text_input(
        "Search query:",
        placeholder="revenue growth drivers",
        key="rag_chunks",
    )
    if q:
        with st.spinner("Retrieving chunks..."):
            try:
                chunks = kb.retrieve(q, ticker=ticker)

                if not chunks:
                    st.markdown('<div style="color:#6b7280">No matching chunks found. Try broadening your search.</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f"**{len(chunks)} chunk(s) retrieved**")
                    for i, c in enumerate(chunks, 1):
                        chunk_ticker = c.get("ticker", "")
                        section = c.get("section", "")
                        score = c.get("score", 0)
                        source = c.get("source", "")
                        source_name = source.split("/")[-1] if source else "Unknown"
                        text = c.get("text", "")

                        # Relevance bar
                        bar_pct = min(score * 100, 100) if isinstance(score, (int, float)) else 0
                        bar_color = "#00ff88" if bar_pct > 60 else "#ffaa00" if bar_pct > 30 else "#ff3366"

                        header = f"Chunk {i}"
                        if chunk_ticker:
                            header += f" -- {chunk_ticker}"
                        if section:
                            header += f" / {section}"
                        header += f" (score: {score:.3f})" if isinstance(score, (int, float)) else f" (score: {score})"

                        with st.expander(header):
                            st.markdown(
                                f'<div style="height:4px;border-radius:2px;background:#1f2937;margin-bottom:8px">'
                                f'<div style="height:4px;border-radius:2px;background:{bar_color};width:{bar_pct}%"></div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                            st.markdown(f"**Source:** `{source_name}`")
                            st.text(text[:2000] if text else "No text available")

            except Exception as e:
                st.error(f"Chunk retrieval failed: {e}")
