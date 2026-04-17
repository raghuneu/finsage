# Orchestration Architecture — Airflow & dbt

## What It Does

Apache Airflow schedules and monitors the daily data collection pipeline, while dbt handles SQL-based transformations from RAW to STAGING to ANALYTICS. Together, they ensure data is fresh, validated, and transformed on a predictable schedule.

---

## Airflow DAG Structure

```mermaid
graph TD
    subgraph "Parallel Data Collection"
        T1["fetch_stock_prices<br/>StockPriceLoader<br/>50 tickers × batches of 10"]
        T2["fetch_fundamentals<br/>FundamentalsLoader<br/>50 tickers × batches of 10"]
        T3["fetch_news<br/>NewsLoader<br/>50 tickers × batches of 10"]
        T4["fetch_sec_data<br/>XBRLLoader + SECFilingLoader<br/>50 tickers × batches of 10"]
        T5["fetch_s3_filings<br/>S3 filing sync"]
    end
    
    GATE["check_loaders_success<br/>Quality Gate<br/>Requires ≥25 tickers<br/>with fresh data"]
    
    DBT_S["run_dbt_staging<br/>dbt run --select staging<br/>5 views"]
    
    DBT_A["run_dbt_analytics<br/>dbt run --select analytics<br/>7 tables"]
    
    DQ["data_quality_check<br/>Validate analytics output"]
    
    T1 --> GATE
    T2 --> GATE
    T3 --> GATE
    T4 --> GATE
    T5 --> GATE
    
    GATE --> DBT_S
    DBT_S --> DBT_A
    DBT_A --> DQ
```

---

## Schedule & Configuration

| Setting | Value | Why |
|---------|-------|-----|
| **Schedule** | `0 22 * * 1-5` (10 PM UTC / 5 PM EST) | After US market close (4 PM EST), with buffer for data availability |
| **Weekdays only** | Mon-Fri | No stock market data on weekends; saves API calls and compute |
| **Retries** | 3 attempts, 5-minute delay | External APIs can have transient failures |
| **Execution timeout** | 2 hours | Upper bound for full pipeline with 50 tickers |
| **CeleryExecutor** | Redis broker + PostgreSQL metadata | Enables parallel task execution across workers |

---

## Batch Processing Strategy

```mermaid
flowchart TD
    A["50 tickers from config/tickers.yaml"] --> B["Split into batches of 10"]
    
    B --> C["Batch 1: AAPL, MSFT, GOOGL,<br/>AMZN, META, NVDA, TSLA,<br/>BRK-B, JPM, V"]
    B --> D["Batch 2: Next 10 tickers"]
    B --> E["Batch 3: ..."]
    B --> F["Batch 4: ..."]
    B --> G["Batch 5: Last 10 tickers"]
    
    C --> H["Process sequentially within batch"]
    H --> I["Rate-limit delay between batches"]
    
    I --> D
    
    subgraph "Per-batch delays"
        J["NewsAPI: 30s between batches<br/>(strict rate limit)"]
        K["Stock/SEC/XBRL: 5s between batches"]
    end
```

**Why batches of 10:** API rate limits vary by source. NewsAPI's free tier is the most restrictive (100 requests/day). Batching with delays prevents hitting rate limits while maximizing throughput.

---

## Quality Gate — check_loaders_success

```mermaid
flowchart TD
    A["Query each RAW table"] --> B["SELECT COUNT(DISTINCT TICKER)<br/>WHERE ingested_at >= CURRENT_DATE()"]
    
    B --> C["RAW_STOCK_PRICES: 48 tickers"]
    B --> D["RAW_FUNDAMENTALS: 42 tickers"]
    B --> E["RAW_NEWS: 35 tickers"]
    B --> F["RAW_SEC_FILINGS: 50 tickers"]
    
    C & D & E & F --> G{Any table < 25 tickers?}
    
    G -->|Yes| H["AirflowException<br/>Block dbt from running<br/>on stale data"]
    G -->|No| I["PASS — proceed to dbt"]
```

**Why 25-ticker minimum:** At 50% coverage, the analytics tables would have enough data to be useful. Below that threshold, running dbt would produce misleading analytics (missing companies, incomplete signals).

