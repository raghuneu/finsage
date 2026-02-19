# FinSage Project Log

## Week 1 (Feb 9 - Feb 15, 2026)

### Implemented

**Environment Setup**

- Created virtual environment with Python 3.13
- Installed core dependencies: snowflake-snowpark-python, yfinance, pandas, requests, httpx, beautifulsoup4
- Configured .env file for credential management using python-dotenv
- Established Snowflake connection with session management module

**Data Source Exploration**

- Yahoo Finance API: Retrieved OHLCV data (Open, High, Low, Close, Volume) plus dividends and stock splits
- Alpha Vantage API: Explored fundamental metrics (market cap, P/E ratios, EBITDA, revenue)
- NewsAPI: Retrieved news articles with title, source, author, description, content, publication date

**Database Schema Design**

- Designed RAW layer schema with three tables: raw_stock_prices, raw_fundamentals, raw_news
- Included metadata columns: source, ingested_at for data lineage tracking
- Defined primary keys: (ticker, date) for prices, (ticker, fiscal_quarter) for fundamentals, article_id for news

**RAW Layer Implementation**

- Created FINSAGE_DB database with RAW schema in Snowflake
- Implemented SQL DDL scripts for table creation
- Built Python executors to run SQL migrations

**Data Loading Scripts**

- Stock prices loader: Fetched 1-month historical data from Yahoo Finance
- Fundamentals loader: Retrieved company financial metrics
- News loader: Collected articles from NewsAPI with proper API key management

**Production-Grade Enhancements**

- Idempotency: Implemented MERGE statements using temporary staging tables instead of DELETE-INSERT pattern to prevent data loss on failure
- Data Quality Validation: Built pre-load validation functions checking for negative prices, null critical fields, and logical consistency (high >= low, open/close within range)
- Data Quality Scoring: Added data_quality_score column (0-100 scale) with deduction logic for missing or invalid fields
- Incremental Loading: Implemented logic to query last loaded date and fetch only new data, reducing API calls and execution time

**Version Control**

- Initialized Git repository with proper .gitignore
- Organized folder structure: scripts/, sql/, notebooks/, dbt_finsage/
- Made incremental commits for each major feature

### Challenges

**Timestamp Data Type Issues**

- Snowflake rejected pandas datetime objects during write_pandas operation
- Root cause: Timezone-aware datetime from yfinance causing type mismatch
- Solution: Convert timestamps to string format using strftime before loading

**MERGE Statement Learning Curve**

- Initial confusion about staging table approach for MERGE operations
- Required understanding of temporary tables and their lifecycle in Snowflake
- Resolved by creating temp staging tables with LIKE clause, then executing MERGE

**Column Case Sensitivity**

- Snowflake creates uppercase columns by default, pandas uses lowercase
- Caused "invalid identifier" errors during data loading
- Solution: Uppercase all DataFrame columns before write_pandas operation

**Migration Execution Tracking**

- Forgot to run ALTER TABLE migrations for quality score columns
- Led to missing column errors during subsequent loads
- Implemented systematic migration script naming (01*, 02*, etc.) and verification queries

**API Key Security**

- Initially hardcoded NewsAPI key in Python script
- Learned industry practice of storing credentials in .env files
- Refactored to use environment variables with dotenv library

---

## Week 2 (Feb 16 - Feb 19, 2026)

### Implemented

**dbt Project Initialization**

- Installed dbt-snowflake adapter
- Initialized dbt_finsage project with Snowflake connection configuration
- Created STAGING and ANALYTICS schemas in Snowflake
- Configured profiles.yml with connection parameters and 4-thread concurrency

**Staging Models Development**

- stg_stock_prices: Added daily_return calculation using LAG window function, filtered to last 2 years, added is_valid flag
- stg_fundamentals: Validated revenue and market_cap fields, filtered invalid records
- stg_news: Implemented basic sentiment analysis using keyword matching (profit/growth = positive, loss/decline = negative), filtered to last 3 months

**dbt Source Configuration**

- Defined raw schema sources in schema.yml
- Documented model descriptions and column definitions
- Configured data tests: not_null tests for ticker, date, and close columns

**Data Quality Testing**

- Executed dbt test command to validate staging models
- All 3 tests passed: ticker not null, date not null, close not null
- Verified parallel test execution using 4 threads

**Verification Scripts**

- Built Python scripts to query and validate staging layer data
- Confirmed daily_return calculations were accurate (e.g., -0.67%, -3.46% drops observed)
- Verified sentiment classification in news staging table

### Challenges

**dbt Threading Concept**

- Initial confusion about what threads parameter controls
- Learned threads enable parallel model execution for independent models
- Understood trade-off between speed and resource usage (4 threads chosen for development balance)

**Window Function NULL Handling**

- First row in daily_return calculation returned NULL (no previous day to compare)
- Caused TypeError in Python formatting when attempting to format None as float
- Solution: Added conditional check (if row['DAILY_RETURN'] is not None) before formatting

**Example Model Cleanup**

- dbt init created example models in models/example/ folder
- Caused warning about unused configuration paths in dbt_project.yml
- Removed example folder and warning disappeared

**View vs Table Decision**

- dbt created staging models as views by default
- Need to understand when to use tables vs views for performance
- Views are appropriate for staging layer as they stay fresh with source data

**Sentiment Analysis Limitations**

- Basic keyword matching for sentiment is overly simplistic
- Recognized need for more sophisticated NLP or Snowflake Cortex sentiment functions
- Documented as future enhancement for analytics layer

---
