# FinSage Observability Layer

## Overview

The observability layer gives end-to-end visibility into FinSage's data pipelines, AI model calls, data quality, and system health. It follows a three-pillar approach — **Logs, Metrics, Traces** — built entirely on Snowflake-native primitives so there are no external monitoring services to deploy.

All instrumentation is **non-intrusive**: every tracking call is wrapped in `try/except` so an observability failure never blocks the business pipeline.

### What it answers

| Question | Where to look |
|----------|---------------|
| Did the last data load succeed? | `FCT_PIPELINE_RUNS` |
| How fresh is our RAW data? | `FCT_HEALTH_CHECKS` (DATA_FRESHNESS), dbt source freshness |
| Are quality scores degrading over time? | `FCT_DATA_QUALITY_HISTORY` |
| Which LLM calls are slowest or failing? | `FCT_LLM_CALLS` |
| Which component runs the most Snowflake queries? | Query Attribution (via `QUERY_TAG`) |
| Is the system healthy right now? | `FCT_HEALTH_CHECKS` (latest per component) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                             │
│  Data Loaders ─── CAVM Pipeline ─── Airflow DAG ─── FastAPI    │
└──────┬──────────────┬───────────────────┬──────────────┬────────┘
       │              │                   │              │
       ▼              ▼                   ▼              ▼
  PipelineTracker  PipelineTracker   Quality Snapshot  Middleware
  (per-stage)      + LLMCallTracker  (per-table)      (latency)
       │              │                   │              │
       ▼              ▼                   ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Snowflake ANALYTICS Schema                      │
