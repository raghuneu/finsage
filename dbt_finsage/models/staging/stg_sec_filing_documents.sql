-- Clean and standardize SEC filing documents (MD&A, Risk Factors)

WITH source AS (
    SELECT * FROM {{ source('raw', 'raw_sec_filing_documents') }}
),

cleaned AS (
    SELECT
        filing_id,
        ticker,
        cik,
        form_type,
        filing_date,
        period_of_report,
        fiscal_year,
        fiscal_period,
        company_name,
        s3_raw_key,
        s3_mda_key,
        s3_risk_key,
        file_format,
        file_size_bytes,
        mda_text,
        risk_factors_text,
        mda_word_count,
        risk_word_count,
        download_status,
        extraction_status,
        extraction_error,
        data_quality_score,
        source,
        ingested_at,
        updated_at,

        -- Derived flags
        CASE
            WHEN mda_text IS NOT NULL AND LENGTH(mda_text) > 100 THEN TRUE
            ELSE FALSE
        END AS has_mda,

        CASE
            WHEN risk_factors_text IS NOT NULL AND LENGTH(risk_factors_text) > 100 THEN TRUE
            ELSE FALSE
        END AS has_risk_factors,

        -- Validation flag
        CASE
            WHEN filing_id IS NULL THEN FALSE
            WHEN ticker IS NULL THEN FALSE
            WHEN form_type NOT IN ('10-K', '10-Q') THEN FALSE
            ELSE TRUE
        END AS is_valid

    FROM source
)

SELECT * FROM cleaned
WHERE is_valid = TRUE
