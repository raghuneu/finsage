"""Verify news data was loaded"""

from snowflake_connection import get_session

session = get_session()

result = session.sql("SELECT TICKER, TITLE, DATA_QUALITY_SCORE FROM RAW.RAW_NEWS LIMIT 3").collect()

print("News articles:")
for row in result:
    print(f"  {row['TICKER']} | Score: {row['DATA_QUALITY_SCORE']} | {row['TITLE'][:40]}...")

session.close()
