"""FinSage Research Report -- Generate comprehensive financial research reports."""

import os
import sys
import time
import streamlit as st
from pathlib import Path

from utils.connections import get_snowflake, load_tickers, render_sidebar
from utils.styles import inject_css
from utils.helpers import page_header, require_snowflake, section_header, metric_card, pipeline_tracker, sanitize_ticker, escape_latex

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "sec_filings"))
sys.path.insert(0, str(PROJECT_ROOT / "agents"))
sys.path.insert(0, str(PROJECT_ROOT))

inject_css()
ticker = sanitize_ticker(render_sidebar())
session = get_snowflake()

page_header("Research Report", "Generate comprehensive financial research reports")
require_snowflake(session)

# ── Custom ticker input ────────────────────────────────────
col_t, col_s = st.columns([1, 3])
with col_t:
    st.markdown(
        '<div style="color:#4b5563;font-size:0.7rem;font-weight:600;'
        'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Ticker</div>',
        unsafe_allow_html=True,
    )
    custom = st.text_input("Ticker:", value=ticker, max_chars=5, key="report_ticker", label_visibility="collapsed")
    custom = custom.strip().upper()
    if custom:
        try:
            ticker = sanitize_ticker(custom)
        except ValueError:
            st.error(f"Invalid ticker: must be 1-10 uppercase letters.")
            st.stop()

# ── Data readiness check ──────────────────────────────────
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from utils.data_readiness import check_data_readiness

readiness = check_data_readiness(session, ticker)

if readiness["ready"]:
    st.markdown(
        f'<div class="fs-card" style="border-left:3px solid #22c55e">'
        f'<strong>Data Ready</strong> — All data sources available for {ticker}. '
        f'Stock: {readiness["counts"]["stock"]}, '
        f'Fundamentals: {readiness["counts"]["fundamentals"]}, '
        f'News: {readiness["counts"]["news"]}, '
        f'SEC: {readiness["counts"]["sec"]}'
        f'</div>',
        unsafe_allow_html=True,
    )
elif readiness["min_viable"]:
    st.markdown(
        f'<div class="fs-card" style="border-left:3px solid #f59e0b">'
        f'<strong>Partial Data</strong> — Missing: {", ".join(readiness["missing"])}. '
        f'Reports will be generated with available data. '
        f'Click "Load Missing Data" to fetch missing sources.'
        f'</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f'<div class="fs-card" style="border-left:3px solid #ef4444">'
        f'<strong>Data Not Available</strong> — Required data missing for {ticker}: '
        f'{", ".join(readiness["missing"])}. Load data before generating a report.'
        f'</div>',
        unsafe_allow_html=True,
    )

if not readiness["ready"]:
    if st.button("Load Missing Data", type="secondary"):
        from utils.on_demand_loader import ensure_data_for_ticker

        progress_bar = st.progress(0, text="Starting data load...")
        stage_progress = {
            "checking": 0.1, "loading": 0.3, "dbt": 0.7,
            "verifying": 0.9, "done": 1.0, "ready": 1.0,
        }

        def _update_progress(stage, detail=""):
            pct = stage_progress.get(stage, 0.5)
            progress_bar.progress(pct, text=detail or stage.capitalize())

        with st.spinner(f"Loading data for {ticker}..."):
            load_result = ensure_data_for_ticker(
                ticker=ticker,
                session=session,
                progress_callback=_update_progress,
            )

        final = load_result["readiness"]
        if final["ready"]:
            st.success(f"All data loaded for {ticker}.")
        elif final["min_viable"]:
            st.warning(f"Partial data loaded. Still missing: {', '.join(final['missing'])}")
        else:
            st.error(f"Could not load required data for {ticker}. Missing: {', '.join(final['missing'])}")
            st.stop()

        st.rerun()

if not readiness["min_viable"]:
    st.info("Load data above before generating a report.")
    st.stop()

# ── Report type selector ────────────────────────────────────
st.markdown("")
report_type = st.radio(
    "Report Type",
    ["Quick Report (Cortex)", "Full CAVM Pipeline (PDF)"],
    horizontal=True,
)

# ── Sections overview ──────────────────────────────────────
sections = ["Executive Summary", "Financial Performance", "Stock Analysis",
            "Sentiment", "Risk Factors", "Mgmt Credibility", "Forward Outlook"]
