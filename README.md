# FinSage: AI-Powered Financial Research Report Generator

An end-to-end automated system that generates professional financial research reports for U.S. public companies using Large Language Models, multi-agent architecture, and modern data engineering tools.

## Problem Statement

Investment decisions worth billions of dollars depend on high-quality financial research reports. However, producing these reports is:

- **Labor-intensive**: Analysts spend weeks gathering data from multiple sources
- **Time-consuming**: Manual analysis of financial statements, news, and market data
- **Expensive**: Professional reports cost thousands of dollars
- **Inconsistent**: Quality varies based on analyst expertise

**FinSage automates this process**, generating 15-20 page professional financial reports with charts, analysis, and citations in under 30 minutes.

## Solution Overview

FinSage implements a three-stage pipeline:

1. **Data Collection**: Gathers heterogeneous data from Yahoo Finance, NewsAPI, SEC EDGAR (XBRL + filing documents), and Alpha Vantage
2. **Data Analysis**: Uses multi-agent architecture with Code Agent Variable Memory (CAVM) for dynamic analysis
3. **Report Generation**: Produces formatted PDF reports with 8 chart types using a two-stage writing framework

## Feature Status

| Feature | Status | Notes |
|---|---|---|
| Data ingestion pipeline (Yahoo, Alpha Vantage, NewsAPI, SEC EDGAR, S3 filings) | ✅ Done | Idempotent MERGE, quality scoring, incremental loading, 50 tickers |
| dbt staging layer (5 views) | ✅ Done | `stg_stock_prices`, `stg_fundamentals`, `stg_news`, `stg_sec_filings`, `stg_sec_filing_documents` |
| dbt analytics layer (6 tables) | ✅ Done | `dim_company`, `dim_date`, `fct_stock_metrics`, `fct_fundamentals_growth`, `fct_news_sentiment_agg`, `fct_sec_financial_summary` |
| Multi-agent CAVM PDF generation | ✅ Done | Chart → Validation → Analysis → Report, reportlab output |
| VLM chart refinement (3-iteration loop) | ✅ Done | Snowflake Cortex `claude-sonnet-4-6` |
| Chart retry on validation failure | ✅ Done | Up to 3 attempts per chart, pipeline aborts if >2 skipped |
| React frontend (5 pages) + FastAPI backend | ✅ Done | Dashboard, Analytics Explorer, SEC Filings, Report Generation, Ask FinSage |
| AWS Bedrock Knowledge Base RAG | ✅ Done | Llama 3 with citations, cross-ticker comparison |
| Bedrock Guardrails | ✅ Done | Investment-advice denial, PII redaction, contextual grounding |
| Bedrock multi-model comparison + benchmarks | ✅ Done | Llama3, Titan, Mistral, Claude; results logged to `fct_model_benchmarks` |
| Airflow DAG (daily 5 PM EST) | ✅ Done | 5 parallel fetches → loader gate → dbt → QC |
| Terraform S3 infrastructure | ✅ Done | Bucket `finsage-sec-filings-808683` |
| Cortex SENTIMENT() in staging | ✅ Done | Replaces keyword matching |
| Loader retry + rate limiting | ✅ Done | tenacity exponential backoff, NewsAPI 5 req/min |

## Technology Stack

### Data Engineering

- **Snowflake**: Cloud data warehouse + Cortex LLM/VLM (`claude-opus-4-6`, `claude-sonnet-4-6`) + Cortex SUMMARIZE/SENTIMENT
- **dbt 1.7**: 5 staging views + 6 analytics tables with tests
- **Apache Airflow 2.8**: Daily DAG (Docker Compose, CeleryExecutor)
- **Snowpark Python**: In-warehouse Python execution

### AI / Models

- **AWS Bedrock**: Knowledge Base RAG (Llama 3), Guardrails, multi-model (Llama3 / Titan / Mistral / Claude)
- **Snowflake Cortex**: `claude-opus-4-6` LLM (analysis, code gen), `claude-sonnet-4-6` VLM (chart critique, validation), `SUMMARIZE`, `SENTIMENT`
- **boto3**: AWS SDK for Bedrock + S3

### Data Sources

- **Yahoo Finance** (yfinance): OHLCV + quarterly fundamentals
- **Alpha Vantage**: Company fundamentals supplement
- **NewsAPI**: News articles (rate-limited)
- **SEC EDGAR**: 10-K / 10-Q filings, XBRL data, filing documents

