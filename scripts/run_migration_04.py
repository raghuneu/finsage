"""Run migration to add quality score to fundamentals"""

from snowflake_connection import get_session

session = get_session()

sql = "ALTER TABLE RAW.RAW_FUNDAMENTALS ADD COLUMN DATA_QUALITY_SCORE FLOAT DEFAULT 100.0"

print("Executing migration...")
session.sql(sql).collect()
print("✅ Migration completed - quality score column added to fundamentals!")

session.close()
