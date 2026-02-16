# FinSage Database Schema Design

## RAW Schema

Raw data as ingested from external APIs, minimal transformation.

### raw_stock_prices

Stores daily stock price data from Yahoo Finance.

**Columns:**

- `ticker` (VARCHAR) - Stock symbol (e.g., 'AAPL')
- `date` (DATE) - Trading date
- `open` (FLOAT) - Opening price
- `high` (FLOAT) - Highest price of the day
- `low` (FLOAT) - Lowest price of the day
- `close` (FLOAT) - Closing price
- `volume` (BIGINT) - Trading volume
- `dividends` (FLOAT) - Dividend amount
- `stock_splits` (FLOAT) - Stock split ratio
- `source` (VARCHAR) - Data source identifier
- `ingested_at` (TIMESTAMP) - When data was loaded

**Primary Key:** (ticker, date)

### raw_fundamentals

Stores company fundamental financial data from Yahoo Finance and Alpha Vantage.

**Columns:**

- `ticker` (VARCHAR) - Stock symbol (e.g., 'AAPL')
- `fiscal_quarter` (VARCHAR) - Fiscal period (e.g., 'Q4 2024')
- `market_cap` (BIGINT) - Market capitalization
- `revenue` (FLOAT) - Total revenue
- `net_income` (FLOAT) - Net income/profit
- `eps` (FLOAT) - Earnings per share
- `pe_ratio` (FLOAT) - Price-to-earnings ratio
- `profit_margin` (FLOAT) - Profit margin percentage
- `debt_to_equity` (FLOAT) - Debt-to-equity ratio
- `total_assets` (FLOAT) - Total assets
- `total_liabilities` (FLOAT) - Total liabilities
- `source` (VARCHAR) - Data source identifier
- `ingested_at` (TIMESTAMP) - When data was loaded

**Primary Key:** (ticker, fiscal_quarter)

### raw_news

Stores news articles from NewsAPI and other sources.

**Columns:**

- `article_id` (VARCHAR) - Unique identifier for the article
- `ticker` (VARCHAR) - Related stock symbol
- `title` (TEXT) - Article headline
- `description` (TEXT) - Article summary/snippet
- `content` (TEXT) - Full article content
- `author` (VARCHAR) - Article author
- `source_name` (VARCHAR) - News source (e.g., 'Reuters')
- `url` (VARCHAR) - Article URL
- `published_at` (TIMESTAMP) - Publication timestamp
- `ingested_at` (TIMESTAMP) - When data was loaded

**Primary Key:** (article_id)