### Frontend

- **Next.js 16** (App Router): React framework with TypeScript
- **React 19**: UI library
- **MUI 9** (Material UI): Component library with custom "Fancy Flirt" theme
- **Tailwind CSS 4**: Utility-first styling
- **Recharts**: Statistical charts (bar, line, area, scatter)
- **lightweight-charts**: Interactive price charts (candlestick, SMA, volume)
- **FastAPI**: Python backend API connecting React frontend to Snowflake
- **Axios**: HTTP client

### Reporting

- **reportlab**: Branded PDF assembly (Midnight Teal theme)
- **matplotlib**: 8-chart generation with VLM refinement

### Infrastructure

- **Terraform**: AWS S3 infrastructure as code (`terraform/s3/`)
- **AWS S3**: SEC filing storage (`finsage-sec-filings-808683`)
- **Docker Compose**: Airflow stack

### Dev Tooling

- **Python 3.9+**, **pandas**, **tenacity** (retries), **pytest**, **python-dotenv**
- **TypeScript 5**, **ESLint 9**, **PostCSS**

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND (Next.js 16)              │
│  Dashboard │ Analytics │ SEC Filings │ Report │ Ask FinSage  │
└────────────────────────────┬─────────────────────────────────┘
                             │ Axios / REST
┌────────────────────────────▼─────────────────────────────────┐
│                     FastAPI BACKEND (Python)                  │
│  /api/dashboard │ /api/analytics │ /api/sec │ /api/report    │
│  /api/chat │ /api/pipeline │ /api/tickers │ /api/health      │
└──────┬──────────────────┬────────────────────┬───────────────┘
       │                  │                    │
       ▼                  ▼                    ▼
┌─────────────┐  ┌────────────────┐  ┌─────────────────────┐
│  Snowflake  │  │  AWS Bedrock   │  │   CAVM Pipeline     │
│  Cortex AI  │  │  KB RAG        │  │   (Report Gen)      │
│  Data WH    │  │  Guardrails    │  │   Chart → Validate  │
│             │  │  Multi-Model   │  │   → Analyze → PDF   │
└──────┬──────┘  └───────┬────────┘  └─────────────────────┘
       │                 │
       ▼                 ▼
┌──────────────────────────────────────────────────────────────┐
│                    DATA COLLECTION LAYER                      │
│   Yahoo Finance │ NewsAPI │ Alpha Vantage │ SEC EDGAR        │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│  RAW LAYER (Snowflake)                                       │
│  raw_stock_prices │ raw_fundamentals │ raw_news              │
│  raw_sec_filings │ raw_sec_filing_documents │                │
│  raw_sec_filing_text                                         │
└──────────────────────────────┬───────────────────────────────┘
       │ dbt
       ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGING LAYER (dbt views)                                   │
│  stg_stock_prices │ stg_fundamentals │ stg_news              │
│  stg_sec_filings │ stg_sec_filing_documents                  │
└──────────────────────────────┬───────────────────────────────┘
       │ dbt
       ▼
