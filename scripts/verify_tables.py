"""Verify RAW tables were created"""

from snowflake_connection import get_session

session = get_session()

# Show tables in RAW schema
result = session.sql("SHOW TABLES IN SCHEMA RAW").collect()

print("Tables in RAW schema:")
for row in result:
    print(f"  - {row['name']}")

session.close()
