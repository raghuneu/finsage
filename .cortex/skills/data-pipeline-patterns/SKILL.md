---
name: data-pipeline-patterns
description: FinSage data loader development guide — BaseDataLoader extension, quality scoring, rate limiting, and incremental loading
---

# Data Pipeline Patterns for FinSage

Reference guide for building and maintaining data loaders in the FinSage pipeline.

## Architecture

```
External APIs → DataLoader.fetch_data() → transform_data() → validate_data()
                                                                    ↓
config/tickers.yaml → pipeline.run_pipeline() ← calculate_quality_score()
                                                                    ↓
                      ThreadPoolExecutor(3) → _load_to_snowflake() → MERGE
```

## BaseDataLoader Pattern

All loaders extend `src/data_loaders/base_loader.py`:

```python
from src.data_loaders.base_loader import BaseDataLoader

class NewDataLoader(BaseDataLoader):
    """Loader for [data source description]."""

    def fetch_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch raw data from external source.

        Must handle:
        - API rate limiting
        - Network errors with retry
        - Empty responses (return empty DataFrame)
        """
        ...

    def transform_data(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Transform raw data to match Snowflake schema.

        Must:
        - Rename columns to UPPER_SNAKE_CASE
        - Add SOURCE column with data source identifier
        - Add INGESTED_AT column with current timestamp
        - Cast types to match target table schema
        """
        ...

    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate transformed data before loading.

        Must check:
        - DataFrame is not empty
        - Required columns are present
        - No null values in key columns
        - Data types are correct
        """
        ...

    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate data quality score (0-100).

        Start at 100 and deduct for issues:
        - Missing values: -2 per column with >5% nulls
        - Duplicates: -5 if any duplicate key rows
        - Stale data: -10 if newest row is >7 days old
        - Volume: -5 if row count < expected minimum
        """
        ...
```

## Template Method Flow

The `load()` method in `BaseDataLoader` orchestrates the pipeline:

```python
def load(self, ticker: str) -> dict:
    """Template method — do not override."""
    last_date = self.client.get_last_loaded_date(table=self.table, ticker=ticker)
    raw = self.fetch_data(ticker, start_date=last_date)
    transformed = self.transform_data(raw)
    if not self.validate_data(transformed):
        raise DataValidationError(f"Validation failed for {ticker}")
    score = self.calculate_quality_score(transformed)
    self._load_to_snowflake(transformed)
    return {"ticker": ticker, "rows": len(transformed), "quality_score": score}
```

## Existing Loaders

| Loader | Source | Target Table | Rate Limit |
|--------|--------|-------------|------------|
| `StockLoader` | yfinance | RAW_STOCK_PRICES | None (yfinance handles) |
| `FundamentalsLoader` | yfinance | RAW_FUNDAMENTALS | None |
| `NewsLoader` | NewsAPI | RAW_NEWS | Class-level limiter |
| `SecLoader` | SEC EDGAR | RAW_SEC_FILINGS | 10 req/s with User-Agent |
| `XbrlLoader` | SEC XBRL API | RAW_SEC_FILINGS (enrichment) | 10 req/s with User-Agent |

## Quality Score Calculation

Start at 100 and apply deductions:

```python
def calculate_quality_score(self, df: pd.DataFrame) -> float:
    score = 100.0

    # Completeness: -2 per column with >5% nulls
    for col in df.columns:
        null_pct = df[col].isnull().mean()
        if null_pct > 0.05:
            score -= 2

    # Uniqueness: -5 if duplicate key rows exist
    key_cols = ["TICKER", "DATE"]  # Adjust per loader
    if df.duplicated(subset=key_cols).any():
        score -= 5

    # Freshness: -10 if newest data is >7 days old
    if "DATE" in df.columns:
        latest = pd.to_datetime(df["DATE"]).max()
        if (pd.Timestamp.now() - latest).days > 7:
            score -= 10

    # Volume: -5 if below expected minimum
    if len(df) < self.expected_min_rows:
        score -= 5

    return max(0, score)
```

## Rate Limiting

### SEC EDGAR (10 requests/second)

```python
import time

class SecLoader(BaseDataLoader):
    _last_request_time = 0
    _min_interval = 0.1  # 10 req/s

    def _rate_limited_request(self, url: str) -> requests.Response:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

        response = requests.get(url, headers={
            "User-Agent": "FinSage Pipeline contact@example.com"
        })
        self._last_request_time = time.time()
        return response
```

### Retry with Tenacity

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True
)
def fetch_with_retry(self, url: str) -> dict:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()
```

## Pipeline Orchestration

`src/orchestration/data_pipeline.py` runs loaders with ThreadPoolExecutor:

```python
def run_pipeline(tickers: list[str], loaders: list[BaseDataLoader]):
    """Run all loaders for all tickers with max 3 concurrent workers."""
    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for ticker in tickers:
            for loader in loaders:
                future = executor.submit(loader.load, ticker)
                futures[future] = (ticker, loader.__class__.__name__)

        for future in as_completed(futures):
            ticker, loader_name = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.exception(f"Failed: {loader_name} for {ticker}")
                results.append({"ticker": ticker, "loader": loader_name, "error": str(e)})

    return results
```

## Configuration

Tickers are loaded from `config/tickers.yaml`:

```yaml
tickers:
  - AAPL
  - GOOGL
  - JPM
  - MSFT
  - TSLA
```

Never hardcode ticker lists. Always read from config:

```python
import yaml

with open("config/tickers.yaml") as f:
    config = yaml.safe_load(f)
    tickers = config["tickers"]
```

## Required Columns for All Loaders

Every loader output must include these columns:

| Column | Type | Description |
|--------|------|-------------|
| TICKER | VARCHAR | Stock symbol (from config) |
| SOURCE | VARCHAR | Data source identifier (e.g., "yfinance", "sec_edgar") |
| INGESTED_AT | TIMESTAMP | Ingestion timestamp (`pd.Timestamp.now()`) |

Plus loader-specific columns matching the target RAW table schema.

## Adding a New Loader

1. Create `src/data_loaders/new_source_loader.py`
2. Extend `BaseDataLoader`
3. Implement all 4 required methods
4. Add rate limiting if hitting an external API
5. Add to `run_pipeline()` loader list
6. Create corresponding RAW table in Snowflake
7. Create dbt staging view and analytics table
8. Write tests in `tests/test_new_source_loader.py`
9. Update Airflow DAG if applicable
