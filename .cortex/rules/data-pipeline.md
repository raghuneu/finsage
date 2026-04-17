# Data Pipeline Conventions

Rules for building and maintaining data loaders in FinSage.

## Loader Structure

All data loaders MUST extend `BaseDataLoader` from `src/data_loaders/base_loader.py` and implement:

1. `fetch_data(ticker, start_date, end_date)` — Fetch from external source
2. `transform_data(raw_df)` — Transform to Snowflake schema
3. `validate_data(df)` — Validate before loading
4. `calculate_quality_score(df)` — Score 0-100

Do not override `load()` — it is the template method that orchestrates the pipeline.

## Required Output Columns

Every loader output DataFrame must include:

- `TICKER` — Stock symbol from config
- `SOURCE` — Data source identifier (e.g., "yfinance", "sec_edgar", "newsapi")
- `INGESTED_AT` — Current timestamp (`pd.Timestamp.now()`)

Plus loader-specific columns matching the target RAW table schema.

## Configuration

- Read tickers from `config/tickers.yaml` — never hardcode ticker lists
- Read API keys and credentials from environment variables via `os.environ` or `python-dotenv`
- Connection parameters for Snowflake come from environment variables

## Incremental Loading

Always use `get_last_loaded_date()` to determine the start date for data fetching:

```python
last_date = self.client.get_last_loaded_date(table=self.table, ticker=ticker)
new_data = self.fetch_data(ticker, start_date=last_date)
```

This avoids re-fetching all historical data on every run.

## Quality Scoring

Quality score must be 0-100. Start at 100 and deduct for issues:

| Deduction | Condition |
|-----------|-----------|
| -2 per column | Column has >5% null values |
| -5 | Duplicate key rows exist |
| -10 | Newest data is >7 days old |
| -5 | Row count below expected minimum |

Document any custom deductions in the loader's docstring.

## Rate Limiting

All external API calls must be rate-limited:

| API | Rate Limit | Implementation |
|-----|-----------|----------------|
| SEC EDGAR | 10 req/s | Class-level `_last_request_time` + sleep |
| NewsAPI | Per-plan limits | Class-level rate limiter |
| yfinance | Handled by library | No custom limiting needed |

Include required User-Agent headers for SEC EDGAR.

## Error Handling

- Use `tenacity` for retry with exponential backoff — no manual retry loops
- Catch specific exceptions, not bare `except:`
- Log errors with context: ticker, loader name, error type
- Never return empty DataFrame silently on error — raise or log at ERROR level
- Snowpark sessions must be closed in `finally` blocks

## Testing

Every loader must have tests in `tests/test_<loader_name>.py` covering:

- `fetch_data` returns valid DataFrame (mocked API)
- `transform_data` produces correct column names and types
- `validate_data` rejects invalid data
- `quality_score` returns 0-100
- `load` calls `merge_data` on the client
