{{
    config(
        materialized='table',
        schema='ANALYTICS'
    )
}}

-- ──────────────────────────────────────────────────────────────
-- dim_company
-- One row per ticker with descriptive company attributes.
-- Grain: one row per ticker.
-- ──────────────────────────────────────────────────────────────

WITH tickers AS (
    SELECT DISTINCT ticker FROM {{ ref('stg_stock_prices') }}
),

latest_fundamentals AS (
    SELECT
        ticker,
        market_cap,
        pe_ratio,
        profit_margin,
        debt_to_equity
    FROM {{ ref('stg_fundamentals') }}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_quarter DESC) = 1
),

latest_sec AS (
    SELECT
        ticker,
        cik,
        form_type AS latest_form_type
    FROM {{ ref('stg_sec_filings') }}
    QUALIFY ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY filed_date DESC) = 1
),

news_coverage AS (
    SELECT
        ticker,
        COUNT(*)            AS total_news_articles,
        MIN(published_at)   AS earliest_news_date,
        MAX(published_at)   AS latest_news_date
    FROM {{ ref('stg_news') }}
    GROUP BY ticker
),

stock_range AS (
    SELECT
        ticker,
        MIN(date)           AS price_history_start,
        MAX(date)           AS price_history_end,
        COUNT(*)            AS total_trading_days
    FROM {{ ref('stg_stock_prices') }}
    GROUP BY ticker
)

SELECT
    t.ticker,

    -- SEC identifiers
    s.cik,
    s.latest_form_type,

    -- Fundamentals snapshot
    f.market_cap,
    f.pe_ratio,
    f.profit_margin,
    -- Yahoo Finance reports D/E as a percentage (e.g. 63.78 = 63.78%);
    -- normalise to a ratio (0.6378) consistent with FCT_SEC_FINANCIAL_SUMMARY.
    ROUND(f.debt_to_equity / 100, 4) AS debt_to_equity,

    -- Price data availability
    sr.price_history_start,
    sr.price_history_end,
    sr.total_trading_days,

    -- News coverage
    nc.total_news_articles,
    nc.earliest_news_date,
    nc.latest_news_date,

    -- ── Company size classification ───────────────────────────
    CASE
        WHEN f.market_cap >= 200000000000 THEN 'MEGA_CAP'
        WHEN f.market_cap >= 10000000000  THEN 'LARGE_CAP'
        WHEN f.market_cap >= 2000000000   THEN 'MID_CAP'
        WHEN f.market_cap >= 300000000    THEN 'SMALL_CAP'
        WHEN f.market_cap IS NOT NULL     THEN 'MICRO_CAP'
        ELSE 'UNKNOWN'
    END                                     AS market_cap_category,

    -- ── Data completeness score ───────────────────────────────
    (
        CASE WHEN sr.ticker IS NOT NULL THEN 1 ELSE 0 END +
        CASE WHEN f.ticker  IS NOT NULL THEN 1 ELSE 0 END +
        CASE WHEN nc.ticker IS NOT NULL THEN 1 ELSE 0 END +
        CASE WHEN s.ticker  IS NOT NULL THEN 1 ELSE 0 END
    )                                       AS data_sources_available,

    CURRENT_TIMESTAMP()                     AS dbt_updated_at

FROM tickers t
LEFT JOIN latest_fundamentals f  ON t.ticker = f.ticker
LEFT JOIN latest_sec          s  ON t.ticker = s.ticker
LEFT JOIN news_coverage       nc ON t.ticker = nc.ticker
LEFT JOIN stock_range         sr ON t.ticker = sr.ticker

ORDER BY t.ticker
