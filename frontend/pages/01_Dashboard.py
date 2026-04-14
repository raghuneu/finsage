"""
FinSage Dashboard - Real-time company metrics and market signals.

Queries Snowflake analytics tables directly (no document_agent dependency)
to display key metrics, signals, interactive price chart, and recent headlines.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.connections import get_snowflake, render_sidebar
from utils.styles import inject_css, create_plotly_template
from utils.helpers import (
    page_header, signal_html, fmt_money, metric_card,
    require_snowflake, safe_query, safe_collect, section_header,
    sanitize_ticker, esc,
)

inject_css()
ticker = sanitize_ticker(render_sidebar())
session = get_snowflake()

page_header(f"Dashboard -- {ticker}", "Real-time company metrics and market signals")
require_snowflake(session)

TPL = create_plotly_template()

# ── Fetch data from analytics layer ────────────────────────────
profile = {}
try:
    rows = session.sql(f"""
        SELECT MARKET_CAP, MARKET_CAP_CATEGORY, PE_RATIO, PROFIT_MARGIN,
               DEBT_TO_EQUITY, TOTAL_TRADING_DAYS, TOTAL_NEWS_ARTICLES,
               DATA_SOURCES_AVAILABLE
        FROM ANALYTICS.DIM_COMPANY
        WHERE TICKER = '{ticker}'
    """).collect()
    if rows:
        r = rows[0]
        profile = {
            "market_cap": r["MARKET_CAP"],
            "pe_ratio": r["PE_RATIO"],
            "profit_margin": r["PROFIT_MARGIN"],
        }
except Exception:
    pass

stock = {}
try:
    rows = session.sql(f"""
        SELECT DATE, CLOSE, OPEN, HIGH, LOW, VOLUME,
               DAILY_RETURN_PCT, SMA_7D, SMA_30D, SMA_90D,
               VOLATILITY_30D_PCT, TREND_SIGNAL
        FROM ANALYTICS.FCT_STOCK_METRICS
        WHERE TICKER = '{ticker}'
        ORDER BY DATE DESC
        LIMIT 1
    """).collect()
    if rows:
        r = rows[0]
        stock = {
            "close": r["CLOSE"],
            "daily_return_pct": r["DAILY_RETURN_PCT"],
            "trend_signal": r["TREND_SIGNAL"],
        }
except Exception:
    pass

fundamentals = {}
try:
    rows = session.sql(f"""
        SELECT REVENUE, REVENUE_GROWTH_YOY_PCT, NET_INCOME,
               EPS, FUNDAMENTAL_SIGNAL
        FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
        WHERE TICKER = '{ticker}'
        ORDER BY FISCAL_QUARTER DESC
        LIMIT 1
    """).collect()
    if rows:
        r = rows[0]
        fundamentals = {
            "revenue": r["REVENUE"],
            "revenue_growth_yoy_pct": r["REVENUE_GROWTH_YOY_PCT"],
            "fundamental_signal": r["FUNDAMENTAL_SIGNAL"],
        }
except Exception:
    pass

sentiment = {}
try:
    rows = session.sql(f"""
        SELECT SENTIMENT_SCORE, SENTIMENT_LABEL, SENTIMENT_TREND
        FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG
        WHERE TICKER = '{ticker}'
        ORDER BY NEWS_DATE DESC
        LIMIT 1
    """).collect()
    if rows:
        r = rows[0]
        sentiment = {
            "sentiment_score": r["SENTIMENT_SCORE"],
            "sentiment_label": r["SENTIMENT_LABEL"],
            "sentiment_trend": r["SENTIMENT_TREND"],
        }
except Exception:
    pass

sec_fin = {}
try:
    rows = session.sql(f"""
        SELECT FINANCIAL_HEALTH
        FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
        WHERE TICKER = '{ticker}'
        ORDER BY FISCAL_YEAR DESC, FISCAL_PERIOD DESC
        LIMIT 1
    """).collect()
    if rows:
        sec_fin = {"financial_health": rows[0]["FINANCIAL_HEALTH"]}
except Exception:
    pass

# ── Key Metrics Row ────────────────────────────────────────────
section_header("Key Metrics", "Latest data from the analytics layer")

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    metric_card("Market Cap", fmt_money(profile.get("market_cap")))
with c2:
    price = stock.get("close")
    ret = stock.get("daily_return_pct")
    price_str = f"${price:.2f}" if price is not None else "N/A"
    delta_str = f"{ret:+.2f}%" if ret is not None else None
    metric_card("Price", price_str, delta_str)
with c3:
    rev = fundamentals.get("revenue")
    yoy = fundamentals.get("revenue_growth_yoy_pct")
    yoy_str = f"{yoy:+.1f}% YoY" if yoy is not None else None
    metric_card("Revenue", fmt_money(rev), yoy_str)
with c4:
    score = sentiment.get("sentiment_score")
    trend = sentiment.get("sentiment_trend", "")
    score_str = f"{score:.3f}" if score is not None else "N/A"
    metric_card("Sentiment", score_str, trend if trend else None)
with c5:
    pe = profile.get("pe_ratio")
    metric_card("P/E Ratio", f"{pe:.1f}" if pe else "N/A")

st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)

# ── Signals Row ────────────────────────────────────────────────
section_header("Market Signals")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown("**Stock Trend**")
    st.markdown(signal_html(stock.get("trend_signal", "N/A")), unsafe_allow_html=True)
with c2:
    st.markdown("**Fundamentals**")
    st.markdown(signal_html(fundamentals.get("fundamental_signal", "N/A")), unsafe_allow_html=True)
with c3:
    st.markdown("**Sentiment**")
    st.markdown(signal_html(sentiment.get("sentiment_label", "N/A")), unsafe_allow_html=True)
with c4:
    st.markdown("**Financial Health**")
    st.markdown(signal_html(sec_fin.get("financial_health", "N/A")), unsafe_allow_html=True)

st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)

# ── Price Chart (Plotly with SMAs + Volume) ───────────────────
section_header("Price History", "Last 90 trading days with moving averages")

price_df = safe_query(session, f"""
    SELECT DATE, OPEN, HIGH, LOW, CLOSE, VOLUME, SMA_7D, SMA_30D, SMA_90D
    FROM ANALYTICS.FCT_STOCK_METRICS
    WHERE TICKER = '{ticker}'
    ORDER BY DATE DESC
    LIMIT 90
