"""Verify stock data was loaded"""

from snowflake_connection import get_session

session = get_session()

result = session.sql("SELECT TICKER, CLOSE, SOURCE FROM RAW.RAW_STOCK_PRICES LIMIT 3").collect()

print("Sample data from RAW_STOCK_PRICES:")
for row in result:
    print(f"  {row['TICKER']} | Close: ${row['CLOSE']} | Source: {row['SOURCE']}")

session.close()
