# FinSage: AI-Powered Financial Research Report Generator

An end-to-end automated system that generates professional financial research reports for U.S. public companies using Large Language Models, multi-agent architecture, and modern data engineering tools.

## Problem Statement

Investment decisions worth billions of dollars depend on high-quality financial research reports. However, producing these reports is:

- **Labor-intensive**: Analysts spend weeks gathering data from multiple sources
- **Time-consuming**: Manual analysis of financial statements, news, and market data
- **Expensive**: Professional reports cost thousands of dollars
- **Inconsistent**: Quality varies based on analyst expertise

**FinSage automates this process**, generating 15-20 page professional financial reports with charts, analysis, and citations in under 30 minutes.

## Solution Overview

FinSage implements a three-stage pipeline:

1. **Data Collection**: Gathers heterogeneous data from Yahoo Finance, NewsAPI, and financial databases
2. **Data Analysis**: Uses multi-agent architecture with Code Agent Variable Memory (CAVM) for dynamic analysis
3. **Report Generation**: Produces formatted reports with visualizations using two-stage writing framework

## Technology Stack

### Data Engineering

- **Snowflake**: Cloud data warehouse for scalable storage and compute
- **dbt (Data Build Tool)**: SQL-based transformations with built-in testing
- **Apache Airflow**: Workflow orchestration and scheduling (planned)
- **Snowpark Python**: In-database Python execution

### Data Sources

- **Yahoo Finance API**: Daily stock prices (OHLCV data)
- **NewsAPI**: Financial news articles and sentiment
- **Alpha Vantage**: Company fundamentals (revenue, earnings, ratios)

### AI/ML

- **Snowflake Cortex LLM**: Built-in language models for analysis
- **GPT-4 Vision**: Chart quality refinement (planned)
- **Cortex Search**: Vector embeddings for semantic retrieval (planned)

### Development Tools

- **Python 3.13**: Core programming language
- **pandas**: Data manipulation
- **Git/GitHub**: Version control
- **dotenv**: Secure credential management

## Architecture

```

┌─────────────────────────────────────────┐
│ DATA COLLECTION LAYER │
│ Yahoo Finance | NewsAPI | Alpha Vantage │
└─────────────────────────────────────────┘
↓
┌─────────────────────────────────────────┐
│ RAW LAYER (Snowflake) │
│ raw_stock_prices | raw_fundamentals │
│ raw_news │
└─────────────────────────────────────────┘
↓
┌─────────────────────────────────────────┐
│ STAGING LAYER (dbt transformations) │
│ stg_stock_prices | stg_fundamentals │
│ stg_news (with sentiment) │
└─────────────────────────────────────────┘
↓
┌─────────────────────────────────────────┐
│ ANALYTICS LAYER (planned) │
│ Financial metrics | Growth calculations │
│ Comparative analysis │
└─────────────────────────────────────────┘
↓
┌─────────────────────────────────────────┐
│ REPORT GENERATION (planned) │
│ Multi-page PDF with charts & citations │
└─────────────────────────────────────────┘

```

## Key Features Implemented

### Production-Grade Data Pipeline

- **Idempotent Loading**: MERGE statements prevent duplicate data
- **Data Quality Validation**: Pre-load checks for data integrity
- **Quality Scoring**: 0-100 score tracking data completeness
- **Incremental Loading**: Only fetches new data since last run

### Data Transformation

- **Automated dbt Models**: SQL-based transformations with dependency management
- **Parallel Execution**: 4-thread concurrency for faster processing
- **Built-in Testing**: Automated validation of data quality rules

### Security & Best Practices

- Environment variable management for API keys
- Structured logging and error handling
- Git version control with proper .gitignore
- Modular code organization

## Project Structure

