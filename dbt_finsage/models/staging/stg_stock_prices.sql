-- Clean and standardize raw stock price data

WITH source AS (
    SELECT * FROM {{ source('raw', 'raw_stock_prices') }}
),

cleaned AS (
    SELECT
        ticker,
        date,
        open,
        high,
        low,
        close,
        volume,
        dividends,
        stock_splits,
        source,
        ingested_at,
        data_quality_score,
        
        -- Calculate daily return
        (close - LAG(close) OVER (PARTITION BY ticker ORDER BY date)) 
            / NULLIF(LAG(close) OVER (PARTITION BY ticker ORDER BY date), 0) AS daily_return,
        
        -- Validation: is data valid?
        CASE 
            WHEN close IS NULL THEN FALSE
            WHEN volume < 0 THEN FALSE
            WHEN close <= 0 THEN FALSE
            WHEN high < low THEN FALSE
            ELSE TRUE
        END AS is_valid
        
    FROM source
    WHERE date >= DATEADD(year, -2, CURRENT_DATE())  -- Last 2 years only
)

SELECT * FROM cleaned
WHERE is_valid = TRUE
