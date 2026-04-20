<div align="center">

# FinSage

**AI-Powered Financial Research Report Generator**

<h3><a href="https://teamfinsage.vercel.app/">https://teamfinsage.vercel.app</a></h3>

[![Python](https://img.shields.io/badge/Python-3.9-3776AB?style=flat-square&logo=python&logoColor=white)](#)
[![Snowflake](https://img.shields.io/badge/Snowflake-Cortex_AI-29B5E8?style=flat-square&logo=snowflake&logoColor=white)](#)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](#)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=next.js&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white)](#)
[![dbt](https://img.shields.io/badge/dbt-1.7-FF694B?style=flat-square&logo=dbt&logoColor=white)](#)
[![Airflow](https://img.shields.io/badge/Airflow-2.8-017CEE?style=flat-square&logo=apache-airflow&logoColor=white)](#)
[![AWS](https://img.shields.io/badge/AWS-Bedrock-FF9900?style=flat-square&logo=amazon-aws&logoColor=white)](#)

*Built for DAMG 7374 -- Gen AI with Applications in Data Engineering (Northeastern University, Spring 2026)*

**Raghu Ram Shanta Rajamani** -- [shantharajamani.r@northeastern.edu](mailto:shantharajamani.r@northeastern.edu)
**Ojas Misra** -- [misra.o@northeastern.edu](mailto:misra.o@northeastern.edu)
**Shrirangesh Vedanarayanan** -- [vedanarayanan.s@northeastern.edu](mailto:vedanarayanan.s@northeastern.edu)

[What It Does](#what-it-does) · [The Stack](#the-stack) · [Architecture](#architecture) · [Frontend Pages](#frontend-pages) · [Features](#features) · [Getting Started](#getting-started) · [Project Structure](#project-structure) · [Output](#output) · [Tickers](#tickers)

</div>

<div align="center">

You want to research **AAPL**. You have **two hours**, not two weeks. Analyst reports cost thousands. Free summaries are too shallow to trust. So what do you actually do?

FinSage generates 15--20 page professional financial research reports -- with charts, SEC filing analysis, and citations -- in under 7 minutes. It pulls data from 5 sources, runs it through a 4-agent AI pipeline, and delivers a branded PDF with written analysis for any U.S. public company. 50 tickers come pre-loaded; type any valid ticker and FinSage fetches the data on demand.

</div>

<p align="center">
  <img src="docs/screenshots/Dashboard.png" alt="Dashboard" width="90%"/>
</p>

---

<h2 align="center">What It Does</h2>

| Step | What Happens | Time |
|------|-------------|------|
| **1. Fetch & Stage** | Pulls prices, news, 10-K filings, and fundamentals into Snowflake. dbt cleans and promotes to analytics tables. | ~1:30 |
| **2. Chart Agent** | Generates 8 matplotlib charts from analytics data. Each chart goes through a 3-iteration AI vision critique loop until quality passes. | ~2:00 |
| **3. Validation** | A second AI agent independently verifies every chart for visual quality and data integrity. Failed charts get regenerated. | ~1:00 |
| **4. Analysis** | Per-chart written analysis tied to the underlying numbers. SEC MD&A and Risk Factors summarized via Cortex. | ~1:30 |
| **5. PDF Assembly** | Branded 15--20 page report with executive summary, all charts, analysis sections, and a Q&A chatbot. | ~0:45 |

<p align="center"><strong>Total: ~7 minutes end-to-end.</strong></p>

<p align="center">
  <img src="docs/screenshots/report_pipeline.png" alt="Report Pipeline" width="90%"/>
</p>

---

<h2 align="center">The Stack</h2>

<h3 align="center">Data Engineering</h3>

- **Snowflake** -- Cloud data warehouse, Cortex LLM/VLM (`claude-sonnet-4-6`, `mistral-large`), Cortex SUMMARIZE, Cortex SENTIMENT
- **dbt 1.7** -- 5 staging views + 6 analytics tables with automated tests
- **Apache Airflow 2.8** -- Daily scheduled DAG (Docker Compose, CeleryExecutor)
- **Snowpark Python** -- In-warehouse Python execution

<h3 align="center">AI / Models</h3>

- **Snowflake Cortex** -- `claude-sonnet-4-6` VLM for chart critique, `mistral-large` for analysis, SUMMARIZE for SEC filings, SENTIMENT for news
- **AWS Bedrock** -- Knowledge Base RAG (Llama 3 with citations), Guardrails (investment-advice denial, PII redaction, contextual grounding), multi-model inference (Llama3, Titan, Mistral, Claude)

<h3 align="center">Frontend</h3>

- **Next.js 16** (App Router) + **React 19** + **TypeScript**
- **MUI 9** (Material UI) with custom theme
- **Recharts** (statistical charts) + **lightweight-charts** (candlestick/volume)
- **FastAPI** backend connecting React to Snowflake

<h3 align="center">Infrastructure</h3>

- **Terraform** -- AWS S3 infrastructure as code
- **Docker Compose** -- Airflow orchestration stack
- **AWS S3** -- SEC filing document storage

---

<h2 align="center">Architecture</h2>

<p align="center">
  <img src="docs/screenshots/architecture.png" alt="Architecture" width="90%"/>
</p>

<h3 align="center">CAVM Pipeline (Multi-Agent Report Generation)</h3>

| Agent | Role | Technology |
|-------|------|-----------|
| **01 -- Chart** | Generates 8 matplotlib charts from analytics tables. 3-iteration VLM refinement: initial draw --> AI critique --> redraw --> final. | `claude-opus-4-6` (Cortex LLM) + `claude-sonnet-4-6` (Cortex VLM) + matplotlib |
| **02 -- Validation** | Independently verifies visual quality and data integrity of every chart. Aborts if >2 charts fail. Auto-retries up to 3x. | `claude-sonnet-4-6` (Cortex VLM) |
| **03 -- Analysis** | Writes per-chart analysis tied to underlying numbers. Summarizes SEC MD&A and Risk Factors via Cortex SUMMARIZE. | `claude-opus-4-6` (Cortex LLM) + Cortex SUMMARIZE |
| **04 -- Report** | Assembles branded PDF: navy header, teal accents, gold highlights, color-coded signals. 15--20 pages. | `claude-opus-4-6` (Cortex LLM) + reportlab |

---

<h2 align="center">Frontend Pages</h2>

| Route | Page | What It Does |
|-------|------|-------------|
| `/` | Dashboard | KPI cards, signal badges, interactive candlestick chart with SMA overlays and volume, news headlines |
| `/analytics` | Analytics Explorer | 4-tab interface: Stock Metrics, Fundamentals, Sentiment, SEC Financials with interactive charts |
| `/sec` | SEC Filings | Filing inventory table, timeline visualization, 4 Cortex analysis modes (Summary, Risk, MD&A, Cross-Company) |
| `/report` | Report Generation | Quick Report (Cortex LLM markdown) and Full CAVM Pipeline with live 4-stage stepper and PDF download |

---

<h2 align="center">Features</h2>

| Feature | Details |
|---------|---------|
| Data pipeline + on-demand loading | 50 pre-loaded tickers via Airflow. Any valid U.S. ticker works on demand -- FinSage auto-fetches prices, fundamentals, news, and SEC filings before report generation. Idempotent MERGE, quality scoring (0--100), incremental fetch, retry with exponential backoff. |
| Three-layer Snowflake architecture | RAW (ingestion) --> STAGING (dbt views, cleaning) --> ANALYTICS (dbt tables, tested) |
| CAVM multi-agent report generation | Chart Agent --> Validation Agent --> Analysis Agent --> Report Agent, with VLM refinement loop |
| Vision-enhanced chart refinement | 3-iteration critique loop: Cortex `claude-sonnet-4-6` evaluates each chart, suggests improvements, chart is regenerated |
| React frontend (5 pages) | Dashboard, Analytics Explorer, SEC Filing Analysis, Report Generation (with live pipeline stepper), Ask FinSage chatbot |
| SEC filing RAG | Bedrock Knowledge Base over 10-K/10-Q filings, cross-ticker comparison, citations |
| Content guardrails | Blocks investment advice, redacts PII, detects hallucinations via contextual grounding |
| Multi-model benchmarking | Side-by-side comparison across Llama3, Titan, Mistral, Claude with consensus synthesis |
| Airflow orchestration | Daily DAG at 5 PM EST: 5 parallel data fetches --> dbt transformations --> quality checks |
| Branded PDF output | Midnight Teal theme, 8 chart types, color-coded signals (bullish/bearish), executive summary |

---

<h2 align="center">Getting Started</h2>

### Prerequisites

- Python 3.9+
- Node.js 18+
- Snowflake account
- API keys: NewsAPI, Alpha Vantage (optional), AWS credentials (for Bedrock/S3)

### 1. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Fill in: Snowflake creds, NEWSAPI_KEY, AWS keys, Bedrock KB/Guardrail IDs
```

### 3. Initialize database and run dbt

```bash
python scripts/create_raw_schema.py
python scripts/run_migration_05.py

cd dbt_finsage
dbt debug    # verify Snowflake connection
dbt run      # build staging + analytics layers
dbt test     # run data quality tests
```

### 4. Start the application

```bash
# Terminal 1: FastAPI backend
cd frontend-react/api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2: React frontend
cd frontend-react
npm install
npm run dev
# Open http://localhost:3000
```

### 5. Load data and generate reports

```bash
# Load data from all sources
python -c "from src.orchestration.data_pipeline import run_pipeline; run_pipeline()"

# Generate a full research report
python agents/orchestrator.py --ticker AAPL --debug
```

### Airflow (optional)

```bash
cd airflow
docker-compose up -d    # starts webserver, scheduler, worker
# Open http://localhost:8080 (airflow/airflow)
```

---

<h2 align="center">Project Structure</h2>

```
finsage-project/
├── frontend-react/             # React frontend + FastAPI backend
│   ├── app/                    # Next.js App Router (5 pages)
│   ├── components/             # Reusable UI components
│   ├── lib/                    # API client, theme, ticker context
│   └── api/                    # FastAPI backend + routers
├── agents/                     # CAVM multi-agent pipeline
│   ├── orchestrator.py         # Coordinates all 4 agents
│   ├── chart_agent.py          # Chart generation + VLM refinement
│   ├── validation_agent.py     # Chart quality verification
│   ├── analysis_agent.py       # Per-chart LLM analysis
│   └── report_agent.py         # PDF assembly (reportlab)
├── src/
│   ├── data_loaders/           # 5 loaders (stock, fundamentals, news, SEC, XBRL)
│   ├── orchestration/          # Pipeline runner
│   └── utils/                  # Snowflake client, logger, data readiness
├── scripts/sec_filings/        # Bedrock KB RAG, Guardrails, multi-model
├── dbt_finsage/                # dbt project (5 staging views + 6 analytics tables)
├── airflow/                    # Docker Compose Airflow stack + DAG
├── sql/                        # DDL migrations (01-08)
├── terraform/s3/               # AWS S3 infrastructure as code
├── config/tickers.yaml         # 50 pre-loaded tickers (custom tickers loaded on demand)
├── tests/                      # pytest suite
├── docs/screenshots/           # Application screenshots
├── outputs/                    # Generated reports
└── requirements.txt            # Python dependencies
```

---

<h2 align="center">Output</h2>

Reports are saved to `outputs/<TICKER>_<YYYYMMDD>_<HHMMSS>/` and include:

- **8 chart PNGs**: `price_sma`, `eps_trend`, `revenue_growth`, `sentiment`, `volatility`, `financial_health`, `margin_trend`, `balance_sheet`
- **VLM refinement artifacts**: `_iter1.png`, `_iter2.png`, `_iter3.png` per chart
- **`chart_manifest.json`**: Chart metadata and file paths
- **`pipeline_result.json`**: Full execution log
- **Final branded PDF**: 15--20 pages, Midnight Teal theme

<p align="center">
  <img src="docs/screenshots/generated_report.png" alt="Generated Report" width="90%"/>
</p>

---

<h2 align="center">Tickers</h2>

<p align="center">50 tickers come pre-loaded across 5 sectors via Airflow. Enter any valid U.S. stock ticker in the UI and FinSage will automatically fetch prices, fundamentals, news, and SEC filings on demand.</p>

<h3 align="center">Pre-loaded Tickers</h3>

| Sector | Tickers |
|--------|---------|
| Technology | AAPL, MSFT, NVDA, GOOGL, META, AVGO, ORCL, CRM, ADBE, AMD, SNAP, PINS |
| Consumer / Retail | AMZN, TSLA, WMT, HD, MCD, NKE, COST, PEP, KO, PG |
| Finance | JPM, V, MA, BAC, WFC, GS, MS, BLK, AXP, C |
| Healthcare | UNH, JNJ, LLY, ABBV, PFE, MRK, TMO, ABT, DHR, BMY |
| Energy / Industrial | XOM, CVX, LIN, NEE, UNP, RTX, HON, CAT, BA, NFLX |

---

<div align="center">

## License

MIT License

---

*This is an academic project demonstrating modern data engineering practices with LLMs. Not intended for actual investment decisions.*

</div>
