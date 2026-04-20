{{
    config(
        materialized='table',
        schema='ANALYTICS'
    )
}}

-- ──────────────────────────────────────────────────────────────
-- fct_sec_financial_summary
-- Pivots long-format XBRL data into one row per ticker/period.
-- Grain: one row per ticker per fiscal year + fiscal period.
-- ──────────────────────────────────────────────────────────────

WITH base AS (
    SELECT
        ticker,
        cik,
        concept,
        value,
        -- Re-derive fiscal_year from the period end date so that
        -- comparative rows (prior-year data reported in later filings)
        -- land in the correct calendar year.  The XBRL 'fy' field
        -- reflects the filing's own fiscal year, not the period year.
        YEAR(TO_DATE(TRIM(period_end, '"'), 'YYYY-MM-DD'))
                                            AS fiscal_year,
        fiscal_period,
        period_end,
        form_type,
        filed_date,
        reporting_frequency
    FROM {{ ref('stg_sec_filings') }}
),

-- Deduplicate: the same (ticker, concept, fiscal_year, fiscal_period)
-- may appear multiple times across different filings (e.g. 10-K reports
-- current + prior year, and quarterly filings overlap).  Keep the row
-- with the latest period_end; break ties with the most recent filing.
deduped AS (
    SELECT *
    FROM (
        SELECT
            base.*,
            ROW_NUMBER() OVER (
                PARTITION BY ticker, cik, concept, fiscal_year, fiscal_period
                ORDER BY period_end DESC, filed_date DESC
            ) AS _rn
        FROM base
    )
    WHERE _rn = 1
),

-- Pivot: one row per ticker/period, each XBRL concept becomes a column
pivoted AS (
    SELECT
        ticker,
        cik,
        fiscal_year,
        fiscal_period,
        reporting_frequency,

        MAX(CASE WHEN concept = 'Revenues'
            THEN value END)                         AS revenues,

        MAX(CASE WHEN concept = 'RevenueFromContractWithCustomerExcludingAssessedTax'
            THEN value END)                         AS revenue_from_contracts,

        MAX(CASE WHEN concept = 'SalesRevenueNet'
            THEN value END)                         AS sales_revenue_net,

        MAX(CASE WHEN concept = 'SalesRevenueGoodsNet'
            THEN value END)                         AS sales_revenue_goods_net,

        MAX(CASE WHEN concept = 'RevenuesNetOfInterestExpense'
            THEN value END)                         AS revenues_net_of_interest,

        MAX(CASE WHEN concept = 'NetIncomeLoss'
            THEN value END)                         AS net_income,

        MAX(CASE WHEN concept = 'Assets'
            THEN value END)                         AS total_assets,

        MAX(CASE WHEN concept = 'Liabilities'
            THEN value END)                         AS total_liabilities,

        MAX(CASE WHEN concept = 'StockholdersEquity'
            THEN value END)                         AS stockholders_equity,

        MAX(CASE WHEN concept = 'OperatingIncomeLoss'
            THEN value END)                         AS operating_income,

        MAX(CASE WHEN concept = 'EarningsPerShareBasic'
            THEN value END)                         AS eps_basic,

        MAX(CASE WHEN concept = 'EarningsPerShareDiluted'
            THEN value END)                         AS eps_diluted,

        MAX(CASE WHEN concept = 'CashAndCashEquivalentsAtCarryingValue'
            THEN value END)                         AS cash_and_equivalents,

        -- Most recent filing date and form for this period
        MAX(filed_date)                             AS filed_date,
        MAX(form_type)                              AS form_type,
        MAX(period_end)                             AS period_end

    FROM deduped
    GROUP BY ticker, cik, fiscal_year, fiscal_period, reporting_frequency
),

