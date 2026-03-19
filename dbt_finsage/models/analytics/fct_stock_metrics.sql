{{
    config(
        materialized='table',
        schema='ANALYTICS'
    )
}}

-- ──────────────────────────────────────────────────────────────
-- fct_stock_metrics
-- Daily stock metrics with rolling averages and volatility.
-- Grain: one row per ticker per trading day.
-- ──────────────────────────────────────────────────────────────

WITH base AS (
    SELECT
        ticker,
        date,
        open,
        high,
        low,
        close,
        volume,
        daily_return
    FROM {{ ref('stg_stock_prices') }}
),

with_metrics AS (
    SELECT
        ticker,
        date,
        open,
        high,
        low,
        close,
        volume,
        daily_return,

        -- ── Rolling averages ──────────────────────────────────
        AVG(close) OVER (
            PARTITION BY ticker
            ORDER BY date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS sma_7d,

        AVG(close) OVER (
            PARTITION BY ticker
            ORDER BY date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS sma_30d,

        AVG(close) OVER (
            PARTITION BY ticker
            ORDER BY date
            ROWS BETWEEN 89 PRECEDING AND CURRENT ROW
        ) AS sma_90d,

        -- ── Volume moving average ─────────────────────────────
        AVG(volume) OVER (
            PARTITION BY ticker
            ORDER BY date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS avg_volume_30d,

        -- ── Volatility (std dev of daily returns, 30d) ────────
        STDDEV(daily_return) OVER (
            PARTITION BY ticker
            ORDER BY date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS volatility_30d,

        -- ── Price range ───────────────────────────────────────
        high - low AS daily_range,

        ROUND(((high - low) / NULLIF(close, 0)) * 100, 4)
            AS daily_range_pct,

        -- ── 52-week high / low ────────────────────────────────
        MAX(high) OVER (
            PARTITION BY ticker
            ORDER BY date
            ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
        ) AS week_52_high,

        MIN(low) OVER (
            PARTITION BY ticker
            ORDER BY date
            ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
        ) AS week_52_low,

        -- ── Relative position within 52-week range ───────────
        ROUND(
            (close - MIN(low) OVER (
                PARTITION BY ticker ORDER BY date
                ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
            ))
            / NULLIF(
                MAX(high) OVER (
                    PARTITION BY ticker ORDER BY date
                    ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
                )
                - MIN(low) OVER (
                    PARTITION BY ticker ORDER BY date
                    ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
                ), 0
            ) * 100, 2
        ) AS price_position_52w_pct

    FROM base
)

SELECT
    ticker,
    date,
    open,
    high,
    low,
    close,
    volume,
    ROUND(daily_return * 100, 4)        AS daily_return_pct,
    ROUND(sma_7d, 4)                    AS sma_7d,
    ROUND(sma_30d, 4)                   AS sma_30d,
    ROUND(sma_90d, 4)                   AS sma_90d,
    ROUND(avg_volume_30d, 0)            AS avg_volume_30d,
    ROUND(volatility_30d * 100, 4)      AS volatility_30d_pct,
    ROUND(daily_range, 4)               AS daily_range,
    daily_range_pct,
    week_52_high,
    week_52_low,
    price_position_52w_pct,

    -- ── Derived signals (useful for report generation later) ──
    CASE
        WHEN close > sma_30d AND sma_7d > sma_30d THEN 'BULLISH'
        WHEN close < sma_30d AND sma_7d < sma_30d THEN 'BEARISH'
        ELSE 'NEUTRAL'
    END AS trend_signal,

    CURRENT_TIMESTAMP() AS dbt_updated_at

FROM with_metrics
ORDER BY ticker, date
