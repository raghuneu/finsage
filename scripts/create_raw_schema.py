"""Create RAW schema and tables in Snowflake"""

from snowflake_connection import get_session

# Create session
session = get_session()

# Read the SQL file
with open('sql/01_create_raw_schema.sql', 'r') as f:
    sql_content = f.read()

# Split by semicolons and execute each statement
sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

for statement in sql_statements:
    print(f"Executing: {statement[:50]}...")
    session.sql(statement).collect()
    print("✅ Success")

session.close()
print("\n✅ RAW schema and tables created successfully!")
