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

1. **Data Collection**: Gathers heterogeneous data from Yahoo Finance, NewsAPI, and financial databases
2. **Data Analysis**: Uses multi-agent architecture with Code Agent Variable Memory (CAVM) for dynamic analysis
3. **Report Generation**: Produces formatted reports with visualizations using two-stage writing framework

## Feature Status

| Feature | Status | Notes |
|---|---|---|
| Data ingestion pipeline (Yahoo, Alpha Vantage, NewsAPI, SEC EDGAR) | ✅ Done | Idempotent MERGE, quality scoring, incremental loading |
| dbt staging layer (4 views) | ✅ Done | `stg_stock_prices`, `stg_fundamentals`, `stg_news`, `stg_sec_filings` |
| dbt analytics layer (6 tables) | ✅ Done | `dim_company`, `dim_date`, `fct_stock_metrics`, `fct_fundamentals_growth`, `fct_news_sentiment_agg`, `fct_sec_financial_summary` |
| Multi-agent CAVM PDF generation | ✅ Done | Chart → Validation → Analysis → Report, reportlab output |
| VLM chart refinement (3-iteration loop) | ✅ Done | Snowflake Cortex `pixtral-large` |
| Chart retry on validation failure | ✅ Done | Up to 3 attempts per chart, pipeline aborts if >2 skipped |
| Streamlit frontend (10 pages) | ✅ Done | Dashboard, Pipeline, Analytics, SEC, RAG, Report, Multi-Model, Guardrails, Q&A, Status |
| AWS Bedrock Knowledge Base RAG | ✅ Done | Llama 3 with citations, cross-ticker comparison |
| Bedrock Guardrails | ✅ Done | Investment-advice denial, PII redaction, contextual grounding |
| Bedrock multi-model comparison + benchmarks | ✅ Done | Llama3, Titan, Mistral, Claude; results logged to `fct_model_benchmarks` |
| Airflow DAG (daily 5 PM EST) | ✅ Done | Parallel fetch → loader gate → dbt → QC |
| Terraform S3 infrastructure | ✅ Done | Bucket `finsage-sec-filings-808683` |
| Cortex SENTIMENT() in staging | ✅ Done | Replaces keyword matching |
| Loader retry + rate limiting | ✅ Done | tenacity exponential backoff, NewsAPI 5 req/min |
| Airflow holiday-calendar aware `is_trading_day` | 🔄 In Progress | Currently weekday-only; US market holidays pending |
| Streamlit caching rollout | 🔄 In Progress | `@st.cache_data` on Dashboard + Analytics; remaining pages pending |

## Technology Stack

### Data Engineering

- **Snowflake**: Cloud data warehouse + Cortex LLM/VLM (pixtral-large, mistral-large) + Cortex SUMMARIZE/SENTIMENT
- **dbt 1.7**: Staging views + analytics tables with tests
- **Apache Airflow 2.8**: Daily DAG (Docker Compose, CeleryExecutor)
- **Snowpark Python**: In-warehouse Python execution

### AI / Models

- **AWS Bedrock**: Knowledge Base RAG (Llama 3), Guardrails, multi-model (Llama3 / Titan / Mistral / Claude)
- **Snowflake Cortex**: `pixtral-large` VLM (chart critique), `mistral-large` LLM, `SUMMARIZE`, `SENTIMENT`
- **boto3**: AWS SDK for Bedrock + S3

### Data Sources

- **Yahoo Finance** (yfinance): OHLCV + quarterly fundamentals
- **Alpha Vantage**: Company fundamentals supplement
- **NewsAPI**: News articles (rate-limited)
- **SEC EDGAR**: 10-K / 10-Q filings + XBRL

### Reporting / Frontend

- **reportlab**: Branded PDF assembly (Midnight Teal theme)
- **matplotlib**: 6-chart generation
- **Streamlit**: 10-page interactive UI
- **Plotly**: Dashboard / Analytics Explorer visualizations

### Infrastructure

- **Terraform**: AWS S3 infrastructure as code (`terraform/s3/`)
- **AWS S3**: SEC filing storage (`finsage-sec-filings-808683`)
- **Docker Compose**: Airflow stack

### Dev Tooling

- **Python 3.9+**, **pandas**, **tenacity** (retries), **pytest** (73 tests), **python-dotenv**

## Architecture

```

┌─────────────────────────────────────────┐
│ DATA COLLECTION LAYER │
│ Yahoo Finance | NewsAPI | Alpha Vantage │
└─────────────────────────────────────────┘
↓
┌─────────────────────────────────────────┐
│ RAW LAYER (Snowflake) │
│ raw_stock_prices | raw_fundamentals │
│ raw_news │
└─────────────────────────────────────────┘
↓
┌─────────────────────────────────────────┐
│ STAGING LAYER (dbt transformations) │
│ stg_stock_prices | stg_fundamentals │
│ stg_news (with sentiment) │
└─────────────────────────────────────────┘
↓
┌─────────────────────────────────────────┐
│ ANALYTICS LAYER (planned) │
│ Financial metrics | Growth calculations │
│ Comparative analysis │
└─────────────────────────────────────────┘
↓
┌─────────────────────────────────────────┐
│ REPORT GENERATION (planned) │
│ Multi-page PDF with charts & citations │
└─────────────────────────────────────────┘

```