┌──────────────────────────────────────────────────────────────┐
│  ANALYTICS LAYER (dbt tables)                                │
│  dim_company │ dim_date │ fct_stock_metrics                  │
│  fct_fundamentals_growth │ fct_news_sentiment_agg            │
│  fct_sec_financial_summary                                   │
└──────────────────────────────────────────────────────────────┘
```

## Key Features

### Production-Grade Data Pipeline

- **50 Tracked Tickers**: Top US stocks across 5 sectors (Technology, Consumer, Finance, Healthcare, Energy/Industrial)
- **Idempotent Loading**: MERGE statements prevent duplicate data
- **Data Quality Validation**: Pre-load checks for data integrity
- **Quality Scoring**: 0-100 score tracking data completeness
- **Incremental Loading**: Only fetches new data since last run
- **Retry + Rate Limiting**: tenacity exponential backoff, NewsAPI 5 req/min

### Multi-Agent Report Generation (CAVM Pipeline)

`agents/orchestrator.py` coordinates four agents in sequence:

1. **Chart Agent** (`chart_agent.py` + `chart_data_prep.py`, `chart_specs.py`, `chart_validation.py`) — Queries ANALYTICS layer, generates 8 matplotlib charts per ticker, uses 3-iteration VLM refinement loop (Snowflake Cortex `claude-sonnet-4-6`: initial → critique → refined → final)
2. **Validation Agent** (`validation_agent.py`) — Validates chart visual quality and data integrity, flags failures for re-generation
3. **Analysis Agent** (`analysis_agent.py`) — Per-chart LLM analysis via Snowflake Cortex, plus SEC MD&A/Risk Factors summarization via Cortex SUMMARIZE
4. **Report Agent** (`report_agent.py`) — Assembles branded PDF with reportlab (Midnight Teal color scheme)

Chart types: `price_sma`, `eps_trend`, `revenue_growth`, `sentiment`, `volatility`, `financial_health`, `margin_trend`, `balance_sheet`

### React Frontend (5 Pages)

| Route | Page | Features |
|---|---|---|
| `/` | Dashboard | KPI cards, signal badges, interactive price chart (candlestick + SMA + volume), news headlines |
| `/analytics` | Analytics Explorer | 4-tab interface: Stock Metrics, Fundamentals, Sentiment, SEC Financials |
| `/sec` | SEC Filings | Filing inventory table, timeline scatter chart, 4 Cortex analysis modes (Summary, Risk, MD&A, Comparison) |
| `/report` | Report Generation | Quick Report (Cortex LLM markdown) and Full CAVM Pipeline (4-stage stepper with polling, PDF download) |
| `/ask` | Ask FinSage | Chat interface powered by Snowflake Cortex with suggested questions |

### SEC Filing Processing

- Filing download from SEC EDGAR + S3 storage
- Bedrock Knowledge Base RAG with citations
- Bedrock Guardrails (investment-advice denial, PII redaction, contextual grounding)
- Multi-model comparison + consensus synthesis

### Data Transformation (dbt)

- **5 staging models**: materialized as **views** in `staging` schema
- **6 analytics models**: materialized as **tables** in `analytics` schema
- Automated validation with dbt tests

## Project Structure

```
finsage-project/
├── frontend-react/                 # React frontend + FastAPI backend
│   ├── app/                        # Next.js App Router pages
│   │   ├── layout.tsx              # Root layout, metadata, fonts
│   │   ├── ThemeRegistry.tsx       # MUI + TickerProvider + AppShell
│   │   ├── globals.css             # Tailwind, CSS vars, markdown styles
│   │   ├── page.tsx                # / — Dashboard
│   │   ├── analytics/page.tsx      # /analytics — Analytics Explorer
│   │   ├── sec/page.tsx            # /sec — SEC Filing Analysis
│   │   ├── report/page.tsx         # /report — Report Generation
│   │   └── ask/page.tsx            # /ask — Ask FinSage Chat
│   ├── components/                 # Reusable UI components
│   │   ├── AppShell.tsx            # Sidebar nav + ticker selector
│   │   ├── MetricCard.tsx          # KPI card with delta indicator
│   │   ├── PriceChart.tsx          # lightweight-charts candlestick
│   │   ├── SignalBadge.tsx         # BULLISH/BEARISH color chip
│   │   ├── SectionHeader.tsx       # Left-bordered section title
│   │   ├── ChatMessage.tsx         # Chat bubble component
│   │   └── LoadingSkeleton.tsx     # Skeleton loading states
│   ├── lib/                        # Shared utilities
│   │   ├── api.ts                  # Axios client + all API functions
│   │   ├── theme.ts               # MUI theme ("Fancy Flirt" palette)
│   │   └── ticker-context.tsx      # React Context for active ticker
│   ├── api/                        # FastAPI backend (Python)
│   │   ├── main.py                 # FastAPI app, CORS, router mounting
│   │   ├── deps.py                 # Snowpark session factory
│   │   ├── requirements.txt        # Python deps (FastAPI, Snowpark)
│   │   └── routers/
│   │       ├── dashboard.py        # /api/dashboard — KPIs, price, headlines
│   │       ├── analytics.py        # /api/analytics — stock, fundamentals, sentiment, SEC
│   │       ├── sec.py              # /api/sec — filing inventory + Cortex analysis
│   │       ├── report.py           # /api/report — quick report + CAVM pipeline
│   │       ├── chat.py             # /api/chat — Ask FinSage Q&A
│   │       └── pipeline.py         # /api/pipeline — data readiness + on-demand loading
│   ├── package.json                # Next.js 16, React 19, MUI 9, Recharts, etc.
│   ├── next.config.ts
│   ├── tsconfig.json
│   └── postcss.config.mjs          # Tailwind v4 PostCSS plugin
├── agents/                         # CAVM multi-agent report generation
│   ├── orchestrator.py             # Coordinates chart → validation → analysis → report
│   ├── chart_agent.py              # Chart generation with VLM refinement
│   ├── chart_data_prep.py          # Data preparation for charts
│   ├── chart_specs.py              # Chart type specifications
│   ├── chart_validation.py         # Chart quality validation logic
│   ├── vision_utils.py             # VLM interaction utilities
│   ├── validation_agent.py         # Chart visual quality + data integrity
│   ├── analysis_agent.py           # Per-chart LLM analysis + SEC summarization
│   └── report_agent.py             # Branded PDF assembly with reportlab
├── src/
│   ├── data_loaders/               # Base loader + 5 loaders
│   │   ├── base_loader.py          # Abstract BaseDataLoader template
│   │   ├── stock_loader.py         # Yahoo Finance OHLCV
│   │   ├── fundamentals_loader.py  # Alpha Vantage / yfinance fundamentals
│   │   ├── news_loader.py          # NewsAPI articles
│   │   ├── sec_loader.py           # SEC EDGAR XBRL filings
│   │   ├── xbrl_loader.py          # XBRL data parsing
│   │   └── fetch_all_ciks.py       # SEC CIK lookup utility
│   ├── orchestration/
│   │   └── data_pipeline.py        # Runs all loaders in sequence
│   └── utils/
│       ├── logger.py               # Structured logging
│       ├── snowflake_client.py     # Snowflake connection helper
│       ├── data_readiness.py       # Per-ticker data readiness checks
│       └── on_demand_loader.py     # On-demand data loading for frontend
├── scripts/
│   ├── sec_filings/                # Bedrock KB RAG, Guardrails, multi-model, S3
│   │   ├── bedrock_kb.py           # Knowledge Base RAG client
│   │   ├── guardrails.py           # Bedrock Guardrails for content safety
│   │   ├── multi_model.py          # Multi-model comparison (Llama3, Titan, Mistral, Claude)
│   │   ├── s3_utils.py             # S3 filing storage management
│   │   ├── filing_downloader.py    # SEC EDGAR filing downloads
│   │   ├── text_extractor.py       # PDF/HTML text extraction
│   │   └── document_agent.py       # SEC document analysis agent
│   ├── load_sample_*.py            # Legacy individual data loaders
│   ├── run_migration_*.py          # SQL DDL migration runners
│   └── verify_*.py                 # Data verification scripts
├── dbt_finsage/                    # dbt project
│   ├── dbt_project.yml
│   └── models/
│       ├── staging/                # 5 views in staging schema
│       │   ├── stg_stock_prices.sql
│       │   ├── stg_fundamentals.sql
│       │   ├── stg_news.sql
│       │   ├── stg_sec_filings.sql
│       │   └── stg_sec_filing_documents.sql
│       └── analytics/              # 6 tables in analytics schema
│           ├── dim_company.sql
│           ├── dim_date.sql
│           ├── fct_stock_metrics.sql
│           ├── fct_fundamentals_growth.sql
│           ├── fct_news_sentiment_agg.sql
│           └── fct_sec_financial_summary.sql
├── airflow/                        # Docker Compose Airflow stack
│   ├── dags/
│   │   └── data_collection_dag.py  # Daily 5 PM EST, 5 parallel fetches
│   └── docker-compose.yaml
├── sql/                            # DDL migrations (01-08)
├── terraform/s3/                   # AWS S3 infrastructure as code
├── tests/                          # pytest test suite
├── config/tickers.yaml             # 50 tracked ticker symbols
├── outputs/                        # Generated reports: <TICKER>_<YYYYMMDD>_<HHMMSS>/
├── requirements.txt                # Core Python deps (pipeline, agents, charts)
└── requirements_2.txt              # Airflow + dbt deps
```

## Setup Instructions

### Prerequisites

- Python 3.9+
- Node.js 18+
- Snowflake account
- API keys: NewsAPI, Alpha Vantage (optional), AWS credentials

### Installation

1. **Clone the repository**

```bash
git clone <your-repo-url>
cd finsage-project
```

2. **Create virtual environment and install Python dependencies**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure credentials**

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
# ── Snowflake Connection ──────────────────────────────
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_WAREHOUSE=FINSAGE_WH
SNOWFLAKE_DATABASE=FINSAGE_DB
SNOWFLAKE_SCHEMA=RAW

# ── Data Source API Keys ─────────────────────────────
NEWSAPI_KEY=
SEC_USER_AGENT=

# ── AWS Credentials ──────────────────────────────────
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1

# ── AWS S3 (SEC filing document storage) ─────────────
FINSAGE_S3_BUCKET=

# ── AWS Bedrock (RAG, guardrails, multi-model) ───────
BEDROCK_KB_ID=
BEDROCK_MODEL_ID=meta.llama3-8b-instruct-v1:0
BEDROCK_GUARDRAIL_ID=
BEDROCK_GUARDRAIL_VERSION=DRAFT
BEDROCK_MULTI_MODELS=meta.llama3-8b-instruct-v1:0,mistral.mistral-7b-instruct-v0:2,meta.llama3-70b-instruct-v1:0

# ── Snowflake Cortex AI Models ───────────────────────
CORTEX_MODEL_LLM=claude-opus-4-6
CORTEX_MODEL_VLM=claude-sonnet-4-6
```