**Why block dbt instead of proceeding with partial data:** Analysts rely on the ANALYTICS tables being comprehensive. Running dbt on 10 out of 50 tickers would make `dim_company` incomplete and `fct_stock_metrics` appear to show missing companies as having no data.

---

## Docker Compose Topology

```mermaid
graph TD
    subgraph "Docker Compose Stack"
        PG["postgres:13<br/>Airflow metadata DB<br/>Port 5432"]
        RD["redis:7.2<br/>Celery broker<br/>Port 6379"]
        
        WS["airflow-webserver<br/>Port 8080<br/>UI dashboard"]
        SC["airflow-scheduler<br/>DAG scheduling<br/>Health: port 8974"]
        WK["airflow-worker<br/>CeleryExecutor<br/>Task execution"]
        TR["airflow-triggerer<br/>Async/deferred tasks"]
        
        INIT["airflow-init<br/>DB migration<br/>Admin user creation"]
        
        FL["flower (optional)<br/>Celery monitoring<br/>Port 5555"]
    end
    
    subgraph "Mounted Volumes"
        V1["scripts/"]
        V2["src/"]
        V3["config/"]
        V4["dbt_finsage/"]
        V5["airflow/dags/"]
        V6["airflow/logs/"]
    end
    
    PG --> WS
    PG --> SC
    PG --> WK
    RD --> WK
    RD --> SC
    
    INIT --> PG
    
    V1 & V2 & V3 & V4 & V5 & V6 --> WK
    V5 --> SC
```

### Container Resource Requirements

Checked by `airflow-init`:
- Minimum 4GB RAM
- Minimum 2 CPUs
- Minimum 10GB disk space

### Environment Variables Passed Through

```
SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, SNOWFLAKE_DATABASE, SNOWFLAKE_WAREHOUSE
NEWSAPI_KEY, ALPHA_VANTAGE_API_KEY, SEC_USER_AGENT
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
BEDROCK_KB_ID, BEDROCK_GUARDRAIL_ID
```

---

## dbt Transformation Pipeline

### Model Dependency Graph

```mermaid
graph LR
    subgraph "RAW (Sources)"
        S1["raw_stock_prices"]
        S2["raw_fundamentals"]
        S3["raw_news"]
        S4["raw_sec_filings"]
        S5["raw_sec_filing_documents"]
    end
    
    subgraph "STAGING (Views)"
        M1["stg_stock_prices<br/>VIEW"]
        M2["stg_fundamentals<br/>VIEW"]
        M3["stg_news<br/>VIEW"]
        M4["stg_sec_filings<br/>VIEW"]
        M5["stg_sec_filing_documents<br/>VIEW"]
    end
    
    subgraph "ANALYTICS (Tables)"
        A1["dim_company<br/>TABLE"]
        A2["dim_date<br/>TABLE"]
        A3["fct_stock_metrics<br/>TABLE"]
        A4["fct_fundamentals_growth<br/>TABLE"]
        A5["fct_news_sentiment_agg<br/>TABLE"]
        A6["fct_sec_financial_summary<br/>TABLE"]
    end
    
    S1 --> M1
    S2 --> M2
    S3 --> M3
    S4 --> M4
    S5 --> M5
    
    M1 --> A1
    M2 --> A1
    M3 --> A1
    M4 --> A1
    
    M1 --> A3
    M2 --> A4
    M3 --> A5
    M4 --> A6
```

### dbt Execution in Airflow

```mermaid
sequenceDiagram
    participant DAG as Airflow DAG
    participant BASH as BashOperator
    participant DBT as dbt CLI
    participant SF as Snowflake

    DAG->>BASH: run_dbt_staging
    BASH->>DBT: dbt run --select staging --project-dir dbt_finsage
    DBT->>SF: CREATE OR REPLACE VIEW stg_stock_prices AS ...
    DBT->>SF: CREATE OR REPLACE VIEW stg_fundamentals AS ...
    DBT->>SF: CREATE OR REPLACE VIEW stg_news AS ...
    DBT->>SF: CREATE OR REPLACE VIEW stg_sec_filings AS ...
    SF-->>DBT: Views created
    DBT-->>BASH: Success
    
    DAG->>BASH: run_dbt_analytics
    BASH->>DBT: dbt run --select analytics --project-dir dbt_finsage
    DBT->>SF: CREATE TABLE analytics.dim_company AS ...
    DBT->>SF: CREATE TABLE analytics.fct_stock_metrics AS ...
    DBT->>SF: CREATE TABLE analytics.fct_fundamentals_growth AS ...
    DBT->>SF: CREATE TABLE analytics.fct_news_sentiment_agg AS ...
    DBT->>SF: CREATE TABLE analytics.fct_sec_financial_summary AS ...
    SF-->>DBT: Tables created
    DBT-->>BASH: Success
```

