# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FinSage is an AI-powered financial research report generator for U.S. public companies. It automates data collection, analysis, and generation of 15-20 page PDF research reports with visualizations and citations. Built for DAMG 7374 (Northeastern University).

The system combines a Snowflake data warehouse with AWS Bedrock AI services and Snowflake Cortex LLM/VLM capabilities to deliver end-to-end financial intelligence — from raw data ingestion through multi-agent report generation, evaluation, and interactive Q&A.

## Environment Setup

```bash
py -m venv venv
venv\Scripts\activate          # PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install matplotlib snowflake-ml-python  # needed for POCs/
```

Credentials go in `.env` (not committed): Snowflake account/user/password/warehouse/database/role, NewsAPI key, AWS credentials, Bedrock KB/Guardrail IDs.

## Key Commands

### Data Pipeline
```bash
python -c "from src.orchestration.data_pipeline import run_pipeline; run_pipeline()"

# Legacy individual loaders
python scripts/load_sample_stock_data.py
python scripts/load_sample_fundamentals.py
python scripts/load_sec_data.py
```

### dbt Transformations
```bash
cd dbt_finsage
dbt debug                        # verify Snowflake connection
dbt run                          # run all models
dbt run --select staging         # run only staging layer
dbt run --select analytics       # run only analytics layer
dbt test                         # data quality tests
dbt run --select analytics.fct_stock_metrics  # single model
```

### Report Generation (CAVM Pipeline)
```bash
python agents/orchestrator.py --ticker AAPL
python agents/orchestrator.py --ticker AAPL --debug
python agents/orchestrator.py --ticker AAPL --skip-charts   # reuse last charts (fast)
python agents/orchestrator.py --ticker AAPL --skip-charts --charts-dir outputs/AAPL_20260404_104147
```

### Report Evaluation
```bash
python evaluator/cli.py outputs/AAPL_20260416_143000          # full LLM scoring (needs Snowflake)
python evaluator/cli.py outputs/AAPL_20260416_143000 --no-llm  # rule-based only
python evaluator/cli.py --latest                               # auto-select newest output
```

### React Frontend + FastAPI
```bash
cd frontend-react
npm install
npm run dev                   # Next.js dev server → http://localhost:3000

# FastAPI backend (separate terminal)
cd frontend-react/api
pip install -r requirements.txt
uvicorn main:app --reload     # → http://localhost:8000
```

### Tests
```bash
pytest                                    # run all tests
pytest tests/test_evaluator.py -v        # evaluator tests (no Snowflake needed)
pytest tests/test_data_loaders.py        # data loader tests
pytest --cov=src --cov=agents --cov-report=term-missing  # with coverage
pytest -k "test_validate"               # filter by name
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
python scripts/sec_filings/multi_model.py
```

## Architecture

### Data Flow: Three-Layer Snowflake Pipeline

**RAW** (ingestion) → **STAGING** (cleaning, dbt views) → **ANALYTICS** (fact/dimension tables, dbt tables)

- Data sources: Yahoo Finance (stock prices), Alpha Vantage (fundamentals), NewsAPI (articles), SEC EDGAR (10-K/10-Q)
- Loading uses idempotent MERGE statements via temp staging tables
- Every table has `source` and `ingested_at` columns for lineage
- `data_quality_score` (0–100) computed pre-load; incremental loading via `get_last_loaded_date()`
- Warehouse schema quick reference: `.astro/warehouse.md` — always check column names here before writing SQL

### Multi-Agent CAVM Report Pipeline

`agents/orchestrator.py` coordinates four stages, tracked by `RunContext` + `PipelineTracker` (observability):

1. **Chart Agent** (`chart_agent.py`) — Queries ANALYTICS layer, generates 8 matplotlib charts, 3-iteration VLM refinement loop via Snowflake Cortex
2. **Validation Agent** (`validation_agent.py`) — Rule checks (file, size, dimensions, plausibility) + VLM score per chart; one re-render attempt on failure
3. **Analysis Agent** (`analysis_agent.py`) — Per-chart LLM analysis via Cortex (claude-opus-4-6), SEC MD&A/Risk summarization, company overview, peer comparison
4. **Report Agent** (`report_agent.py`) — Branded PDF with reportlab (Midnight Teal palette)

**Output directory** (`outputs/<TICKER>_<YYYYMMDD>_<HHMMSS>/`):
- 8 chart PNGs + `chart_manifest.json` (VLM scores, data_summary per chart)
- `pipeline_result.json` — run summary (ticker, elapsed, pdf_path, charts_summary)
- `analysis_result.json` — full LLM text (chart analyses, investment thesis, section texts) — used by evaluator
- Final branded PDF

