"""Run migration to add quality score to news"""

from snowflake_connection import get_session

session = get_session()

sql = "ALTER TABLE RAW.RAW_NEWS ADD COLUMN DATA_QUALITY_SCORE FLOAT DEFAULT 100.0"

print("Executing migration...")
session.sql(sql).collect()
print("✅ Migration completed - quality score column added to news!")

session.close()
