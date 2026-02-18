"""Verify staging stock data"""

from snowflake_connection import get_session

session = get_session()

result = session.sql("""
    SELECT ticker, date, close, daily_return, is_valid 
    FROM STAGING.stg_stock_prices 
    LIMIT 5
""").collect()

print("Staging stock prices:")
for row in result:
    daily_return = f"{row['DAILY_RETURN']:.4f}" if row['DAILY_RETURN'] is not None else 'N/A'
    print(f"  {row['TICKER']} | {row['DATE']} | ${row['CLOSE']:.2f} | Return: {daily_return}")

session.close()