```

finsage-project/
├── .env # Credentials (not in Git)
├── .gitignore
├── README.md
├── schema*design.md # Database schema documentation
├── scripts/ # Python scripts
│ ├── snowflake_connection.py
│ ├── load_sample_stock_data.py
│ ├── load_sample_fundamentals.py
│ ├── load_sample_news.py
│ ├── verify*_.py # Data verification scripts
│ └── run*migration*_.py # Database migrations
├── sql/ # SQL DDL scripts
│ ├── 01_create_raw_schema.sql
│ ├── 02_add_quality_score_column.sql
│ └── 05_create_staging_schema.sql
├── dbt_finsage/ # dbt project
│ ├── dbt_project.yml
│ └── models/
│ └── staging/
│ ├── stg_stock_prices.sql
│ ├── stg_fundamentals.sql
│ ├── stg_news.sql
│ └── schema.yml
└── notebooks/ # Jupyter notebooks (planned)

```

## Setup Instructions

### Prerequisites

- Python 3.13+
- Snowflake account (academic or trial)
- API keys: NewsAPI, Alpha Vantage (optional)

### Installation

1. **Clone the repository**

```bash
git clone <your-repo-url>
cd finsage-project
```

2. **Create virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install snowflake-snowpark-python yfinance pandas httpx beautifulsoup4 python-dotenv dbt-snowflake
```

4. **Configure credentials**

Create `.env` file in project root:

```
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ROLE=your_role
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=FINSAGE_DB
SNOWFLAKE_SCHEMA=RAW
NEWSAPI_KEY=your_newsapi_key
```

5. **Initialize database**

```bash
python scripts/create_raw_schema.py
python scripts/run_migration_05.py
```

6. **Initialize dbt**

```bash
cd dbt_finsage
dbt debug  # Verify connection
dbt run    # Run all models
dbt test   # Run data quality tests
```

### Running the Pipeline

**Load data:**

```bash
python scripts/load_sample_stock_data.py
python scripts/load_sample_fundamentals.py
python scripts/load_sample_news.py
```

**Transform data:**

```bash
cd dbt_finsage
dbt run --select staging
dbt test --select staging
```

**Verify results:**

```bash
python scripts/verify_staging_stock.py
```

## Current Progress

**Completed (Week 1-2):**

- ✅ Environment setup and Snowflake connection
- ✅ RAW layer with 3 data sources
- ✅ Production-grade loading (idempotency, quality checks, incremental)
- ✅ dbt project with 3 staging models
- ✅ Automated data quality testing

**In Progress (Week 3):**

- 🔄 Analytics layer (financial metrics calculations)
- 🔄 CAVM architecture implementation

**Planned (Week 4-8):**

- 📋 Chart generation with iterative VLM refinement
- 📋 Chain-of-Analysis (CoA) generation
- 📋 Two-stage report writing framework
- 📋 Airflow DAG orchestration
- 📋 PDF report generation

**Progress: ~20% complete**

Key innovations being implemented:

- **CAVM Architecture**: Unified programmable workspace for data, tools, and agents
- **Iterative Vision-Enhanced Mechanism**: Chart quality improvement using VLM feedback
- **Two-Stage Writing**: CoA generation followed by report composition

## Why These Tools?

**Snowflake**: Industry-standard cloud data warehouse with native AI capabilities (Cortex)

**dbt**: Transforms data engineering into software engineering with version control, testing, and documentation

**Airflow**: Production-grade orchestration used by Airbnb, Twitter, and thousands of companies

**Python**: Versatile language with rich ecosystem for data engineering and AI

## Team

Graduate students at Northeastern University
Course: DAMG 7374 - Data Engineering: Impact of Generative AI with LLMs

## License

MIT License

## Contact

For questions or collaboration: [shantharajamani.r@northeastern.edu](mailto:shantharajamani.r@northeastern.edu) | [misra.o@northeastern.edu](mailto:misra.o@northeastern.edu) | [vedanarayanan.s@northeastern.edu](mailto:vedanarayanan.s@northeastern.edu)

---

**Note**: This is an academic project demonstrating modern data engineering practices with LLMs. Not intended for actual investment decisions.

```

```
