-- FinSage Observability Layer — Core Tables
-- Tracks pipeline execution, data quality trends, LLM call performance,
-- and automated health checks.
-- Run this migration after 08_create_model_benchmarks.sql.

-- ═══════════════════════════════════════════════════════════════
-- 1. Pipeline Run History
-- ═══════════════════════════════════════════════════════════════
-- One row per pipeline stage execution (CAVM stages, data loaders, dbt runs).
-- Enables: success/failure tracking, duration trending, error analysis.

CREATE TABLE IF NOT EXISTS FINSAGE_DB.ANALYTICS.FCT_PIPELINE_RUNS (
    run_id            VARCHAR       NOT NULL,
    pipeline_type     VARCHAR       NOT NULL,   -- CAVM, DATA_LOAD, DBT
    ticker            VARCHAR,                  -- NULL for non-ticker pipelines (e.g. dbt)
    stage             VARCHAR       NOT NULL,   -- chart_generation, validation, analysis, report, stock_loader, etc.
    status            VARCHAR       NOT NULL,   -- STARTED, SUCCESS, FAILED
    started_at        TIMESTAMP_NTZ NOT NULL,
    ended_at          TIMESTAMP_NTZ,
    duration_seconds  FLOAT,
    rows_affected     INTEGER,
    error_message     VARCHAR,
    metadata          VARIANT,                  -- Flexible JSON for stage-specific details
    created_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ═══════════════════════════════════════════════════════════════
-- 2. Data Quality History
-- ═══════════════════════════════════════════════════════════════
-- Daily snapshot of quality scores per source table and ticker.
-- Enables: quality trend dashboards, degradation alerts, SLA monitoring.

CREATE TABLE IF NOT EXISTS FINSAGE_DB.ANALYTICS.FCT_DATA_QUALITY_HISTORY (
    snapshot_date         DATE          NOT NULL,
    table_name            VARCHAR       NOT NULL,
    ticker                VARCHAR,
    avg_quality_score     FLOAT,
    min_quality_score     FLOAT,
    max_quality_score     FLOAT,
    row_count             INTEGER,
    null_pct_critical     FLOAT,        -- % of rows with NULL in critical columns
    freshness_hours       FLOAT,        -- Hours since most recent ingested_at
    created_at            TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ═══════════════════════════════════════════════════════════════
-- 3. LLM / VLM Call Tracking
-- ═══════════════════════════════════════════════════════════════
-- Tracks every Cortex and Bedrock LLM call for cost/latency analysis.
-- Extends the pattern from FCT_MODEL_BENCHMARKS to cover all LLM usage.

CREATE TABLE IF NOT EXISTS FINSAGE_DB.ANALYTICS.FCT_LLM_CALLS (
    call_id           VARCHAR       NOT NULL,
    run_id            VARCHAR       NOT NULL,
    model_name        VARCHAR       NOT NULL,   -- claude-sonnet-4-6, mistral-large, etc.
    provider          VARCHAR       NOT NULL,   -- CORTEX, BEDROCK
    call_type         VARCHAR       NOT NULL,   -- CHART_CRITIQUE, CHART_REFINE, ANALYSIS, SUMMARIZE, CHAT, VLM_VALIDATE
    ticker            VARCHAR,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    latency_ms        INTEGER,
    status            VARCHAR       NOT NULL,   -- SUCCESS, FAILED, TIMEOUT
    error_message     VARCHAR,
    called_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ═══════════════════════════════════════════════════════════════
-- 4. Health Check History
-- ═══════════════════════════════════════════════════════════════
-- Scheduled health check results for all system components.
-- Enables: uptime tracking, degradation detection, alerting.

CREATE TABLE IF NOT EXISTS FINSAGE_DB.ANALYTICS.FCT_HEALTH_CHECKS (
    check_id          VARCHAR       NOT NULL,
    component         VARCHAR       NOT NULL,   -- SNOWFLAKE, BEDROCK_KB, GUARDRAILS, S3, CORTEX_LLM, FASTAPI
    status            VARCHAR       NOT NULL,   -- HEALTHY, DEGRADED, DOWN
    latency_ms        INTEGER,
    details           VARCHAR,
    checked_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);


-- ═══════════════════════════════════════════════════════════════
-- 5. Health Check Stored Procedure
-- ═══════════════════════════════════════════════════════════════
-- Checks: Snowflake connectivity, RAW freshness, analytics row counts,
-- pipeline success rate in last 24h.

CREATE OR REPLACE PROCEDURE FINSAGE_DB.ANALYTICS.SP_RUN_HEALTH_CHECKS()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    INSERT INTO ANALYTICS.FCT_HEALTH_CHECKS (check_id, component, status, latency_ms, details)
    SELECT UUID_STRING(), 'SNOWFLAKE', 'HEALTHY', 0, 'Procedure executed successfully';

    INSERT INTO ANALYTICS.FCT_HEALTH_CHECKS (check_id, component, status, latency_ms, details)
    SELECT
        UUID_STRING(),
        'DATA_FRESHNESS',
        CASE WHEN MAX(freshness_hrs) > 48 THEN 'DEGRADED' ELSE 'HEALTHY' END,
        0,
        'Oldest source: ' || ROUND(MAX(freshness_hrs), 1) || 'h'
    FROM (
        SELECT TIMESTAMPDIFF(HOUR, MAX(INGESTED_AT), CURRENT_TIMESTAMP()) AS freshness_hrs FROM RAW.RAW_STOCK_PRICES
        UNION ALL
        SELECT TIMESTAMPDIFF(HOUR, MAX(INGESTED_AT), CURRENT_TIMESTAMP()) FROM RAW.RAW_FUNDAMENTALS
        UNION ALL
        SELECT TIMESTAMPDIFF(HOUR, MAX(INGESTED_AT), CURRENT_TIMESTAMP()) FROM RAW.RAW_NEWS
        UNION ALL
        SELECT TIMESTAMPDIFF(HOUR, MAX(INGESTED_AT), CURRENT_TIMESTAMP()) FROM RAW.RAW_SEC_FILINGS
    );

    INSERT INTO ANALYTICS.FCT_HEALTH_CHECKS (check_id, component, status, latency_ms, details)
    SELECT
        UUID_STRING(),
        'ANALYTICS_TABLES',
        CASE WHEN MIN(cnt) = 0 THEN 'DOWN' ELSE 'HEALTHY' END,
        0,
        'Min row count across analytics tables: ' || MIN(cnt)
    FROM (
        SELECT COUNT(*) AS cnt FROM ANALYTICS.FCT_STOCK_METRICS
        UNION ALL
        SELECT COUNT(*) FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
        UNION ALL
        SELECT COUNT(*) FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG
        UNION ALL
        SELECT COUNT(*) FROM ANALYTICS.DIM_COMPANY
    );

    INSERT INTO ANALYTICS.FCT_HEALTH_CHECKS (check_id, component, status, latency_ms, details)
    SELECT
        UUID_STRING(),
        'PIPELINE_SUCCESS_RATE',
        CASE
            WHEN total_stages = 0 THEN 'DEGRADED'
            WHEN fail_pct > 25 THEN 'DEGRADED'
            ELSE 'HEALTHY'
        END,
        0,
        total_stages || ' stages in 24h, ' || ROUND(fail_pct, 1) || '% failed'
    FROM (
        SELECT
            COUNT(*) AS total_stages,
            COALESCE(SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 0) AS fail_pct
        FROM ANALYTICS.FCT_PIPELINE_RUNS
        WHERE started_at >= DATEADD(HOUR, -24, CURRENT_TIMESTAMP())
          AND status IN ('SUCCESS', 'FAILED')
    );

    RETURN 'Health checks completed';
END;
$$;


-- ═══════════════════════════════════════════════════════════════
-- 6. Scheduled Task — runs health checks hourly
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE TASK FINSAGE_DB.ANALYTICS.TASK_HEALTH_CHECKS
    WAREHOUSE = FINSAGE_WH
    SCHEDULE = '60 MINUTE'
    COMMENT = 'Hourly health checks — writes to FCT_HEALTH_CHECKS'
AS
    CALL ANALYTICS.SP_RUN_HEALTH_CHECKS();

ALTER TASK FINSAGE_DB.ANALYTICS.TASK_HEALTH_CHECKS RESUME;
