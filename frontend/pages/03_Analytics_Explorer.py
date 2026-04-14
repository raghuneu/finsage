"""
FinSage Analytics Explorer - Interactive views of the ANALYTICS layer.

Four tabs: Stock Metrics, Fundamentals, Sentiment, and SEC Financials.
All charts powered by Plotly with dark Bloomberg-style theme.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.connections import get_snowflake, render_sidebar
from utils.styles import inject_css, create_plotly_template
from utils.helpers import (
    page_header, signal_html, require_snowflake, safe_query, section_header, fmt_money,
    sanitize_ticker,
)

inject_css()
ticker = sanitize_ticker(render_sidebar())
session = get_snowflake()

TPL = create_plotly_template()

page_header(f"Analytics Explorer -- {ticker}", "Interactive views of the ANALYTICS layer")
require_snowflake(session)

t1, t2, t3, t4 = st.tabs(["Stock Metrics", "Fundamentals", "Sentiment", "SEC Financials"])

# ── Tab 1: Stock Metrics ───────────────────────────────────────
with t1:
    section_header("Stock Metrics", "Price history, moving averages, and volatility")

    df = safe_query(session, f"""
        SELECT DATE, OPEN, HIGH, LOW, CLOSE, SMA_7D, SMA_30D, SMA_90D, VOLUME,
               DAILY_RETURN_PCT, VOLATILITY_30D_PCT, TREND_SIGNAL
        FROM ANALYTICS.FCT_STOCK_METRICS
        WHERE TICKER='{ticker}' ORDER BY DATE DESC LIMIT 90
    """)
    if df is not None and not df.empty:
        latest = df.iloc[0]
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Trend:** {signal_html(latest['TREND_SIGNAL'])}", unsafe_allow_html=True)
        with c2:
            close_val = latest['CLOSE']
            st.markdown(f"**Latest Close:** ${close_val:.2f}" if close_val is not None else "**Latest Close:** N/A")
        with c3:
            vol = latest.get('VOLATILITY_30D_PCT')
            st.markdown(f"**30d Volatility:** {vol:.2f}%" if vol is not None else "**30d Volatility:** N/A")

        st.markdown("")

        df_sorted = df.sort_values("DATE")

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.7, 0.3], vertical_spacing=0.03,
        )

        # Price + SMAs
        fig.add_trace(go.Scatter(
            x=df_sorted["DATE"], y=df_sorted["CLOSE"],
            name="Close", line=dict(color="#00d4ff", width=2),
            hovertemplate="$%{y:.2f}<extra>Close</extra>",
        ), row=1, col=1)

        for sma, color, dash in [
            ("SMA_7D", "#00ff88", None), ("SMA_30D", "#ffaa00", "dot"), ("SMA_90D", "#ff3366", "dash"),
        ]:
            if sma in df_sorted.columns:
                fig.add_trace(go.Scatter(
                    x=df_sorted["DATE"], y=df_sorted[sma],
                    name=sma.replace("_", " "), line=dict(color=color, width=1, dash=dash), opacity=0.7,
                ), row=1, col=1)

        # Volume
        colors = ["#00ff88" if c >= o else "#ff3366" for c, o in zip(df_sorted["CLOSE"], df_sorted["OPEN"])]
        fig.add_trace(go.Bar(
            x=df_sorted["DATE"], y=df_sorted["VOLUME"], name="Volume",
            marker_color=colors, opacity=0.5,
        ), row=2, col=1)

        fig.update_layout(**TPL, height=500, showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(0,0,0,0)", font=dict(color="#e5e7eb"), bordercolor="rgba(0,0,0,0)"),
            xaxis2=dict(gridcolor="#1f2937", linecolor="#1f2937", tickfont=dict(color="#6b7280")),
            yaxis2=dict(gridcolor="#1f2937", linecolor="#1f2937", tickfont=dict(color="#6b7280")),
        )
        fig.update_yaxes(title_text="Price ($)", row=1, col=1, title_font=dict(color="#6b7280"))
        fig.update_yaxes(title_text="Vol", row=2, col=1, title_font=dict(color="#6b7280"))

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with st.expander("Raw Data", expanded=False):
            st.dataframe(df.head(30), use_container_width=True)
    else:
        st.markdown('<div class="fs-card" style="text-align:center;color:#6b7280">No stock metrics available.</div>', unsafe_allow_html=True)

# ── Tab 2: Fundamentals ───────────────────────────────────────
with t2:
    section_header("Fundamentals Growth", "Quarterly financials and growth rates")

    df = safe_query(session, f"""
        SELECT FISCAL_QUARTER, REVENUE, NET_INCOME, EPS,
               REVENUE_GROWTH_QOQ_PCT, REVENUE_GROWTH_YOY_PCT,
               NET_MARGIN_PCT, FUNDAMENTAL_SIGNAL
        FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
        WHERE TICKER='{ticker}' ORDER BY FISCAL_QUARTER DESC LIMIT 12
    """)
    if df is not None and not df.empty:
        latest = df.iloc[0]
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Signal:** {signal_html(latest['FUNDAMENTAL_SIGNAL'])}", unsafe_allow_html=True)
        with c2:
            st.markdown(f"**Revenue:** {fmt_money(latest.get('REVENUE'))}")
        with c3:
            eps = latest.get("EPS")
            st.markdown(f"**EPS:** ${eps:.2f}" if eps is not None else "**EPS:** N/A")

        st.markdown("")
        df_sorted = df.sort_values("FISCAL_QUARTER")

        # Revenue bar chart
        rev_df = df_sorted.dropna(subset=["REVENUE"])
        if not rev_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=rev_df["FISCAL_QUARTER"], y=rev_df["REVENUE"],
                marker_color="#00d4ff", name="Revenue",
                text=[fmt_money(v) for v in rev_df["REVENUE"]],
                textposition="outside", textfont=dict(color="#6b7280", size=10),
                hovertemplate="%{x}<br>Revenue: %{text}<extra></extra>",
            ))
            fig.update_layout(**TPL, height=350, title="Quarterly Revenue", showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # EPS area chart
        eps_df = df_sorted.dropna(subset=["EPS"])
        if not eps_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=eps_df["FISCAL_QUARTER"], y=eps_df["EPS"],
                fill="tozeroy", fillcolor="rgba(0,212,255,0.1)",
                line=dict(color="#00d4ff", width=2), name="EPS",
                hovertemplate="%{x}<br>EPS: $%{y:.2f}<extra></extra>",
            ))
            fig.update_layout(**TPL, height=300, title="Earnings Per Share Trend", showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with st.expander("Raw Data", expanded=False):
            st.dataframe(df, use_container_width=True)
    else:
        st.markdown('<div class="fs-card" style="text-align:center;color:#6b7280">No fundamentals data available.</div>', unsafe_allow_html=True)

# ── Tab 3: Sentiment ──────────────────────────────────────────
with t3:
    section_header("News Sentiment", "Daily sentiment aggregation from news articles")

    df = safe_query(session, f"""
        SELECT NEWS_DATE, TOTAL_ARTICLES, POSITIVE_COUNT, NEGATIVE_COUNT,
               SENTIMENT_SCORE, SENTIMENT_SCORE_7D_AVG,
               SENTIMENT_LABEL, SENTIMENT_TREND
        FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG
        WHERE TICKER='{ticker}' ORDER BY NEWS_DATE DESC LIMIT 30
    """)
    if df is not None and not df.empty:
        latest = df.iloc[0]
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Sentiment:** {signal_html(latest['SENTIMENT_LABEL'])}", unsafe_allow_html=True)
        with c2:
            st.markdown(f"**Trend:** {latest.get('SENTIMENT_TREND', 'N/A')}")
        with c3:
            st.markdown(f"**Articles Today:** {latest.get('TOTAL_ARTICLES', 0)}")

        st.markdown("")
        df_sorted = df.sort_values("NEWS_DATE")

        # Sentiment score line with zero reference
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_sorted["NEWS_DATE"], y=df_sorted["SENTIMENT_SCORE"],
            name="Daily Score", line=dict(color="#00d4ff", width=2),
            hovertemplate="%{x}<br>Score: %{y:.3f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df_sorted["NEWS_DATE"], y=df_sorted["SENTIMENT_SCORE_7D_AVG"],
            name="7-Day Avg", line=dict(color="#ffaa00", width=1.5, dash="dot"),
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="#6b7280", opacity=0.5)
        fig.update_layout(**TPL, height=350, title="Sentiment Score", showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(0,0,0,0)", font=dict(color="#e5e7eb"), bordercolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Stacked positive/negative bar
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=df_sorted["NEWS_DATE"], y=df_sorted["POSITIVE_COUNT"],
            name="Positive", marker_color="#00ff88",
        ))
        fig2.add_trace(go.Bar(
            x=df_sorted["NEWS_DATE"], y=df_sorted["NEGATIVE_COUNT"],
            name="Negative", marker_color="#ff3366",
        ))
        fig2.update_layout(**TPL, height=250, barmode="stack", title="Article Sentiment Distribution",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(0,0,0,0)", font=dict(color="#e5e7eb"), bordercolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        with st.expander("Raw Data", expanded=False):
            st.dataframe(df, use_container_width=True)
    else:
        st.markdown('<div class="fs-card" style="text-align:center;color:#6b7280">No sentiment data available.</div>', unsafe_allow_html=True)

# ── Tab 4: SEC Financials ─────────────────────────────────────
with t4:
    section_header("SEC Financial Summary", "Financials extracted from SEC filings (XBRL)")

    df = safe_query(session, f"""
        SELECT FISCAL_YEAR, FISCAL_PERIOD, TOTAL_REVENUE, NET_INCOME,
               OPERATING_MARGIN_PCT, NET_MARGIN_PCT, RETURN_ON_EQUITY_PCT,
               DEBT_TO_EQUITY_RATIO, REVENUE_GROWTH_YOY_PCT, FINANCIAL_HEALTH
        FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
        WHERE TICKER='{ticker}' ORDER BY FISCAL_YEAR DESC LIMIT 10
    """)
    if df is not None and not df.empty:
        latest = df.iloc[0]
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Health:** {signal_html(latest['FINANCIAL_HEALTH'])}", unsafe_allow_html=True)
        with c2:
            st.markdown(f"**Revenue:** {fmt_money(latest.get('TOTAL_REVENUE'))}")
        with c3:
            margin = latest.get("NET_MARGIN_PCT")
            st.markdown(f"**Net Margin:** {margin:.1f}%" if margin is not None else "**Net Margin:** N/A")

        st.markdown("")
        df_sorted = df.sort_values(["FISCAL_YEAR", "FISCAL_PERIOD"])
        df_sorted["PERIOD"] = df_sorted["FISCAL_YEAR"].astype(str) + " " + df_sorted["FISCAL_PERIOD"].astype(str)

        # Revenue bar
        rev_df = df_sorted.dropna(subset=["TOTAL_REVENUE"])
        if not rev_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=rev_df["PERIOD"], y=rev_df["TOTAL_REVENUE"],
                marker_color="#00d4ff", name="Revenue",
                text=[fmt_money(v) for v in rev_df["TOTAL_REVENUE"]],
                textposition="outside", textfont=dict(color="#6b7280", size=10),
            ))
            fig.update_layout(**TPL, height=350, title="Revenue by Period", showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Margin dual-line
        margin_df = df_sorted.dropna(subset=["OPERATING_MARGIN_PCT", "NET_MARGIN_PCT"], how="all")
        if not margin_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=margin_df["PERIOD"], y=margin_df["OPERATING_MARGIN_PCT"],
                name="Operating Margin", line=dict(color="#00ff88", width=2),
                hovertemplate="%{x}<br>Op Margin: %{y:.1f}%<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=margin_df["PERIOD"], y=margin_df["NET_MARGIN_PCT"],
                name="Net Margin", line=dict(color="#00d4ff", width=2),
                fill="tonexty", fillcolor="rgba(0,212,255,0.05)",
                hovertemplate="%{x}<br>Net Margin: %{y:.1f}%<extra></extra>",
            ))
            fig.update_layout(**TPL, height=300, title="Margin Trends", showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            bgcolor="rgba(0,0,0,0)", font=dict(color="#e5e7eb"), bordercolor="rgba(0,0,0,0)"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with st.expander("Raw Data", expanded=False):
            st.dataframe(df, use_container_width=True)
    else:
        st.markdown('<div class="fs-card" style="text-align:center;color:#6b7280">No SEC financial data available.</div>', unsafe_allow_html=True)
