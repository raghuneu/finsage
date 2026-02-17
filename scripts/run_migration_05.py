"""Create STAGING and ANALYTICS schemas"""

from snowflake_connection import get_session

session = get_session()

with open('sql/05_create_staging_schema.sql', 'r') as f:
    sql_content = f.read()

sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

for statement in sql_statements:
    print(f"Executing: {statement[:60]}...")
    session.sql(statement).collect()
    print("✅ Success")

session.close()
print("\n✅ STAGING and ANALYTICS schemas created!")
