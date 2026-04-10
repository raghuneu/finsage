{{
    config(
        materialized='table',
        schema='ANALYTICS'
    )
}}

-- ──────────────────────────────────────────────────────────────
-- fct_news_sentiment_agg
-- Daily aggregated news sentiment per ticker.
-- Grain: one row per ticker per day.
-- Now uses Snowflake Cortex ML sentiment scores.
-- ──────────────────────────────────────────────────────────────

WITH base AS (
    SELECT
        ticker,
        article_id,
        title,
        published_at,
        DATE(published_at)  AS news_date,
        sentiment,           -- 'positive' | 'negative' | 'neutral' (Cortex-derived)
        sentiment_score,     -- float -1.0 to +1.0 from CORTEX.SENTIMENT()
        data_quality_score
    FROM {{ ref('stg_news') }}
),

daily_agg AS (
    SELECT
        ticker,
        news_date,

        -- ── Volume metrics ────────────────────────────────────
        COUNT(article_id)                           AS total_articles,

        COUNT(CASE WHEN sentiment = 'positive' THEN 1 END)
                                                    AS positive_count,
        COUNT(CASE WHEN sentiment = 'negative' THEN 1 END)
                                                    AS negative_count,
        COUNT(CASE WHEN sentiment = 'neutral'  THEN 1 END)
                                                    AS neutral_count,

        -- ── Daily sentiment score: avg of Cortex scores ───────
        -- More precise than the old (+1 / -1 / 0) integer method
        ROUND(AVG(sentiment_score), 4)              AS sentiment_score,

        -- ── Sentiment ratio (% positive of non-neutral) ───────
        ROUND(
            COUNT(CASE WHEN sentiment = 'positive' THEN 1 END)
            / NULLIF(
                COUNT(CASE WHEN sentiment IN ('positive','negative') THEN 1 END)
            , 0) * 100
        , 2)                                        AS positive_ratio_pct,

        -- ── Average data quality of articles ─────────────────
        ROUND(AVG(data_quality_score), 2)           AS avg_data_quality

    FROM base
    GROUP BY ticker, news_date
),

with_rolling AS (
    SELECT
        ticker,
        news_date,
        total_articles,
        positive_count,
        negative_count,
        neutral_count,
        sentiment_score,
        positive_ratio_pct,
        avg_data_quality,

        -- ── 7-day rolling sentiment average ───────────────────
        ROUND(
            AVG(sentiment_score) OVER (
                PARTITION BY ticker
                ORDER BY news_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            )
        , 4)                                        AS sentiment_score_7d_avg,

        -- ── 7-day rolling article volume ──────────────────────
        SUM(total_articles) OVER (
            PARTITION BY ticker
            ORDER BY news_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        )                                           AS articles_7d_total,

        -- ── News momentum (today's volume vs 7d avg) ─────────
        ROUND(
            total_articles / NULLIF(
                AVG(total_articles) OVER (
                    PARTITION BY ticker
                    ORDER BY news_date
                    ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                )
            , 0)
        , 4)                                        AS news_volume_momentum

    FROM daily_agg
)

SELECT
    ticker,
    news_date,
    total_articles,
    positive_count,
    negative_count,
    neutral_count,
    sentiment_score,
    sentiment_score_7d_avg,
    positive_ratio_pct,
    articles_7d_total,
    news_volume_momentum,
    avg_data_quality,

    -- ── Daily sentiment label ─────────────────────────────────
    CASE
        WHEN sentiment_score >= 0.2  THEN 'BULLISH'
        WHEN sentiment_score <= -0.2 THEN 'BEARISH'
        WHEN total_articles = 0      THEN 'NO_COVERAGE'
        ELSE 'NEUTRAL'
    END                                             AS sentiment_label,

    -- ── Trend vs 7-day average ────────────────────────────────
    CASE
        WHEN sentiment_score > sentiment_score_7d_avg + 0.1 THEN 'IMPROVING'
        WHEN sentiment_score < sentiment_score_7d_avg - 0.1 THEN 'DETERIORATING'
        ELSE 'STABLE'
    END                                             AS sentiment_trend,

    CURRENT_TIMESTAMP()                             AS dbt_updated_at

FROM with_rolling
ORDER BY ticker, news_date
