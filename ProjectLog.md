# FinSage Project Log

## Week 1 (Feb 9 - Feb 15, 2026)

### Implemented

**Environment Setup**

- Created virtual environment with Python 3.13
- Installed core dependencies: snowflake-snowpark-python, yfinance, pandas, requests, httpx, beautifulsoup4
- Configured .env file for credential management using python-dotenv
- Established Snowflake connection with session management module

**Data Source Exploration**

- Yahoo Finance API: Retrieved OHLCV data (Open, High, Low, Close, Volume) plus dividends and stock splits
- Alpha Vantage API: Explored fundamental metrics (market cap, P/E ratios, EBITDA, revenue)
- NewsAPI: Retrieved news articles with title, source, author, description, content, publication date

**Database Schema Design**

- Designed RAW layer schema with three tables: raw_stock_prices, raw_fundamentals, raw_news
- Included metadata columns: source, ingested_at for data lineage tracking
- Defined primary keys: (ticker, date) for prices, (ticker, fiscal_quarter) for fundamentals, article_id for news

**RAW Layer Implementation**

- Created FINSAGE_DB database with RAW schema in Snowflake
- Implemented SQL DDL scripts for table creation
- Built Python executors to run SQL migrations

**Data Loading Scripts**

- Stock prices loader: Fetched 1-month historical data from Yahoo Finance
- Fundamentals loader: Retrieved company financial metrics
- News loader: Collected articles from NewsAPI with proper API key management

**Production-Grade Enhancements**

- Idempotency: Implemented MERGE statements using temporary staging tables instead of DELETE-INSERT pattern to prevent data loss on failure
- Data Quality Validation: Built pre-load validation functions checking for negative prices, null critical fields, and logical consistency (high >= low, open/close within range)
- Data Quality Scoring: Added data_quality_score column (0-100 scale) with deduction logic for missing or invalid fields
- Incremental Loading: Implemented logic to query last loaded date and fetch only new data, reducing API calls and execution time

**Version Control**

- Initialized Git repository with proper .gitignore
- Organized folder structure: scripts/, sql/, notebooks/, dbt_finsage/
- Made incremental commits for each major feature

### Challenges

**Timestamp Data Type Issues**

- Snowflake rejected pandas datetime objects during write_pandas operation
- Root cause: Timezone-aware datetime from yfinance causing type mismatch
- Solution: Convert timestamps to string format using strftime before loading

**MERGE Statement Learning Curve**

- Initial confusion about staging table approach for MERGE operations
- Required understanding of temporary tables and their lifecycle in Snowflake
- Resolved by creating temp staging tables with LIKE clause, then executing MERGE

**Column Case Sensitivity**

- Snowflake creates uppercase columns by default, pandas uses lowercase
- Caused "invalid identifier" errors during data loading
- Solution: Uppercase all DataFrame columns before write_pandas operation

**Migration Execution Tracking**

- Forgot to run ALTER TABLE migrations for quality score columns
- Led to missing column errors during subsequent loads
- Implemented systematic migration script naming (01*, 02*, etc.) and verification queries

**API Key Security**

- Initially hardcoded NewsAPI key in Python script
- Learned industry practice of storing credentials in .env files
- Refactored to use environment variables with dotenv library

---

## Week 2 (Feb 16 - Feb 19, 2026)

### Implemented

**dbt Project Initialization**

- Installed dbt-snowflake adapter
- Initialized dbt_finsage project with Snowflake connection configuration
- Created STAGING and ANALYTICS schemas in Snowflake
- Configured profiles.yml with connection parameters and 4-thread concurrency

**Staging Models Development**

- stg_stock_prices: Added daily_return calculation using LAG window function, filtered to last 2 years, added is_valid flag
- stg_fundamentals: Validated revenue and market_cap fields, filtered invalid records
- stg_news: Implemented basic sentiment analysis using keyword matching (profit/growth = positive, loss/decline = negative), filtered to last 3 months

**dbt Source Configuration**

- Defined raw schema sources in schema.yml
- Documented model descriptions and column definitions
- Configured data tests: not_null tests for ticker, date, and close columns

**Data Quality Testing**

- Executed dbt test command to validate staging models
- All 3 tests passed: ticker not null, date not null, close not null
- Verified parallel test execution using 4 threads

**Verification Scripts**

