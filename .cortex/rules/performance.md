# Performance Guidelines

## Context Window Management

- Use `/compact` proactively when context grows large during multi-file edits
- For large-scale refactoring, break work into smaller focused sessions
- Reference `.astro/warehouse.md` for schema lookups instead of running DESCRIBE queries repeatedly

## Snowflake Query Performance

- Always include `WHERE TICKER = ...` to avoid full table scans
- Use `LIMIT` for exploratory queries
- Use `ORDER BY` + `LIMIT` instead of fetching all rows and sorting in Python
- Prefer Snowflake aggregate functions over pandas post-processing for large datasets
- Close Snowpark sessions promptly — don't hold connections longer than needed

## Python Performance

- Use `pandas` vectorized operations over row-by-row iteration
- Cache expensive Snowflake query results when the same data is used multiple times in a pipeline run
- Use `concurrent.futures` for parallel API calls (Alpha Vantage, NewsAPI)
- Profile slow operations before optimizing — don't guess

## Streamlit Performance

- Use `@st.cache_data` for expensive Snowflake queries with appropriate TTL
- Use `@st.cache_resource` for Snowpark session creation
- Avoid re-querying Snowflake on every Streamlit rerun
- Use `st.spinner()` for long-running operations to provide user feedback

## dbt Performance

- Staging models as views (no materialization cost)
- Analytics models as tables (query performance over build cost)
- Use incremental models if table sizes grow significantly
