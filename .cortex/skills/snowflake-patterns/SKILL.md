---
name: snowflake-patterns
description: FinSage Snowflake patterns — idempotent MERGE, Cortex functions, Snowpark sessions, and query conventions
---

# Snowflake Patterns for FinSage

Reference guide for writing Snowflake SQL and Snowpark code within FinSage.

## Database Layout

```
FINSAGE_DB
├── RAW          — Append-only ingested data from external sources
├── STAGING      — dbt views: validation, filtering, Cortex SENTIMENT enrichment
└── ANALYTICS    — dbt tables: aggregations, window functions, derived signals
```

## Column Naming Convention

All columns use **UPPER_SNAKE_CASE**. Never use lowercase or camelCase.

```sql
-- CORRECT
SELECT TICKER, DATE, CLOSE_PRICE, SMA_20, TREND_SIGNAL
FROM FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS

-- WRONG
SELECT ticker, date, closePrice, sma20
```

Always verify column names against `.astro/warehouse.md` before writing queries.

## Idempotent MERGE Pattern

All data loaders use this pattern for upserts. It prevents duplicates when re-running loaders:

```python
def merge_data(self, df: pd.DataFrame, table: str, key_columns: list):
    """Idempotent MERGE using temp staging table."""
    temp_table = f"STG_TEMP_{table}_{uuid.uuid4().hex[:8]}"

    try:
        # 1. Write DataFrame to temp table
        session.write_pandas(df, temp_table, auto_create_table=True)

        # 2. MERGE from temp into target
        merge_keys = " AND ".join(
            f"target.{k} = source.{k}" for k in key_columns
        )
        update_cols = [c for c in df.columns if c not in key_columns]
        update_set = ", ".join(f"target.{c} = source.{c}" for c in update_cols)
        insert_cols = ", ".join(df.columns)
        insert_vals = ", ".join(f"source.{c}" for c in df.columns)

        sql = f"""
        MERGE INTO {table} AS target
        USING {temp_table} AS source
        ON {merge_keys}
        WHEN MATCHED THEN UPDATE SET {update_set}
        WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})
        """
        session.sql(sql).collect()
    finally:
        # 3. Always clean up temp table
        session.sql(f"DROP TABLE IF EXISTS {temp_table}").collect()
```

## Incremental Loading

Use `get_last_loaded_date()` to avoid re-fetching all historical data:

```python
last_date = self.client.get_last_loaded_date(
    table="RAW_STOCK_PRICES",
    date_column="DATE",
    ticker=ticker
)
# Fetch only data after last_date
new_data = yf.download(ticker, start=last_date + timedelta(days=1))
```

## Snowpark Session Management

Always create and close sessions in try/finally:

```python
from src.utils.snowflake_client import SnowflakeClient

client = SnowflakeClient()
try:
    df = client.query_to_dataframe(
        "SELECT * FROM FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS WHERE TICKER = %s LIMIT 100",
        params=["AAPL"]
    )
    # Process df...
finally:
    client.close()
```

Never leave sessions open in error paths. The `finally` block ensures cleanup even when exceptions occur.

## Cortex LLM/VLM Functions

### COMPLETE — Text Generation

```sql
SELECT SNOWFLAKE.CORTEX.COMPLETE(
    'mistral-large2',
    'Analyze the financial health of AAPL based on: revenue growth 12%, debt-to-equity 1.5'
) AS analysis;
```

Used in: `agents/analysis_agent.py` for chain-of-analysis generation.

### SUMMARIZE — Text Summarization

```sql
SELECT SNOWFLAKE.CORTEX.SUMMARIZE(
    filing_text,  -- Must be < 40,000 characters
    'Summarize the key financial data from this SEC filing'
) AS summary
FROM FINSAGE_DB.RAW.RAW_SEC_FILING_TEXT
WHERE TICKER = 'AAPL';
```

Used in: dbt staging models for SEC filing summarization.

### SENTIMENT — Sentiment Scoring

```sql
SELECT SNOWFLAKE.CORTEX.SENTIMENT(TITLE || ' ' || CONTENT) AS SENTIMENT_SCORE
FROM FINSAGE_DB.RAW.RAW_NEWS
WHERE TICKER = 'MSFT';
```

Returns a FLOAT between -1.0 (bearish) and 1.0 (bullish). Used in staging models to enrich raw news data.

## Query Patterns by Table

### FCT_STOCK_METRICS

```sql
-- Latest price + signals for a ticker
SELECT TICKER, DATE, CLOSE_PRICE, VOLUME, SMA_20, SMA_50, TREND_SIGNAL
FROM FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS
WHERE TICKER = 'AAPL'
ORDER BY DATE DESC
LIMIT 1;

-- Price history for chart generation
SELECT DATE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE, VOLUME
FROM FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS
WHERE TICKER = 'TSLA'
  AND DATE >= DATEADD('month', -6, CURRENT_DATE())
ORDER BY DATE;
```

### FCT_FUNDAMENTALS_GROWTH

```sql
-- Growth metrics for fundamental analysis
SELECT TICKER, METRIC_NAME, DATE, VALUE, QOQ_GROWTH, YOY_GROWTH, FUNDAMENTAL_SIGNAL
FROM FINSAGE_DB.ANALYTICS.FCT_FUNDAMENTALS_GROWTH
WHERE TICKER = 'GOOGL'
ORDER BY DATE DESC;
```

### FCT_NEWS_SENTIMENT_AGG

```sql
-- Aggregated daily sentiment
SELECT TICKER, SENTIMENT_DATE, AVG_SENTIMENT, ARTICLE_COUNT, SENTIMENT_LABEL
FROM FINSAGE_DB.ANALYTICS.FCT_NEWS_SENTIMENT_AGG
WHERE TICKER = 'JPM'
  AND SENTIMENT_DATE >= DATEADD('day', -30, CURRENT_DATE())
ORDER BY SENTIMENT_DATE;
```

### FCT_SEC_FINANCIAL_SUMMARY

```sql
-- SEC filing financial summaries
SELECT TICKER, FILING_TYPE, PERIOD_END, REVENUE, NET_INCOME, FINANCIAL_HEALTH
FROM FINSAGE_DB.ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
WHERE TICKER = 'MSFT'
ORDER BY PERIOD_END DESC;
```

## Categorical Signal Values

These are the ONLY valid values for signal columns. Use these exact strings:

| Column | Valid Values |
|--------|-------------|
| TREND_SIGNAL | `BULLISH`, `BEARISH`, `NEUTRAL` |
| FUNDAMENTAL_SIGNAL | `STRONG_GROWTH`, `MODERATE_GROWTH`, `DECLINING`, `MIXED` |
| SENTIMENT_LABEL | `BULLISH`, `BEARISH`, `NEUTRAL`, `NO_COVERAGE` |
| FINANCIAL_HEALTH | `EXCELLENT`, `HEALTHY`, `FAIR`, `UNPROFITABLE` |

## Anti-Patterns

| Anti-Pattern | Risk | Correct Pattern |
|-------------|------|-----------------|
| `f"WHERE TICKER = '{ticker}'"` | SQL injection | Use parameterized queries |
| `SELECT *` in production | Schema changes break code | Enumerate columns |
| Missing `WHERE TICKER` | Full table scan | Always filter by ticker |
| Missing `LIMIT` in exploration | Memory exhaustion | Add `LIMIT 100` |
| `session.sql(...).collect()` without try/finally | Session leak | Wrap in try/finally |
| Lowercase column names | Query failure | Use UPPER_SNAKE_CASE |
