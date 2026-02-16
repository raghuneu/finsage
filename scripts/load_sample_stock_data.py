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
hist['ingested_at'] = datetime.now()

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
df.columns = df.columns.str.upper()
session.sql("DELETE FROM RAW.RAW_STOCK_PRICES WHERE TICKER = 'AAPL'").collect()
session.write_pandas(df, 'RAW_STOCK_PRICES', database='FINSAGE_DB', schema='RAW', auto_create_table=False)

print(f"✅ Loaded {len(df)} rows for {ticker_symbol}")
session.close()
