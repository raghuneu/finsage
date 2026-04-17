---
name: dbt-finsage
description: FinSage dbt project patterns — staging views, analytics tables, Cortex enrichment, and testing
---

# dbt Patterns for FinSage

Reference for the `dbt_finsage/` project that transforms raw data into analytics-ready tables.

## Project Structure

```
dbt_finsage/
├── dbt_project.yml
├── profiles.yml
├── macros/
│   └── generate_schema_name.sql    — Custom schema routing
├── models/
│   ├── staging/                    — Views: validate + filter + enrich
│   │   ├── stg_stock_prices.sql
│   │   ├── stg_fundamentals.sql
│   │   ├── stg_news.sql
│   │   └── stg_sec_filings.sql
│   └── analytics/                  — Tables: aggregate + derive signals
│       ├── dim_company.sql
│       ├── dim_date.sql
│       ├── fct_stock_metrics.sql
│       ├── fct_fundamentals_growth.sql
│       ├── fct_news_sentiment_agg.sql
│       └── fct_sec_financial_summary.sql
└── tests/                          — Schema tests (not_null, unique, etc.)
```

## Layer Conventions

### Staging (Views)

- Materialized as **views** (lightweight, always fresh)
- Purpose: validate, filter, rename, type-cast, and enrich raw data
- Naming: `stg_<source_name>.sql`
- Source: RAW schema tables via `{{ source('raw', 'RAW_TABLE_NAME') }}`

Staging models:
1. **Filter** out obviously invalid records (nulls in key columns, future dates)
2. **Rename** columns if needed (rare — RAW already uses UPPER_SNAKE_CASE)
3. **Type-cast** for consistency
4. **Enrich** with Cortex functions:
   ```sql
   -- In stg_news.sql
   SELECT
       TICKER,
       TITLE,
       CONTENT,
       PUBLISHED_AT,
       SNOWFLAKE.CORTEX.SENTIMENT(TITLE || ' ' || COALESCE(CONTENT, '')) AS SENTIMENT_SCORE,
       SOURCE,
       INGESTED_AT
   FROM {{ source('raw', 'RAW_NEWS') }}
   WHERE TICKER IS NOT NULL
     AND PUBLISHED_AT IS NOT NULL
   ```

### Analytics (Tables)

- Materialized as **tables** (pre-computed for query performance)
- Purpose: aggregate, calculate derived metrics, derive categorical signals
- Naming: `dim_<entity>.sql` for dimensions, `fct_<metric>.sql` for facts

Analytics models:
1. **Window functions** for moving averages, growth rates
2. **Signal derivation** via CASE statements
3. **Aggregation** for daily/period-level summaries
4. **Joins** across staging views for cross-referencing

## Key SQL Patterns

### Moving Averages (FCT_STOCK_METRICS)

```sql
SELECT
    TICKER,
    DATE,
    CLOSE_PRICE,
    AVG(CLOSE_PRICE) OVER (
        PARTITION BY TICKER
        ORDER BY DATE
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS SMA_20,
    AVG(CLOSE_PRICE) OVER (
        PARTITION BY TICKER
        ORDER BY DATE
        ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
    ) AS SMA_50
FROM {{ ref('stg_stock_prices') }}
```

### Signal Derivation (TREND_SIGNAL)

```sql
CASE
    WHEN SMA_20 > SMA_50 AND CLOSE_PRICE > SMA_20 THEN 'BULLISH'
    WHEN SMA_20 < SMA_50 AND CLOSE_PRICE < SMA_20 THEN 'BEARISH'
    ELSE 'NEUTRAL'
END AS TREND_SIGNAL
```

### Growth Rates (FCT_FUNDAMENTALS_GROWTH)

```sql
SELECT
    TICKER,
    METRIC_NAME,
    DATE,
    VALUE,
    -- Quarter-over-Quarter
    (VALUE - LAG(VALUE, 1) OVER (PARTITION BY TICKER, METRIC_NAME ORDER BY DATE))
    / NULLIF(ABS(LAG(VALUE, 1) OVER (PARTITION BY TICKER, METRIC_NAME ORDER BY DATE)), 0)
    AS QOQ_GROWTH,
    -- Year-over-Year
    (VALUE - LAG(VALUE, 4) OVER (PARTITION BY TICKER, METRIC_NAME ORDER BY DATE))
    / NULLIF(ABS(LAG(VALUE, 4) OVER (PARTITION BY TICKER, METRIC_NAME ORDER BY DATE)), 0)
    AS YOY_GROWTH
FROM {{ ref('stg_fundamentals') }}
```

### Sentiment Aggregation (FCT_NEWS_SENTIMENT_AGG)

```sql
SELECT
    TICKER,
    DATE_TRUNC('day', PUBLISHED_AT)::DATE AS SENTIMENT_DATE,
    AVG(SENTIMENT_SCORE) AS AVG_SENTIMENT,
    COUNT(*) AS ARTICLE_COUNT,
    CASE
        WHEN AVG(SENTIMENT_SCORE) > 0.2 THEN 'BULLISH'
        WHEN AVG(SENTIMENT_SCORE) < -0.2 THEN 'BEARISH'
        WHEN COUNT(*) = 0 THEN 'NO_COVERAGE'
        ELSE 'NEUTRAL'
    END AS SENTIMENT_LABEL
FROM {{ ref('stg_news') }}
GROUP BY TICKER, DATE_TRUNC('day', PUBLISHED_AT)::DATE
```

## Custom Schema Macro

`macros/generate_schema_name.sql` routes models to correct schemas:

```sql
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
```

Staging models use `schema: STAGING`, analytics use `schema: ANALYTICS` in their config.

## Testing

### Schema Tests (in YAML)

```yaml
models:
  - name: fct_stock_metrics
    columns:
      - name: TICKER
        tests:
          - not_null
      - name: DATE
        tests:
          - not_null
      - name: TREND_SIGNAL
        tests:
          - accepted_values:
              values: ['BULLISH', 'BEARISH', 'NEUTRAL']
```

### Running Tests

```bash
# All tests
dbt test

# Specific model
dbt test --select fct_stock_metrics

# Only schema tests
dbt test --select test_type:schema
```

## dbt Commands

```bash
# Full build (compile + run + test)
dbt build

# Compile only (check SQL validity)
dbt compile

# Run specific model and downstream
dbt run --select fct_stock_metrics+

# Debug connection
dbt debug
```

## Downstream Consumers

Changes to dbt models affect these consumers:

| Model | Consumer | Impact |
|-------|----------|--------|
| fct_stock_metrics | chart_agent.py (price, volume, technical charts) | Chart data breaks if columns renamed |
| fct_fundamentals_growth | chart_agent.py (fundamental, growth charts) | Growth calculations affected |
| fct_news_sentiment_agg | chart_agent.py (sentiment chart) | Sentiment display affected |
| fct_sec_financial_summary | chart_agent.py (SEC chart), analysis_agent.py | Filing analysis breaks |
| dim_company | analysis_agent.py, frontend company page | Company metadata missing |
| All analytics tables | Streamlit frontend pages | Frontend queries fail |

Always verify downstream consumers after modifying any dbt model.

## Adding a New Model

1. Create SQL file in appropriate directory (`staging/` or `analytics/`)
2. Add schema config (materialization, schema routing)
3. Add column-level tests in YAML
4. Run `dbt compile` to verify SQL
5. Run `dbt run --select new_model` to create
6. Run `dbt test --select new_model` to validate
7. Update `.astro/warehouse.md` with new table documentation
8. Verify downstream agent queries still work
