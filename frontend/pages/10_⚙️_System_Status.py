"""FinSage System Status -- Health checks for all connected services."""

import os
import sys
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path

from utils.connections import get_snowflake, get_kb, get_guardrail, get_multi_model, load_tickers, render_sidebar
from utils.styles import inject_css, create_plotly_template
from utils.helpers import page_header, section_header, health_card, metric_card, esc

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "sec_filings"))
sys.path.insert(0, str(PROJECT_ROOT))

inject_css()
render_sidebar()
session = get_snowflake()
kb = get_kb()
guardrail = get_guardrail()
mm = get_multi_model()
TPL = create_plotly_template()

page_header("System Status", "Health checks for all connected services and integrations")

# ── Pre-check AWS ──────────────────────────────────────────
aws_identity = None
try:
    import boto3
    sts = boto3.client("sts")
    aws_identity = sts.get_caller_identity()
except Exception:
    pass

# ── Overall status banner ──────────────────────────────────
services = {
    "Snowflake": session is not None,
    "AWS": aws_identity is not None,
    "Bedrock KB": kb is not None,
    "Guardrails": guardrail is not None,
    "Multi-Model": mm is not None,
}
total = len(services)
healthy = sum(1 for v in services.values() if v)

if healthy == total:
    status_color = "#00ff88"
    status_label = "All Systems Operational"
    dot_cls = "green pulse"
elif healthy >= 2:
    status_color = "#ffaa00"
    status_label = f"{healthy}/{total} Services Connected"
    dot_cls = "amber"
else:
    status_color = "#ff3366"
    status_label = f"Only {healthy}/{total} Services Connected"
    dot_cls = "red"

