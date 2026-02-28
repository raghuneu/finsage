"""Create SEC filing text table for LLM analysis"""

from pathlib import Path
import sys

script_path = Path(__file__).resolve()
project_root = script_path.parent.parent
sql_file = project_root / 'sql' / '07_create_sec_filing_text.sql'

sys.path.insert(0, str(script_path.parent))
from snowflake_connection import get_session

if not sql_file.exists():
    print(f"❌ SQL file not found: {sql_file}")
    sys.exit(1)

session = get_session()

print("Creating RAW_SEC_FILING_TEXT table...\n")

with open(sql_file, 'r', encoding='utf-8') as f:
    sql_content = f.read()

sql_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

for idx, statement in enumerate(sql_statements, 1):
    print(f"[{idx}/{len(sql_statements)}] Executing: {statement[:60]}...")
    session.sql(statement).collect()
    print("✅ Success")

# Verify
print("\nVerifying table creation...")
result = session.sql('DESCRIBE TABLE RAW.RAW_SEC_FILING_TEXT').collect()
print(f"\n✅ Table created with {len(result)} columns:")
for row in result:
    print(f"  - {row['name']:30} {row['type']}")

session.close()
print("\n🎉 RAW_SEC_FILING_TEXT ready for use!")