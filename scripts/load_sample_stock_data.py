"""Load sample stock data from Yahoo Finance into RAW table"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from snowflake_connection import get_session

def validate_prices(df):
    if (df['open'] < 0).any() or (df['high'] < 0).any() or (df['low'] < 0).any() or (df['close'] < 0).any():
        raise ValueError("Price columns cannot have negative values.")
    if (df['high'] < df['low']).any():
        raise ValueError("High price cannot be less than low price.")
    if (df['open'] < df['low']).any() or (df['open'] > df['high']).any():
        raise ValueError("Open price must be between low and high.")
    if (df['close'] < df['low']).any() or (df['close'] > df['high']).any():
        raise ValueError("Close price must be between low and high.")
    print("Price validation passed.")

def calculate_quality_score(df):
    """Calculate data quality score (0-100)"""
    score = 100.0
    
    # Deduct points for issues
    if (df['high'] < df['low']).any():
        score -= 20
    if (df['open'] < df['low']).any() or (df['open'] > df['high']).any():
        score -= 10
    if (df['close'] < df['low']).any() or (df['close'] > df['high']).any():
        score -= 10
    if df[['open', 'high', 'low', 'close']].isnull().any().any():
        score -= 30
        
    return score



# Fetch stock data
ticker_symbol = "AAPL"
ticker = yf.Ticker(ticker_symbol)
hist = ticker.history(period="1mo")

# Prepare data for Snowflake
hist = hist.reset_index()
hist['ticker'] = ticker_symbol
hist['source'] = 'yahoo_finance'
hist['ingested_at'] = pd.Timestamp.now()

# Rename columns to match Snowflake schema
hist = hist.rename(columns={
    'Date': 'date',
    'Open': 'open',
    'High': 'high',
    'Low': 'low',
    'Close': 'close',
    'Volume': 'volume',
    'Dividends': 'dividends',
    'Stock Splits': 'stock_splits'
})

# Select only needed columns
df = hist[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 
           'dividends', 'stock_splits', 'source', 'ingested_at']].copy()
validate_prices(df)
df['data_quality_score'] = calculate_quality_score(df)


# Load to Snowflake
session = get_session()

result = session.sql("SELECT COUNT(*) as cnt FROM RAW.RAW_STOCK_PRICES").collect()
print(f"Row count: {result[0]['CNT']}")

df['date'] = df['date'].dt.tz_localize(None).dt.strftime('%Y-%m-%d')
df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
df.columns = df.columns.str.upper()

# Create temporary staging table
session.sql("""
    CREATE TEMPORARY TABLE IF NOT EXISTS temp_stock_staging LIKE RAW.RAW_STOCK_PRICES
""").collect()

# Load to staging table
session.write_pandas(df, 'TEMP_STOCK_STAGING', auto_create_table=False, overwrite=True)

# MERGE from staging to raw
merge_sql = """
MERGE INTO RAW.RAW_STOCK_PRICES target
USING TEMP_STOCK_STAGING source
ON target.TICKER = source.TICKER AND target.DATE = source.DATE
WHEN MATCHED THEN 
    UPDATE SET 
        OPEN = source.OPEN,
        HIGH = source.HIGH,
        LOW = source.LOW,
        CLOSE = source.CLOSE,
        VOLUME = source.VOLUME,
        DIVIDENDS = source.DIVIDENDS,
        STOCK_SPLITS = source.STOCK_SPLITS,
        INGESTED_AT = source.INGESTED_AT,
        DATA_QUALITY_SCORE = source.DATA_QUALITY_SCORE
WHEN NOT MATCHED THEN
    INSERT (TICKER, DATE, OPEN, HIGH, LOW, CLOSE, VOLUME, DIVIDENDS, STOCK_SPLITS, SOURCE, INGESTED_AT, DATA_QUALITY_SCORE)
    VALUES (source.TICKER, source.DATE, source.OPEN, source.HIGH, source.LOW, source.CLOSE, 
            source.VOLUME, source.DIVIDENDS, source.STOCK_SPLITS, source.SOURCE, source.INGESTED_AT, source.DATA_QUALITY_SCORE)
"""

session.sql(merge_sql).collect()
print(f"✅ Merged {len(df)} rows for {ticker_symbol}")

result = session.sql("SELECT TICKER, DATE, CLOSE, DATA_QUALITY_SCORE FROM RAW.RAW_STOCK_PRICES LIMIT 3").collect()


session.close()