st.markdown(
    f'<div class="fs-card" style="text-align:center;padding:24px;border-top:3px solid {status_color}">'
    f'<span class="status-dot {dot_cls}" style="width:12px;height:12px"></span>'
    f'<span style="color:{status_color};font-size:1.3rem;font-weight:700;margin-left:8px">{status_label}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown("")

# ═══════════════════════════════════════════════════════════
# Service Health Cards — 3x2 grid
# ═══════════════════════════════════════════════════════════
c1, c2, c3 = st.columns(3)

with c1:
    if session:
        try:
            import time as _t
            _t0 = _t.time()
            info = session.sql(
                "SELECT CURRENT_USER() u, CURRENT_ROLE() r, "
                "CURRENT_WAREHOUSE() w, CURRENT_DATABASE() d"
            ).collect()[0]
            _ms = int((_t.time() - _t0) * 1000)
            detail = f"User: {info['U']} | Role: {info['R']} | DB: {info['D']} | {_ms}ms"
        except Exception:
            detail = "Connected"
        health_card("Snowflake", "healthy", detail)
    else:
        health_card("Snowflake", "down", "Check .env credentials")

with c2:
    if aws_identity:
        health_card("AWS", "healthy", f"Account: {aws_identity['Account']}")
    else:
        health_card("AWS", "down", "Set AWS credentials in .env")

with c3:
    if kb:
        kb_id = os.getenv("BEDROCK_KB_ID", "N/A")
        health_card("Bedrock KB", "healthy", f"KB ID: {kb_id[:20]}{'...' if len(kb_id) > 20 else ''}")
    else:
        kb_id = os.getenv("BEDROCK_KB_ID", "")
        if kb_id:
            health_card("Bedrock KB", "degraded", "ID set but init failed")
        else:
            health_card("Bedrock KB", "down", "Set BEDROCK_KB_ID in .env")

c4, c5, c6 = st.columns(3)

with c4:
    if guardrail:
        health_card("Guardrails", "healthy", f"ID: {esc(str(guardrail.guardrail_id))}")
    else:
        health_card("Guardrails", "down", "Set BEDROCK_GUARDRAIL_ID in .env")

with c5:
    if mm:
        health_card("Multi-Model", "healthy", f"{len(mm.models)} models configured")
    else:
        health_card("Multi-Model", "down", "Check AWS Bedrock access")

with c6:
    bucket = os.getenv("FINSAGE_S3_BUCKET", "")
    if bucket and aws_identity:
        health_card("S3 Storage", "healthy", f"Bucket: {bucket}")
    elif bucket:
        health_card("S3 Storage", "degraded", "Bucket set, AWS not valid")
    else:
        health_card("S3 Storage", "down", "Set FINSAGE_S3_BUCKET in .env")

# ═══════════════════════════════════════════════════════════
# Data Table Coverage — Plotly Treemap
# ═══════════════════════════════════════════════════════════
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("Data Table Coverage", "Row counts across all Snowflake layers")

if session:
    table_data = []
    all_tables = {
        "RAW": ["RAW_STOCK_PRICES", "RAW_FUNDAMENTALS", "RAW_NEWS", "RAW_SEC_FILINGS", "RAW_SEC_FILING_DOCUMENTS"],
        "STAGING": ["STG_STOCK_PRICES", "STG_FUNDAMENTALS", "STG_NEWS", "STG_SEC_FILINGS"],
        "ANALYTICS": ["DIM_COMPANY", "FCT_STOCK_METRICS", "FCT_FUNDAMENTALS_GROWTH", "FCT_NEWS_SENTIMENT_AGG", "FCT_SEC_FINANCIAL_SUMMARY"],
    }

    labels = ["FINSAGE_DB"]
    parents = [""]
    values = [0]
    colors = ["#0a0e17"]

    schema_colors = {"RAW": "#0c4a6e", "STAGING": "#3a2e05", "ANALYTICS": "#064e3b"}

    for schema, tables in all_tables.items():
        labels.append(schema)
        parents.append("FINSAGE_DB")
        values.append(0)
        colors.append(schema_colors[schema])

        for table in tables:
            try:
                cnt = session.sql(f"SELECT COUNT(*) AS c FROM {schema}.{table}").collect()[0]["C"]
            except Exception:
                cnt = 0
            labels.append(table)
            parents.append(schema)
            values.append(max(cnt, 1))  # min 1 for visibility
            colors.append(schema_colors[schema] if cnt > 0 else "#374151")

    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=parents,
        values=values,
        marker=dict(colors=colors, line=dict(width=1, color="#0a0e17")),
        textfont=dict(color="#f9fafb"),
        hovertemplate="<b>%{label}</b><br>Rows: %{value:,}<extra></extra>",
        branchvalues="remainder",
    ))
    fig.update_layout(
        paper_bgcolor="#0a0e17",
        plot_bgcolor="#0a0e17",
        margin=dict(l=4, r=4, t=4, b=4),
        height=350,
        font=dict(color="#e5e7eb"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.markdown(
        '<div class="fs-card" style="text-align:center;color:#6b7280">'
        'Connect to Snowflake to view data coverage.</div>',
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════
# Snowflake Cortex
# ═══════════════════════════════════════════════════════════
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("Snowflake Cortex")

if session:
    c_llm, c_vlm, c_sum = st.columns(3)
    with c_llm:
        try:
            import time as _t
            _t0 = _t.time()
            session.sql("SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large', 'Reply with only OK') AS result").collect()
            _ms = int((_t.time() - _t0) * 1000)
            st.markdown(f'<span class="status-dot green pulse"></span> **mistral-large** -- responding ({_ms}ms)', unsafe_allow_html=True)
        except Exception as e:
            st.markdown(f'<span class="status-dot red"></span> **mistral-large** -- {esc(e)}', unsafe_allow_html=True)

    with c_vlm:
        st.markdown('<span class="status-dot amber"></span> **pixtral-large** -- not tested (needs image)', unsafe_allow_html=True)

    with c_sum:
        try:
            _t0 = _t.time()
            session.sql("SELECT SNOWFLAKE.CORTEX.SUMMARIZE('Test summary.') AS result").collect()
            _ms = int((_t.time() - _t0) * 1000)
            st.markdown(f'<span class="status-dot green pulse"></span> **SUMMARIZE** -- available ({_ms}ms)', unsafe_allow_html=True)
        except Exception as e:
            st.markdown(f'<span class="status-dot red"></span> **SUMMARIZE** -- {esc(e)}', unsafe_allow_html=True)
else:
    st.markdown('<div style="color:#6b7280;font-size:0.85rem">Snowflake not connected. Cannot test Cortex.</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# Environment Variables — Grid with indicators
# ═══════════════════════════════════════════════════════════
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("Environment Variables")

env_vars = [
    ("SNOWFLAKE_ACCOUNT", "Snowflake account"),
    ("SNOWFLAKE_USER", "Snowflake user"),
    ("SNOWFLAKE_PASSWORD", "Snowflake password"),
    ("SNOWFLAKE_DATABASE", "Target database"),
    ("SNOWFLAKE_WAREHOUSE", "Compute warehouse"),
    ("SNOWFLAKE_SCHEMA", "Default schema"),
    ("SNOWFLAKE_ROLE", "Access role"),
    ("AWS_ACCESS_KEY_ID", "AWS access key"),
    ("AWS_SECRET_ACCESS_KEY", "AWS secret key"),
    ("AWS_DEFAULT_REGION", "AWS region"),
    ("FINSAGE_S3_BUCKET", "S3 bucket"),
    ("BEDROCK_KB_ID", "KB ID"),
    ("BEDROCK_GUARDRAIL_ID", "Guardrail ID"),
    ("BEDROCK_GUARDRAIL_VERSION", "Guardrail version"),
    ("BEDROCK_MODEL_ID", "Bedrock model"),
    ("NEWSAPI_KEY", "News API key"),
    ("ALPHA_VANTAGE_API_KEY", "Alpha Vantage key"),
]

set_count = 0
# Render as 3-column grid
for row_start in range(0, len(env_vars), 3):
    cols = st.columns(3)
    for i in range(3):
        idx = row_start + i
        if idx < len(env_vars):
            var, desc = env_vars[idx]
            val = os.getenv(var, "")
            with cols[i]:
                if val:
                    set_count += 1
                    if any(kw in var.upper() for kw in ["PASSWORD", "SECRET", "KEY", "TOKEN"]):
                        display = val[:4] + "****"
                    else:
                        display = val[:20] + "..." if len(val) > 20 else val
                    st.markdown(
                        f'<div style="padding:6px 0">'
                        f'<span class="status-dot green"></span>'
                        f'<code style="font-size:0.75rem">{var}</code>'
                        f'<br><span style="color:#4b5563;font-size:0.7rem;margin-left:14px">{display}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="padding:6px 0">'
                        f'<span class="status-dot red"></span>'
                        f'<code style="font-size:0.75rem">{var}</code>'
                        f'<br><span style="color:#4b5563;font-size:0.7rem;margin-left:14px">not set</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

st.markdown(
    f'<div style="color:#6b7280;font-size:0.8rem;margin-top:8px">'
    f'{set_count}/{len(env_vars)} environment variables configured</div>',
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════
# Report Outputs
# ═══════════════════════════════════════════════════════════
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("Report Outputs")

outputs_dir = PROJECT_ROOT / "outputs"
if outputs_dir.exists():
    runs = sorted(
        [d for d in outputs_dir.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    if runs:
        st.markdown(f'<div style="color:#f9fafb;font-weight:600">{len(runs)} report run(s)</div>', unsafe_allow_html=True)
        for run in runs[:10]:
            has_pdf = any(run.glob("*.pdf"))
            has_manifest = (run / "chart_manifest.json").exists()
            icons = []
            if has_pdf:
                icons.append("PDF")
            if has_manifest:
                icons.append("Charts")
            tags = ", ".join(icons) if icons else "incomplete"
            dot = "green" if has_pdf else "amber"
            st.markdown(
                f'<span class="status-dot {dot}"></span> '
                f'<code>{run.name}</code> <span style="color:#4b5563;font-size:0.8rem">({tags})</span>',
                unsafe_allow_html=True,
            )
        if len(runs) > 10:
            st.markdown(f'<div style="color:#4b5563;font-size:0.8rem">... and {len(runs) - 10} more</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#6b7280">No report runs found yet.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div style="color:#6b7280">No outputs directory found. Reports will be created when generated.</div>', unsafe_allow_html=True)
