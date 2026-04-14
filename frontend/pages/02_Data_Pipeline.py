"""
FinSage Data Pipeline - Snowflake warehouse status and pipeline controls.

Shows layer-level table counts (RAW / STAGING / ANALYTICS),
S3 filing inventory, and an interactive pipeline runner.
"""

import streamlit as st
import plotly.graph_objects as go

from utils.connections import get_snowflake, load_tickers, render_sidebar
from utils.styles import inject_css, create_plotly_template
from utils.helpers import page_header, ds_card, require_snowflake, section_header, metric_card, esc

inject_css()
ticker = render_sidebar()
session = get_snowflake()
tickers = load_tickers()
TPL = create_plotly_template()

page_header("Data Pipeline", "Snowflake warehouse status and pipeline controls")

# ── Data Sources ───────────────────────────────────────────────
section_header("Data Sources", "Ingestion endpoints feeding the Snowflake warehouse")

c1, c2, c3, c4 = st.columns(4)
with c1:
    ds_card("📈", "Yahoo Finance", "Stock Prices + Fundamentals")
with c2:
    ds_card("📰", "NewsAPI", "Financial News Articles")
with c3:
    ds_card("📄", "SEC EDGAR", "10-K / 10-Q Filings + XBRL")
with c4:
    ds_card("☁️", "AWS S3", "Extracted Filing Text")

require_snowflake(session)

# ── Snowflake Layer Status ─────────────────────────────────────
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("Snowflake Layers", "Row counts across the three-layer architecture")

RAW_TABLES = ["RAW_STOCK_PRICES", "RAW_FUNDAMENTALS", "RAW_NEWS", "RAW_SEC_FILINGS", "RAW_SEC_FILING_DOCUMENTS"]
STAGING_TABLES = ["STG_STOCK_PRICES", "STG_FUNDAMENTALS", "STG_NEWS", "STG_SEC_FILINGS"]
ANALYTICS_TABLES = ["DIM_COMPANY", "FCT_STOCK_METRICS", "FCT_FUNDAMENTALS_GROWTH", "FCT_NEWS_SENTIMENT_AGG", "FCT_SEC_FINANCIAL_SUMMARY"]

# Collect row counts for visualization
table_names = []
table_counts = []
table_layers = []
layer_colors = {"RAW": "#00d4ff", "STAGING": "#ffaa00", "ANALYTICS": "#00ff88"}

for schema, tables in [("RAW", RAW_TABLES), ("STAGING", STAGING_TABLES), ("ANALYTICS", ANALYTICS_TABLES)]:
    for t in tables:
        try:
            cnt = session.sql(f"SELECT COUNT(*) AS c FROM {schema}.{t}").collect()[0]["C"]
        except Exception:
            cnt = 0
        table_names.append(t)
        table_counts.append(cnt)
        table_layers.append(schema)

# Horizontal bar chart
fig = go.Figure()
for layer in ["ANALYTICS", "STAGING", "RAW"]:
    mask = [i for i, l in enumerate(table_layers) if l == layer]
    fig.add_trace(go.Bar(
        y=[table_names[i] for i in mask],
        x=[table_counts[i] for i in mask],
        name=layer,
        orientation="h",
        marker_color=layer_colors[layer],
        text=[f"{table_counts[i]:,}" for i in mask],
        textposition="auto",
        textfont=dict(color="#e5e7eb"),
    ))

fig.update_layout(
    **TPL,
    height=max(350, len(table_names) * 28),
    barmode="group",
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                bgcolor="rgba(0,0,0,0)", font=dict(color="#e5e7eb"), bordercolor="rgba(0,0,0,0)"),
    xaxis_title="Row Count",
    yaxis=dict(autorange="reversed"),
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── S3 Filing Counts ───────────────────────────────────────────
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("S3 SEC Filings", "Filing documents stored in the S3 bucket")

try:
    import boto3
    s3c = boto3.client("s3", region_name="us-east-1")
    bucket = "finsage-sec-filings-808683"

    raw_n = 0
    for pg in s3c.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="filings/raw/"):
        raw_n += len([o for o in pg.get("Contents", []) if not o["Key"].endswith("/")])

    ext_n = 0
    for pg in s3c.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="filings/extracted/"):
        ext_n += len([o for o in pg.get("Contents", []) if not o["Key"].endswith("/")])

    c1, c2 = st.columns(2)
    with c1:
        metric_card("Raw Filings (HTML)", str(raw_n))
    with c2:
        metric_card("Extracted Text Files", str(ext_n))
except ImportError:
    st.markdown(
        '<div class="fs-card" style="border-left:3px solid #ffaa00;color:#6b7280">'
        'boto3 is not installed. Install it to view S3 filing counts.</div>',
        unsafe_allow_html=True,
    )
except Exception as e:
    st.markdown(
        f'<div class="fs-card" style="border-left:3px solid #ffaa00;color:#6b7280">'
        f'S3 unavailable: {esc(e)}</div>',
        unsafe_allow_html=True,
    )

# ── Pipeline Runner ────────────────────────────────────────────
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("Run Pipeline", "Execute the data ingestion pipeline for selected tickers")

with st.expander("Pipeline Controls", expanded=False):
    sel = st.multiselect("Tickers", tickers, default=[ticker] if ticker in tickers else tickers[:1])

    c1, c2, c3, c4 = st.columns(4)
    ls = c1.checkbox("Stocks", True)
    lf = c2.checkbox("Fundamentals", True)
    ln = c3.checkbox("News", False)
    le = c4.checkbox("SEC", False)

    if not sel:
        st.markdown('<div style="color:#6b7280;font-size:0.85rem">Select at least one ticker to run the pipeline.</div>', unsafe_allow_html=True)
    elif st.button("Run Pipeline", type="primary"):
        with st.spinner("Running data pipeline..."):
            try:
                from orchestration.data_pipeline import run_pipeline
                r = run_pipeline(
                    tickers=sel,
                    load_stocks=ls,
                    load_fundamentals=lf,
                    load_news=ln,
                    load_sec=le,
                )
                success_cnt = len(r.get("success", []))
                partial_cnt = len(r.get("partial", []))
                failed_cnt = len(r.get("failed", []))
                st.success(f"Pipeline complete: {success_cnt} successful, {partial_cnt} partial, {failed_cnt} failed")
                if r.get("failed"):
                    st.warning(f"Failed tickers: {', '.join(r['failed'])}")
            except Exception as e:
                st.error(f"Pipeline execution failed: {e}")
