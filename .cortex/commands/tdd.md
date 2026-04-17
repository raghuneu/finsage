---
description: Guide TDD workflow with FinSage-specific mocking patterns
argument-hint: "[module or feature to test]"
---

# TDD Workflow

Run a Test-Driven Development cycle with FinSage-specific mocking patterns.

## Steps

1. **Identify the behavior** to implement or fix:
   ```
   User: Add validation for negative stock prices in StockLoader
   → Behavior: transform_data() should reject rows with CLOSE_PRICE < 0
   ```

2. **Write a failing test first** (RED):
   ```bash
   # Create or edit test file
   # tests/test_stock_loader.py::test_transform_rejects_negative_prices

   pytest tests/test_stock_loader.py::test_transform_rejects_negative_prices -v
   # Expected: FAILED
   ```

3. **Write minimal code to pass** (GREEN):
   - Edit the source file to make the test pass
   - Don't over-engineer — just satisfy the test
   ```bash
   pytest tests/test_stock_loader.py::test_transform_rejects_negative_prices -v
   # Expected: PASSED
   ```

4. **Refactor** if needed, then verify all tests still pass:
   ```bash
   pytest tests/ -v
   ```

5. **Check coverage**:
   ```bash
   pytest tests/ --cov=src --cov=agents --cov-report=term-missing
   # Target: 80%+ line coverage
   ```

## Mocking Cheat Sheet

### Mock Snowflake

```python
@pytest.fixture
def mock_snowflake():
    client = MagicMock()
    client.get_last_loaded_date.return_value = "2024-01-01"
    client.merge_data.return_value = None
    client.query_to_dataframe.return_value = pd.DataFrame()
    return client
```

### Mock AWS Bedrock

```python
@pytest.fixture
def mock_bedrock():
    with patch("boto3.client") as mock:
        bedrock = MagicMock()
        mock.return_value = bedrock
        yield bedrock
```

### Mock External APIs

```python
@pytest.fixture
def mock_yfinance():
    with patch("yfinance.download") as mock:
        mock.return_value = sample_stock_df()
        yield mock
```

### Mock SEC EDGAR

```python
@pytest.fixture
def mock_sec(requests_mock):
    requests_mock.get(
        "https://data.sec.gov/submissions/CIK0000320193.json",
        json=sample_submissions_response()
    )
```

## Test Organization

- File: `tests/test_<module_name>.py`
- Fixtures: `tests/conftest.py`
- Pattern: Arrange-Act-Assert (AAA)
- Naming: `test_<method>_<scenario>_<expected>` (e.g., `test_transform_data_negative_prices_filtered`)