-- Coalesce revenue fields (companies report under different concepts)
with_derived AS (
    SELECT
        ticker,
        cik,
        fiscal_year,
        fiscal_period,
        reporting_frequency,
        period_end,
        filed_date,
        form_type,

        -- Use whichever revenue concept is populated
        COALESCE(revenues, revenue_from_contracts, sales_revenue_net, sales_revenue_goods_net, revenues_net_of_interest)  AS total_revenue,
        revenues,
        revenue_from_contracts,
        sales_revenue_net,
        sales_revenue_goods_net,
        revenues_net_of_interest,
        net_income,
        total_assets,
        total_liabilities,
        stockholders_equity,
        operating_income,
        eps_basic,
        eps_diluted,
        cash_and_equivalents,

        -- ── Derived metrics ───────────────────────────────────
        ROUND(
            net_income / NULLIF(COALESCE(revenues, revenue_from_contracts, sales_revenue_net, sales_revenue_goods_net, revenues_net_of_interest), 0) * 100
        , 4)                                        AS net_margin_pct,

        ROUND(
            operating_income / NULLIF(COALESCE(revenues, revenue_from_contracts, sales_revenue_net, sales_revenue_goods_net, revenues_net_of_interest), 0) * 100
        , 4)                                        AS operating_margin_pct,

        ROUND(
            net_income / NULLIF(total_assets, 0) * 100
        , 4)                                        AS return_on_assets_pct,

        ROUND(
            net_income / NULLIF(stockholders_equity, 0) * 100
        , 4)                                        AS return_on_equity_pct,

        total_assets - total_liabilities            AS book_value,

        ROUND(
            total_liabilities / NULLIF(stockholders_equity, 0)
        , 4)                                        AS debt_to_equity_ratio,

        -- ── YoY growth (vs same period prior year) ────────────
        LAG(COALESCE(revenues, revenue_from_contracts, sales_revenue_net, sales_revenue_goods_net, revenues_net_of_interest), 1) OVER (
            PARTITION BY ticker, fiscal_period
            ORDER BY fiscal_year
        )                                           AS revenue_prior_year,

        ROUND(
            (
                COALESCE(revenues, revenue_from_contracts, sales_revenue_net, sales_revenue_goods_net, revenues_net_of_interest)
                - LAG(COALESCE(revenues, revenue_from_contracts, sales_revenue_net, sales_revenue_goods_net, revenues_net_of_interest), 1) OVER (
                    PARTITION BY ticker, fiscal_period ORDER BY fiscal_year
                )
            ) / NULLIF(
                LAG(COALESCE(revenues, revenue_from_contracts, sales_revenue_net, sales_revenue_goods_net, revenues_net_of_interest), 1) OVER (
                    PARTITION BY ticker, fiscal_period ORDER BY fiscal_year
                )
            , 0) * 100
        , 4)                                        AS revenue_growth_yoy_pct,

        ROUND(
            (
                net_income
                - LAG(net_income, 1) OVER (
                    PARTITION BY ticker, fiscal_period ORDER BY fiscal_year
                )
            ) / NULLIF(
                ABS(LAG(net_income, 1) OVER (
                    PARTITION BY ticker, fiscal_period ORDER BY fiscal_year
                ))
            , 0) * 100
        , 4)                                        AS net_income_growth_yoy_pct

    FROM pivoted
)

SELECT
    ticker,
    cik,
    fiscal_year,
    fiscal_period,
    reporting_frequency,
    period_end,
    filed_date,
    form_type,
    total_revenue,
    net_income,
    operating_income,
    total_assets,
    total_liabilities,
    stockholders_equity,
    cash_and_equivalents,
    eps_basic,
    eps_diluted,
    book_value,
    net_margin_pct,
    operating_margin_pct,
    return_on_assets_pct,
    return_on_equity_pct,
    debt_to_equity_ratio,
    revenue_prior_year,
    revenue_growth_yoy_pct,
    net_income_growth_yoy_pct,

    -- ── Financial health signal ───────────────────────────────
    CASE
        WHEN net_margin_pct > 15 AND revenue_growth_yoy_pct > 10 THEN 'EXCELLENT'
        WHEN net_margin_pct > 5  AND revenue_growth_yoy_pct > 0  THEN 'HEALTHY'
        WHEN net_margin_pct < 0                                   THEN 'UNPROFITABLE'
        ELSE 'FAIR'
    END                                             AS financial_health,

    CURRENT_TIMESTAMP()                             AS dbt_updated_at

FROM with_derived
ORDER BY ticker, fiscal_year, fiscal_period
