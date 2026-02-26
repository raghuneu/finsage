"""Verify SEC data was loaded"""

from snowflake_connection import get_session

session = get_session()

result = session.sql("""
    SELECT TICKER, CONCEPT, FISCAL_YEAR, FISCAL_PERIOD, VALUE, FORM_TYPE
    FROM RAW.RAW_SEC_FILINGS
    WHERE FISCAL_PERIOD = 'FY'
    ORDER BY FISCAL_YEAR DESC
    LIMIT 5
""").collect()

print("SEC filings data:")
for row in result:
    print(f"  {row['TICKER']} | {row['CONCEPT']} | FY{row['FISCAL_YEAR']} | ${row['VALUE']:,.0f}")

session.close()
