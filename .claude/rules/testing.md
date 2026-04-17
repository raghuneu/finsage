# Testing Requirements

## Framework

Use **pytest** as the testing framework.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov=agents --cov-report=term-missing

# Run specific test file
pytest tests/test_chart_agent.py -v
```

## Test-Driven Development

Mandatory workflow for new features and bug fixes:
1. Write test first (RED) — test should FAIL
2. Run test — verify it FAILS
3. Write minimal implementation (GREEN) — test should PASS
4. Run test — verify it PASSES
5. Refactor (IMPROVE) — tests must stay green
6. Verify coverage

## Edge Cases You MUST Test

1. `None` / empty DataFrame inputs
2. Invalid or unknown ticker symbols
3. Snowflake connection failures / session closure
4. Missing columns in query results
5. Empty query results (no data for a ticker)
6. Malformed dates or numeric overflow
7. API rate limits (Alpha Vantage, NewsAPI, SEC EDGAR)
8. Large datasets (full history for active tickers)

## Test Structure (AAA Pattern)

```python
def test_fetch_stock_metrics_valid_ticker():
    # Arrange
    session = create_mock_session(sample_stock_data)

    # Act
    result = fetch_stock_metrics(session, "AAPL")

    # Assert
    assert not result.empty
    assert "close" in result.columns
    assert result["date"].is_monotonic_increasing
```

## Test Anti-Patterns to Avoid

- Testing implementation details instead of behavior
- Tests depending on each other (shared mutable state)
- Asserting too little (just checking `not None`)
- Not mocking external dependencies (Snowflake, AWS, APIs)
- Tests that require live Snowflake/AWS connections without mocking

## Mocking External Services

- Mock Snowpark sessions with controlled DataFrame returns
- Mock boto3 clients for S3/Bedrock operations
- Mock API responses for Alpha Vantage, NewsAPI, SEC EDGAR
- Use `unittest.mock.patch` or `pytest-mock` fixtures

## Test File Organization

```
tests/
  test_chart_agent.py        # Chart generation and data fetching
  test_analysis_agent.py     # LLM analysis and SEC summarization
  test_orchestrator.py       # Pipeline orchestration
  test_data_loaders.py       # Data loader unit tests
  test_snowflake_client.py   # Snowflake connection utilities
```
