"""Verify fundamentals data was loaded"""

from snowflake_connection import get_session

session = get_session()

result = session.sql("SELECT TICKER, MARKET_CAP, PE_RATIO, PROFIT_MARGIN FROM RAW.RAW_FUNDAMENTALS").collect()

print("Fundamentals data:")
for row in result:
    print(f"  {row['TICKER']} | Market Cap: ${row['MARKET_CAP']:,} | P/E: {row['PE_RATIO']} | Margin: {row['PROFIT_MARGIN']}")

session.close()
