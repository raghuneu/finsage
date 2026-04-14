-- Bedrock multi-model benchmark observability table
-- Populated by scripts/sec_filings/multi_model.py after each compare() run.
-- Surfaced in the Streamlit Multi-Model Analysis page.

CREATE TABLE IF NOT EXISTS FINSAGE_DB.ANALYTICS.FCT_MODEL_BENCHMARKS (
    run_id            VARCHAR       NOT NULL,
    ticker            VARCHAR,
    model_name        VARCHAR       NOT NULL,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    latency_ms        INTEGER,
    ran_at            TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Helpful index for the UI dashboard (latency + tokens by model)
-- Snowflake auto-clusters small tables; explicit clustering not needed yet.
