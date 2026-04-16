# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FinSage is an AI-powered financial research report generator for U.S. public companies. It ingests data from Yahoo Finance, NewsAPI, and SEC EDGAR into Snowflake, transforms it with dbt, and uses Snowflake Cortex LLMs (Mistral, Llama 3.1-70B) to generate charts and analysis. The target output is a 15-20 page professional report.

## Environment Setup

Credentials are stored in `.env` at the project root (not committed). Required variables: Snowflake account/user/password/warehouse/database/role, NewsAPI key, Alpha Vantage key.

```bash
pip install -r requirements.txt          # Core: Snowflake, yfinance, dbt, pandas
pip install -r requirements_2.txt        # Extended: Airflow + providers
pip install matplotlib snowflake-ml-python  # Needed for POCs/Iterative_Chart_Generation.py
pip install colorlog                     # Colored logging
```

## Common Commands

**Data pipeline:**
```bash
python src/orchestration/data_pipeline.py         # Run all data loaders (stocks, fundamentals, SEC)
python POCs/Iterative_Chart_Generation.py --mock  # Chart generation with no credentials needed
python POCs/Iterative_Chart_Generation.py --ticker AAPL --days 60  # Real mode (needs Snowflake)
```

**dbt transformations:**
```bash
cd dbt_finsage
dbt debug                              # Verify Snowflake connection
dbt run                                # Run all models (staging → analytics)
dbt run --select staging               # Run only staging layer
dbt run --select analytics.fct_stock_metrics  # Run a single model
dbt test                               # Run all data quality tests
dbt test --select stg_stock_prices     # Test a specific model
dbt docs generate && dbt docs serve    # Browse lineage docs
```

**Verification scripts** (read-only queries against Snowflake):
```bash
python scripts/verify_stock_data.py
python scripts/verify_staging_stock.py
python scripts/verify_fundamentals.py
python scripts/verify_sec_data.py
```

**Airflow** (local dev only):
```bash
airflow standalone    # DAG runs at 5 PM EST on weekdays
```

## Architecture: Three-Layer Snowflake Pipeline

Data flows through three Snowflake schemas, all in `FINSAGE_DB`:

```
External APIs → RAW (raw.raw_*) → STAGING (staging.stg_*) → ANALYTICS (analytics.fct_* / dim_*)
```

- **RAW**: Idempotent MERGE-based loads using temp staging tables. Loaders are in `src/data_loaders/` and share the abstract `BaseDataLoader` from `base_loader.py`. `SnowflakeClient` (`src/utils/snowflake_client.py`) manages sessions and exposes the MERGE helper used by all loaders.
- **STAGING**: dbt views — clean, validate, and add basic derived columns (e.g., daily returns via LAG, keyword-based sentiment).
- **ANALYTICS**: dbt materialized tables — `fct_stock_metrics` (SMA-7/30/90, volatility, 52-week range, BULLISH/BEARISH/NEUTRAL signals), `fct_fundamentals_growth` (QoQ/YoY rates), `fct_news_sentiment_agg` (rolling sentiment trends), `fct_sec_financial_summary` (XBRL pivots), `dim_company`.

Tickers to track are configured in `config/tickers.yaml` (currently AAPL, MSFT, GOOGL).

## POC: Iterative Chart Generation

`POCs/Iterative_Chart_Generation.py` implements the core LLM→render→VLM-critique→refine loop from the FinSight paper (3 iterations). The loop runs entirely through Snowflake Cortex (Llama 3.1-70B for both code generation and critique roles). Charts output to `outputs/iterative_charts/`. Use `--mock` to run without any API credentials.

## Key Architectural Decisions

- **Idempotent loading**: All loaders use MERGE (not INSERT) so re-running is safe. Data quality scores (0–100) are stored alongside raw records.
- **dbt schema naming**: A custom macro in `dbt_finsage/models/macros/generate_schema_name.sql` controls how dbt resolves schema names — check it before changing schema config in `dbt_project.yml`.
- **Path resolution**: Scripts in `src/` resolve `project_root` via `Path(__file__).parent.parent.parent` — this matters when running from different working directories.
- **Windows logging**: `src/utils/logger.py` uses `colorlog` with explicit UTF-8 encoding to handle Windows console limitations.
- **CIK cache**: `src/data_loaders/fetch_all_ciks.py` caches SEC CIK lookups locally to avoid repeated API calls.
