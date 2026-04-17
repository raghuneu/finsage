# Pipeline Debug Workflow

Debug the CAVM (Chart → Analysis → Validation → Metrics) pipeline.

## Step 1: Verify Snowflake Connection

```bash
python scripts/snowflake_connection.py
```

If this fails, check `.env` for correct credentials:
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_PASSWORD`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`

## Step 2: Verify Data Availability

Check that analytics tables have data for the target ticker:

```sql
SELECT COUNT(*) FROM FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS WHERE TICKER = '<ticker>';
SELECT COUNT(*) FROM FINSAGE_DB.ANALYTICS.FCT_FUNDAMENTALS_GROWTH WHERE TICKER = '<ticker>';
SELECT COUNT(*) FROM FINSAGE_DB.ANALYTICS.FCT_NEWS_SENTIMENT_AGG WHERE TICKER = '<ticker>';
SELECT COUNT(*) FROM FINSAGE_DB.ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY WHERE TICKER = '<ticker>';
SELECT COUNT(*) FROM FINSAGE_DB.ANALYTICS.DIM_COMPANY WHERE TICKER = '<ticker>';
```

## Step 3: Verify Column Names

Cross-reference SQL queries in `agents/chart_agent.py` against actual Snowflake columns. Check `.astro/warehouse.md` for the definitive column reference.

Common failure: Python code references a column name that doesn't match the Snowflake schema (e.g., `close_price` vs `CLOSE`).

## Step 4: Trace the Pipeline Stages

1. **Chart Agent** (`agents/chart_agent.py`) — fetches data, generates charts
2. **Validation Agent** (`agents/validation_agent.py`) — validates chart quality
3. **Analysis Agent** (`agents/analysis_agent.py`) — LLM analysis + SEC summarization
4. **Report Orchestrator** (`agents/orchestrator.py`) — assembles final report

Run each stage independently to isolate the failure point.

## Step 5: Check Output Directory

Verify `outputs/` directory exists and is writable. Charts are saved as PNG files there.
