---
description: Run the CAVM report generation pipeline with diagnostics
argument-hint: "<TICKER>"
---

# Report Generation

Run the full CAVM pipeline for a ticker with pre-flight checks and diagnostics.

## Steps

1. **Verify Snowflake data availability**:
   ```sql
   -- Check all 4 analytics tables have data for the ticker
   SELECT 'FCT_STOCK_METRICS' AS TBL, COUNT(*) AS ROWS
   FROM FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS WHERE TICKER = '$TICKER'
   UNION ALL
   SELECT 'FCT_FUNDAMENTALS_GROWTH', COUNT(*)
   FROM FINSAGE_DB.ANALYTICS.FCT_FUNDAMENTALS_GROWTH WHERE TICKER = '$TICKER'
   UNION ALL
   SELECT 'FCT_NEWS_SENTIMENT_AGG', COUNT(*)
   FROM FINSAGE_DB.ANALYTICS.FCT_NEWS_SENTIMENT_AGG WHERE TICKER = '$TICKER'
   UNION ALL
   SELECT 'FCT_SEC_FINANCIAL_SUMMARY', COUNT(*)
   FROM FINSAGE_DB.ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY WHERE TICKER = '$TICKER';
   ```

   If any table returns 0 rows:
   - Run `dbt build` to refresh analytics tables
   - Check if the raw data exists for this ticker
   - Run the data pipeline if raw data is missing

2. **Verify column names** match what agents expect:
   - Cross-check `agents/chart_agent.py` data fetcher queries against `.astro/warehouse.md`
   - Confirm TREND_SIGNAL, FUNDAMENTAL_SIGNAL, SENTIMENT_LABEL, FINANCIAL_HEALTH columns exist

3. **Run the pipeline**:
   ```python
   from agents.orchestrator import generate_report_pipeline
   import logging
   logging.basicConfig(level=logging.DEBUG)

   result = generate_report_pipeline("$TICKER", output_dir="output/")
   ```

4. **Validate output directory**:
   ```bash
   ls -la output/${TICKER}_*/
   # Expected: 8 chart PNGs + manifest.json + ${TICKER}_report.pdf
   ```

   Check for:
   - [ ] All 8 chart images present (price_history, volume_analysis, technical_indicators, fundamental_metrics, growth_analysis, sentiment_overview, peer_comparison, sec_financial_summary)
   - [ ] manifest.json with generation metadata
   - [ ] PDF report file
   - [ ] No error logs in pipeline output

5. **Diagnose failures** if any charts are missing:
   - Check pipeline logs for the specific chart type that failed
   - Verify the data fetcher returned data for that chart type
   - Check if VLM refinement exhausted all iterations (fallback should have activated)
   - Verify subprocess execution didn't timeout

6. **Report results**:
   - Number of charts generated successfully
   - Pipeline duration
   - Any warnings or soft failures from validation
   - Quality scores from manifest
