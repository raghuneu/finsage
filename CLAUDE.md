# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FinSage is an AI-powered financial research report generation system for U.S. public companies. It automates data collection, analysis, and generation of 15-20 page PDF research reports with visualizations and citations. Built for DAMG 7374 (Northeastern University).

The system combines a Snowflake data warehouse with AWS Bedrock AI services and Snowflake Cortex LLM/VLM capabilities to deliver end-to-end financial intelligence — from raw data ingestion through multi-agent report generation and interactive Q&A.

## Key Commands

### Environment Setup
```bash
source venv/bin/activate
pip install -r requirements.txt          # all local dev deps
```

### Data Pipeline
```bash
# Modular pipeline (preferred)
python -c "from src.orchestration.data_pipeline import run_pipeline; run_pipeline()"

# Individual loaders (legacy scripts/)
python scripts/load_sample_stock_data.py
python scripts/load_sample_fundamentals.py
python scripts/load_sample_news.py
python scripts/load_sec_data.py
```

### dbt Transformations
```bash
cd dbt_finsage
dbt debug                        # verify Snowflake connection
dbt run                          # run all models
dbt test                         # data quality tests
dbt run --select staging         # run only staging layer
dbt run --select analytics       # run only analytics layer
```

### Report Generation (Multi-Agent Pipeline)
```bash
python agents/orchestrator.py --ticker AAPL --debug
python agents/orchestrator.py --ticker AAPL --skip-charts --charts-dir outputs/AAPL_20260404_104147
```

### Streamlit Frontend
```bash
streamlit run app.py
```

### Airflow (Docker Compose)
```bash
cd airflow
docker-compose up airflow-webserver    # http://localhost:8080
docker-compose up airflow-scheduler
docker-compose up airflow-worker
```

### SEC Filing Analysis (Bedrock)
```bash
# Multi-model comparison CLI
python scripts/sec_filings/multi_model.py
```

## Architecture

### Data Flow: Three-Layer Snowflake Architecture

**RAW** (ingestion) → **STAGING** (cleaning, dbt views) → **ANALYTICS** (fact/dimension tables, dbt tables)

- Data sources: Yahoo Finance (stock prices), Alpha Vantage (fundamentals), NewsAPI (articles), SEC EDGAR (10-K/10-Q filings)
- Loading uses idempotent MERGE statements with temporary staging tables
- Every table has `source` and `ingested_at` columns for lineage
- `data_quality_score` (0-100) computed pre-load with deductions for missing/invalid fields
- Incremental loading: queries only data since `get_last_loaded_date()`

### Multi-Agent Report Generation (CAVM Pipeline)

`agents/orchestrator.py` coordinates four agents in sequence:

