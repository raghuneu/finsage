# Snowflake SQL Conventions

Rules for writing Snowflake SQL within FinSage — queries, dbt models, and Snowpark code.

## Table References

Always use fully-qualified names: `FINSAGE_DB.SCHEMA.TABLE_NAME`

```sql
-- CORRECT
SELECT * FROM FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS WHERE TICKER = 'AAPL' LIMIT 10;

-- WRONG (unqualified — depends on session context)
SELECT * FROM FCT_STOCK_METRICS WHERE TICKER = 'AAPL';
```

## Column Names

All columns are **UPPER_SNAKE_CASE**. Before writing any query, verify column names against `.astro/warehouse.md`.

```sql
-- CORRECT
SELECT TICKER, DATE, CLOSE_PRICE, SMA_20, TREND_SIGNAL

-- WRONG
SELECT ticker, date, closePrice, sma20, trendSignal
```

## Mandatory Filters

- Every analytical query MUST include `WHERE TICKER = ...` (or equivalent filtering)
- Every exploratory query MUST include `LIMIT` clause
- No `SELECT *` in production code — enumerate columns explicitly

## Parameterized Queries

Never interpolate user input into SQL strings:

```python
# CRITICAL — SQL injection vulnerability
query = f"SELECT * FROM t WHERE TICKER = '{user_input}'"

# CORRECT — parameterized
result = client.query_to_dataframe(
    "SELECT * FROM t WHERE TICKER = %s LIMIT 100",
    params=[sanitized_ticker]
)
```

In Streamlit, always use `sanitize_ticker()` before any query:

```python
ticker = sanitize_ticker(st.text_input("Ticker"))
if ticker:
    df = safe_query(f"SELECT ... WHERE TICKER = '{ticker}' LIMIT 100")
```

## Categorical Signal Values

Use only these exact string values:

| Column | Values |
|--------|--------|
| TREND_SIGNAL | BULLISH, BEARISH, NEUTRAL |
| FUNDAMENTAL_SIGNAL | STRONG_GROWTH, MODERATE_GROWTH, DECLINING, MIXED |
| SENTIMENT_LABEL | BULLISH, BEARISH, NEUTRAL, NO_COVERAGE |
| FINANCIAL_HEALTH | EXCELLENT, HEALTHY, FAIR, UNPROFITABLE |

## Date Handling

- Use `DATE` type for date columns, not strings
- Use Snowflake date functions: `DATEADD`, `DATEDIFF`, `DATE_TRUNC`
- Never compare dates as strings: `WHERE DATE > '2024-01-01'` — use `WHERE DATE > '2024-01-01'::DATE`

## MERGE Pattern

For data upserts, use the temp staging table MERGE pattern:

1. Write data to temp table
2. MERGE into target using natural key
3. Drop temp table in `finally` block

MERGE keys per table:

| Table | MERGE Keys |
|-------|-----------|
| RAW_STOCK_PRICES | TICKER + DATE |
| RAW_FUNDAMENTALS | TICKER + METRIC_NAME + DATE |
| RAW_NEWS | TICKER + PUBLISHED_AT + TITLE |
| RAW_SEC_FILINGS | ACCESSION_NUMBER |

## Cortex Function Usage

```sql
-- Text generation
SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', prompt);

-- Summarization (input must be < 40,000 characters)
SELECT SNOWFLAKE.CORTEX.SUMMARIZE(text_column);

-- Sentiment (returns FLOAT -1.0 to 1.0)
SELECT SNOWFLAKE.CORTEX.SENTIMENT(text_column);
```

## Performance

- Filter on clustering keys (TICKER, DATE) for partition pruning
- Avoid `ORDER BY` in subqueries unless required
- Use `query_to_dataframe()` for large result sets
- Include explicit `PARTITION BY` and `ORDER BY` in window functions
