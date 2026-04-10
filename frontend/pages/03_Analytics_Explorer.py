import streamlit as st
from utils.connections import get_snowflake, get_ticker
from utils.styles import inject_css
from utils.helpers import page_header, signal_html, require_snowflake, safe_query

inject_css()
session = get_snowflake()
ticker = get_ticker()

page_header(f"Analytics Explorer — {ticker}", "Interactive views of the ANALYTICS layer")
require_snowflake(session)

t1, t2, t3, t4 = st.tabs(["Stock Metrics", "Fundamentals", "Sentiment", "SEC Financials"])

with t1:
    df = safe_query(session, f"""
        SELECT DATE, CLOSE, SMA_7D, SMA_30D, SMA_90D, VOLUME,
               DAILY_RETURN_PCT, VOLATILITY_30D_PCT, TREND_SIGNAL
        FROM ANALYTICS.FCT_STOCK_METRICS
        WHERE TICKER='{ticker}' ORDER BY DATE DESC LIMIT 90
    """)
    if df is not None and not df.empty:
        st.markdown(f"**Trend:** {signal_html(df.iloc[0]['TREND_SIGNAL'])}", unsafe_allow_html=True)
        chart_df = df[["DATE", "CLOSE", "SMA_7D", "SMA_30D"]].sort_values("DATE").set_index("DATE")
        st.line_chart(chart_df)
        st.dataframe(df.head(20), use_container_width=True)
    else:
        st.info("No stock metrics available.")

with t2:
    df = safe_query(session, f"""
        SELECT FISCAL_QUARTER, REVENUE, NET_INCOME, EPS,
               REVENUE_GROWTH_QOQ_PCT, REVENUE_GROWTH_YOY_PCT,
               NET_MARGIN_PCT, FUNDAMENTAL_SIGNAL
        FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
        WHERE TICKER='{ticker}' ORDER BY FISCAL_QUARTER DESC LIMIT 12
    """)
    if df is not None and not df.empty:
        st.markdown(f"**Signal:** {signal_html(df.iloc[0]['FUNDAMENTAL_SIGNAL'])}", unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No fundamentals data available.")

with t3:
    df = safe_query(session, f"""
        SELECT NEWS_DATE, TOTAL_ARTICLES, POSITIVE_COUNT, NEGATIVE_COUNT,
               SENTIMENT_SCORE, SENTIMENT_SCORE_7D_AVG,
               SENTIMENT_LABEL, SENTIMENT_TREND
        FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG
        WHERE TICKER='{ticker}' ORDER BY NEWS_DATE DESC LIMIT 30
    """)
    if df is not None and not df.empty:
        label = df.iloc[0]["SENTIMENT_LABEL"]
        trend = df.iloc[0]["SENTIMENT_TREND"]
        st.markdown(f"**Sentiment:** {signal_html(label)} ({trend})", unsafe_allow_html=True)
        chart_df = df[["NEWS_DATE", "SENTIMENT_SCORE", "SENTIMENT_SCORE_7D_AVG"]].sort_values("NEWS_DATE").set_index("NEWS_DATE")
        st.line_chart(chart_df)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No sentiment data available.")

with t4:
    df = safe_query(session, f"""
        SELECT FISCAL_YEAR, FISCAL_PERIOD, TOTAL_REVENUE, NET_INCOME,
               OPERATING_MARGIN_PCT, NET_MARGIN_PCT, RETURN_ON_EQUITY_PCT,
               DEBT_TO_EQUITY_RATIO, REVENUE_GROWTH_YOY_PCT, FINANCIAL_HEALTH
        FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
        WHERE TICKER='{ticker}' ORDER BY FISCAL_YEAR DESC LIMIT 10
    """)
    if df is not None and not df.empty:
        st.markdown(f"**Health:** {signal_html(df.iloc[0]['FINANCIAL_HEALTH'])}", unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No SEC financial data available.")
