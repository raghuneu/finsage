"""FinSage Multi-Model Analysis -- Compare responses across Bedrock LLMs."""

import sys
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path

from utils.connections import get_multi_model, get_ticker, load_tickers
from utils.styles import inject_css, create_plotly_template
from utils.helpers import page_header, section_header, metric_card, sanitize_ticker

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "sec_filings"))
sys.path.insert(0, str(PROJECT_ROOT))

inject_css()
mm = get_multi_model()
ticker = sanitize_ticker(get_ticker())
TPL = create_plotly_template()

page_header("Multi-Model Analysis", "Compare responses across Bedrock LLMs and synthesize consensus")

if not mm:
    st.markdown(
        '<div class="fs-card fs-card-accent">'
        '<h4>Multi-Model Analyzer Not Configured</h4>'
        '<div style="color:#6b7280;font-size:0.85rem;line-height:1.6">'
        'Requires valid AWS credentials with Bedrock access. '
        'Set <code>AWS_ACCESS_KEY_ID</code>, <code>AWS_SECRET_ACCESS_KEY</code>, '
        'and <code>AWS_DEFAULT_REGION</code> in your <code>.env</code> file.'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Model info ──────────────────────────────────────────────
with st.expander("Configured Models", expanded=False):
    for model in mm.models:
        short_name = model.split(".")[-1].split("-v")[0]
        st.markdown(f'<span class="status-dot green pulse"></span> `{short_name}` ({model})', unsafe_allow_html=True)

# ── Input ───────────────────────────────────────────────────
q = st.text_input("Question:", placeholder=f"Rate {ticker}'s financial health and outlook")

col1, col2 = st.columns([1, 1])
with col1:
    use_ctx = st.checkbox("Include Snowflake analytics context", value=True)
with col2:
    mode = st.radio("Mode:", ["Consensus (with synthesis)", "Compare only"], horizontal=True)

if st.button("Run Comparison", type="primary") and q:

    ctx = None
    if use_ctx:
        with st.spinner("Loading analytics context..."):
            try:
                from multi_model import get_ticker_context
                ctx = get_ticker_context(ticker)
                if ctx:
                    st.caption(f"Analytics context loaded ({len(ctx)} chars)")
            except Exception:
                st.caption("Proceeding without analytics context")

    with st.spinner(f"Running analysis across {len(mm.models)} models..."):
        try:
            r = mm.consensus(q, ctx) if mode.startswith("Consensus") else mm.compare(q, ctx)
        except Exception as e:
            st.error(f"Multi-model analysis failed: {e}")
            st.stop()

    # ── Model Responses ─────────────────────────────────────
    section_header("Model Responses")

    responses = r.get("responses", {})
    if not responses:
        st.markdown('<div style="color:#ffaa00">No model responses received.</div>', unsafe_allow_html=True)
        st.stop()

    # Color per model
    model_colors = ["#00d4ff", "#00ff88", "#ffaa00", "#ff3366", "#a78bfa", "#f472b6"]
    cols = st.columns(len(responses))
    for i, (name, resp) in enumerate(responses.items()):
        color = model_colors[i % len(model_colors)]
        with cols[i]:
            success = resp.get("success", False)
            latency = resp.get("latency_ms", 0)
            dot = "green" if success else "red"
            st.markdown(
                f'<div class="fs-card" style="border-top:3px solid {color}">'
                f'<h4><span class="status-dot {dot}"></span> {name}</h4>'
                f'<div style="color:#4b5563;font-size:0.75rem;margin-bottom:8px">{latency:,}ms</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if success:
                st.markdown(resp.get("output", "")[:800])
            else:
                st.markdown(f'<div style="color:#ff3366;font-size:0.85rem">{resp.get("error", "Unknown error")[:200]}</div>', unsafe_allow_html=True)

    # ── Consensus ───────────────────────────────────────────
    consensus_text = r.get("consensus")
    if consensus_text:
        st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
        section_header("Consensus Analysis")
        st.markdown(f'<div class="consensus-box">{consensus_text}</div>', unsafe_allow_html=True)

    # ── Performance Summary ─────────────────────────────────
    st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
    section_header("Performance Summary")

    summary = r.get("summary", {})
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        succeeded = summary.get("succeeded", 0)
        total = summary.get("total_models", 0)
        metric_card("Models", f"{succeeded}/{total}")
    with c2:
        fastest = summary.get("fastest_ms")
        metric_card("Fastest", f"{fastest:,}ms" if fastest else "N/A")
    with c3:
        slowest = summary.get("slowest_ms")
        metric_card("Slowest", f"{slowest:,}ms" if slowest else "N/A")
    with c4:
        failed_count = summary.get("failed", 0)
        metric_card("Failed", str(failed_count))

    # ── Plotly latency bar ─────────────────────────────────
    latency_data = {
        name: resp.get("latency_ms", 0)
        for name, resp in responses.items()
        if resp.get("success")
    }
    if latency_data:
        names = list(latency_data.keys())
        values = list(latency_data.values())
        colors = [model_colors[i % len(model_colors)] for i in range(len(names))]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=names, x=values, orientation="h",
            marker_color=colors,
            text=[f"{v:,}ms" for v in values],
            textposition="auto",
            textfont=dict(color="#e5e7eb"),
        ))
        fig.update_layout(**TPL, height=max(200, len(names) * 50),
            title="Response Latency (ms)", showlegend=False,
            yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
