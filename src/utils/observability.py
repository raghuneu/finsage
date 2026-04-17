"""
FinSage Observability Module
=============================
Centralized run-context management, structured logging, and pipeline/LLM
call tracking backed by Snowflake observability tables.

Tables written to:
    - ANALYTICS.FCT_PIPELINE_RUNS
    - ANALYTICS.FCT_LLM_CALLS
    - ANALYTICS.FCT_DATA_QUALITY_HISTORY
    - ANALYTICS.FCT_HEALTH_CHECKS

Usage:
    from src.utils.observability import RunContext, PipelineTracker

    ctx = RunContext(pipeline_type="CAVM", ticker="AAPL")
    tracker = PipelineTracker(snowpark_session, ctx)

    tracker.start_stage("chart_generation")
    # ... do work ...
    tracker.end_stage("chart_generation", status="SUCCESS", rows_affected=6)
"""

import json
import uuid
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Any

from .logger import setup_logger

_logger = setup_logger(__name__, "observability.log")


# ──────────────────────────────────────────────────────────────
# Run context — propagated across all components in a pipeline run
# ──────────────────────────────────────────────────────────────

class RunContext:
    """Immutable context for a single pipeline execution."""

    def __init__(self, pipeline_type: str, ticker: Optional[str] = None,
                 run_id: Optional[str] = None):
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.pipeline_type = pipeline_type
        self.ticker = ticker
        self.started_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "pipeline_type": self.pipeline_type,
            "ticker": self.ticker,
        }

    def __repr__(self) -> str:
        return f"RunContext(run_id={self.run_id}, type={self.pipeline_type}, ticker={self.ticker})"


# ──────────────────────────────────────────────────────────────
# Structured log helper
# ──────────────────────────────────────────────────────────────

class StructuredLogger:
    """Wraps a standard logger and emits JSON-structured entries to the file
    handler while keeping human-readable colorlog output on the console."""

    def __init__(self, name: str, log_file: str, ctx: Optional[RunContext] = None):
        self.logger = setup_logger(name, log_file)
        self.ctx = ctx
        self.component = name

    def _build_entry(self, level: str, message: str, **extra: Any) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "component": self.component,
            "message": message,
        }
        if self.ctx:
            entry["run_id"] = self.ctx.run_id
            entry["pipeline_type"] = self.ctx.pipeline_type
            entry["ticker"] = self.ctx.ticker
        entry.update(extra)
        return json.dumps(entry, default=str)

    def info(self, message: str, **extra: Any) -> None:
        self.logger.info(message)
        _logger.debug(self._build_entry("INFO", message, **extra))

    def warning(self, message: str, **extra: Any) -> None:
        self.logger.warning(message)
        _logger.debug(self._build_entry("WARNING", message, **extra))

    def error(self, message: str, **extra: Any) -> None:
        self.logger.error(message)
        _logger.debug(self._build_entry("ERROR", message, **extra))


# ──────────────────────────────────────────────────────────────
# Pipeline stage tracker — writes to FCT_PIPELINE_RUNS
# ──────────────────────────────────────────────────────────────

class PipelineTracker:
    """Records pipeline stage executions to Snowflake."""

    def __init__(self, session, ctx: RunContext):
        self.session = session
        self.ctx = ctx
        self._stage_starts: dict[str, float] = {}

    def start_stage(self, stage: str) -> None:
        """Record the start of a pipeline stage."""
        self._stage_starts[stage] = time.time()
        self._insert_run(stage, "STARTED")
        _logger.info("Stage started: %s (run_id=%s)", stage, self.ctx.run_id)

    def end_stage(self, stage: str, status: str = "SUCCESS",
                  rows_affected: Optional[int] = None,
                  error_message: Optional[str] = None,
                  metadata: Optional[dict] = None) -> float:
        """Record the completion of a pipeline stage. Returns duration in seconds."""
        start = self._stage_starts.pop(stage, time.time())
        duration = round(time.time() - start, 2)
        self._insert_run(
            stage, status,
            duration_seconds=duration,
            rows_affected=rows_affected,
            error_message=error_message,
            metadata=metadata,
        )
        _logger.info(
            "Stage ended: %s status=%s duration=%.1fs (run_id=%s)",
            stage, status, duration, self.ctx.run_id,
        )
        return duration

    def _insert_run(self, stage: str, status: str, *,
                    duration_seconds: Optional[float] = None,
                    rows_affected: Optional[int] = None,
                    error_message: Optional[str] = None,
                    metadata: Optional[dict] = None) -> None:
        ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ended = f"'{ts_now}'" if status in ("SUCCESS", "FAILED") else "NULL"
        dur = str(duration_seconds) if duration_seconds is not None else "NULL"
        rows = str(rows_affected) if rows_affected is not None else "NULL"
        err = f"$${error_message}$$" if error_message else "NULL"
        meta = f"PARSE_JSON($${json.dumps(metadata, default=str)}$$)" if metadata else "NULL"

        sql = f"""
            INSERT INTO ANALYTICS.FCT_PIPELINE_RUNS
            (run_id, pipeline_type, ticker, stage, status, started_at, ended_at,
             duration_seconds, rows_affected, error_message, metadata)
            VALUES (
                '{self.ctx.run_id}', '{self.ctx.pipeline_type}',
                {f"'{self.ctx.ticker}'" if self.ctx.ticker else "NULL"},
                '{stage}', '{status}', '{ts_now}', {ended},
                {dur}, {rows}, {err}, {meta}
            )
        """
        try:
            self.session.sql(sql).collect()
        except Exception as exc:
            _logger.warning("Failed to write pipeline run: %s", exc)