4. **Initialize database**

```bash
python scripts/create_raw_schema.py
python scripts/run_migration_05.py
```

5. **Initialize dbt**

```bash
cd dbt_finsage
dbt debug  # Verify connection
dbt run    # Run all models
dbt test   # Run data quality tests
```

6. **Set up the React frontend**

```bash
cd frontend-react
npm install
```

7. **Install FastAPI backend dependencies**

```bash
cd frontend-react/api
pip install -r requirements.txt
```

### Running the Application

**Start the FastAPI backend** (from `frontend-react/api/`):

```bash
cd frontend-react/api
uvicorn main:app --reload --port 8000
```

**Start the React frontend** (from `frontend-react/`):

```bash
cd frontend-react
npm run dev
```

The frontend runs at `http://localhost:3000` and the API at `http://localhost:8000`.

**Load data:**

```bash
# Modular pipeline (preferred)
python -c "from src.orchestration.data_pipeline import run_pipeline; run_pipeline()"

# Individual loaders (legacy)
python scripts/load_sample_stock_data.py
python scripts/load_sample_fundamentals.py
python scripts/load_sample_news.py
python scripts/load_sec_data.py
```

**Run dbt transformations:**

```bash
cd dbt_finsage
dbt run --select staging     # Staging layer only
dbt run --select analytics   # Analytics layer only
dbt run                      # All models
dbt test                     # Data quality tests
```

