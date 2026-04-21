# CLAUDE.md

Project context for AI-assisted development. Architecture overview, key commands, and conventions for working on the FinSage codebase.

## Project Overview

FinSage is an AI-powered financial research report generation system for U.S. public companies. It automates data collection, analysis, and generation of 15-20 page PDF research reports with visualizations and citations. Built for DAMG 7374 (Northeastern University).

The system combines a Snowflake data warehouse with AWS Bedrock AI services and Snowflake Cortex LLM/VLM capabilities to deliver end-to-end financial intelligence — from raw data ingestion through multi-agent report generation and interactive Q&A.

## Key Commands

### Environment Setup
```bash
source venv/bin/activate
pip install -r requirements.txt
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

### Frontend (Next.js + FastAPI)
```bash
# Terminal 1: FastAPI backend
cd frontend-react/api
uvicorn main:app --reload --port 8000

# Terminal 2: Next.js frontend
cd frontend-react
npm run dev
# http://localhost:3000
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

1. **Chart Agent** (`chart_agent.py`) — Queries ANALYTICS layer, generates 8 matplotlib charts per ticker, uses 3-iteration VLM refinement loop (Snowflake Cortex claude-sonnet-4-6: initial → critique → refined → final)
2. **Validation Agent** (`validation_agent.py`) — Validates chart visual quality and data integrity, flags failures for re-generation
3. **Analysis Agent** (`analysis_agent.py`) — Per-chart LLM analysis via Snowflake Cortex (claude-opus-4-6, mistral-large), plus SEC MD&A/Risk Factors summarization via Cortex SUMMARIZE
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

### Frontend (`frontend-react/`)

Next.js 16 (App Router) + React 19 + TypeScript + MUI 9 + FastAPI backend. Five pages:

1. **Dashboard (`/`)** — KPI cards, signal badges, interactive candlestick chart with SMA overlays, news headlines
2. **Analytics Explorer (`/analytics`)** — 4-tab interface: Stock Metrics, Fundamentals, Sentiment, SEC Financials
3. **SEC Filings (`/sec`)** — Filing inventory, timeline, 4 Cortex analysis modes (Summary, Risk, MD&A, Cross-Company)
4. **Report Generation (`/report`)** — Quick Report (Cortex markdown) and Full CAVM Pipeline with live stepper + PDF download
5. **Ask FinSage** — Dual-source Q&A (Snowflake Cortex vs. Bedrock KB)

FastAPI backend lives under `frontend-react/api/` and routes to Snowflake, Bedrock, and the CAVM pipeline.

### Airflow DAG (`airflow/dags/data_collection_dag.py`)

Scheduled daily at 5 PM EST. Tasks: 5 parallel data fetches → `run_dbt_transformations` → `data_quality_check`. Uses CeleryExecutor with Redis broker and PostgreSQL metadata DB.

### dbt Project (`dbt_finsage/`)

- Profile: `dbt_finsage` (Snowflake connection via `~/.dbt/profiles.yml`)
- Staging models (5): materialized as **views** in `staging` schema
- Analytics models (6): materialized as **tables** in `analytics` schema — `dim_company`, `fct_stock_metrics`, `fct_fundamentals_growth`, `fct_news_sentiment_agg`, `fct_sec_financial_summary`, plus supporting models

## Tech Stack

- **Python 3.9** with virtual environment (`venv/`)
- **Snowflake** (SFEDU02 academic account) — warehouse, Cortex LLM/VLM (claude-opus-4-6, claude-sonnet-4-6, mistral-large), Cortex Search, Cortex SUMMARIZE, Cortex SENTIMENT
- **AWS Bedrock** — Knowledge Base RAG (Llama 3), Guardrails (content safety/grounding), multi-model inference (Llama3, Titan, Mistral, Claude)
- **AWS S3** — SEC filing document storage (`finsage-sec-filings-808683`)
- **dbt 1.7** for SQL transformations
- **Apache Airflow 2.8** for orchestration (Docker Compose stack)
- **reportlab** for PDF generation, **matplotlib** for charts
- **Next.js 16 / React 19 / TypeScript / MUI 9 / FastAPI** for the frontend
- **Terraform** for AWS S3 infrastructure (`terraform/s3/`)
- **boto3** for AWS SDK interactions

## Configuration

- Credentials in `.env` (not committed): Snowflake creds, NewsAPI key, AWS credentials, Bedrock KB/Guardrail IDs
- Tracked tickers defined in `config/tickers.yaml` (50 tickers across 5 sectors)
- Snowflake target: `FINSAGE_DB` database, `FINSAGE_WH` warehouse
- SQL DDL migrations in `sql/` (numbered 01-08)

## Project Structure

```
finsage-project/
├── agents/                     # CAVM multi-agent report generation pipeline
│   ├── orchestrator.py         # Coordinates chart → validation → analysis → report
│   ├── chart_agent.py          # 8 matplotlib charts with VLM refinement loop
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
├── frontend-react/             # Next.js + FastAPI frontend
│   ├── app/                    # Next.js App Router (5 pages)
│   ├── components/             # Reusable UI components
│   ├── lib/                    # API client, theme, ticker context
│   └── api/                    # FastAPI backend + routers
├── dbt_finsage/                # dbt project (staging views + analytics tables)
├── airflow/                    # Docker Compose Airflow stack + DAGs
├── sql/                        # DDL migrations (01-08)
├── terraform/s3/               # AWS S3 infrastructure as code
├── config/tickers.yaml         # Tracked ticker symbols
├── outputs/                    # Generated reports: <TICKER>_<YYYYMMDD>_<HHMMSS>/
└── requirements.txt / requirements-airflow.txt
```

## Output

Generated reports go to `outputs/<TICKER>_<YYYYMMDD>_<HHMMSS>/` containing:
- 8 chart PNGs (price_sma, eps_trend, revenue_growth, sentiment, volatility, financial_health, margin_trend, balance_sheet)
- Iterative VLM refinement artifacts (`_iter1.png`, `_iter2.png`, `_iter3.png` per chart)
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

**Tracked tickers:** 50 U.S. public companies across Technology, Consumer/Retail, Finance, Healthcare, and Energy/Industrial sectors. Full list in `config/tickers.yaml`.

**Categorical signals:**
- `TREND_SIGNAL`: BULLISH, BEARISH, NEUTRAL
- `FUNDAMENTAL_SIGNAL`: STRONG_GROWTH, MODERATE_GROWTH, DECLINING, MIXED
- `SENTIMENT_LABEL`: BULLISH, BEARISH, NEUTRAL, NO_COVERAGE
- `FINANCIAL_HEALTH`: EXCELLENT, HEALTHY, FAIR, UNPROFITABLE

More detail in `docs/warehouse.md` (full schema dump with column-level metadata).