1. **Chart Agent** (`chart_agent.py`) — Queries ANALYTICS layer, generates 6 matplotlib charts per ticker, uses 3-iteration VLM refinement loop (Snowflake Cortex claude-sonnet-4-6: initial → critique → refined → final)
2. **Validation Agent** (`validation_agent.py`) — Validates chart visual quality and data integrity, flags failures for re-generation
3. **Analysis Agent** (`analysis_agent.py`) — Per-chart LLM analysis via Snowflake Cortex (mistral-large), plus SEC MD&A/Risk Factors summarization via Cortex SUMMARIZE
4. **Report Agent** (`report_agent.py`) — Assembles branded PDF with reportlab (Midnight Teal color scheme: #0f2027 header, #00b4d8 accent, #06d6a0 bullish, #ef476f bearish)

Agents share state via Snowflake ANALYTICS layer + filesystem (output directory per run).

### SEC Filing Processing (`scripts/sec_filings/`)

End-to-end SEC filing pipeline with AWS Bedrock integration:

- **`filing_downloader.py`** — Downloads 10-K/10-Q filings from SEC EDGAR
- **`text_extractor.py`** — Extracts text from PDF/HTML filing documents
- **`s3_utils.py`** — Manages S3 storage for filings (bucket: `finsage-sec-filings-808683`)
  - Layout: `filings/raw/{ticker}/{form_type}/`, `filings/extracted/{ticker}/{form_type}/`
- **`bedrock_kb.py`** — Bedrock Knowledge Base RAG client
  - `retrieve()` — Vector search over SEC filing embeddings
  - `ask()` — Retrieval-augmented generation with citations (Llama 3 models)
  - `cross_ticker_analysis()` — Comparative analysis across companies
- **`guardrails.py`** — Bedrock Guardrails for content safety
  - Blocks investment advice (denied topics), redacts PII, detects hallucinations via contextual grounding
  - `generate()` — LLM generation with guardrails applied
  - `check_output()` — Validate text without a model call
- **`multi_model.py`** — Multi-model comparison via Bedrock (Llama3, Titan, Mistral, Claude)
  - `compare()` — Parallel inference with latency tracking
  - `consensus()` — Synthesizes agreement/disagreement across models
- **`document_agent.py`** — SEC document analysis agent integrating Snowflake analytics context

### Data Loaders (`src/data_loaders/`)

All loaders extend `base_loader.py` (abstract `BaseDataLoader` with template methods: `fetch_data`, `validate_data`, `calculate_quality_score`, `load`). The `src/orchestration/data_pipeline.py` orchestrates all loaders.

### Streamlit Frontend (`app.py`)

Full-featured interactive UI with 10 pages:

1. **Dashboard** — Real-time company metrics (market cap, price, revenue, sentiment, P/E)
2. **Data Pipeline** — Snowflake layer status, S3 filing counts, pipeline execution
3. **Analytics Explorer** — Stock metrics, fundamentals, sentiment, SEC financials with charts
4. **SEC Filing Analysis** — Filing listing, document-level analysis (summary, risks, MD&A comparison)
5. **RAG Search** — Ask questions, cross-ticker analysis, raw chunk retrieval from Bedrock KB
6. **Research Report** — Full 7-section report generation
7. **Multi-Model Analysis** — Side-by-side model comparison with consensus synthesis
8. **Guardrails Demo** — Interactive guardrail testing with preset examples
9. **Ask FinSage** — Dual-source Q&A (Snowflake Cortex vs. Bedrock KB)
10. **System Status** — Health checks for Snowflake, AWS, Bedrock KB, Guardrails, Multi-Model

### Airflow DAG (`airflow/dags/data_collection_dag.py`)

Scheduled daily at 5 PM EST. Tasks: 4 parallel data fetches → `run_dbt_transformations` → `data_quality_check`. Uses CeleryExecutor with Redis broker and PostgreSQL metadata DB.

### dbt Project (`dbt_finsage/`)

- Profile: `dbt_finsage` (Snowflake connection via `~/.dbt/profiles.yml`)
- Staging models (4): materialized as **views** in `staging` schema
- Analytics models (5): materialized as **tables** in `analytics` schema — `dim_company`, `fct_stock_metrics`, `fct_fundamentals_growth`, `fct_news_sentiment_agg`, `fct_sec_financial_summary`

## Tech Stack

- **Python 3.9** with virtual environment (`venv/`)
- **Snowflake** (SFEDU02 academic account) — warehouse, Cortex LLM/VLM (claude-sonnet-4-6, mistral-large), Cortex Search, Cortex SUMMARIZE
- **AWS Bedrock** — Knowledge Base RAG (Llama 3), Guardrails (content safety/grounding), multi-model inference (Llama3, Titan, Mistral, Claude)
- **AWS S3** — SEC filing document storage (`finsage-sec-filings-808683`)
- **dbt 1.7** for SQL transformations
- **Apache Airflow 2.8** for orchestration (Docker Compose stack)
- **reportlab** for PDF generation, **matplotlib** for charts
- **Streamlit** for interactive frontend (`app.py`, 10 pages)
- **Terraform** for AWS S3 infrastructure (`terraform/s3/`)
- **boto3** for AWS SDK interactions

## Configuration

- Credentials in `.env` (not committed): Snowflake creds, NewsAPI key, AWS credentials, Bedrock KB/Guardrail IDs
- Tracked tickers defined in `config/tickers.yaml` (AAPL, MSFT, GOOGL)
- Snowflake target: `FINSAGE_DB` database, `FINSAGE_WH` warehouse
- SQL DDL migrations in `sql/` (numbered 01-07)

## Project Structure

```
finsage-project/
├── agents/                     # CAVM multi-agent report generation pipeline
│   ├── orchestrator.py         # Coordinates chart → validation → analysis → report
│   ├── chart_agent.py          # 6 matplotlib charts with VLM refinement loop
│   ├── validation_agent.py     # Chart quality and data integrity checks
│   ├── analysis_agent.py       # Per-chart LLM analysis + SEC summarization
│   └── report_agent.py         # Branded PDF assembly with reportlab
├── src/
│   ├── data_loaders/           # Base loader + stock, fundamentals, news, SEC loaders
│   ├── orchestration/          # data_pipeline.py — runs all loaders
│   └── utils/                  # logger.py, snowflake_client.py
├── scripts/
│   ├── sec_filings/            # Bedrock KB RAG, Guardrails, multi-model, S3, document agent
│   ├── load_sample_*.py        # Legacy individual data loaders
│   ├── run_migration_*.py      # SQL DDL migration runners
│   └── verify_*.py             # Data verification scripts
├── dbt_finsage/                # dbt project (staging views + analytics tables)
├── airflow/                    # Docker Compose Airflow stack + DAGs
├── sql/                        # DDL migrations (01-07)
├── terraform/s3/               # AWS S3 infrastructure as code
├── config/tickers.yaml         # Tracked ticker symbols
├── app.py                      # Streamlit frontend (10 pages)
├── outputs/                    # Generated reports: <TICKER>_<YYYYMMDD>_<HHMMSS>/
├── POCs/                       # Proof of concept scripts (Cortex, chart generation)
└── requirements.txt / requirements-airflow.txt
```

## Output

Generated reports go to `outputs/<TICKER>_<YYYYMMDD>_<HHMMSS>/` containing:
- 6 chart PNGs (price_sma, eps_trend, revenue_growth, sentiment, volatility, financial_health)
- Iterative VLM refinement artifacts (iter1_tmp.png, iter2_tmp.png)
- `chart_manifest.json` — Chart metadata and file paths
- `pipeline_result.json` — Full pipeline execution results
- Final branded PDF report (15-20 pages)

## Data Warehouse Quick Reference

When querying the warehouse, use these table mappings:

| Concept | Table | Key Column(s) | Date Column |
|---------|-------|---------------|-------------|
| Companies | FINSAGE_DB.ANALYTICS.DIM_COMPANY | TICKER | DBT_UPDATED_AT |
| Stock prices (daily) | FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS | TICKER, DATE | DATE |
| Fundamentals (quarterly) | FINSAGE_DB.ANALYTICS.FCT_FUNDAMENTALS_GROWTH | TICKER, FISCAL_QUARTER | DBT_UPDATED_AT |
| News sentiment (daily) | FINSAGE_DB.ANALYTICS.FCT_NEWS_SENTIMENT_AGG | TICKER, NEWS_DATE | NEWS_DATE |
| SEC financials (annual/quarterly) | FINSAGE_DB.ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY | TICKER, FISCAL_YEAR, FISCAL_PERIOD | PERIOD_END |
| Raw stock prices | FINSAGE_DB.RAW.RAW_STOCK_PRICES | TICKER, DATE | DATE |
| Raw fundamentals | FINSAGE_DB.RAW.RAW_FUNDAMENTALS | TICKER, FISCAL_QUARTER | INGESTED_AT |
| Raw news articles | FINSAGE_DB.RAW.RAW_NEWS | ARTICLE_ID | PUBLISHED_AT |
| Raw SEC XBRL filings | FINSAGE_DB.RAW.RAW_SEC_FILINGS | TICKER, CONCEPT, PERIOD_END, FISCAL_PERIOD | PERIOD_END |
| Raw SEC filing documents | FINSAGE_DB.RAW.RAW_SEC_FILING_DOCUMENTS | FILING_ID | FILING_DATE |
| Raw SEC filing text | FINSAGE_DB.RAW.RAW_SEC_FILING_TEXT | TICKER, ACCESSION_NUMBER | FILING_DATE |

**Tracked tickers:** AAPL, GOOGL, JPM, MSFT, TSLA

**Categorical signals:**
- `TREND_SIGNAL`: BULLISH, BEARISH, NEUTRAL
- `FUNDAMENTAL_SIGNAL`: STRONG_GROWTH, MODERATE_GROWTH, DECLINING, MIXED
- `SENTIMENT_LABEL`: BULLISH, BEARISH, NEUTRAL, NO_COVERAGE
- `FINANCIAL_HEALTH`: EXCELLENT, HEALTHY, FAIR, UNPROFITABLE

> Auto-generated by `/data:init` on 2026-04-14. Run `/data:init --refresh` to update.

## Development Workflow

This project follows the Everything Claude Code (ECC) development methodology. Detailed rules are in `.claude/rules/`.

### Workflow Sequence

1. **Research & Reuse** — Check existing code before writing new code. Search `src/`, `agents/`, `scripts/` for similar patterns.
2. **Plan First** — For complex features, create an implementation plan before coding. Break into small, testable steps.
3. **TDD** — Write tests first (RED), implement (GREEN), refactor (IMPROVE). Use `pytest`.
4. **Code Review** — After writing code, review for security, quality, and correctness. Check SQL column names against `.astro/warehouse.md`.
5. **Commit** — Use conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`

### Custom Commands

- `/pipeline-debug` — Debug CAVM pipeline failures (connection, data, column names, stage tracing)
- `/dbt-validate` — Run dbt debug → compile → run → test → verify downstream consumers
- `/data-quality` — Cross-layer data quality checks (RAW → STAGING → ANALYTICS consistency)

## Code Quality Standards

### Size Limits
- Functions: < 50 lines
- Files: < 800 lines
- Nesting: < 4 levels deep

### Mandatory Practices
- Type annotations on all function signatures
- Specific exception handling (no bare `except:`)
- Meaningful error messages with context (ticker, stage, function)
- No hardcoded secrets — use `.env` + `python-dotenv`
- No `print()` for debugging — use `src/utils/logger.py`

### Before Every Commit
- [ ] `pytest` passes
- [ ] `cd dbt_finsage && dbt compile` succeeds (if dbt models changed)
- [ ] No hardcoded secrets or `.env` files staged
- [ ] SQL column names verified against `.astro/warehouse.md`
- [ ] No `print()` debug statements in production code
