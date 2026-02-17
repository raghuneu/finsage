"""Load sample fundamentals data from Yahoo Finance into RAW table with quality checks"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from snowflake_connection import get_session

ticker_symbol = "AAPL"

def validate_fundamentals(df):
    """Validate fundamentals data quality"""
    if (df['market_cap'] < 0).any():
        raise ValueError("Market cap cannot be negative")
    if (df['revenue'] < 0).any():
        raise ValueError("Revenue cannot be negative")
    print("Fundamentals validation passed.")

def calculate_quality_score(df):
    """Calculate data quality score for fundamentals (0-100)"""
    score = 100.0
    
    # Deduct points for missing critical fields
    if df['revenue'].isnull().any():
        score -= 30
    if df['net_income'].isnull().any():
        score -= 20
    if df['eps'].isnull().any():
        score -= 10
    if df['pe_ratio'].isnull().any():
        score -= 10
        
    return score

# Fetch company fundamentals
ticker = yf.Ticker(ticker_symbol)
info = ticker.info

# Prepare data for Snowflake
data = {
    'ticker': ticker_symbol,
    'fiscal_quarter': 'Q4 2024',
    'market_cap': info.get('marketCap'),
    'revenue': info.get('totalRevenue'),
    'net_income': info.get('netIncomeToCommon'),
    'eps': info.get('trailingEps'),
    'pe_ratio': info.get('trailingPE'),
    'profit_margin': info.get('profitMargins'),
    'debt_to_equity': info.get('debtToEquity'),
    'total_assets': info.get('totalAssets'),
    'total_liabilities': info.get('totalDebt'),
    'source': 'yahoo_finance',
    'ingested_at': pd.Timestamp.now()
}

df = pd.DataFrame([data])

# Validate data
validate_fundamentals(df)

# Calculate quality score
df['data_quality_score'] = calculate_quality_score(df)

# Format timestamp
df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')

df.columns = df.columns.str.upper()

# Load to Snowflake
session = get_session()

# Drop and recreate temporary staging table with new schema
session.sql("DROP TABLE IF EXISTS TEMP_FUNDAMENTALS_STAGING").collect()
session.sql("""
    CREATE TEMPORARY TABLE TEMP_FUNDAMENTALS_STAGING LIKE RAW.RAW_FUNDAMENTALS
""").collect()


# Load to staging
session.write_pandas(df, 'TEMP_FUNDAMENTALS_STAGING', auto_create_table=False, overwrite=True)

# MERGE from staging to raw
merge_sql = """
MERGE INTO RAW.RAW_FUNDAMENTALS target
USING TEMP_FUNDAMENTALS_STAGING source
ON target.TICKER = source.TICKER AND target.FISCAL_QUARTER = source.FISCAL_QUARTER
WHEN MATCHED THEN 
    UPDATE SET 
        MARKET_CAP = source.MARKET_CAP,
        REVENUE = source.REVENUE,
        NET_INCOME = source.NET_INCOME,
        EPS = source.EPS,
        PE_RATIO = source.PE_RATIO,
        PROFIT_MARGIN = source.PROFIT_MARGIN,
        DEBT_TO_EQUITY = source.DEBT_TO_EQUITY,
        TOTAL_ASSETS = source.TOTAL_ASSETS,
        TOTAL_LIABILITIES = source.TOTAL_LIABILITIES,
        INGESTED_AT = source.INGESTED_AT,
        DATA_QUALITY_SCORE = source.DATA_QUALITY_SCORE
WHEN NOT MATCHED THEN
    INSERT (TICKER, FISCAL_QUARTER, MARKET_CAP, REVENUE, NET_INCOME, EPS, PE_RATIO, 
            PROFIT_MARGIN, DEBT_TO_EQUITY, TOTAL_ASSETS, TOTAL_LIABILITIES, SOURCE, INGESTED_AT, DATA_QUALITY_SCORE)
    VALUES (source.TICKER, source.FISCAL_QUARTER, source.MARKET_CAP, source.REVENUE, source.NET_INCOME, 
            source.EPS, source.PE_RATIO, source.PROFIT_MARGIN, source.DEBT_TO_EQUITY, source.TOTAL_ASSETS, 
            source.TOTAL_LIABILITIES, source.SOURCE, source.INGESTED_AT, source.DATA_QUALITY_SCORE)
"""

session.sql(merge_sql).collect()
print(f"✅ Merged fundamentals for {ticker_symbol}")

session.close()
