"""Shared helpers for FinSage frontend pages."""

import streamlit as st


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


def signal_html(s):
    """Return a colored signal badge as raw HTML."""
    bullish = {"BULLISH", "STRONG_GROWTH", "EXCELLENT", "HEALTHY", "IMPROVING"}
    bearish = {"BEARISH", "DECLINING", "UNPROFITABLE", "CRITICAL", "DETERIORATING"}
    if s in bullish:
        return f'<span class="signal-bullish">&#9650; {s}</span>'
    elif s in bearish:
        return f'<span class="signal-bearish">&#9660; {s}</span>'
    return f'<span class="signal-neutral">&#9679; {s}</span>'


def signal_badge(s):
    """Return just the colored text (no background pill)."""
    bullish = {"BULLISH", "STRONG_GROWTH", "EXCELLENT", "HEALTHY", "IMPROVING"}
    bearish = {"BEARISH", "DECLINING", "UNPROFITABLE", "CRITICAL", "DETERIORATING"}
    if s in bullish:
        return f'<span style="color:#06d6a0;font-weight:700">&#9650; {s}</span>'
    elif s in bearish:
        return f'<span style="color:#ef476f;font-weight:700">&#9660; {s}</span>'
    return f'<span style="color:#94a3b8;font-weight:700">&#9679; {s}</span>'


def metric_card(title, value, delta=None):
    """Render a styled metric card."""
    delta_html = ""
    if delta is not None:
        cls = "delta-up" if "+" in str(delta) or (isinstance(delta, (int, float)) and delta > 0) else "delta-down"
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
    """Render a styled section header with teal accent border."""
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f'<div class="fs-section"><h3>{title}</h3>{sub}</div>',
        unsafe_allow_html=True,
    )


def page_header(title, subtitle=None):
    """Render the page title and subtitle."""
    st.markdown(f'<div class="fs-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="fs-subtitle">{subtitle}</div>', unsafe_allow_html=True)


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
    """Render a gradient data source card."""
    st.markdown(
        f'<div class="ds-card">'
        f'<div class="icon">{icon}</div>'
        f'<div class="name">{name}</div>'
        f'<div class="sub">{subtitle}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
