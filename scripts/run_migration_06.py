"""Create SEC filings table"""

from snowflake_connection import get_session

session = get_session()

with open('sql/06_create_sec_table.sql', 'r') as f:
    sql = f.read()

session.sql(sql).collect()
print("✅ SEC filings table created!")
session.close()
