{{
    config(
        materialized='table',
        schema='ANALYTICS'
    )
}}

-- ──────────────────────────────────────────────────────────────
-- fct_fundamentals_growth
-- Quarterly fundamentals with QoQ and YoY growth rates.
-- Grain: one row per ticker per fiscal quarter.
-- ──────────────────────────────────────────────────────────────

WITH base AS (
    SELECT
        ticker,
        fiscal_quarter,
        market_cap,
        revenue,
        net_income,
        eps,
        pe_ratio,
        profit_margin,
        debt_to_equity,
        total_assets,
        total_liabilities
    FROM {{ ref('stg_fundamentals') }}
),

with_growth AS (
    SELECT
        ticker,
        fiscal_quarter,
        market_cap,
        revenue,
        net_income,
        eps,
        pe_ratio,
        profit_margin,
        debt_to_equity,
        total_assets,
        total_liabilities,

        -- ── Derived metrics ───────────────────────────────────
        total_assets - total_liabilities        AS book_value,

        ROUND(
            (net_income / NULLIF(total_assets, 0)) * 100, 4
        )                                       AS return_on_assets_pct,

        ROUND(
            (net_income / NULLIF(revenue, 0)) * 100, 4
        )                                       AS net_margin_pct,

        -- ── QoQ Growth (vs previous quarter) ─────────────────
        LAG(revenue, 1) OVER (
            PARTITION BY ticker ORDER BY fiscal_quarter
        )                                       AS revenue_prev_quarter,

        ROUND(
            (revenue - LAG(revenue, 1) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            )) / NULLIF(LAG(revenue, 1) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            ), 0) * 100, 4
        )                                       AS revenue_growth_qoq_pct,

        ROUND(
            (net_income - LAG(net_income, 1) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            )) / NULLIF(ABS(LAG(net_income, 1) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            )), 0) * 100, 4
        )                                       AS net_income_growth_qoq_pct,

        ROUND(
            (eps - LAG(eps, 1) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            )) / NULLIF(ABS(LAG(eps, 1) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            )), 0) * 100, 4
        )                                       AS eps_growth_qoq_pct,

        -- ── YoY Growth (vs same quarter last year) ────────────
        LAG(revenue, 4) OVER (
            PARTITION BY ticker ORDER BY fiscal_quarter
        )                                       AS revenue_same_quarter_ly,

        ROUND(
            (revenue - LAG(revenue, 4) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            )) / NULLIF(LAG(revenue, 4) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            ), 0) * 100, 4
        )                                       AS revenue_growth_yoy_pct,

        ROUND(
            (net_income - LAG(net_income, 4) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            )) / NULLIF(ABS(LAG(net_income, 4) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            )), 0) * 100, 4
        )                                       AS net_income_growth_yoy_pct,

        ROUND(
            (eps - LAG(eps, 4) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            )) / NULLIF(ABS(LAG(eps, 4) OVER (
                PARTITION BY ticker ORDER BY fiscal_quarter
            )), 0) * 100, 4
        )                                       AS eps_growth_yoy_pct

    FROM base
)

SELECT
    ticker,
    fiscal_quarter,
    market_cap,
    revenue,
    net_income,
    eps,
    pe_ratio,
    profit_margin,
    debt_to_equity,
    total_assets,
    total_liabilities,
    book_value,
    return_on_assets_pct,
    net_margin_pct,

    -- QoQ
    revenue_prev_quarter,
    revenue_growth_qoq_pct,
    net_income_growth_qoq_pct,
    eps_growth_qoq_pct,

    -- YoY
    revenue_same_quarter_ly,
    revenue_growth_yoy_pct,
    net_income_growth_yoy_pct,
    eps_growth_yoy_pct,

    -- ── Health signal ─────────────────────────────────────────
    CASE
        WHEN revenue_growth_yoy_pct > 10 AND net_income_growth_yoy_pct > 0
            THEN 'STRONG_GROWTH'
        WHEN revenue_growth_yoy_pct > 0 AND net_income_growth_yoy_pct > 0
            THEN 'MODERATE_GROWTH'
        WHEN revenue_growth_yoy_pct < 0 AND net_income_growth_yoy_pct < 0
            THEN 'DECLINING'
        ELSE 'MIXED'
    END AS fundamental_signal,

    CURRENT_TIMESTAMP() AS dbt_updated_at

FROM with_growth
ORDER BY ticker, fiscal_quarter
