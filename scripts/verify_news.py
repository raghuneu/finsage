"""Verify news data was loaded"""

from snowflake_connection import get_session

session = get_session()

result = session.sql("SELECT TICKER, TITLE, SOURCE_NAME, PUBLISHED_AT FROM RAW.RAW_NEWS LIMIT 3").collect()

print("News articles:")
for row in result:
    print(f"  {row['TICKER']} | {row['SOURCE_NAME']} | {row['TITLE'][:50]}...")

session.close()
