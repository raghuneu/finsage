"""Load sample stock data from Yahoo Finance into RAW table"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from snowflake_connection import get_session

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
           'dividends', 'stock_splits', 'source', 'ingested_at']]

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
        INGESTED_AT = source.INGESTED_AT
WHEN NOT MATCHED THEN
    INSERT (TICKER, DATE, OPEN, HIGH, LOW, CLOSE, VOLUME, DIVIDENDS, STOCK_SPLITS, SOURCE, INGESTED_AT)
    VALUES (source.TICKER, source.DATE, source.OPEN, source.HIGH, source.LOW, source.CLOSE, 
            source.VOLUME, source.DIVIDENDS, source.STOCK_SPLITS, source.SOURCE, source.INGESTED_AT)
"""

session.sql(merge_sql).collect()
print(f"✅ Merged {len(df)} rows for {ticker_symbol}")

session.close()