### Report Evaluation System (`evaluator/`)

Post-pipeline quality gate. Reads `pipeline_result.json`, `analysis_result.json`, `chart_manifest.json`.

Five dimensions (weighted):
- **completeness** (20%) — all artifacts, texts, PDF present
- **data_quality** (20%) — financial bounds, no NaN/None in critical fields
- **text_quality** (35%) — rule-based (word count, no markdown, numeric density) + optional Cortex LLM scoring
- **chart_quality** (15%) — aggregates VLM scores from `chart_manifest.json`
- **consistency** (10%) — key figures cited in text, signal tone matches data

Verdicts: `GOLDEN` (90+) → `PUBLICATION_READY` (75+) → `NEEDS_REVISION` (50+) → `REJECTED`

Output: `eval_report_card.json` in the output directory + colour-coded terminal table.

### SEC Filing Processing (`scripts/sec_filings/`)

- `filing_downloader.py` — Downloads 10-K/10-Q from SEC EDGAR
- `s3_utils.py` — S3 storage (`finsage-sec-filings-808683`): `filings/raw/{ticker}/{form_type}/`
- `bedrock_kb.py` — Bedrock Knowledge Base RAG (vector search + citations)
- `guardrails.py` — Bedrock Guardrails (blocks investment advice, redacts PII, contextual grounding)
- `multi_model.py` — Parallel multi-model comparison (Llama3, Titan, Mistral, Claude) with consensus

### Observability (`src/utils/observability.py`)

Every pipeline run creates a `RunContext` (auto-generates `run_id`) and a `PipelineTracker` that writes stage timing and status to:
- `ANALYTICS.FCT_PIPELINE_RUNS`
- `ANALYTICS.FCT_LLM_CALLS`
- `ANALYTICS.FCT_DATA_QUALITY_HISTORY`
- `ANALYTICS.FCT_HEALTH_CHECKS`

The `run_id` is also appended to `pipeline_result.json` after the pipeline completes.

### React Frontend (`frontend-react/`)

Next.js 15 + MUI + FastAPI backend (`frontend-react/api/`). Replaces the old Streamlit frontend.

Pages: Dashboard, Analytics, SEC Filing Analysis, RAG Search, Report Generation, Ask FinSage, Observability.

API routes live in `frontend-react/api/routers/` — one file per domain (dashboard, analytics, sec, report, chat, pipeline, observability).

### dbt Project (`dbt_finsage/`)

- Profile: `dbt_finsage` (Snowflake via `~/.dbt/profiles.yml`)
- Staging models (4): materialized as **views**
- Analytics models (5): materialized as **tables** — `dim_company`, `fct_stock_metrics`, `fct_fundamentals_growth`, `fct_news_sentiment_agg`, `fct_sec_financial_summary`
- Custom schema macro in `models/macros/generate_schema_name.sql` controls schema resolution — check before changing `dbt_project.yml`

## Tech Stack

- **Python 3.12** — backend, agents, data loaders
- **Snowflake** (`FINSAGE_DB`, `FINSAGE_WH`) — data warehouse, Cortex LLM/VLM (claude-opus-4-6, mistral-large), Cortex SUMMARIZE
- **AWS Bedrock** — Knowledge Base RAG, Guardrails, multi-model inference
- **AWS S3** — SEC filing document storage
- **dbt 1.7** — SQL transformations
- **Apache Airflow 2.8** — Docker Compose orchestration (daily 5 PM EST)
- **Next.js 15 + MUI** — React frontend
- **FastAPI** — API backend for React frontend
- **reportlab + matplotlib** — PDF and chart generation
- **Terraform** — AWS S3 infrastructure (`terraform/s3/`)

## Development Workflow

Rules are in `.claude/rules/` (coding style, testing, git workflow, security, performance, agents) and `.cortex/rules/`.

- **Before writing SQL**: verify column names against `.astro/warehouse.md`
- **Commit style**: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- **Before commit**: `pytest` passes, `dbt compile` succeeds if dbt models changed, no hardcoded secrets

### Custom Commands (`.claude/commands/`)
- `/pipeline-debug` — Debug CAVM pipeline failures (connection, data, column names)
- `/dbt-validate` — Run dbt debug → compile → run → test → verify downstream
- `/data-quality` — Cross-layer data quality checks (RAW → STAGING → ANALYTICS)