# ──────────────────────────────────────────────────────────────
# LLM call tracker — writes to FCT_LLM_CALLS
# ──────────────────────────────────────────────────────────────

class LLMCallTracker:
    """Records LLM/VLM call metrics to Snowflake."""

    def __init__(self, session, ctx: RunContext):
        self.session = session
        self.ctx = ctx

    def record_call(self, model_name: str, provider: str, call_type: str,
                    latency_ms: int, status: str = "SUCCESS",
                    prompt_tokens: Optional[int] = None,
                    completion_tokens: Optional[int] = None,
                    error_message: Optional[str] = None) -> None:
        call_id = uuid.uuid4().hex[:12]
        p_tok = str(prompt_tokens) if prompt_tokens is not None else "NULL"
        c_tok = str(completion_tokens) if completion_tokens is not None else "NULL"
        err = f"$${error_message}$$" if error_message else "NULL"

        sql = f"""
            INSERT INTO ANALYTICS.FCT_LLM_CALLS
            (call_id, run_id, model_name, provider, call_type, ticker,
             prompt_tokens, completion_tokens, latency_ms, status, error_message)
            VALUES (
                '{call_id}', '{self.ctx.run_id}', '{model_name}', '{provider}',
                '{call_type}', {f"'{self.ctx.ticker}'" if self.ctx.ticker else "NULL"},
                {p_tok}, {c_tok}, {latency_ms}, '{status}', {err}
            )
        """
        try:
            self.session.sql(sql).collect()
        except Exception as exc:
            _logger.warning("Failed to write LLM call: %s", exc)


# ──────────────────────────────────────────────────────────────
# Data quality snapshot — writes to FCT_DATA_QUALITY_HISTORY
# ──────────────────────────────────────────────────────────────

def snapshot_data_quality(session) -> int:
    """Aggregate current quality scores from RAW tables into FCT_DATA_QUALITY_HISTORY.

    Returns the number of rows inserted.
    """
    raw_tables = {
        "RAW.RAW_STOCK_PRICES": {"critical_col": "CLOSE", "date_col": "INGESTED_AT"},
        "RAW.RAW_FUNDAMENTALS": {"critical_col": "REVENUE", "date_col": "INGESTED_AT"},
        "RAW.RAW_NEWS": {"critical_col": "TITLE", "date_col": "INGESTED_AT"},
        "RAW.RAW_SEC_FILINGS": {"critical_col": "VALUE", "date_col": "INGESTED_AT"},
        "RAW.RAW_SEC_FILING_DOCUMENTS": {"critical_col": "FILING_ID", "date_col": "INGESTED_AT"},
    }
    rows_inserted = 0
    for table, conf in raw_tables.items():
        sql = f"""
            INSERT INTO ANALYTICS.FCT_DATA_QUALITY_HISTORY
            (snapshot_date, table_name, ticker, avg_quality_score, min_quality_score,
             max_quality_score, row_count, null_pct_critical, freshness_hours)
            SELECT
                CURRENT_DATE(),
                '{table}',
                TICKER,
                AVG(DATA_QUALITY_SCORE),
                MIN(DATA_QUALITY_SCORE),
                MAX(DATA_QUALITY_SCORE),
                COUNT(*),
                ROUND(SUM(CASE WHEN {conf["critical_col"]} IS NULL THEN 1 ELSE 0 END)
                      * 100.0 / NULLIF(COUNT(*), 0), 2),
                ROUND(TIMESTAMPDIFF(HOUR, MAX({conf["date_col"]}), CURRENT_TIMESTAMP()), 1)
            FROM {table}
            GROUP BY TICKER
        """
        try:
            session.sql(sql).collect()
            rows_inserted += 1
            _logger.info("Quality snapshot captured for %s", table)
        except Exception as exc:
            _logger.warning("Quality snapshot failed for %s: %s", table, exc)
    return rows_inserted
