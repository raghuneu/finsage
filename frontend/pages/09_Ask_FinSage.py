"""FinSage Ask -- Dual-source Q&A with Snowflake Cortex and Bedrock KB."""

import sys
import streamlit as st
from pathlib import Path

from utils.connections import get_snowflake, get_kb, render_sidebar
from utils.styles import inject_css
from utils.helpers import page_header, section_header, sanitize_ticker, esc

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "sec_filings"))
sys.path.insert(0, str(PROJECT_ROOT))

inject_css()
ticker = sanitize_ticker(render_sidebar())
session = get_snowflake()
kb = get_kb()

page_header(f"Ask FinSage -- {ticker}", "Dual-source Q&A: Snowflake Cortex or Bedrock Knowledge Base")

# ── Availability check ──────────────────────────────────────
cortex_available = session is not None
kb_available = kb is not None

if not cortex_available and not kb_available:
    st.markdown(
        '<div class="fs-card fs-card-accent">'
        '<h4>No Data Sources Available</h4>'
        '<div style="color:#6b7280;font-size:0.85rem;line-height:1.6">'
        'Neither Snowflake Cortex nor Bedrock Knowledge Base is configured. '
        'Set Snowflake credentials or <code>BEDROCK_KB_ID</code> in your <code>.env</code> file.'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Source indicators (compact) ────────────────────────────
c1, c2 = st.columns(2)
with c1:
    dot = "green pulse" if cortex_available else "red"
    label = "Connected" if cortex_available else "Not connected"
    st.markdown(
        f'<div class="fs-card" style="padding:12px 16px">'
        f'<span class="status-dot {dot}"></span>'
        f'<span style="color:#f9fafb;font-weight:600;font-size:0.85rem">Snowflake Cortex</span>'
        f' <span style="color:#6b7280;font-size:0.75rem">-- {label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
with c2:
    dot = "green pulse" if kb_available else "red"
    label = "Connected" if kb_available else "Not configured"
    st.markdown(
        f'<div class="fs-card" style="padding:12px 16px">'
        f'<span class="status-dot {dot}"></span>'
        f'<span style="color:#f9fafb;font-weight:600;font-size:0.85rem">Bedrock KB</span>'
        f' <span style="color:#6b7280;font-size:0.75rem">-- {label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Source selector ─────────────────────────────────────────
source_options = []
if cortex_available:
    source_options.append("Snowflake Cortex")
if kb_available:
    source_options.append("Bedrock KB")
if cortex_available and kb_available:
    source_options.append("Both (Side by Side)")

source = st.radio("Select source:", source_options, horizontal=True)

# ── Suggested questions as pills ───────────────────────────
suggestions = [
    f"What is {ticker}'s competitive advantage?",
    f"Summarize {ticker}'s risk factors",
    f"How has {ticker}'s revenue trended?",
    f"Key takeaways from {ticker}'s MD&A?",
]
pills = " ".join(
    f'<span class="pill-btn" style="cursor:default">{s}</span>'
    for s in suggestions
)
st.markdown(f'<div style="margin:8px 0 16px">{pills}</div>', unsafe_allow_html=True)

# ── Chat interface ─────────────────────────────────────────
if "ask_messages" not in st.session_state:
    st.session_state["ask_messages"] = []

# Display history
for msg in st.session_state["ask_messages"]:
    with st.chat_message(msg["role"]):
        if msg.get("source_label"):
            st.markdown(
                f'<span class="pill-btn" style="cursor:default;font-size:0.7rem">{msg["source_label"]}</span>',
                unsafe_allow_html=True,
            )
        st.markdown(msg["content"])
        if msg.get("citations"):
            with st.expander("Citations"):
                for c in msg["citations"]:
                    src = c.get("source", "")
                    name = src.split("/")[-1] if src else "Unknown"
                    st.markdown(f'<div class="citation-box"><strong style="color:#00d4ff">{esc(name)}</strong></div>', unsafe_allow_html=True)

# Chat input
if q := st.chat_input(f"Ask about {ticker}..."):
    st.session_state["ask_messages"].append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)

    # ── Cortex response ────────────────────────────────
    if source in ("Snowflake Cortex", "Both (Side by Side)"):
        with st.chat_message("assistant"):
            st.markdown('<span class="pill-btn" style="cursor:default;font-size:0.7rem">Cortex</span>', unsafe_allow_html=True)
            with st.spinner("Analyzing with Cortex..."):
                try:
                    from document_agent import ask_question
                    answer = ask_question(session, ticker, q)
                    st.markdown(answer)
                    st.session_state["ask_messages"].append({
                        "role": "assistant", "content": answer, "source_label": "Cortex",
                    })
                except ImportError:
                    err = "Could not import document_agent."
                    st.error(err)
                    st.session_state["ask_messages"].append({"role": "assistant", "content": err, "source_label": "Cortex"})
                except Exception as e:
                    err = f"Cortex query failed: {e}"
                    st.error(err)
                    st.session_state["ask_messages"].append({"role": "assistant", "content": err, "source_label": "Cortex"})

    # ── Bedrock KB response ────────────────────────────
    if source in ("Bedrock KB", "Both (Side by Side)"):
        with st.chat_message("assistant"):
            st.markdown('<span class="pill-btn" style="cursor:default;font-size:0.7rem">Bedrock KB</span>', unsafe_allow_html=True)
            with st.spinner("Searching Knowledge Base..."):
                try:
                    r = kb.ask(q, ticker=ticker)
                    answer = r.get("answer", "No answer returned.")
                    citations = r.get("citations", [])
                    st.markdown(answer)
                    if citations:
                        with st.expander("Citations"):
                            for c in citations:
                                src = c.get("source", "")
                                name = src.split("/")[-1] if src else "Unknown"
                                st.markdown(f'<div class="citation-box"><strong style="color:#00d4ff">{esc(name)}</strong></div>', unsafe_allow_html=True)
                    st.session_state["ask_messages"].append({
                        "role": "assistant", "content": answer,
                        "source_label": "Bedrock KB", "citations": citations,
                    })
                except Exception as e:
                    err = f"Knowledge Base query failed: {e}"
                    st.error(err)
                    st.session_state["ask_messages"].append({"role": "assistant", "content": err, "source_label": "Bedrock KB"})

if not st.session_state["ask_messages"]:
    st.markdown(
        '<div style="text-align:center;color:#4b5563;padding:40px 0">'
        f'Ask a question about {ticker} to get started</div>',
        unsafe_allow_html=True,
    )

# Clear chat
if st.session_state["ask_messages"]:
    if st.button("Clear Chat", key="clear_ask"):
        st.session_state["ask_messages"] = []
        st.rerun()
