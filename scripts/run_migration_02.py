"""Run migration to add data quality columns"""

from snowflake_connection import get_session

session = get_session()

# Read the migration SQL file
with open('sql/02_add_quality_score_column.sql', 'r') as f:
    sql_content = f.read()

# Split by semicolons and execute each statement
sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

for statement in sql_statements:
    print(f"Executing: {statement[:60]}...")
    session.sql(statement).collect()
    print("✅ Success")

session.close()
print("\n✅ Migration completed - quality columns added!")