**Why separate dbt commands (staging then analytics):**
- Staging views must exist before analytics tables reference them
- If staging fails, analytics doesn't run (fail-fast)
- Allows retrying just one layer if needed

### dbt Testing Strategy

| Test Type | Example | Purpose |
|-----------|---------|---------|
| `not_null` | `ticker` in all tables | No missing identifiers |
| `unique` | `(ticker, date)` compound key | No duplicate rows |
| `accepted_values` | `trend_signal IN ('BULLISH', 'BEARISH', 'NEUTRAL')` | Only valid categorical values |
| `relationships` | `fct_stock_metrics.ticker → dim_company.ticker` | Referential integrity |

---

## Full DAG Timeline (Typical Execution)

```
5:00 PM EST — DAG triggered
  │
  ├── 5:00-5:30 PM — Parallel data collection (5 tasks)
  │     ├── fetch_stock_prices   ──── ~15 min (50 tickers, batches of 10)
  │     ├── fetch_fundamentals   ──── ~20 min (API rate limits)
  │     ├── fetch_news           ──── ~25 min (strict NewsAPI limits)
  │     ├── fetch_sec_data       ──── ~10 min (XBRL + filings)
  │     └── fetch_s3_filings     ──── ~5 min
  │
  ├── 5:30 PM — check_loaders_success (quality gate)
  │
  ├── 5:31 PM — run_dbt_staging (~1 min for views)
  │
  ├── 5:32 PM — run_dbt_analytics (~3-5 min for tables with window functions)
  │
  └── 5:37 PM — data_quality_check (~1 min)
  
Total: ~35-40 minutes
```

---

## dbt Project Configuration

```yaml
# dbt_project.yml
name: 'dbt_finsage'
version: '1.0.0'
profile: 'dbt_finsage'   # → ~/.dbt/profiles.yml (Snowflake connection)

models:
  dbt_finsage:
    staging:
      +materialized: view       # Always fresh, zero storage cost
      +schema: staging          # FINSAGE_DB.STAGING
    analytics:
      +materialized: table      # Materialized for performance
      +schema: ANALYTICS        # FINSAGE_DB.ANALYTICS
```

### Custom Schema Macro

```sql
-- macros/generate_schema_name.sql
-- Overrides dbt default to use the schema name directly (no prefix)
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
```

**Why:** By default, dbt prefixes schema names with the target schema (e.g., `PUBLIC_staging`). This macro ensures models deploy to exactly `STAGING` and `ANALYTICS`.

---

## Q&A for This Section

**Q: Why Airflow instead of a simple cron job?**
A: Airflow provides DAG-based dependency management (data collection must complete before dbt), retry logic, logging, a web UI for monitoring, and the quality gate pattern. A cron job can't express "run dbt only if all 5 loaders succeeded with 25+ tickers."

**Q: Why CeleryExecutor instead of LocalExecutor?**
A: CeleryExecutor enables true parallel task execution across workers. The 5 data collection tasks run simultaneously on separate workers. LocalExecutor would run them sequentially.

**Q: Why not use Airflow's SnowflakeOperator?**
A: The data loaders need the full Python API (yfinance, requests, httpx), not just SQL execution. BashOperator/PythonOperator gives full control over the loading logic.

**Q: Why split dbt into staging and analytics instead of running `dbt run` once?**
A: Split execution provides better error isolation. If analytics fails (e.g., a column rename), staging views are still updated and available for ad-hoc queries.

**Q: How do you handle Airflow DAG failures?**
A: 3 automatic retries with 5-minute delays. The quality gate prevents dbt from running on partial data. Failed tasks are visible in the Airflow web UI for manual investigation.

---

*Previous: [06-frontend-architecture.md](./06-frontend-architecture.md) | Next: [08-infrastructure-architecture.md](./08-infrastructure-architecture.md)*
