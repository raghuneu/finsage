"""Load sample fundamentals data from Yahoo Finance into RAW table"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from snowflake_connection import get_session

# Fetch company fundamentals
ticker_symbol = "AAPL"
ticker = yf.Ticker(ticker_symbol)
info = ticker.info

# Prepare data for Snowflake
data = {
    'ticker': ticker_symbol,
    'fiscal_quarter': 'Q4 2024',  # You'd normally get this from the API
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
    'ingested_at': datetime.now()
}

df = pd.DataFrame([data])
df.columns = df.columns.str.upper()

# Load to Snowflake
session = get_session()
session.sql(f"DELETE FROM RAW.RAW_FUNDAMENTALS WHERE TICKER = '{ticker_symbol}'").collect()
session.write_pandas(df, 'RAW_FUNDAMENTALS', database='FINSAGE_DB', schema='RAW', auto_create_table=False)

print(f"✅ Loaded fundamentals for {ticker_symbol}")
session.close()