- Built Python scripts to query and validate staging layer data
- Confirmed daily_return calculations were accurate (e.g., -0.67%, -3.46% drops observed)
- Verified sentiment classification in news staging table

### Challenges

**dbt Threading Concept**

- Initial confusion about what threads parameter controls
- Learned threads enable parallel model execution for independent models
- Understood trade-off between speed and resource usage (4 threads chosen for development balance)

**Window Function NULL Handling**

- First row in daily_return calculation returned NULL (no previous day to compare)
- Caused TypeError in Python formatting when attempting to format None as float
- Solution: Added conditional check (if row['DAILY_RETURN'] is not None) before formatting

**Example Model Cleanup**

- dbt init created example models in models/example/ folder
- Caused warning about unused configuration paths in dbt_project.yml
- Removed example folder and warning disappeared

**View vs Table Decision**

- dbt created staging models as views by default
- Need to understand when to use tables vs views for performance
- Views are appropriate for staging layer as they stay fresh with source data

**Sentiment Analysis Limitations**

- Basic keyword matching for sentiment is overly simplistic
- Recognized need for more sophisticated NLP or Snowflake Cortex sentiment functions
- Documented as future enhancement for analytics layer

---

## Week 3 (Feb 20 - Feb 28, 2026)

### Implemented

**Code Refactoring & Logging**

- Refactored data loading scripts into modular architecture under src/data_loaders/
- Built centralized logger (src/utils/logger.py) to replace scattered print() statements
- Created config/tickers.yaml for externalized ticker management instead of hardcoded lists
- Minor bug fixes across data pipeline scripts

**Airflow Setup**

- Set up Apache Airflow with Docker Compose (7 containers: webserver, scheduler, worker, triggerer, init, PostgreSQL, Redis)
- Created initial data_collection_dag.py with parallel data fetch tasks
- Configured CeleryExecutor with Redis broker for parallel task execution
- Wired real project scripts into Airflow DAG with volume mounts for scripts/, src/, config/, dbt_finsage/
- Added Architecture document outlining the system design

**SEC EDGAR Data Integration**

- Built XBRL data loader (XBRLLoader) for structured financial data from SEC EDGAR
- Implemented incremental loading with CIK (Central Index Key) resolution for ticker-to-CIK mapping
- Created stg_sec_filings staging model to complete RAW layer with 4 data sources
- Added SQL DDL migration (06_create_sec_table.sql) for RAW_SEC_FILINGS table

**SEC Filing Pipeline & AWS Infrastructure**

- Built SEC filing downloader (filing_downloader.py) for 10-K and 10-Q PDFs from EDGAR
- Built text extractor (text_extractor.py) for parsing MD&A and Risk Factors sections
- Built S3 utilities (s3_utils.py) for uploading filings to AWS S3
- Created Terraform configuration (terraform/s3/) for S3 bucket (finsage-sec-filings-808683) with versioning, AES-256 encryption, public access blocking, and lifecycle rules
- Defined IAM policies: full R/W for application, read-only for Snowflake external stage
- Added SQL DDL migration (07_create_filing_documents.sql) for RAW_SEC_FILING_DOCUMENTS

**Requirements Cleanup**

- Removed version pinning from requirements.txt for broader compatibility

### Challenges

**Airflow Volume Mounting**

- Docker containers needed access to project scripts, config, and dbt directory
- Required careful volume mount configuration to maintain correct paths inside containers
- Solution: Mapped host directories (scripts/, src/, config/, dbt_finsage/) as volumes in docker-compose.yaml

**SEC EDGAR Rate Limiting**

- SEC EDGAR requires a User-Agent header with contact email and recommends max 10 requests/second
- Initial requests were rejected without proper headers
- Solution: Added SEC_USER_AGENT environment variable to .env, implemented 0.3s delays between requests

**CIK Resolution Complexity**

- SEC filings use CIK numbers, not ticker symbols
- No single reliable API for ticker-to-CIK mapping
- Solution: Built 4-tier cascade: in-memory cache → SEC company_tickers.json bulk download → SEC EDGAR CGI search → hardcoded fallback for common tickers, with persistent cache in config/cik_cache.json

**Terraform State Management**

- First time using Terraform for infrastructure-as-code
- Needed to understand state files, plan/apply workflow, and resource lifecycle
- Learned to use terraform plan before apply to preview changes