│                                                                  │
│  FCT_PIPELINE_RUNS  FCT_LLM_CALLS  FCT_DATA_QUALITY_HISTORY    │
│  FCT_HEALTH_CHECKS  (+ QUERY_TAG on every session)              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Router: /api/observability/*                            │
│  React Dashboard: /observability (5 tabs)                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Files Modified and Created

### New files

| File | Purpose |
|------|---------|
| `sql/09_create_observability_tables.sql` | DDL for 4 tables, 1 stored procedure, 1 scheduled task |
| `src/utils/observability.py` | Core Python module: `RunContext`, `StructuredLogger`, `PipelineTracker`, `LLMCallTracker`, `snapshot_data_quality()` |
| `dbt_finsage/models/exposures.yml` | dbt exposures documenting 5 downstream consumers |
| `frontend-react/api/routers/observability.py` | FastAPI router with 7 endpoints |
| `frontend-react/app/observability/page.tsx` | React dashboard page with 5 tabs |

### Modified files

| File | Change |
|------|--------|
| `src/utils/snowflake_client.py` | Added `component` parameter and `QUERY_TAG` JSON tagging |
| `agents/orchestrator.py` | Instrumented CAVM pipeline with `RunContext` + `PipelineTracker` (4 stages) |
| `src/data_loaders/base_loader.py` | Non-intrusive `PipelineTracker` wrapping the `load()` method |
| `dbt_finsage/models/staging/schema.yml` | Added source freshness checks with per-table thresholds |
| `frontend-react/api/main.py` | Added `RequestMetricsMiddleware` and registered observability router |
| `frontend-react/lib/api.ts` | Added 7 API client functions for observability endpoints |
| `frontend-react/components/AppShell.tsx` | Added "Observability" navigation item |
| `airflow/dags/data_collection_dag.py` | Enabled `email_on_failure`, `dagrun_timeout`, component tagging, quality snapshot task |

---

## Snowflake Tables

All tables live in `FINSAGE_DB.ANALYTICS`.

### FCT_PIPELINE_RUNS

Tracks every pipeline stage execution (data loaders, CAVM stages, dbt runs).

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | VARCHAR | Unique identifier per pipeline execution (shared across all stages in a run) |
| `pipeline_type` | VARCHAR | `CAVM`, `DATA_LOAD`, or `DBT` |
| `ticker` | VARCHAR | Stock ticker (NULL for non-ticker pipelines) |
| `stage` | VARCHAR | Stage name: `chart_generation`, `validation`, `analysis`, `report_generation`, `StockDataLoader`, etc. |
| `status` | VARCHAR | `STARTED`, `SUCCESS`, or `FAILED` |
| `started_at` | TIMESTAMP_NTZ | When the stage began |
| `ended_at` | TIMESTAMP_NTZ | When the stage finished |
| `duration_seconds` | FLOAT | Wall-clock duration |
| `rows_affected` | INTEGER | Row count produced by this stage |
| `error_message` | VARCHAR | Error text (truncated to 500 chars) |
| `metadata` | VARIANT | Flexible JSON for stage-specific details (e.g. `{"quality_score": 87.5}`) |

### FCT_DATA_QUALITY_HISTORY

Daily snapshots of quality scores aggregated per RAW table and ticker.

| Column | Type | Description |
|--------|------|-------------|
| `snapshot_date` | DATE | Date of the snapshot |
| `table_name` | VARCHAR | Fully-qualified RAW table name |
| `ticker` | VARCHAR | Stock ticker |
| `avg_quality_score` | FLOAT | Average `data_quality_score` across rows |
| `min_quality_score` | FLOAT | Minimum score |
| `max_quality_score` | FLOAT | Maximum score |
| `row_count` | INTEGER | Total rows for this table+ticker |
| `null_pct_critical` | FLOAT | Percentage of rows with NULL in the critical column |
| `freshness_hours` | FLOAT | Hours since the most recent `ingested_at` |

### FCT_LLM_CALLS

Tracks every Cortex and Bedrock LLM/VLM invocation.

| Column | Type | Description |
|--------|------|-------------|
| `call_id` | VARCHAR | Unique call identifier |
| `run_id` | VARCHAR | Links to the parent pipeline run |
| `model_name` | VARCHAR | `claude-sonnet-4-6`, `mistral-large`, etc. |
| `provider` | VARCHAR | `CORTEX` or `BEDROCK` |
| `call_type` | VARCHAR | `CHART_CRITIQUE`, `CHART_REFINE`, `ANALYSIS`, `SUMMARIZE`, `CHAT`, `VLM_VALIDATE` |
| `ticker` | VARCHAR | Stock ticker |
| `prompt_tokens` | INTEGER | Input token count |
| `completion_tokens` | INTEGER | Output token count |
| `latency_ms` | INTEGER | Round-trip latency in milliseconds |
| `status` | VARCHAR | `SUCCESS`, `FAILED`, or `TIMEOUT` |

### FCT_HEALTH_CHECKS

Results from automated system health checks (written by the stored procedure).

| Column | Type | Description |
|--------|------|-------------|
| `check_id` | VARCHAR | Unique check identifier |
| `component` | VARCHAR | `SNOWFLAKE`, `DATA_FRESHNESS`, `ANALYTICS_TABLES`, `PIPELINE_SUCCESS_RATE` |
| `status` | VARCHAR | `HEALTHY`, `DEGRADED`, or `DOWN` |
| `latency_ms` | INTEGER | Check latency |
| `details` | VARCHAR | Human-readable status message |
| `checked_at` | TIMESTAMP_NTZ | When the check ran |

---

## Stored Procedure and Scheduled Task

### SP_RUN_HEALTH_CHECKS

A SQL stored procedure that performs 4 checks in a single call:

1. **SNOWFLAKE** — Connectivity test (if the procedure runs, Snowflake is up)
2. **DATA_FRESHNESS** — Checks `MAX(ingested_at)` across all RAW tables; DEGRADED if any source is >48 hours old
3. **ANALYTICS_TABLES** — Checks row counts in the 4 core analytics tables; DOWN if any table has 0 rows
4. **PIPELINE_SUCCESS_RATE** — Counts SUCCESS/FAILED stages in the last 24 hours; DEGRADED if >25% failure rate or no stages at all

```sql
USE WAREHOUSE FINSAGE_WH;
CALL FINSAGE_DB.ANALYTICS.SP_RUN_HEALTH_CHECKS();
```

### TASK_HEALTH_CHECKS

A Snowflake Task that runs `SP_RUN_HEALTH_CHECKS()` every 60 minutes automatically.

```sql
-- Check task status
SHOW TASKS IN SCHEMA FINSAGE_DB.ANALYTICS;

-- See recent executions
SELECT *
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'TASK_HEALTH_CHECKS'))
ORDER BY SCHEDULED_TIME DESC
LIMIT 5;

-- Pause the task
ALTER TASK FINSAGE_DB.ANALYTICS.TASK_HEALTH_CHECKS SUSPEND;

-- Resume the task
ALTER TASK FINSAGE_DB.ANALYTICS.TASK_HEALTH_CHECKS RESUME;
```

---

## Python Module: `src/utils/observability.py`

### RunContext

A context object that carries `run_id`, `pipeline_type`, and `ticker` across all components in a single pipeline execution.

```python
from src.utils.observability import RunContext

ctx = RunContext(pipeline_type="CAVM", ticker="AAPL")
# ctx.run_id  -> auto-generated 12-char hex string
# ctx.ticker  -> "AAPL"
```

### PipelineTracker

Records stage start/end to `FCT_PIPELINE_RUNS`.

```python
from src.utils.observability import RunContext, PipelineTracker

ctx = RunContext(pipeline_type="DATA_LOAD", ticker="MSFT")
tracker = PipelineTracker(snowpark_session, ctx)

tracker.start_stage("fetch_data")
# ... do work ...
duration = tracker.end_stage("fetch_data", status="SUCCESS", rows_affected=500)
print(f"Took {duration}s")
```

On failure:

```python
try:
    tracker.start_stage("transform")
    # ... work ...
    tracker.end_stage("transform", status="SUCCESS")
except Exception as e:
    tracker.end_stage("transform", status="FAILED", error_message=str(e)[:500])
```

### LLMCallTracker

Records individual LLM/VLM calls to `FCT_LLM_CALLS`.

```python
from src.utils.observability import RunContext, LLMCallTracker
import time

ctx = RunContext(pipeline_type="CAVM", ticker="AAPL")
llm_tracker = LLMCallTracker(snowpark_session, ctx)

t0 = time.time()
# ... call the model ...
latency_ms = round((time.time() - t0) * 1000)

llm_tracker.record_call(
    model_name="claude-sonnet-4-6",
    provider="CORTEX",
    call_type="CHART_CRITIQUE",
    latency_ms=latency_ms,
    status="SUCCESS",
    prompt_tokens=1200,
    completion_tokens=350,
)
```

### StructuredLogger

Emits JSON-structured log entries with run context for grep-friendly log files.

```python
from src.utils.observability import RunContext, StructuredLogger

ctx = RunContext(pipeline_type="CAVM", ticker="AAPL")
logger = StructuredLogger("chart_agent", "chart_agent.log", ctx=ctx)

logger.info("Generating charts", chart_count=6)
logger.error("Chart validation failed", chart_name="price_sma")
```

Log output (in `observability.log`):
```json
{"ts": "2026-04-17T10:30:00+00:00", "level": "INFO", "component": "chart_agent", "message": "Generating charts", "run_id": "a1b2c3d4e5f6", "pipeline_type": "CAVM", "ticker": "AAPL", "chart_count": 6}
```

### snapshot_data_quality()

Aggregates current quality scores from all RAW tables into `FCT_DATA_QUALITY_HISTORY`.

```python
from src.utils.observability import snapshot_data_quality

rows = snapshot_data_quality(snowpark_session)
print(f"Snapshotted {rows} table-ticker groups")
```

---

## QUERY_TAG Attribution

Every `SnowflakeClient` instance tags its session with a JSON `QUERY_TAG`:

```json
{"app": "finsage", "component": "airflow_stock_loader"}
```

The CAVM pipeline also includes `run_id`:

```json
{"app": "finsage", "component": "cavm_pipeline", "run_id": "a1b2c3d4e5f6"}
```

This allows attribution queries against `INFORMATION_SCHEMA.QUERY_HISTORY`:

```sql
SELECT
    TRY_PARSE_JSON(QUERY_TAG):component::VARCHAR AS component,
    COUNT(*) AS query_count,
    ROUND(SUM(TOTAL_ELAPSED_TIME) / 1000.0, 1) AS total_elapsed_sec
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATEADD('HOUR', -24, CURRENT_TIMESTAMP()),
    CURRENT_TIMESTAMP()
))
WHERE TRY_PARSE_JSON(QUERY_TAG):app = 'finsage'
GROUP BY component
ORDER BY query_count DESC;
```

To pass a custom component name when creating a client:

```python
from src.utils.snowflake_client import SnowflakeClient

client = SnowflakeClient(component="my_custom_loader")
```

---

## dbt Source Freshness

The `dbt_finsage/models/staging/schema.yml` file defines freshness thresholds for all RAW source tables using `ingested_at` as the loaded-at field.

| Source Table | Warn After | Error After |
|-------------|-----------|------------|
| `raw_stock_prices` | 24 hours | 48 hours |
| `raw_news` | 24 hours | 48 hours |
| `raw_fundamentals` | 168 hours (7 days) | 336 hours (14 days) |
| `raw_sec_filings` | 168 hours (7 days) | 720 hours (30 days) |
| `raw_sec_filing_documents` | 168 hours (7 days) | 720 hours (30 days) |

Run freshness checks:

```bash
cd dbt_finsage
dbt source freshness
```

---

## dbt Exposures

The `dbt_finsage/models/exposures.yml` file documents all downstream consumers of the analytics models:

| Exposure | Type | Models Consumed |
|----------|------|-----------------|
| `react_dashboard` | application | All 5 analytics models |
| `cavm_report_pipeline` | ml | All 5 analytics models |
| `streamlit_analytics_explorer` | application | 4 analytics models |
| `ask_finsage_chat` | application | `fct_stock_metrics`, `dim_company`, `fct_fundamentals_growth` |
| `airflow_data_quality_gate` | application | All 5 analytics models |

These exposures enable dbt to show lineage from source tables all the way through to the applications that consume them.

---

## FastAPI Middleware

`frontend-react/api/main.py` includes `RequestMetricsMiddleware` that logs every API request:

- Method, path, status code, and latency in milliseconds
- Sets `X-Response-Time-Ms` response header for client-side visibility

---

## Airflow Integration

The `airflow/dags/data_collection_dag.py` includes:

- `email_on_failure: True` on all tasks (email address from `AIRFLOW_ALERT_EMAIL` env var)
- `dagrun_timeout=timedelta(hours=4)` to prevent hung runs
- Component-tagged `SnowflakeClient` calls (e.g., `component="airflow_stock_loader"`)
- `task_quality_snapshot` task that calls `snapshot_data_quality()` after each data collection run

---

## Dashboard

The observability dashboard is accessible at `http://localhost:3000/observability` and has 5 tabs:

### Health tab
Shows the latest health check result per component (SNOWFLAKE, DATA_FRESHNESS, ANALYTICS_TABLES, PIPELINE_SUCCESS_RATE) with status chips (HEALTHY/DEGRADED/DOWN) and detail messages.

### Pipeline Runs tab
Displays recent pipeline stage executions with run_id, pipeline type, ticker, stage, status, duration, and timestamp. Includes a bar chart of stages by pipeline type over the last 7 days.

### Data Quality tab
Shows quality score trends across RAW tables as a line chart (one line per table) and a detail table with avg/min/max scores, row counts, and freshness hours.

### LLM Calls tab
Lists individual model invocations with model name, provider, call type, latency, token counts, and status. Includes a horizontal bar chart summarizing calls by model over the last 7 days.

### Query Attribution tab
Shows Snowflake query counts and total elapsed time broken down by FinSage component, derived from `QUERY_TAG` metadata in `INFORMATION_SCHEMA.QUERY_HISTORY`.

### API endpoints

All endpoints are served at `/api/observability/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health-checks` | GET | Latest health check per component |
| `/pipeline-runs?limit=50` | GET | Recent pipeline stage executions |
| `/pipeline-runs/summary` | GET | Success/failure counts by pipeline type (7 days) |
| `/data-quality?days=7` | GET | Quality score trends per table per day |
| `/llm-calls?limit=50` | GET | Recent LLM/VLM calls |
| `/llm-calls/summary` | GET | Call count and latency by model (7 days) |
| `/query-attribution` | GET | Query count by component (24 hours) |

---

## How to Test

### 1. Verify Snowflake tables exist

```sql
USE WAREHOUSE FINSAGE_WH;
CALL FINSAGE_DB.ANALYTICS.SP_RUN_HEALTH_CHECKS();
SELECT * FROM FINSAGE_DB.ANALYTICS.FCT_HEALTH_CHECKS ORDER BY CHECKED_AT DESC LIMIT 10;
```

### 2. Test pipeline tracking via a data load

```bash
source venv/bin/activate
python -c "
from src.data_loaders.stock_loader import StockDataLoader
StockDataLoader().load('AAPL')
"
```

```sql
SELECT run_id, stage, status, duration_seconds
FROM FINSAGE_DB.ANALYTICS.FCT_PIPELINE_RUNS
ORDER BY started_at DESC LIMIT 10;
```

### 3. Test CAVM pipeline tracking

```bash
python agents/orchestrator.py --ticker AAPL --debug
```

```sql
-- Should show chart_generation, validation, analysis, report_generation stages
SELECT run_id, stage, status, duration_seconds
FROM FINSAGE_DB.ANALYTICS.FCT_PIPELINE_RUNS
WHERE pipeline_type = 'CAVM'
ORDER BY started_at DESC LIMIT 10;
```

### 4. Test data quality snapshots

```bash
python -c "
from src.utils.snowflake_client import SnowflakeClient
from src.utils.observability import snapshot_data_quality
count = snapshot_data_quality(SnowflakeClient('test').session)
print(f'Snapshotted {count} table groups')
"
```

```sql
SELECT * FROM FINSAGE_DB.ANALYTICS.FCT_DATA_QUALITY_HISTORY
ORDER BY snapshot_date DESC LIMIT 20;
```

### 5. Test QUERY_TAG attribution

```sql
SELECT
    TRY_PARSE_JSON(QUERY_TAG):component::VARCHAR AS component,
    COUNT(*) AS query_count
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATEADD('HOUR', -1, CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP()
))
WHERE TRY_PARSE_JSON(QUERY_TAG):app = 'finsage'
GROUP BY component
ORDER BY query_count DESC;
```

### 6. Test dbt source freshness

```bash
cd dbt_finsage
dbt source freshness
```

### 7. Test the dashboard

```bash
# Terminal 1
cd frontend-react/api && uvicorn main:app --reload --port 8000

# Terminal 2
cd frontend-react && npm run dev
```

Open `http://localhost:3000/observability` and verify all 5 tabs render.

Test API endpoints directly:

```bash
curl http://localhost:8000/api/observability/health-checks | python -m json.tool
curl http://localhost:8000/api/observability/pipeline-runs | python -m json.tool
curl http://localhost:8000/api/observability/data-quality | python -m json.tool
curl http://localhost:8000/api/observability/llm-calls | python -m json.tool
curl http://localhost:8000/api/observability/query-attribution | python -m json.tool
```

### 8. Verify the scheduled task

```sql
SHOW TASKS IN SCHEMA FINSAGE_DB.ANALYTICS;

SELECT *
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'TASK_HEALTH_CHECKS'))
ORDER BY SCHEDULED_TIME DESC LIMIT 5;
```
