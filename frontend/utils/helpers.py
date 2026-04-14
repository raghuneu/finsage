"""Shared helpers for FinSage frontend pages — dark enterprise theme."""

import html as _html
import re
import streamlit as st


def esc(text) -> str:
    """HTML-escape user/API/exception content before injecting into unsafe_allow_html."""
    return _html.escape(str(text))


def sanitize_ticker(ticker: str) -> str:
    """Validate and sanitize ticker symbol to prevent SQL injection."""
    cleaned = ticker.strip().upper()
    if not re.match(r'^[A-Z]{1,10}$', cleaned):
        raise ValueError(f"Invalid ticker: {ticker!r}")
    return cleaned


def fmt_money(v):
    if v is None:
        return "N/A"
    if abs(v) >= 1e12:
        return f"${v / 1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.0f}M"
    return f"${v:,.0f}"


_BULLISH = {"BULLISH", "STRONG_GROWTH", "EXCELLENT", "HEALTHY", "IMPROVING", "MODERATE_GROWTH"}
_BEARISH = {"BEARISH", "DECLINING", "UNPROFITABLE", "CRITICAL", "DETERIORATING"}


def signal_html(s):
    """Return a colored signal badge as raw HTML."""
    if s in _BULLISH:
        return f'<span class="signal-bullish">&#9650; {s}</span>'
    elif s in _BEARISH:
        return f'<span class="signal-bearish">&#9660; {s}</span>'
    return f'<span class="signal-neutral">&#9679; {s}</span>'


def signal_badge(s):
    """Return just the colored text (no background pill)."""
    if s in _BULLISH:
        return f'<span style="color:#00ff88;font-weight:700">&#9650; {s}</span>'
    elif s in _BEARISH:
        return f'<span style="color:#ff3366;font-weight:700">&#9660; {s}</span>'
    return f'<span style="color:#6b7280;font-weight:700">&#9679; {s}</span>'


def metric_card(title, value, delta=None):
    """Render a styled metric card (dark theme)."""
    delta_html = ""
    if delta is not None:
        is_up = "+" in str(delta) or (isinstance(delta, (int, float)) and delta > 0)
        cls = "delta-up" if is_up else "delta-down"
        delta_html = f'<div class="{cls}">{delta}</div>'
    st.markdown(
        f'<div class="fs-card">'
        f'<h4>{title}</h4>'
        f'<div class="value">{value}</div>'
        f'{delta_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def section_header(title, subtitle=None):
    """Render a styled section header with cyan accent border."""
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f'<div class="fs-section"><h3>{title}</h3>{sub}</div>',
        unsafe_allow_html=True,
    )


def page_header(title, subtitle=None):
    """Render the page title with gradient accent bar."""
    st.markdown(f'<div class="fs-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="fs-subtitle">{subtitle}</div>', unsafe_allow_html=True)
    st.markdown('<div class="fs-title-bar"></div>', unsafe_allow_html=True)


def require_snowflake(session):
    """Guard clause — stops the page if Snowflake is unavailable."""
    if session is None:
        st.warning("Snowflake connection required. Check your .env credentials.")
        st.stop()


def require_kb(kb):
    if kb is None:
        st.error("Set `BEDROCK_KB_ID` in your .env file to enable RAG Search.")
        st.stop()


def safe_query(session, sql):
    """Execute a SQL query and return a pandas DataFrame, or None on error."""
    try:
        return session.sql(sql).to_pandas()
    except Exception as e:
        st.error(f"Query failed: {e}")
        return None


def safe_collect(session, sql):
    """Execute SQL and return raw rows, or empty list on error."""
    try:
        return session.sql(sql).collect()
    except Exception:
        return []


def ds_card(icon, name, subtitle):
    """Render a gradient data source card (dark theme)."""
    st.markdown(
        f'<div class="ds-card">'
        f'<div class="icon">{icon}</div>'
        f'<div class="name">{name}</div>'
        f'<div class="sub">{subtitle}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def health_card(service_name, status, details=None):
    """Render a health check card with status indicator.
    status: 'healthy', 'degraded', or 'down'
    """
    status_map = {
        "healthy": ("green pulse", "Connected", "#00ff88"),
        "degraded": ("amber", "Degraded", "#ffaa00"),
        "down": ("red", "Offline", "#ff3366"),
    }
    dot_cls, label, color = status_map.get(status, status_map["down"])
    details_html = f'<div style="color:#4b5563;font-size:0.8rem;margin-top:8px">{details}</div>' if details else ""
    st.markdown(
        f'<div class="health-card {status}">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">'
        f'<span class="status-dot {dot_cls}"></span>'
        f'<span style="color:#f9fafb;font-weight:600;font-size:0.95rem">{service_name}</span>'
        f'</div>'
        f'<div style="color:{color};font-size:0.8rem;font-weight:600;margin-left:18px">{label}</div>'
        f'{details_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def pipeline_step(step_name, status, icon=""):
    """Render a CAVM pipeline step indicator.
    status: 'pending', 'active', 'done', 'failed'
    """
    st.markdown(
        f'<span class="pipeline-step {status}">{icon} {step_name}</span>',
        unsafe_allow_html=True,
    )


def pipeline_tracker(steps):
    """Render a full horizontal pipeline tracker.
    steps: list of (name, status, icon) tuples
    """
    parts = []
    for i, (name, status, icon) in enumerate(steps):
        conn_cls = "done" if status == "done" else ""
        parts.append(f'<span class="pipeline-step {status}">{icon} {name}</span>')
        if i < len(steps) - 1:
            parts.append(f'<span class="pipeline-connector {conn_cls}"></span>')
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;margin:16px 0">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def kpi_row(metrics):
    """Render a row of KPI metric cards.
    metrics: list of dicts with 'title', 'value', and optional 'delta' keys
    """
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            metric_card(m["title"], m["value"], m.get("delta"))
