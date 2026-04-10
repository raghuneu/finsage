import streamlit as st
from utils.connections import get_snowflake, get_ticker
from utils.styles import inject_css
from utils.helpers import page_header, ds_card, require_snowflake, section_header

inject_css()
session = get_snowflake()
ticker = get_ticker()

page_header("Data Pipeline", "Snowflake warehouse status and pipeline controls")

# ── Data Sources ─────────────────────────────────────────────
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

# ── Layer Status ─────────────────────────────────────────────
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("Snowflake Layers")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("##### RAW")
    for t in ["RAW_STOCK_PRICES", "RAW_FUNDAMENTALS", "RAW_NEWS", "RAW_SEC_FILINGS", "RAW_SEC_FILING_DOCUMENTS"]:
        try:
            cnt = session.sql(f"SELECT COUNT(*) AS c FROM RAW.{t}").collect()[0]["C"]
            st.markdown(f"<span class='status-dot green'></span> `{t}` — **{cnt:,}**", unsafe_allow_html=True)
        except Exception:
            st.markdown(f"<span class='status-dot red'></span> `{t}`", unsafe_allow_html=True)

with c2:
    st.markdown("##### STAGING")
    for t in ["STG_STOCK_PRICES", "STG_FUNDAMENTALS", "STG_NEWS", "STG_SEC_FILINGS", "STG_SEC_FILING_DOCUMENTS"]:
        try:
            cnt = session.sql(f"SELECT COUNT(*) AS c FROM STAGING.{t}").collect()[0]["C"]
            st.markdown(f"<span class='status-dot green'></span> `{t}` — **{cnt:,}**", unsafe_allow_html=True)
        except Exception:
            st.markdown(f"<span class='status-dot red'></span> `{t}`", unsafe_allow_html=True)

with c3:
    st.markdown("##### ANALYTICS")
    for t in ["DIM_COMPANY", "FCT_STOCK_METRICS", "FCT_FUNDAMENTALS_GROWTH", "FCT_NEWS_SENTIMENT_AGG", "FCT_SEC_FINANCIAL_SUMMARY"]:
        try:
            cnt = session.sql(f"SELECT COUNT(*) AS c FROM ANALYTICS.{t}").collect()[0]["C"]
            st.markdown(f"<span class='status-dot green'></span> `{t}` — **{cnt:,}**", unsafe_allow_html=True)
        except Exception:
            st.markdown(f"<span class='status-dot red'></span> `{t}`", unsafe_allow_html=True)

# ── S3 Filing Counts ─────────────────────────────────────────
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("S3 SEC Filings")
try:
    import boto3
    s3c = boto3.client("s3", region_name="us-east-1")
    bucket = "finsage-sec-filings-808683"
    raw_n = sum(
        len([o for o in pg.get("Contents", []) if not o["Key"].endswith("/")])
        for pg in s3c.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="filings/raw/")
    )
    ext_n = sum(
        len([o for o in pg.get("Contents", []) if not o["Key"].endswith("/")])
        for pg in s3c.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="filings/extracted/")
    )
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Raw Filings (HTML)", raw_n)
    with c2:
        st.metric("Extracted Text Files", ext_n)
except Exception as e:
    st.warning(f"S3 unavailable: {e}")

# ── Pipeline Runner ──────────────────────────────────────────
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("Run Pipeline")
with st.expander("Pipeline Controls", expanded=False):
    sel = st.multiselect("Tickers", ["AAPL", "MSFT", "GOOGL", "TSLA", "JPM"], default=[ticker])
    c1, c2, c3, c4 = st.columns(4)
    ls = c1.checkbox("Stocks", True)
    lf = c2.checkbox("Fundamentals", True)
    ln = c3.checkbox("News", False)
    le = c4.checkbox("SEC", False)
    if st.button("Run Pipeline", type="primary"):
        with st.spinner("Running data pipeline..."):
            try:
                from orchestration.data_pipeline import run_pipeline
                r = run_pipeline(tickers=sel, load_stocks=ls, load_fundamentals=lf, load_news=ln, load_sec=le)
                st.success(f"Done! {len(r['success'])} successful, {len(r['partial'])} partial, {len(r['failed'])} failed")
            except Exception as e:
                st.error(f"Pipeline failed: {e}")