""")

if price_df is not None and not price_df.empty:
    price_df = price_df.sort_values("DATE")

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03,
    )

    # Price line
    fig.add_trace(go.Scatter(
        x=price_df["DATE"], y=price_df["CLOSE"],
        name="Close", line=dict(color="#00d4ff", width=2),
        hovertemplate="$%{y:.2f}<extra>Close</extra>",
    ), row=1, col=1)

    # SMAs
    for sma, color, dash in [
        ("SMA_7D", "#00ff88", None),
        ("SMA_30D", "#ffaa00", "dot"),
        ("SMA_90D", "#ff3366", "dash"),
    ]:
        if sma in price_df.columns:
            fig.add_trace(go.Scatter(
                x=price_df["DATE"], y=price_df[sma],
                name=sma.replace("_", " "),
                line=dict(color=color, width=1, dash=dash),
                opacity=0.7,
                hovertemplate="$%{y:.2f}<extra>" + sma.replace("_", " ") + "</extra>",
            ), row=1, col=1)

    # Volume bars
    colors = ["#00ff88" if c >= o else "#ff3366"
              for c, o in zip(price_df["CLOSE"], price_df["OPEN"])]
    fig.add_trace(go.Bar(
        x=price_df["DATE"], y=price_df["VOLUME"],
        name="Volume", marker_color=colors, opacity=0.5,
        hovertemplate="%{y:,.0f}<extra>Volume</extra>",
    ), row=2, col=1)

    fig.update_layout(
        **TPL,
        height=500,
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)", font=dict(color="#e5e7eb", size=11),
            bordercolor="rgba(0,0,0,0)",
        ),
        xaxis2=dict(gridcolor="#1f2937", linecolor="#1f2937", tickfont=dict(color="#6b7280")),
        yaxis2=dict(gridcolor="#1f2937", linecolor="#1f2937", tickfont=dict(color="#6b7280")),
        xaxis_rangeslider_visible=False,
    )
    fig.update_yaxes(title_text="Price ($)", row=1, col=1, title_font=dict(color="#6b7280"))
    fig.update_yaxes(title_text="Vol", row=2, col=1, title_font=dict(color="#6b7280"))

    # Range selector
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=3, label="3M", step="month", stepmode="backward"),
                dict(step="all", label="All"),
            ]),
            bgcolor="#111827",
            activecolor="#00d4ff",
            font=dict(color="#e5e7eb"),
        ),
        row=1, col=1,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.markdown(
        '<div class="fs-card" style="text-align:center;color:#6b7280">'
        'No price history available for this ticker.</div>',
        unsafe_allow_html=True,
    )

st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)

# ── Recent Headlines ───────────────────────────────────────────
section_header("Recent Headlines", "Latest news articles from the data pipeline")

headlines_df = safe_query(session, f"""
    SELECT TITLE, PUBLISHED_AT, SOURCE_NAME
    FROM RAW.RAW_NEWS
    WHERE TICKER = '{ticker}'
      AND TITLE IS NOT NULL
    ORDER BY PUBLISHED_AT DESC
    LIMIT 10
""")

if headlines_df is not None and not headlines_df.empty:
    for _, row in headlines_df.iterrows():
        title = esc(str(row["TITLE"])[:140])
        pub = esc(str(row.get("PUBLISHED_AT", ""))[:10])
        source_name = esc(str(row.get("SOURCE_NAME", "")))
        st.markdown(
            f'<div style="padding:8px 0;border-bottom:1px solid #1f2937">'
            f'<span class="status-dot green"></span>'
            f'<span style="color:#f9fafb;font-weight:500">{title}</span> &nbsp; '
            f'<span style="color:#4b5563;font-size:0.8rem">{pub}'
            f'{" | " + source_name if source_name else ""}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        '<div class="fs-card" style="text-align:center;color:#6b7280">'
        'No recent headlines available for this ticker.</div>',
        unsafe_allow_html=True,
    )
