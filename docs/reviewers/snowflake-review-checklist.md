# Snowflake Review Checklist

Review rubric for Snowflake SQL, schema changes, and data pipeline code in FinSage. Use this when reviewing PRs that touch the warehouse, dbt models, or Snowflake integration code.

## Warehouse Architecture

```
FINSAGE_DB
├── RAW          — Raw ingested data (append-only)
├── STAGING      — dbt staging views (validation + filtering + Cortex SENTIMENT)
└── ANALYTICS    — dbt analytics tables (aggregations, signals, dimensions)
```

### Key Tables

| Schema | Table | Primary Key | Purpose |
|--------|-------|-------------|---------|
| RAW | RAW_STOCK_PRICES | TICKER + DATE | Daily OHLCV from yfinance |
| RAW | RAW_FUNDAMENTALS | TICKER + METRIC_NAME + DATE | Financial metrics |
| RAW | RAW_NEWS | TICKER + PUBLISHED_AT + TITLE | News articles |
| RAW | RAW_SEC_FILINGS | ACCESSION_NUMBER | SEC filing metadata |
| RAW | RAW_SEC_FILING_TEXT | ACCESSION_NUMBER | Full-text extractions |
| ANALYTICS | DIM_COMPANY | TICKER | Company dimension |
| ANALYTICS | FCT_STOCK_METRICS | TICKER + DATE | Prices + SMAs + signals |
| ANALYTICS | FCT_FUNDAMENTALS_GROWTH | TICKER + FISCAL_QUARTER | Growth rates |
| ANALYTICS | FCT_NEWS_SENTIMENT_AGG | TICKER + NEWS_DATE | Aggregated sentiment |
| ANALYTICS | FCT_SEC_FINANCIAL_SUMMARY | TICKER + FISCAL_YEAR + FISCAL_PERIOD | SEC summaries |

Full column-level reference: [`docs/warehouse.md`](../warehouse.md).

## Review Checklist

### Column Names and Schema

- [ ] All column names are UPPER_SNAKE_CASE
- [ ] Column names exist in the referenced table — verify against `docs/warehouse.md`
- [ ] Fully-qualified table references: `FINSAGE_DB.SCHEMA.TABLE`
- [ ] No ambiguous column references in JOINs — always prefix with table alias

### Query Safety

- [ ] Every analytical query includes `WHERE TICKER = ...` or equivalent filter
- [ ] Exploratory queries include `LIMIT` clause
- [ ] No `SELECT *` in production code — enumerate columns explicitly
- [ ] No unbounded `CROSS JOIN` or cartesian products
- [ ] Date filters use `DATE` type, not string comparison

### SQL Injection Prevention

- [ ] No f-string interpolation of user input into SQL
- [ ] Use Snowpark `session.sql()` with parameterized queries
- [ ] User-facing inputs pass through `sanitize_ticker()` before SQL
- [ ] `safe_query()` / `cached_query()` used in frontend code

### MERGE/Upsert Patterns

- [ ] Uses idempotent MERGE with temp staging table pattern:
  ```sql
  CREATE TEMPORARY TABLE stg_temp AS SELECT ...;
  MERGE INTO target USING stg_temp ON match_keys
  WHEN MATCHED THEN UPDATE SET ...
  WHEN NOT MATCHED THEN INSERT (...) VALUES (...);
  ```
- [ ] MERGE keys match the table's natural key (see table above)
- [ ] UPDATE SET clause does not update the primary key columns

### Snowpark Session Management

- [ ] Sessions created via `SnowflakeClient` — not raw `snowflake.connector`
- [ ] Session always closed in `finally` block
- [ ] No session leaks in error paths
- [ ] Connection parameters from environment variables, never hardcoded

### Cortex Functions

- [ ] `SNOWFLAKE.CORTEX.COMPLETE()` — model name is a valid Cortex model
- [ ] `SNOWFLAKE.CORTEX.SUMMARIZE()` — input text < 40,000 characters
- [ ] `SNOWFLAKE.CORTEX.SENTIMENT()` — returns FLOAT, not string
- [ ] Function calls are in correct schema context

### Performance

- [ ] Partition pruning: queries filter on clustering key (typically TICKER or DATE)
- [ ] No unnecessary `ORDER BY` in subqueries
- [ ] `GROUP BY` uses column positions or names consistently
- [ ] Large result sets use `query_to_dataframe()` for efficient transfer
- [ ] Window functions include explicit `PARTITION BY` and `ORDER BY`

### Categorical Signal Values

When reviewing signal derivation logic, verify these are the only valid values:

| Signal | Valid Values |
|--------|-------------|
| TREND_SIGNAL | BULLISH, BEARISH, NEUTRAL |
| FUNDAMENTAL_SIGNAL | STRONG_GROWTH, MODERATE_GROWTH, DECLINING, MIXED |
| SENTIMENT_LABEL | BULLISH, BEARISH, NEUTRAL, NO_COVERAGE |
| FINANCIAL_HEALTH | EXCELLENT, HEALTHY, FAIR, UNPROFITABLE |

## Severity Guidance

Block merges on any of these:

- **CRITICAL** — Data corruption risk (non-idempotent writes, MERGE updating PK columns), SQL injection exposure
- **HIGH** — Wrong column names, missing WHERE clause on large tables, session leaks, hardcoded credentials

Flag but don't block:

- **MEDIUM** — Performance regressions, missing LIMIT on exploratory queries
- **LOW** — Style/formatting, non-standard naming
