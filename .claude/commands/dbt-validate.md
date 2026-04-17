# dbt Validate Workflow

Validate dbt models and ensure they stay in sync with downstream consumers.

## Step 1: Check dbt Connection

```bash
cd dbt_finsage && dbt debug
```

Verify: Snowflake connection, database, warehouse, schema all resolve.

## Step 2: Compile Models

```bash
cd dbt_finsage && dbt compile
```

Check for SQL syntax errors or missing references before running.

## Step 3: Run Models

```bash
cd dbt_finsage && dbt run
```

Verify all staging views and analytics tables build successfully.

## Step 4: Run Tests

```bash
cd dbt_finsage && dbt test
```

Check for: unique key violations, not-null failures, relationship integrity.

## Step 5: Verify Downstream Consumers

After dbt changes, verify these files still work:
- `agents/chart_agent.py` — SQL queries must match updated column names
- `agents/analysis_agent.py` — SEC and fundamental data queries
- `app/streamlit_app.py` — Dashboard queries

Cross-reference against `.astro/warehouse.md` (run `dbt docs generate` to refresh if schema changed).

## Step 6: Refresh Warehouse Reference

If dbt models changed:
```bash
# Re-generate warehouse schema reference
# Use the /data:init cortex command to refresh .astro/warehouse.md
```
