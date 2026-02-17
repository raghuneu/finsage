"""Verify stock data was loaded"""

from snowflake_connection import get_session

session = get_session()

result = session.sql("SELECT TICKER, DATE, CLOSE, DATA_QUALITY_SCORE FROM RAW.RAW_STOCK_PRICES LIMIT 3").collect()

print("Sample data from RAW_STOCK_PRICES:")
for row in result:
    print(f"  {row['TICKER']} | {row['DATE']} | Close: ${row['CLOSE']} | Quality: {row['DATA_QUALITY_SCORE']}")

session.close()