pills_html = " ".join(
    f'<span class="pill-btn" style="cursor:default">{i+1}. {s}</span>'
    for i, s in enumerate(sections)
)
st.markdown(
    f'<div class="fs-card fs-card-accent">'
    f'<h4>Report Sections</h4>'
    f'<div style="margin-top:12px">{pills_html}</div>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown("")

# ═══════════════════════════════════════════════════════════
# Quick Report (Cortex-based Markdown)
# ═══════════════════════════════════════════════════════════
if report_type == "Quick Report (Cortex)":
    st.markdown(
        '<div class="fs-card">'
        '<h4>Quick Report</h4>'
        '<div style="color:#6b7280;font-size:0.85rem">'
        'Generates a Markdown report using Snowflake Cortex LLM and SEC filing analysis. '
        'Typically completes in 30-60 seconds.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    if st.button("Generate Quick Report", type="primary"):
        with st.spinner(f"Generating Cortex report for {ticker}..."):
            try:
                from document_agent import full_report
                start = time.time()
                result = full_report(session, ticker)
                elapsed = time.time() - start
            except ImportError:
                st.error("Could not import document_agent. Check dependencies and scripts/sec_filings directory.")
                st.stop()
            except Exception as e:
                st.error(f"Report generation failed: {e}")
                st.stop()

        st.success(f"Report generated in {elapsed:.1f}s")
        st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
        st.markdown(escape_latex(result))

        st.download_button(
            label="Download as Markdown",
            data=result,
            file_name=f"{ticker}_research_report.md",
            mime="text/markdown",
        )

# ═══════════════════════════════════════════════════════════
# Full CAVM Pipeline (PDF)
# ═══════════════════════════════════════════════════════════
else:
    st.markdown(
        '<div class="fs-card">'
        '<h4>Full CAVM Pipeline</h4>'
        '<div style="color:#6b7280;font-size:0.85rem">'
        'Generates a branded 15-20 page PDF with VLM-refined charts, '
        'chain-of-analysis validation, and an investment thesis. '
        'Typically takes 5-15 minutes.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # Pipeline visualization (shows real-time progress during run)
    if "cavm_stage" not in st.session_state:
        st.session_state["cavm_stage"] = 0
    _stage = st.session_state["cavm_stage"]
    _stage_names = ["Chart Agent", "Validation", "Analysis", "Report"]
    _stage_icons = ["📊", "✓", "🧠", "📄"]
    pipeline_tracker([
        (name, "done" if i < _stage else ("active" if i == _stage else "pending"), icon)
        for i, (name, icon) in enumerate(zip(_stage_names, _stage_icons))
    ])

    col1, col2 = st.columns(2)
    with col1:
        debug = st.checkbox("Debug mode (save all chart iterations)")
    with col2:
        skip_charts = st.checkbox("Skip chart generation (reuse latest)")

    charts_dir_input = None
    if skip_charts:
        outputs_dir = PROJECT_ROOT / "outputs"
        if outputs_dir.exists():
            existing = sorted(
                [d.name for d in outputs_dir.iterdir()
                 if d.is_dir() and d.name.startswith(ticker.upper())],
                reverse=True,
            )
            if existing:
                charts_dir_input = st.selectbox("Select existing chart run:", existing)
                charts_dir_input = str(outputs_dir / charts_dir_input)
            else:
                st.markdown(
                    f'<div style="color:#ffaa00;font-size:0.85rem">'
                    f'No previous chart runs found for {ticker}. Uncheck "Skip chart generation".</div>',
                    unsafe_allow_html=True,
                )
                skip_charts = False
        else:
            st.markdown(
                '<div style="color:#ffaa00;font-size:0.85rem">'
                'No outputs directory found. Uncheck "Skip chart generation".</div>',
                unsafe_allow_html=True,
            )
            skip_charts = False

    if st.button("Generate Full PDF Report", type="primary"):
        try:
            from orchestrator import generate_report_pipeline
        except ImportError:
            st.error("Could not import orchestrator. Check agent dependencies and agents/ directory.")
            st.stop()

        try:
            st.session_state["cavm_stage"] = 0
            with st.status("Running CAVM Pipeline...", expanded=True) as status:
                status.write("Stage 1/4: Chart generation")
                status.write("Stage 2/4: Validation")
                status.write("Stage 3/4: Analysis")
                status.write("Stage 4/4: Report assembly")
                start = time.time()
                result = generate_report_pipeline(
                    ticker=ticker,
                    debug=debug,
                    skip_charts=skip_charts,
                    charts_dir=charts_dir_input,
                )
                elapsed = time.time() - start
                st.session_state["cavm_stage"] = 4
                status.update(label=f"Pipeline complete in {elapsed:.0f}s", state="complete")

            # Success summary
            pdf_path = result.get("pdf_path", "")
            charts = result.get("charts", [])
            validated = sum(1 for c in charts if c.get("validated"))

            st.success(f"PDF report generated in {elapsed:.0f}s ({elapsed / 60:.1f} min)")

            c1, c2, c3 = st.columns(3)
            with c1:
                metric_card("Charts Generated", str(len(charts)))
            with c2:
                metric_card("Charts Validated", str(validated))
            with c3:
                metric_card("Total Time", f"{elapsed:.0f}s")

            # Chart preview
            if charts:
                section_header("Generated Charts")
                chart_cols = st.columns(3)
                for i, chart in enumerate(charts):
                    fpath = chart.get("file_path", "")
                    with chart_cols[i % 3]:
                        if fpath and os.path.exists(fpath):
                            st.image(fpath, caption=chart.get("chart_id", f"Chart {i+1}"))
                        else:
                            st.caption(f"{chart.get('chart_id', f'Chart {i+1}')} (file not found)")

            # Download button
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_data = f.read()
                st.download_button(
                    label="Download PDF Report",
                    data=pdf_data,
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf",
                )
                st.caption(f"PDF saved to: `{pdf_path}`")
            else:
                st.markdown(
                    '<div class="fs-card" style="border-left:3px solid #ffaa00;color:#6b7280">'
                    'PDF file was not found at the expected path.</div>',
                    unsafe_allow_html=True,
                )

        except Exception as e:
            st.session_state["cavm_stage"] = 0
            st.error(f"CAVM pipeline failed: {e}")
            st.markdown(
                '<div class="fs-card">'
                '<h4>Troubleshooting</h4>'
                '<div style="color:#6b7280;font-size:0.85rem">'
                'Common causes: Snowflake connection timeout, missing data in analytics tables, '
                'or Cortex API rate limits. Check terminal output for detailed error logs.'
                '</div></div>',
                unsafe_allow_html=True,
            )
