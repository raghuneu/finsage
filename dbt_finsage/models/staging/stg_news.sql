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

        SNOWFLAKE.CORTEX.SENTIMENT(COALESCE(description, title)) AS sentiment_score,
        CASE
            WHEN SNOWFLAKE.CORTEX.SENTIMENT(COALESCE(description, title)) > 0.1 THEN 'positive'
            WHEN SNOWFLAKE.CORTEX.SENTIMENT(COALESCE(description, title)) < -0.1 THEN 'negative'
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