## Key Features Implemented

### Production-Grade Data Pipeline

- **Idempotent Loading**: MERGE statements prevent duplicate data
- **Data Quality Validation**: Pre-load checks for data integrity
- **Quality Scoring**: 0-100 score tracking data completeness
- **Incremental Loading**: Only fetches new data since last run

### Data Transformation

- **Automated dbt Models**: SQL-based transformations with dependency management
- **Parallel Execution**: 4-thread concurrency for faster processing
- **Built-in Testing**: Automated validation of data quality rules

### Security & Best Practices

- Environment variable management for API keys
- Structured logging and error handling
- Git version control with proper .gitignore
- Modular code organization

## Project Structure

```

finsage-project/
├── .env # Credentials (not in Git)
├── .gitignore
├── README.md
├── schema*design.md # Database schema documentation
├── scripts/ # Python scripts
│ ├── snowflake_connection.py
│ ├── load_sample_stock_data.py
│ ├── load_sample_fundamentals.py
│ ├── load_sample_news.py
│ ├── verify*_.py # Data verification scripts
│ └── run*migration*_.py # Database migrations
├── sql/ # SQL DDL scripts
│ ├── 01_create_raw_schema.sql
│ ├── 02_add_quality_score_column.sql
│ └── 05_create_staging_schema.sql
├── dbt_finsage/ # dbt project
│ ├── dbt_project.yml
│ └── models/
│ └── staging/
│ ├── stg_stock_prices.sql
│ ├── stg_fundamentals.sql
│ ├── stg_news.sql
│ └── schema.yml
└── notebooks/ # Jupyter notebooks (planned)

```

## Setup Instructions

### Prerequisites

- Python 3.13+
- Snowflake account (academic or trial)
- API keys: NewsAPI, Alpha Vantage (optional)

### Installation

1. **Clone the repository**

```bash
git clone <your-repo-url>
cd finsage-project
```

2. **Create virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install snowflake-snowpark-python yfinance pandas httpx beautifulsoup4 python-dotenv dbt-snowflake
```

4. **Configure credentials**

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
# NewsAPI (financial news ingestion, rate-limited to 5 req/min)
NEWSAPI_KEY=

# ── SEC EDGAR ────────────────────────────────────────
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
# Comma-separated list of Bedrock models for multi-model comparison
BEDROCK_MULTI_MODELS=meta.llama3-8b-instruct-v1:0,mistral.mistral-7b-instruct-v0:2,meta.llama3-70b-instruct-v1:0

# ── Snowflake Cortex AI Models ───────────────────────
# Primary LLM (analysis, chart code gen, document agent)
CORTEX_MODEL_LLM=claude-opus-4-6
# Primary VLM (chart critique, validation); falls back to pixtral-large
CORTEX_MODEL_VLM=openai-gpt-5.2
```

5. **Initialize database**

```bash
python scripts/create_raw_schema.py
python scripts/run_migration_05.py
```

6. **Initialize dbt**

```bash
cd dbt_finsage
dbt debug  # Verify connection
dbt run    # Run all models
dbt test   # Run data quality tests
```

### Running the Pipeline

**Load data:**

```bash
python scripts/load_sample_stock_data.py
python scripts/load_sample_fundamentals.py
python scripts/load_sample_news.py
```

**Transform data:**

```bash
cd dbt_finsage
dbt run --select staging
dbt test --select staging
```

**Verify results:**

```bash
python scripts/verify_staging_stock.py
```

## Key Innovations

- **CAVM Architecture**: Unified programmable workspace for data, tools, and agents (chart → validate → analyze → report)
- **Iterative Vision-Enhanced Refinement**: Chart quality improvement via VLM critique loop
- **Two-Stage Writing**: Chain-of-Analysis (CoA) per chart, then synthesized PDF composition
- **Guardrailed RAG**: SEC filing Q&A with Bedrock content safety + contextual grounding

## Why These Tools?

**Snowflake**: Industry-standard cloud data warehouse with native AI capabilities (Cortex)

**dbt**: Transforms data engineering into software engineering with version control, testing, and documentation

**Airflow**: Production-grade orchestration used by Airbnb, Twitter, and thousands of companies

**Python**: Versatile language with rich ecosystem for data engineering and AI

## Team

Graduate students at Northeastern University
Course: DAMG 7374 - Data Engineering: Impact of Generative AI with LLMs

## License

MIT License

## Contact

For questions or collaboration: [shantharajamani.r@northeastern.edu](mailto:shantharajamani.r@northeastern.edu) | [misra.o@northeastern.edu](mailto:misra.o@northeastern.edu) | [vedanarayanan.s@northeastern.edu](mailto:vedanarayanan.s@northeastern.edu)

---

**Note**: This is an academic project demonstrating modern data engineering practices with LLMs. Not intended for actual investment decisions.

```

```
