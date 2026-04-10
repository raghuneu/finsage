-- Clean and enrich news data

WITH source AS (
    SELECT * FROM {{ source('raw', 'raw_news') }}
),

cleaned AS (
    SELECT
        article_id,
        ticker,
        title,
        description,
        content,
        author,
        source_name,
        url,
        published_at,
        ingested_at,
        data_quality_score,

        -- ── Cortex ML sentiment (-1.0 to +1.0) ───────────────
        -- Feed title + description for richer signal than title alone
        SNOWFLAKE.CORTEX.SENTIMENT(
            COALESCE(title, '') || ' ' || COALESCE(description, '')
        )                                           AS sentiment_score,

        -- ── Derived sentiment label ───────────────────────────
        CASE
            WHEN SNOWFLAKE.CORTEX.SENTIMENT(
                COALESCE(title, '') || ' ' || COALESCE(description, '')
            ) >= 0.2  THEN 'positive'
            WHEN SNOWFLAKE.CORTEX.SENTIMENT(
                COALESCE(title, '') || ' ' || COALESCE(description, '')
            ) <= -0.2 THEN 'negative'
            ELSE 'neutral'
        END                                         AS sentiment,

        -- Validation flag
        CASE
            WHEN title IS NULL THEN FALSE
            WHEN url IS NULL THEN FALSE
            WHEN published_at IS NULL THEN FALSE
            ELSE TRUE
        END AS is_valid

    FROM source
    WHERE published_at >= DATEADD(month, -3, CURRENT_DATE())
)

SELECT * FROM cleaned
WHERE is_valid = TRUE
