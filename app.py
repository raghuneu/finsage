"""
FinSage - AI-Powered Financial Research Platform
Complete Streamlit Frontend - covers the ENTIRE pipeline

Covers:
    Stage 1: Data Collection (Yahoo Finance, NewsAPI, SEC EDGAR, S3)
    Stage 2: Data Transformation (Snowflake RAW -> Staging -> Analytics via dbt)
    Stage 3: AI Analysis (Document Agent, Bedrock KB, Guardrails, Multi-Model)

Usage:
    cd ~/finsage
    pip3 install streamlit
    streamlit run app.py
"""

import os, sys, json, time, logging
from datetime import datetime
import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts", "sec_filings"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="FinSage", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.main-title{font-size:2.5rem;font-weight:700;color:#1B3A5C;margin-bottom:0}
.sub-title{font-size:1.1rem;color:#666;margin-top:-10px;margin-bottom:20px}
.signal-bullish{color:#2D7D46;font-weight:700;font-size:1.1rem}
.signal-bearish{color:#CC3333;font-weight:700;font-size:1.1rem}
.signal-neutral{color:#BF8F00;font-weight:700;font-size:1.1rem}
.citation-box{background:#f0f4f8;border-left:4px solid #2E75B6;padding:8px 15px;margin:5px 0;border-radius:0 6px 6px 0;font-size:.85rem}
.consensus-box{background:#e8f4e8;border:2px solid #2D7D46;border-radius:10px;padding:15px;margin:10px 0}
.guardrail-pass{background:#d4edda;border:1px solid #c3e6cb;padding:10px;border-radius:8px}
.guardrail-fail{background:#f8d7da;border:1px solid #f5c6cb;padding:10px;border-radius:8px}
.data-source{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:10px 15px;border-radius:8px;text-align:center;margin:5px}
</style>""", unsafe_allow_html=True)

@st.cache_resource
def get_snowflake():
    try:
        from snowflake_connection import get_session
        return get_session()
    except: return None

@st.cache_resource
def get_kb():
    try:
        from bedrock_kb import BedrockKB
        return BedrockKB()
    except: return None

@st.cache_resource
def get_guardrail():
    try:
        from guardrails import GuardedLLM
        return GuardedLLM()
    except: return None

@st.cache_resource
def get_multi_model():
    try:
        from multi_model import MultiModelAnalyzer
        return MultiModelAnalyzer()
    except: return None

def signal_html(s):
    if s in ("BULLISH","STRONG_GROWTH","EXCELLENT","HEALTHY","IMPROVING"):
        return f'<span class="signal-bullish">▲ {s}</span>'
    elif s in ("BEARISH","DECLINING","UNPROFITABLE","CRITICAL","DETERIORATING"):
        return f'<span class="signal-bearish">▼ {s}</span>'
    return f'<span class="signal-neutral">● {s}</span>'

def fmt_money(v):
    if v is None: return "N/A"
    if abs(v)>=1e12: return f"${v/1e12:.2f}T"
    if abs(v)>=1e9: return f"${v/1e9:.1f}B"
    if abs(v)>=1e6: return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"

session=get_snowflake(); kb=get_kb(); guardrail=get_guardrail(); mm=get_multi_model()

with st.sidebar:
    st.markdown("## 📊 FinSage")
    st.markdown("*AI-Powered Financial Research*")
    st.markdown("---")
    ticker=st.selectbox("Select Ticker",["AAPL","MSFT","GOOGL","TSLA","JPM"])
    st.markdown("---")
    page=st.radio("Navigate",["🏠 Dashboard","📡 Data Pipeline","📊 Analytics Explorer","📄 SEC Filing Analysis","🔍 RAG Search","📝 Research Report","🤖 Multi-Model Analysis","🛡️ Guardrails Demo","❓ Ask FinSage","⚙️ System Status"])
    st.markdown("---")
    st.markdown("### Connections")
    st.markdown(f"{'✅' if session else '❌'} Snowflake")
    st.markdown(f"{'✅' if kb else '❌'} Bedrock KB")
    st.markdown(f"{'✅' if guardrail else '❌'} Guardrails")
    st.markdown(f"{'✅' if mm else '❌'} Multi-Model")
    st.markdown("---")
    st.caption("DAMG 7374 — Spring 2026")
    st.caption("Shrirangesh | Raghu | Omkar")

# ═══════════════ DASHBOARD ═══════════════
if page=="🏠 Dashboard":
    st.markdown(f'<p class="main-title">FinSage — {ticker}</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-title">AI-Powered Financial Research Report Generator</p>',unsafe_allow_html=True)
    if session:
        from document_agent import get_company_intelligence
        intel=get_company_intelligence(session,ticker)
        p=intel.get("profile",{});s=intel.get("stock",{});f=intel.get("fundamentals",{});sent=intel.get("sentiment",{});sf=intel.get("sec_financials",{})
        c1,c2,c3,c4,c5=st.columns(5)
        with c1: st.metric("Market Cap",fmt_money(p.get("market_cap")))
        with c2: st.metric("Price",f"${s.get('close',0):.2f}",f"{s.get('daily_return_pct',0):.2f}%")
        with c3: st.metric("Revenue",fmt_money(f.get("revenue")),f"{f.get('revenue_growth_yoy_pct',0):.1f}% YoY")
        with c4: st.metric("Sentiment",f"{sent.get('sentiment_score',0):.3f}",sent.get("sentiment_trend",""))
        with c5: st.metric("P/E",f"{p.get('pe_ratio',0):.1f}" if p.get('pe_ratio') else "N/A")
        st.markdown("---")
        c1,c2,c3,c4=st.columns(4)
        with c1: st.markdown("**Stock Trend**"); st.markdown(signal_html(s.get("trend_signal","N/A")),unsafe_allow_html=True)
        with c2: st.markdown("**Fundamentals**"); st.markdown(signal_html(f.get("fundamental_signal","N/A")),unsafe_allow_html=True)
        with c3: st.markdown("**Sentiment**"); st.markdown(signal_html(sent.get("sentiment_label","N/A")),unsafe_allow_html=True)
        with c4: st.markdown("**Health**"); st.markdown(signal_html(sf.get("financial_health","N/A")),unsafe_allow_html=True)
        headlines=intel.get("recent_headlines",[])
        if headlines:
            st.markdown("---"); st.markdown("#### Recent Headlines")
            for h in headlines:
                e="🟢" if h["sentiment"]=="positive" else "🔴" if h["sentiment"]=="negative" else "🟡"
                st.markdown(f"{e} {h['title'][:120]}")
    else: st.warning("Connect to Snowflake to see dashboard")

# ═══════════════ DATA PIPELINE ═══════════════
elif page=="📡 Data Pipeline":
    st.markdown("## Data Pipeline Overview")
    c1,c2,c3,c4=st.columns(4)
    with c1: st.markdown('<div class="data-source">📈 Yahoo Finance<br><small>Stock Prices + Fundamentals</small></div>',unsafe_allow_html=True)
    with c2: st.markdown('<div class="data-source">📰 NewsAPI<br><small>Financial News</small></div>',unsafe_allow_html=True)
    with c3: st.markdown('<div class="data-source">📄 SEC EDGAR<br><small>10-K / 10-Q Filings</small></div>',unsafe_allow_html=True)
    with c4: st.markdown('<div class="data-source">☁️ AWS S3<br><small>Extracted Text</small></div>',unsafe_allow_html=True)
    if session:
        st.markdown("### Snowflake Tables")
        c1,c2,c3=st.columns(3)
        with c1:
            st.markdown("#### RAW Layer")
            for t in ["RAW_STOCK_PRICES","RAW_FUNDAMENTALS","RAW_NEWS","RAW_SEC_FILINGS","RAW_SEC_FILING_DOCUMENTS"]:
                try:
                    cnt=session.sql(f"SELECT COUNT(*) AS c FROM RAW.{t}").collect()[0]["C"]
                    st.markdown(f"✅ `{t}` — {cnt:,} rows")
                except: st.markdown(f"❌ `{t}`")
        with c2:
            st.markdown("#### STAGING Layer")
            for t in ["STG_STOCK_PRICES","STG_FUNDAMENTALS","STG_NEWS","STG_SEC_FILINGS"]:
                try:
                    cnt=session.sql(f"SELECT COUNT(*) AS c FROM STAGING.{t}").collect()[0]["C"]
                    st.markdown(f"✅ `{t}` — {cnt:,} rows")
                except: st.markdown(f"❌ `{t}`")
        with c3:
            st.markdown("#### ANALYTICS Layer")
            for t in ["DIM_COMPANY","FCT_STOCK_METRICS","FCT_FUNDAMENTALS_GROWTH","FCT_NEWS_SENTIMENT_AGG","FCT_SEC_FINANCIAL_SUMMARY"]:
                try:
                    cnt=session.sql(f"SELECT COUNT(*) AS c FROM ANALYTICS.{t}").collect()[0]["C"]
                    st.markdown(f"✅ `{t}` — {cnt:,} rows")
                except: st.markdown(f"❌ `{t}`")
        st.markdown("### S3 SEC Filings")
        try:
            import boto3
            s3c=boto3.client("s3",region_name="us-east-1")
            raw_n=sum(len([o for o in pg.get("Contents",[]) if not o["Key"].endswith("/")]) for pg in s3c.get_paginator("list_objects_v2").paginate(Bucket="finsage-sec-filings-808683",Prefix="filings/raw/"))
            ext_n=sum(len([o for o in pg.get("Contents",[]) if not o["Key"].endswith("/")]) for pg in s3c.get_paginator("list_objects_v2").paginate(Bucket="finsage-sec-filings-808683",Prefix="filings/extracted/"))
            c1,c2=st.columns(2)
            with c1: st.metric("Raw Filings (HTML)",raw_n)
            with c2: st.metric("Extracted Text Files",ext_n)
        except Exception as e: st.warning(f"S3: {e}")
        st.markdown("### Run Pipeline")
        sel=st.multiselect("Tickers",["AAPL","MSFT","GOOGL","TSLA","JPM"],default=[ticker])
        c1,c2,c3,c4=st.columns(4)
        ls=c1.checkbox("Stocks",True);lf=c2.checkbox("Fundamentals",True);ln=c3.checkbox("News",False);le=c4.checkbox("SEC",False)
        if st.button("Run Pipeline",type="primary"):
            with st.spinner("Running..."):
                try:
                    from orchestration.data_pipeline import run_pipeline
                    r=run_pipeline(tickers=sel,load_stocks=ls,load_fundamentals=lf,load_news=ln,load_sec=le)
                    st.success(f"Done! {len(r['success'])} ok, {len(r['failed'])} failed")
                except Exception as e: st.error(f"Failed: {e}")

# ═══════════════ ANALYTICS EXPLORER ═══════════════
elif page=="📊 Analytics Explorer":
    st.markdown(f"## Analytics Explorer — {ticker}")
    if not session: st.warning("Connect to Snowflake"); st.stop()
    t1,t2,t3,t4=st.tabs(["Stock Metrics","Fundamentals","Sentiment","SEC Financials"])
    with t1:
        try:
            df=session.sql(f"SELECT DATE,CLOSE,SMA_7D,SMA_30D,SMA_90D,VOLUME,DAILY_RETURN_PCT,VOLATILITY_30D_PCT,TREND_SIGNAL FROM ANALYTICS.FCT_STOCK_METRICS WHERE TICKER='{ticker}' ORDER BY DATE DESC LIMIT 60").to_pandas()
            if not df.empty:
                st.markdown(f"**Signal:** {signal_html(df.iloc[0]['TREND_SIGNAL'])}",unsafe_allow_html=True)
                st.line_chart(df[["DATE","CLOSE","SMA_7D","SMA_30D"]].sort_values("DATE").set_index("DATE"))
                st.dataframe(df.head(20),use_container_width=True)
        except Exception as e: st.error(str(e))
    with t2:
        try:
            df=session.sql(f"SELECT FISCAL_QUARTER,REVENUE,NET_INCOME,EPS,REVENUE_GROWTH_QOQ_PCT,REVENUE_GROWTH_YOY_PCT,NET_MARGIN_PCT,FUNDAMENTAL_SIGNAL FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH WHERE TICKER='{ticker}' ORDER BY FISCAL_QUARTER DESC LIMIT 12").to_pandas()
            if not df.empty:
                st.markdown(f"**Signal:** {signal_html(df.iloc[0]['FUNDAMENTAL_SIGNAL'])}",unsafe_allow_html=True)
                st.dataframe(df,use_container_width=True)
        except Exception as e: st.error(str(e))
    with t3:
        try:
            df=session.sql(f"SELECT NEWS_DATE,TOTAL_ARTICLES,POSITIVE_COUNT,NEGATIVE_COUNT,SENTIMENT_SCORE,SENTIMENT_SCORE_7D_AVG,SENTIMENT_LABEL,SENTIMENT_TREND FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG WHERE TICKER='{ticker}' ORDER BY NEWS_DATE DESC LIMIT 30").to_pandas()
            if not df.empty:
                st.markdown(f"**Sentiment:** {signal_html(df.iloc[0]['SENTIMENT_LABEL'])} ({df.iloc[0]['SENTIMENT_TREND']})",unsafe_allow_html=True)
                st.line_chart(df[["NEWS_DATE","SENTIMENT_SCORE","SENTIMENT_SCORE_7D_AVG"]].sort_values("NEWS_DATE").set_index("NEWS_DATE"))
                st.dataframe(df,use_container_width=True)
        except Exception as e: st.error(str(e))
    with t4:
        try:
            df=session.sql(f"SELECT FISCAL_YEAR,FISCAL_PERIOD,TOTAL_REVENUE,NET_INCOME,OPERATING_MARGIN_PCT,NET_MARGIN_PCT,RETURN_ON_EQUITY_PCT,DEBT_TO_EQUITY_RATIO,REVENUE_GROWTH_YOY_PCT,FINANCIAL_HEALTH FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY WHERE TICKER='{ticker}' ORDER BY FISCAL_YEAR DESC LIMIT 10").to_pandas()
            if not df.empty:
                st.markdown(f"**Health:** {signal_html(df.iloc[0]['FINANCIAL_HEALTH'])}",unsafe_allow_html=True)
                st.dataframe(df,use_container_width=True)
        except Exception as e: st.error(str(e))

# ═══════════════ SEC FILING ANALYSIS ═══════════════
elif page=="📄 SEC Filing Analysis":
    st.markdown(f"## SEC Filing Analysis — {ticker}")
    if not session: st.warning("Connect to Snowflake"); st.stop()
    try:
        df=session.sql(f"SELECT FILING_ID,FORM_TYPE,FILING_DATE,PERIOD_OF_REPORT,COMPANY_NAME,MDA_WORD_COUNT,RISK_WORD_COUNT,EXTRACTION_STATUS,DATA_QUALITY_SCORE FROM RAW.RAW_SEC_FILING_DOCUMENTS WHERE TICKER='{ticker}' ORDER BY FILING_DATE DESC").to_pandas()
        if not df.empty:
            st.markdown(f"**{len(df)} filings found**")
            st.dataframe(df,use_container_width=True)
            mode=st.selectbox("Analysis",["Executive Summary","Risk Analysis","MD&A Analysis","Filing Comparison"])
            if st.button("Run Analysis",type="primary"):
                with st.spinner(f"Running {mode}..."):
                    from document_agent import summarize_filing,analyze_risks,analyze_mda,compare_filings
                    fn={"Executive Summary":summarize_filing,"Risk Analysis":analyze_risks,"MD&A Analysis":analyze_mda,"Filing Comparison":compare_filings}
                    r=fn[mode](session,ticker) if mode!="Filing Comparison" else compare_filings(session,ticker)
                    st.markdown("---"); st.markdown(r)
        else: st.info("No filings found")
    except Exception as e: st.error(str(e))

# ═══════════════ RAG SEARCH ═══════════════
elif page=="🔍 RAG Search":
    st.markdown("## RAG Search — Bedrock Knowledge Base")
    if not kb: st.error("Set BEDROCK_KB_ID in .env"); st.stop()
    t1,t2,t3=st.tabs(["Ask","Cross-Ticker","Raw Chunks"])
    with t1:
        q=st.text_input("Ask about SEC filings:",placeholder="What are Apple's main risk factors?")
        if q:
            with st.spinner("Searching..."):
                r=kb.ask(q,ticker=ticker)
                st.markdown(r["answer"])
                if r.get("citations"):
                    st.markdown("**Citations:**")
                    for c in r["citations"]: st.markdown(f'<div class="citation-box">📄 {c["source"].split("/")[-1]}</div>',unsafe_allow_html=True)
    with t2:
        q=st.text_input("Compare companies:",placeholder="How do companies discuss AI strategy?")
        if q:
            with st.spinner("Analyzing..."):
                r=kb.cross_ticker_analysis(q)
                st.markdown(f"**Tickers:** {', '.join(r['tickers_found'])}"); st.markdown(r["analysis"])
    with t3:
        q=st.text_input("Retrieve chunks:",placeholder="revenue growth drivers")
        if q:
            with st.spinner("Retrieving..."):
                chunks=kb.retrieve(q,ticker=ticker)
                for i,c in enumerate(chunks,1):
                    with st.expander(f"Chunk {i} — {c['ticker']} {c['section']} (score: {c['score']:.3f})"):
                        st.markdown(f"**Source:** `{c['source'].split('/')[-1]}`"); st.text(c["text"][:1000])

# ═══════════════ RESEARCH REPORT ═══════════════
elif page=="📝 Research Report":
    st.markdown(f"## Full Research Report — {ticker}")
    st.markdown("7-section report: Executive Summary, Financial Performance, Stock Analysis, Sentiment, Risks, Management Credibility, Outlook")
    if not session: st.warning("Connect to Snowflake"); st.stop()
    if st.button("Generate Full Report",type="primary"):
        with st.spinner(f"Generating report for {ticker}... (30-60s)"):
            from document_agent import full_report
            start=time.time(); r=full_report(session,ticker); elapsed=time.time()-start
            st.success(f"Generated in {elapsed:.1f}s"); st.markdown("---"); st.markdown(r)

# ═══════════════ MULTI-MODEL ═══════════════
elif page=="🤖 Multi-Model Analysis":
    st.markdown("## Multi-Model Comparison")
    if not mm: st.error("Multi-model not configured"); st.stop()
    q=st.text_input("Question:",placeholder="Rate this company's financial health")
    use_ctx=st.checkbox("Include analytics data",True)
    if st.button("Run Comparison",type="primary") and q:
        ctx=None
        if use_ctx:
            try:
                from multi_model import get_ticker_context; ctx=get_ticker_context(ticker)
            except: pass
        with st.spinner("Running across models..."):
            r=mm.consensus(q,ctx)
            st.markdown("#### Model Responses")
            cols=st.columns(len(r["responses"]))
            for i,(name,resp) in enumerate(r["responses"].items()):
                with cols[i]:
                    st.markdown(f"**{'✅' if resp['success'] else '❌'} {name}**"); st.caption(f"{resp['latency_ms']}ms")
                    if resp["success"]: st.markdown(resp["output"][:600])
                    else: st.error(resp["error"][:100])
            st.markdown("---"); st.markdown("#### Consensus")
            st.markdown(f'<div class="consensus-box">{r.get("consensus","N/A")}</div>',unsafe_allow_html=True)
            s=r["summary"]; st.caption(f"Models: {s['succeeded']}/{s['total_models']} | Fastest: {s.get('fastest_ms')}ms")

# ═══════════════ GUARDRAILS ═══════════════
elif page=="🛡️ Guardrails Demo":
    st.markdown("## Bedrock Guardrails")
    if not guardrail: st.error("Set BEDROCK_GUARDRAIL_ID in .env"); st.stop()
    examples={"Investment Advice (blocks)":"You should buy AAPL stock right now","Price Prediction (blocks)":"AAPL will reach $500 next quarter","PII (masks)":"Contact john@apple.com, SSN 123-45-6789","Clean Text (passes)":"Apple reported 8% revenue growth","Custom":""}
    choice=st.selectbox("Scenario:",list(examples.keys()))
    text=st.text_area("Text:",value=examples[choice],height=100)
    if st.button("Check",type="primary") and text:
        with st.spinner("Checking..."):
            r=guardrail.check_output(text)
            if r["blocked"]: st.markdown('<div class="guardrail-fail">🛡️ <strong>BLOCKED</strong></div>',unsafe_allow_html=True)
            else: st.markdown('<div class="guardrail-pass">✅ <strong>PASSED</strong></div>',unsafe_allow_html=True)
            if r.get("details"):
                for d in r["details"]: st.markdown(f"- {d}")
            st.markdown("**Output:**"); st.code(r.get("output",text))

# ═══════════════ ASK ═══════════════
elif page=="❓ Ask FinSage":
    st.markdown(f"## Ask FinSage about {ticker}")
    src=st.radio("Source:",["Snowflake Cortex (Analytics + Filing)","Bedrock KB (RAG)"],horizontal=True)
    q=st.text_input("Question:",placeholder=f"What is {ticker}'s competitive advantage?")
    if st.button("Ask",type="primary") and q:
        if src.startswith("Snowflake"):
            if not session: st.error("No Snowflake"); st.stop()
            with st.spinner("Analyzing..."):
                from document_agent import ask_question; st.markdown(ask_question(session,ticker,q))
        else:
            if not kb: st.error("No KB"); st.stop()
            with st.spinner("Searching..."):
                r=kb.ask(q,ticker=ticker); st.markdown(r["answer"])
                if r.get("citations"):
                    for c in r["citations"]: st.markdown(f'<div class="citation-box">📄 {c["source"].split("/")[-1]}</div>',unsafe_allow_html=True)

# ═══════════════ SYSTEM STATUS ═══════════════
elif page=="⚙️ System Status":
    st.markdown("## System Status")
    c1,c2=st.columns(2)
    with c1:
        st.markdown("### Snowflake")
        if session:
            st.success("Connected")
            try:
                i=session.sql("SELECT CURRENT_USER() u,CURRENT_ROLE() r,CURRENT_WAREHOUSE() w,CURRENT_DATABASE() d").collect()[0]
                st.markdown(f"User: {i['U']} | Role: {i['R']} | WH: {i['W']} | DB: {i['D']}")
            except: pass
        else: st.error("Not connected")
        st.markdown("### AWS")
        try:
            import boto3; sts=boto3.client("sts"); id=sts.get_caller_identity()
            st.success(f"Account: {id['Account']} | User: {id['Arn'].split('/')[-1]}")
        except Exception as e: st.error(str(e))
    with c2:
        st.markdown("### Bedrock KB")
        if kb:
            h=kb.health_check()
            st.success(f"Healthy — {h['kb_id']}") if h["status"]=="healthy" else st.error(h.get("error"))
        else: st.warning("Not configured")
        st.markdown("### Guardrails")
        if guardrail: st.success(f"Active — {guardrail.guardrail_id}")
        else: st.warning("Not configured")
        st.markdown("### Multi-Model")
        if mm: st.success(f"{len(mm.models)} models"); [st.markdown(f"- `{m}`") for m in mm.models]
        else: st.warning("Not configured")
    st.markdown("### Environment")
    for v in ["SNOWFLAKE_ACCOUNT","SNOWFLAKE_USER","SNOWFLAKE_DATABASE","FINSAGE_S3_BUCKET","BEDROCK_KB_ID","BEDROCK_GUARDRAIL_ID","BEDROCK_MODEL_ID"]:
        val=os.getenv(v,""); st.markdown(f"{'✅' if val else '❌'} `{v}` = `{val[:30]}{'...' if len(val)>30 else ''}`" if val else f"❌ `{v}` — not set")
