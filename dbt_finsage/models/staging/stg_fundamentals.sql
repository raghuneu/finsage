-- Clean and standardize fundamentals data

WITH source AS (
    SELECT * FROM {{ source('raw', 'raw_fundamentals') }}
),

cleaned AS (
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
        source,
        ingested_at,
        data_quality_score,
        
        -- Validation flag
        CASE 
            WHEN revenue IS NULL THEN FALSE
            WHEN market_cap IS NULL THEN FALSE
            WHEN revenue < 0 THEN FALSE
            ELSE TRUE
        END AS is_valid
        
    FROM source
)

SELECT * FROM cleaned
WHERE is_valid = TRUE
