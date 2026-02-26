-- Clean and standardize SEC EDGAR filings data

WITH source AS (
    SELECT * FROM {{ source('raw', 'raw_sec_filings') }}
),

cleaned AS (
    SELECT
        ticker,
        cik,
        concept,
        label,
        period_start,
        period_end,
        value,
        unit,
        fiscal_year,
        fiscal_period,
        form_type,
        filed_date,
        accession_no,
        source,
        ingested_at,
        data_quality_score,

        -- Flag annual vs quarterly
        CASE 
            WHEN fiscal_period = 'FY' THEN 'annual'
            ELSE 'quarterly'
        END AS reporting_frequency,

        -- Validation flag
        CASE
            WHEN value IS NULL THEN FALSE
            WHEN period_end IS NULL THEN FALSE
            WHEN fiscal_year IS NULL THEN FALSE
            ELSE TRUE
        END AS is_valid

    FROM source
)

SELECT * FROM cleaned
WHERE is_valid = TRUE
