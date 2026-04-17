"""Observability API — exposes health, pipeline, quality, and LLM metrics."""

from fastapi import APIRouter, Depends
from snowflake.snowpark import Session

from deps import get_snowpark_session

router = APIRouter()


@router.get("/health-checks")
def get_health_checks(session: Session = Depends(get_snowpark_session)):
    """Latest health check per component."""
    rows = session.sql("""
        SELECT component, status, details, latency_ms, checked_at
        FROM ANALYTICS.FCT_HEALTH_CHECKS
        QUALIFY ROW_NUMBER() OVER (PARTITION BY component ORDER BY checked_at DESC) = 1
        ORDER BY component
    """).collect()
    return [row.as_dict() for row in rows]


@router.get("/pipeline-runs")
def get_pipeline_runs(limit: int = 50, session: Session = Depends(get_snowpark_session)):
    """Recent pipeline stage executions."""
    rows = session.sql(f"""
        SELECT run_id, pipeline_type, ticker, stage, status,
               started_at, ended_at, duration_seconds, rows_affected, error_message
        FROM ANALYTICS.FCT_PIPELINE_RUNS
        ORDER BY started_at DESC
        LIMIT {min(limit, 200)}
    """).collect()
    return [row.as_dict() for row in rows]


@router.get("/pipeline-runs/summary")
def get_pipeline_summary(session: Session = Depends(get_snowpark_session)):
    """Pipeline success/failure counts by type over the last 7 days."""
    rows = session.sql("""
        SELECT
            pipeline_type,
            status,
            COUNT(*) AS stage_count,
            ROUND(AVG(duration_seconds), 1) AS avg_duration_s
        FROM ANALYTICS.FCT_PIPELINE_RUNS
        WHERE started_at >= DATEADD(DAY, -7, CURRENT_TIMESTAMP())
          AND status IN ('SUCCESS', 'FAILED')
        GROUP BY pipeline_type, status
        ORDER BY pipeline_type, status
    """).collect()
    return [row.as_dict() for row in rows]


@router.get("/data-quality")
def get_data_quality(days: int = 7, session: Session = Depends(get_snowpark_session)):
    """Data quality trend — aggregated per table per day."""
    rows = session.sql(f"""
        SELECT snapshot_date, table_name,
               ROUND(AVG(avg_quality_score), 1) AS avg_score,
               SUM(row_count) AS total_rows,
               ROUND(AVG(freshness_hours), 1) AS avg_freshness_hours
        FROM ANALYTICS.FCT_DATA_QUALITY_HISTORY
        WHERE snapshot_date >= DATEADD(DAY, -{min(days, 90)}, CURRENT_DATE())
        GROUP BY snapshot_date, table_name
        ORDER BY snapshot_date DESC, table_name
    """).collect()
    return [row.as_dict() for row in rows]


@router.get("/llm-calls")
def get_llm_calls(limit: int = 50, session: Session = Depends(get_snowpark_session)):
    """Recent LLM/VLM calls with latency and token usage."""
    rows = session.sql(f"""
        SELECT call_id, run_id, model_name, provider, call_type, ticker,
               prompt_tokens, completion_tokens, latency_ms, status, called_at
        FROM ANALYTICS.FCT_LLM_CALLS
        ORDER BY called_at DESC
        LIMIT {min(limit, 200)}
    """).collect()
    return [row.as_dict() for row in rows]


@router.get("/llm-calls/summary")
def get_llm_summary(session: Session = Depends(get_snowpark_session)):
    """LLM cost/latency summary by model over the last 7 days."""
    rows = session.sql("""
        SELECT
            model_name,
            provider,
            COUNT(*) AS call_count,
            ROUND(AVG(latency_ms)) AS avg_latency_ms,
            ROUND(AVG(COALESCE(prompt_tokens, 0) + COALESCE(completion_tokens, 0))) AS avg_total_tokens,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failures
        FROM ANALYTICS.FCT_LLM_CALLS
        WHERE called_at >= DATEADD(DAY, -7, CURRENT_TIMESTAMP())
        GROUP BY model_name, provider
        ORDER BY call_count DESC
    """).collect()
    return [row.as_dict() for row in rows]


@router.get("/query-attribution")
def get_query_attribution(session: Session = Depends(get_snowpark_session)):
    """Query count and credits by FinSage component from QUERY_HISTORY (last 24h)."""
    rows = session.sql("""
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
        ORDER BY query_count DESC
    """).collect()
    return [row.as_dict() for row in rows]
