import streamlit as st
from utils.connections import get_multi_model, get_ticker
from utils.styles import inject_css
from utils.helpers import page_header

inject_css()
mm = get_multi_model()
ticker = get_ticker()

page_header("Multi-Model Analysis", "Compare responses across Bedrock LLMs and synthesize consensus")

if not mm:
    st.error("Multi-model analyzer not configured. Check AWS credentials.")
    st.stop()

q = st.text_input("Question:", placeholder=f"Rate {ticker}'s financial health and outlook")
use_ctx = st.checkbox("Include Snowflake analytics context", True)

if st.button("Run Comparison", type="primary") and q:
    ctx = None
    if use_ctx:
        try:
            from multi_model import get_ticker_context
            ctx = get_ticker_context(ticker)
        except Exception:
            pass

    with st.spinner("Running across models..."):
        r = mm.consensus(q, ctx)

    # ── Model Responses ──────────────────────────────────
    st.markdown("#### Model Responses")
    responses = r.get("responses", {})
    cols = st.columns(len(responses)) if responses else []
    for i, (name, resp) in enumerate(responses.items()):
        with cols[i]:
            success = resp.get("success", False)
            icon = "✅" if success else "❌"
            latency = resp.get("latency_ms", 0)
            st.markdown(f"**{icon} {name}**")
            st.caption(f"{latency}ms")
            if success:
                st.markdown(resp.get("output", "")[:600])
            else:
                st.error(resp.get("error", "Unknown error")[:100])

    # ── Consensus ────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Consensus")
    consensus = r.get("consensus", "N/A")
    st.markdown(f'<div class="consensus-box">{consensus}</div>', unsafe_allow_html=True)

    summary = r.get("summary", {})
    st.caption(
        f"Models: {summary.get('succeeded', 0)}/{summary.get('total_models', 0)} succeeded "
        f"| Fastest: {summary.get('fastest_ms', 'N/A')}ms "
        f"| Slowest: {summary.get('slowest_ms', 'N/A')}ms"
    )
