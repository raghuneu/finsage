# Data Quality Checks

Cross-layer data quality validation for the FinSage pipeline.

## Step 1: RAW Layer Counts

Verify source data exists:

```sql
SELECT 'raw_stock_data' AS table_name, COUNT(*) AS row_count FROM FINSAGE_DB.RAW.RAW_STOCK_DATA
UNION ALL
SELECT 'raw_fundamentals', COUNT(*) FROM FINSAGE_DB.RAW.RAW_FUNDAMENTALS
UNION ALL
SELECT 'raw_news_sentiment', COUNT(*) FROM FINSAGE_DB.RAW.RAW_NEWS_SENTIMENT
UNION ALL
SELECT 'raw_sec_filings', COUNT(*) FROM FINSAGE_DB.RAW.RAW_SEC_FILINGS
UNION ALL
SELECT 'raw_company_info', COUNT(*) FROM FINSAGE_DB.RAW.RAW_COMPANY_INFO;
```

## Step 2: Staging Layer Validation

Verify staging views resolve and return data:

```sql
SELECT 'stg_stock_data' AS view_name, COUNT(*) AS row_count FROM FINSAGE_DB.STAGING.STG_STOCK_DATA
UNION ALL
SELECT 'stg_fundamentals', COUNT(*) FROM FINSAGE_DB.STAGING.STG_FUNDAMENTALS
UNION ALL
SELECT 'stg_news_sentiment', COUNT(*) FROM FINSAGE_DB.STAGING.STG_NEWS_SENTIMENT
UNION ALL
SELECT 'stg_sec_filings', COUNT(*) FROM FINSAGE_DB.STAGING.STG_SEC_FILINGS
UNION ALL
SELECT 'stg_company_info', COUNT(*) FROM FINSAGE_DB.STAGING.STG_COMPANY_INFO;
```

## Step 3: Analytics Layer Checks

Verify final tables have data:

```sql
SELECT 'dim_company' AS table_name, COUNT(*) AS row_count FROM FINSAGE_DB.ANALYTICS.DIM_COMPANY
UNION ALL
SELECT 'fct_stock_metrics', COUNT(*) FROM FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS
UNION ALL
SELECT 'fct_fundamentals_growth', COUNT(*) FROM FINSAGE_DB.ANALYTICS.FCT_FUNDAMENTALS_GROWTH
UNION ALL
SELECT 'fct_news_sentiment_agg', COUNT(*) FROM FINSAGE_DB.ANALYTICS.FCT_NEWS_SENTIMENT_AGG
UNION ALL
SELECT 'fct_sec_financial_summary', COUNT(*) FROM FINSAGE_DB.ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY;
```

## Step 4: Cross-Layer Consistency

Check that all tracked tickers appear in all layers:

```sql
SELECT DISTINCT TICKER FROM FINSAGE_DB.ANALYTICS.DIM_COMPANY
ORDER BY TICKER;
```

All 5 tickers (AAPL, GOOGL, JPM, MSFT, TSLA) should appear. If any are missing, trace back through staging and raw layers.

## Step 5: Freshness Check

Verify data is recent:

```sql
SELECT TICKER, MAX(DATE) AS latest_date
FROM FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS
GROUP BY TICKER
ORDER BY TICKER;
```

## Step 6: Column Name Verification

Verify columns referenced in `agents/chart_agent.py` exist:

```sql
DESCRIBE TABLE FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS;
DESCRIBE TABLE FINSAGE_DB.ANALYTICS.FCT_FUNDAMENTALS_GROWTH;
DESCRIBE TABLE FINSAGE_DB.ANALYTICS.FCT_NEWS_SENTIMENT_AGG;
DESCRIBE TABLE FINSAGE_DB.ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY;
DESCRIBE TABLE FINSAGE_DB.ANALYTICS.DIM_COMPANY;
```