**Generate a report (CAVM pipeline):**

```bash
python agents/orchestrator.py --ticker AAPL --debug
python agents/orchestrator.py --ticker AAPL --skip-charts --charts-dir outputs/AAPL_20260404_104147
```

**Start Airflow (Docker Compose):**

```bash
cd airflow
docker-compose up airflow-webserver    # http://localhost:8080
docker-compose up airflow-scheduler
docker-compose up airflow-worker
```

## Key Innovations

- **CAVM Architecture**: Unified programmable workspace for data, tools, and agents (chart → validate → analyze → report)
- **Iterative Vision-Enhanced Refinement**: Chart quality improvement via 3-iteration VLM critique loop
- **Two-Stage Writing**: Chain-of-Analysis (CoA) per chart, then synthesized PDF composition
- **Guardrailed RAG**: SEC filing Q&A with Bedrock content safety + contextual grounding
- **50-Ticker Scale**: Production-grade pipeline processing top US stocks across 5 market sectors

## Output

Generated reports go to `outputs/<TICKER>_<YYYYMMDD>_<HHMMSS>/` containing:
- 8 chart PNGs (`price_sma`, `eps_trend`, `revenue_growth`, `sentiment`, `volatility`, `financial_health`, `margin_trend`, `balance_sheet`)
- Iterative VLM refinement artifacts (`_iter1.png`, `_iter2.png`, `_iter3.png`)
- `chart_manifest.json` — Chart metadata and file paths
- `pipeline_result.json` — Full pipeline execution results
- Final branded PDF report (15-20 pages)

## Team

Graduate students at Northeastern University
Course: DAMG 7374 - Data Engineering: Impact of Generative AI with LLMs

## License

MIT License

## Contact

For questions or collaboration: [shantharajamani.r@northeastern.edu](mailto:shantharajamani.r@northeastern.edu) | [misra.o@northeastern.edu](mailto:misra.o@northeastern.edu) | [vedanarayanan.s@northeastern.edu](mailto:vedanarayanan.s@northeastern.edu)

---

**Note**: This is an academic project demonstrating modern data engineering practices with LLMs. Not intended for actual investment decisions.