---

## Weeks 4-5 (Mar 1 - Mar 16, 2026)

### Implemented

**Cortex Sentiment PoC (cortex_news_analysis.py)**

- Built end-to-end PoC replacing keyword-based sentiment with Snowflake Cortex SENTIMENT() function
- SENTIMENT() takes concatenated title + description text and returns a continuous float between -1.0 (negative) and +1.0 (positive), far more nuanced than binary keyword matching
- Tested on 20 AAPL headlines from STG_NEWS: average score +0.15 (slightly positive), matching manual assessment
- Added CORTEX.COMPLETE() integration using mistral-large2 to generate 3-sentence analyst commentary from top 10 headlines — validated that Cortex LLM could synthesize financial text coherently
- Implemented labeling thresholds: score > 0.2 → Positive, score < -0.2 → Negative, else Neutral

**Iterative Chart Generation PoC (Iterative_Chart_Generation.py)**

- Built 3-iteration chart refinement pipeline inspired by FinSight paper (Section 2.4): LLM generates matplotlib code → chart rendered as PNG → VLM critiques image → LLM refines code → repeat
- Used Snowflake Cortex llama3.1-70b for both LLM role (code generation) and VLM role (text-based critique)
- Iteration 1: Intentionally minimal chart (single close price line, no labels/grid/legend) to establish baseline
- Iteration 2: LLM adds volume bars (twinx), 5-day moving average, axis labels, gridlines based on VLM critique
- Iteration 3: Publication-ready styling — high/low range shading, area fill, professional color palette (#2563eb price, #f59e0b MA5, #94a3b8 volume), combined legend from dual axes
- Implemented subprocess-based chart execution with 30s timeout for safe LLM code evaluation
- Added code sanitization for known Cortex hallucinations: fillalpha= → alpha=, broken legend calls
- Created --mock mode with hardcoded AAPL data and pre-written mock critiques for offline testing without Snowflake connection
- Output: per-run directory under outputs/iterative_charts/ with 3 PNGs + summary.json containing all critiques and metadata

**Environment Diagnostics**

- Built diagnose_env.py utility to verify Snowflake connection, installed packages, and Cortex model availability before running PoCs

### Challenges

**Cortex Model Availability on SFEDU02**

- Not all Cortex models listed in documentation were available on the academic account
- llama3.1-70b was available and worked for both code generation and text critique, but pixtral-large (true VLM with image input) was not yet tested
- Solution: Used text-based critique as VLM proxy — the LLM critiques based on the code and data context rather than the rendered image; planned to integrate true image-based VLM in the production pipeline

**LLM Code Generation Reliability**

- Cortex llama3.1-70b frequently generated non-executable matplotlib code: hallucinated kwargs (fillalpha=, lineStyle=), missing imports it was told to skip, markdown fences around code blocks
- Required building a sanitization layer and structured system prompts ("Return ONLY raw executable Python code. NO markdown, NO backticks") to get consistent output
- Solution: Explicit system prompt with available variables listed, known-bad kwarg replacement, markdown fence stripping

**Subprocess Chart Rendering**

- Running LLM-generated code directly in the main process risked crashes from bad matplotlib calls
- Solution: Write DataFrame to temp CSV, wrap LLM code in a runner script with proper imports, execute in subprocess with 30s timeout, capture stderr for debugging

---

## Week 6 (Mar 17 - Mar 21, 2026)

### Implemented

**Analytics Layer — 5 dbt Models**

- fct_stock_metrics: Rolling SMA (7/30/90-day), 30-day volatility, 52-week high/low, price position, TREND_SIGNAL derivation (BULLISH when close > SMA_30D and SMA_7D > SMA_30D)
- fct_fundamentals_growth: QoQ and YoY growth rates for revenue, net income, EPS using LAG window functions; FUNDAMENTAL_SIGNAL derivation (STRONG_GROWTH when revenue_growth_yoy > 10% and net_income_growth_yoy > 10%)
- fct_news_sentiment_agg: Daily sentiment aggregation with 7-day rolling average, article counts, positive/negative breakdown; SENTIMENT_LABEL derivation (BULLISH/BEARISH/NEUTRAL/NO_COVERAGE)
- fct_sec_financial_summary: XBRL concept pivot (Revenues, NetIncomeLoss, Assets, Liabilities → columns), derived margins (net profit, operating), D/E ratio, ROE; FINANCIAL_HEALTH signal (EXCELLENT/HEALTHY/FAIR/UNPROFITABLE)
- dim_company: Company dimension with QUALIFY-based deduplication (1 row per ticker), market_cap_category classification, data_sources_available count, trading history range

**PR Merges & Code Quality**

- Fixed PR blockers: safe MERGE pattern, AWS environment variable handling, sys.path fixes
- Moved SEC_USER_AGENT email to .env for security
- Merged PRs #2, #3, #4 consolidating work across branches

**PoC Scripts**

- Committed iterative chart generation PoC using Snowflake Cortex
- Committed Cortex AI sentiment analysis scripts
- Initial working version of iterative chart generation with VLM feedback loop

### Challenges

**XBRL Pivot Logic**

- SEC XBRL data stores financial concepts as rows (one row per concept per period), not columns
- Needed to pivot 12 XBRL concepts into a single summary row per ticker per fiscal period
- Solution: Used conditional aggregation with MAX(CASE WHEN concept = 'Revenues' THEN value END) pattern in fct_sec_financial_summary

**QUALIFY-Based Deduplication**

- dim_company needed exactly 1 row per ticker, but data came from 4 staging sources with potential duplicates
- Standard GROUP BY lost detail; DISTINCT didn't handle conflicting values
- Solution: Used Snowflake's QUALIFY clause with ROW_NUMBER() to pick the most recent record per ticker

**Signal Threshold Calibration**

- Determining thresholds for BULLISH/BEARISH/NEUTRAL signals required empirical testing
- Too aggressive thresholds (e.g., >5% for STRONG_GROWTH) flagged everything as strong; too conservative thresholds missed real trends
- Solution: Tested against AAPL, MSFT, GOOGL historical data and calibrated to >10% YoY revenue + net income growth for STRONG_GROWTH

---

## Week 7 (Mar 22 - Mar 31, 2026)

### Implemented

**Chart Generation Demo — Production-Ready PoC**

- Consolidated duplicate PoC scripts (Iterative_chart_generator.py removed, Iterative_Chart_Generation.py retained as canonical version — 526 lines removed, 24 lines refined)
- Demonstrated working 3-iteration pipeline on real Snowflake data: AAPL price with SMA overlays, EPS trends, volume profiles
- Validated end-to-end flow: Cortex llama3.1-70b generates matplotlib code → subprocess renders PNG → Cortex critiques with structured 4-dimension evaluation (information density, label clarity, visual quality, missing elements) → LLM refines → final VLM approval gate
- Each run produces a timestamped output directory with iter1_basic.png, iter2_improved.png, iter3_professional.png, and summary.json with all critiques
- Merged PR #5 consolidating chart generation work from feature branch

**dbt Configuration & Staging Schema Updates**

- Updated dbt_project.yml materialization config: staging models explicitly set to views, analytics models to tables (18 lines changed)
- Extended staging schema.yml with 31 new lines of column-level documentation and tests for stg_sec_filings (concept, value, period_end, fiscal_year, fiscal_period fields)
- Aligned staging model definitions with downstream analytics layer requirements identified during Week 6

**Document Agent (Initial Version)**

- Built document_agent.py (445 lines) — unified SEC document analysis interface combining Snowflake analytics context with SEC filing text
- Supports 5 analysis modes: summary, risk, MD&A, compare (cross-ticker), Q&A
- Queries both ANALYTICS layer (fct_sec_financial_summary for financial metrics) and SEC filing text for contextual analysis
- Designed as the bridge between raw SEC data and the CAVM pipeline's analysis agent

### Challenges

**VLM Critique Reliability**

- VLM models (pixtral-large) sometimes returned generic feedback that didn't address specific visual issues
- Critique quality varied significantly between runs for the same chart — sometimes "looks good" with no actionable detail
- Solution: Structured the VLM prompt to request specific assessments across 4 dimensions (title, axis labels, legend, data density, colors) with a 1-10 score; added explicit instructions to "Start each issue with no" for parseable output

**Matplotlib Code Sanitization**

- LLM-generated matplotlib code frequently contained hallucinated methods and wrong keyword arguments
- Examples: fillalpha= instead of alpha=, lineStyle= instead of linestyle=, non-existent pyplot functions, broken legend() calls with mismatched handles/labels
- Solution: Built code sanitization layer in execute_chart_code() to fix known bad kwargs (fillalpha= → alpha=, fill_alpha= → alpha=), strip hallucinated method calls, and repair legend patterns before subprocess execution

**Document Agent Snowflake Session Management**

- Document agent needed both Snowflake analytics data and SEC filing text from S3, requiring two different connection patterns
- Long-running analysis queries risked session timeouts
- Solution: Used context-managed sessions with explicit close() in finally blocks; designed each analysis mode as a self-contained query-then-synthesize pattern

---

## Week 8 (Apr 1 - Apr 5, 2026)

### Implemented

**CAVM Pipeline — Complete Implementation**

- Chart Agent (chart_agent.py): Generates 6 matplotlib charts per ticker with VLM refinement loop, subprocess execution with 30s timeout, fallback code for failed renders
- Validation Agent (validation_agent.py): Two-tier quality assurance — rule-based checks (file exists, >10KB, dimensions, data plausibility) then VLM quality scoring (threshold ≥ 6/10, soft pass on VLM failure)
- Analysis Agent (analysis_agent.py): Chain-of-Analysis pattern where each chart analysis receives all prior analyses as context, building a progressive narrative; integrated SEC filing context via Bedrock KB RAG
- Report Agent (report_agent.py): Assembles branded PDF with reportlab using Midnight Teal color scheme (#0f2027 header, #00b4d8 accent, #06d6a0 bullish, #ef476f bearish); generates cover page, TOC, executive summary, chart sections, risk factors, investment recommendation, appendix
- Orchestrator (orchestrator.py): Coordinates 4 agents in sequence with --ticker, --skip-charts, and --debug flags

**Snowflake Cortex Sentiment Upgrade**

- Replaced basic keyword matching in stg_news with Snowflake Cortex ML sentiment scoring
- Moved from binary positive/negative classification to continuous sentiment scores
- Improved sentiment accuracy for financial news articles

**AWS Bedrock Integration**

- Bedrock Knowledge Base RAG (bedrock_kb.py): Vector search over SEC filing embeddings with post-retrieval ticker filtering, retrieve() for pure vector search, ask() for full RAG with Llama 3
- Guardrails (guardrails.py): Content safety validation — blocks investment advice (denied topic), redacts PII, detects hallucinations via contextual grounding; applied post-hoc via apply_guardrail() API
- Multi-model comparison (multi_model.py): Parallel inference across Llama 3, Titan, Mistral with consensus synthesis; ThreadPoolExecutor for concurrent model calls with latency tracking
- Document Agent (document_agent.py): Unified analysis interface combining Snowflake analytics context with SEC filing text for 5 analysis modes (summary, risk, MD&A, compare, Q&A)

**Streamlit Frontend (Initial)**

- Built initial Streamlit frontend (app.py) with 10 pages: Dashboard, Data Pipeline, Analytics Explorer, SEC Filing Analysis, RAG Search, Research Report, Multi-Model Analysis, Guardrails Demo, Ask FinSage, System Status
- Fixed snowflake_client token auth for session management

### Challenges

**Chain-of-Analysis Context Window**

- Feeding all prior analyses as context to each subsequent chart analysis created increasingly long prompts
- Risk of exceeding model context limits for the 8th chart analysis
- Solution: Truncated each prior analysis to 250 characters (later increased to 500 in Phase 3 improvements)

**Bedrock KB Ticker Filtering**

- Bedrock KB vector search is semantic, not metadata-filtered — a query about "AAPL revenue" could return MSFT filing chunks that discuss revenue
- Could not add metadata filters natively to the KB retrieval API
- Solution: Post-retrieval filtering — prepend ticker to query for relevance boost, fetch 3x results, parse S3 URIs to extract ticker from path, filter to matching ticker only

**Snowflake Token vs Password Auth**

- snowflake_client.py had hardcoded password authentication, breaking in environments using token-based auth
- Solution: Added dual auth mode — tries password first, falls back to token authentication

---

## Week 9 (Apr 6 - Apr 11, 2026)

### Implemented

**FinSage Q&A Page (09_Ask_FinSage.py)**

- Built dual-source Q&A interface: user asks a financial question, system queries both Snowflake Cortex COMPLETE() and Bedrock Knowledge Base RAG, then displays both answers side-by-side for comparison
- Implemented ticker-scoped context: Q&A answers grounded in the selected company's analytics data (fct_stock_metrics, fct_sec_financial_summary) rather than generic knowledge
- Added session-managed conversation history with clear/reset functionality

**System Status Page (10_System_Status.py)**

- Built health check dashboard verifying 5 independent services: Snowflake connectivity, AWS Identity (STS get-caller-identity), Bedrock KB availability, Guardrails API response, Multi-Model Analyzer endpoint
- Each service check runs with individual timeout and returns status (healthy/degraded/down) plus latency in ms
- Aggregated into overall system health score with color-coded status cards

**XBRL Loader & Pipeline Integration**

- Built xbrl_loader.py (206 lines) for structured financial data extraction from SEC EDGAR XBRL API
- Integrated XBRL loading into data_pipeline.py orchestration — pipeline now runs: stock → news → fundamentals → SEC filings → XBRL → dbt transformations
- Refactored FundamentalsLoader to fetch multi-quarter data from Yahoo Finance (107 lines changed), enabling quarter-over-quarter comparisons in analytics layer

**Enterprise Frontend Redesign (52 files, +4986/-622 lines)**

- Complete dark-theme redesign across all 10 Streamlit pages — Bloomberg Terminal-inspired aesthetic with consistent color palette (#0f172a background, #1e293b cards, #38bdf8 accents)
- Built reusable design system: styles.py for centralized CSS/theme constants, helpers.py for common UI patterns (metric cards, section headers, status badges)
- Replaced static matplotlib embeds with interactive Plotly charts (zoomable, hoverable, exportable)
- Added CAVM pipeline tracker visualization showing agent progress in real-time
- Built health card grid layout and portfolio treemap visualization for the dashboard overview
- Merged PRs #6, #7, #8 consolidating frontend, backend, and pipeline work

**CI & Testing Foundation**

- Added .github/workflows/ci.yml (45 lines) with automated lint + test pipeline
- Created initial test suite: test_config.py (93 lines), test_data_loaders.py (180 lines), test_helpers.py (57 lines), test_report_agent.py (93 lines)
- Added CLAUDE.md (197 lines) with project guidance, key commands, architecture overview, and tech stack reference

### Challenges

**End-to-End Health Check Coordination**

- System Status page needed to verify 5 independent services with different failure modes and timeout characteristics
- Snowflake checks take 2-5s, AWS STS < 1s, Bedrock KB 3-8s depending on index size — couldn't use a single timeout
- Solution: Built individual health check functions with service-specific timeouts (Snowflake 10s, AWS 5s, Bedrock 15s), ran checks concurrently, and aggregated into overall status with per-service latency display

**Streamlit Layout Limitations**

- Streamlit's column and expander widgets limited precise layout control for the analytics explorer — couldn't achieve nested grid layouts or overlapping elements needed for a Bloomberg-style terminal
- Dark theme required extensive CSS injection via st.markdown(unsafe_allow_html=True), which felt fragile
- Solution for this week: pushed Streamlit as far as possible with custom CSS; recognized need for a more flexible frontend framework (decision to migrate to Next.js came in Week 10)

**Plotly Chart Migration**

- Replacing static matplotlib images with interactive Plotly required restructuring how chart data was passed — matplotlib generates PNG files, Plotly needs DataFrames or dict traces
- Solution: Built adapter functions in helpers.py that accept the same DataFrame inputs as chart_agent but produce Plotly figure objects instead of PNGs; kept matplotlib in the CAVM pipeline (for PDF reports) and used Plotly only in the Streamlit frontend

---

## Week 10 (Apr 12 - Apr 18, 2026)

### Implemented

**Security & Quality Fixes**

- Fixed XSS vulnerabilities, SQL escaping issues, validation defaults, test mismatches, and logic bugs across 20 files
- Redesigned PDF cover page and table of contents with methodology callout box
- Added VLM refinement loop timeouts to prevent pipeline hangs
- Fixed chart fallbacks for volatility, revenue growth, and sentiment charts

**CAVM Pipeline Enhancements (Phases 1-4)**

- Bug Fix — Sentiment chart epoch dates: Added auto-date-conversion loop in chart runner to handle CSV round-trip date loss
- Bug Fix — Operating Margin "None": Added cross-computation (SEC operating_income / fundamentals revenue) and None filtering in report builder
- Bug Fix — Truncated business segments: Switched from 300-char truncation to LLM synthesis of full KB chunks for grammatically complete summaries
- Bug Fix — HTML entity rendering: Added html.unescape() to clean_llm_text() for proper S&P 500 rendering
- New Section — Financial Deep Dive: Multi-quarter income statement trends and balance sheet commentary from FCT_SEC_FINANCIAL_SUMMARY
- New Section — Valuation Analysis: Relative valuation comparison against peers with P/E, profit margin, D/E, market cap
- New Section — Enhanced Company Overview: Expanded to 6-8 sentences with TAM, competitive advantages, and competitive landscape sub-section
- New Charts — margin_trend (net + operating margin line chart) and balance_sheet (stacked bar with assets line overlay)
- Dynamic chart selection: MIN_ROWS threshold map skips charts with insufficient data points
- Strengthened Chain-of-Analysis: Doubled context window (250 → 500 chars), made cross-references mandatory between sections
- Professional tone polish: Upgraded all chart prompts from "3-4 sentence" to "4-6 sentence" with chart-specific analytical requirements
- Citation system: Added "Methodology Notes & Citations" table in the appendix mapping 9 sections to data sources

**Cortex Model Upgrades**

- Audited all available models on SFEDU02 account via SNOWFLAKE.CORTEX.COMPLETE()
- Upgraded analysis_agent.py: mistral-large → mistral-large2 → claude-opus-4-6
- Upgraded chart_agent.py: llama3.1-70b → llama4-maverick → claude-opus-4-6
- Upgraded VLM: Added openai-gpt-5.2 as primary VLM with pixtral-large fallback
- Increased VLM timeout from 60s → 90s → 120s for claude-opus response times

**Parallel Processing**

- Implemented parallel chart generation, validation, and analysis stages using ThreadPoolExecutor with 4 workers
- Added chart data preparation module (chart_data_prep.py), specifications module (chart_specs.py), and validation module (chart_validation.py)

**Next.js Frontend Migration**

- Initialized frontend-react project with Next.js 16, React 19, TypeScript, MUI 9
- Built 5-page application: Dashboard (KPIs + price chart + headlines), Analytics Explorer (4-tab layout), SEC Filing Analysis (filing inventory + AI analysis), Report Generation (quick report + CAVM 4-stage stepper), Ask FinSage (chat interface)
- Implemented "Fancy Flirt" design system: DM Serif Display headings, DM Sans body, editorial warm color palette (#0382B7 primary, #9DCBB8 success, #C96BAE accent, #E58B6D warning, #F8CB86 highlight)
- Built FastAPI backend with 6 REST routers: dashboard, analytics, sec, report, chat, pipeline
- Added pipeline endpoints for data readiness checking and async data loading
- Implemented async CAVM pipeline execution with background threads and polling-based status updates
- Removed Streamlit frontend in favor of frontend-react
- Built report chatbot with Snowflake Cortex for follow-up Q&A on generated reports, including cross-ticker comparison

**Documentation & Observability**

- Added comprehensive warehouse schema documentation (.astro/warehouse.md)
- Created 10 presentation architecture documents covering system architecture, data pipeline, Snowflake warehouse, CAVM pipeline, SEC filing pipeline, frontend, orchestration, infrastructure, design decisions, and talking points
- Implemented observability tracking for data loaders and pipeline stages

**Data Accuracy Fixes (Phases 6-7)**

- Fixed column name mismatch: NET_MARGIN vs NET_MARGIN_PCT causing Key Facts and peer data to show all N/A
- Fixed peer D/E ratios ~100x inflated: Batch SEC D/E override now applies to all tickers in peer set, not just target
- Fixed revenue growth 0.0%: Added annual statement fetching to fundamentals_loader.py, deriving quarterly approximations from annual data; expanded from 5-7 quarters to 16-21 quarters per ticker
- Removed 37 fillna(0) anti-patterns: Charts now preserve None for missing data instead of displaying misleading zeros
- Fixed SEC XBRL dedup: Replaced ABS(value) ASC ordering with YEAR(period_end) = fiscal_year filter to exclude prior-year comparison rows; corrected NFLX net margin from 69.7% to 25.8%
- Normalized Yahoo Finance D/E: Added ROUND(debt_to_equity / 100, 4) in dim_company.sql to convert percentage to ratio
- Added D/E outlier clamp (abs > 20 → None) as defense-in-depth in peer comparison
- Fixed Key Facts backfill: Corrected wrong chart data_summary key names (latest_revenue → total_revenue from financial_health chart)
- Fixed TOC page drift: Added identical onPage callbacks to Pass 1 templates and drift validation between passes
- Added cross-field consistency validation: 5 non-blocking pre-assembly checks (net margin consistency, D/E sanity, stock price sanity, N/A audit, EPS/revenue directional check)
- Rewrote load_sample_fundamentals.py to use modular FundamentalsLoader for all 50 tickers

**Frontend Polish & Features**

- Added detail level option for report generation (brief/standard/detailed)
- Added progress callbacks to CAVM pipeline for real-time status tracking in frontend
- Enhanced report API with progress streaming and history endpoints
- Improved SEC filing downloader with retry logic and caching
- Refined frontend theme and UI components with updated color scheme
- Added cross-ticker comparison and missing ticker alerts to report chat

**Ticker Expansion & Evaluation**

- Expanded tracked tickers from 5 to 50 across 5 sectors via config/tickers.yaml
- Loaded all 50 tickers successfully (0 failures), dbt build: 35 PASS, 0 ERROR
- Added evaluation folder with AAPL, META, PEP report evaluations
- Added AAPL evaluation reports comparing Opus 4.7 and ChatGPT outputs

### Challenges

**Sentiment Chart Epoch Dates**

- X-axis showed 1969-1970 dates instead of 2026 dates on sentiment charts
- Root cause: CSV round-trip in execute_chart_code() — DataFrame written to CSV, subprocess reads back with pd.read_csv(), datetime columns lose their type
- Solution: Added auto-date-conversion loop after pd.read_csv() that detects date columns by name, tries pd.to_datetime() standard parsing, falls back to epoch unit parsing (ms or s)

**XBRL Deduplication Mixing Current and Prior-Year Data**

- NFLX net margin computed as 69.7% instead of ~25.8%
- Root cause: fct_sec_financial_summary.sql dedup used ABS(value) ASC ordering, which mixed current-period and prior-year comparison rows from 10-Q filings (prior-year rows share the current fiscal_year but have a prior-year period_end)
- Solution: Two-CTE approach — current_period CTE filters WHERE YEAR(period_end) = fiscal_year, then deduped CTE applies ROW_NUMBER() on remaining rows

**Yahoo Finance D/E Ratio Scale Mismatch**

- DIM_COMPANY.DEBT_TO_EQUITY showed values like 102.63 for AAPL (should be ~1.03)
- Root cause: Yahoo Finance reports D/E as percentage (102.63 = 102.63%), but the column was stored without normalization
- Solution: Applied ROUND(debt_to_equity / 100, 4) in dim_company.sql; added agent-level clamp (abs > 20 → None) as defense-in-depth

**fillna(0) Anti-Pattern Across Charts**

- Charts displayed misleading zeros where data was actually missing (revenue growth of 0.0%, EPS of 0.0)
- Root cause: 37 occurrences of fillna(0) across chart_data_prep.py and chart_agent.py silently converted NaN/NULL to zero
- Solution: Removed all fillna(0) calls, added _safe_round_list() helper preserving None, rewrote fallback chart code to filter None/NaN and show "N/A" annotations

**Insufficient Quarterly Data for YoY Growth**

- Revenue growth showed 0.0% for 4 out of 5 quarters — only 1 quarter had a YoY comparison
- Root cause: yfinance quarterly_income_stmt returns ~5 quarters, but LAG(revenue, 4) needs 8+ quarters for YoY growth
- Solution: Added annual statement fetching to fundamentals_loader.py; derives quarterly approximations from annual data (revenue/4, net_income/4), clearly marked with source='yahoo_finance_annual_approx'; expanded to 16-21 quarters per ticker

**Next.js and FastAPI Dual-Server Architecture**

- Running two servers (Next.js on port 3000, FastAPI on port 8000) required CORS configuration
- Had to ensure Snowflake credentials were accessible from the FastAPI process without exposing them to the frontend
- Solution: CORS middleware in FastAPI main.py allowing localhost:3000, credentials loaded from .env server-side only

---
