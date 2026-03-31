"""
FinSage — .env Diagnostic Script
Run this to find exactly which variables are missing or wrong.
"""

import os
from pathlib import Path

# ── Try to find the .env file ──────────────────────────────────────────────────
# Try multiple likely locations on Windows
candidate_paths = [
    Path(r"D:\FinSage\finsage\.env"),
    Path(r"D:\FinSage\.env"),
    Path(r"D:\FinSage\FinSight\.env"),
    Path(__file__).parent / ".env",
    Path(__file__).parent.parent / ".env",
    ]

found_env = None
for p in candidate_paths:
    if p.exists():
        found_env = p
        print(f"✅ Found .env at: {p}")
        break

if not found_env:
    print("❌ Could not find .env in any of these locations:")
    for p in candidate_paths:
        print(f"   {p}")
    print("\nPlease create your .env file and re-run.")
    exit(1)

# ── Load it explicitly ─────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(found_env, override=True)

# ── Check each required variable ───────────────────────────────────────────────
required = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
]

print("\nChecking required variables:")
all_ok = True
for key in required:
    val = os.getenv(key)
    if val:
        # Mask password, show first 4 chars of others
        display = "****" if "PASSWORD" in key else f"{val[:4]}..." if len(val) > 4 else val
        print(f"  ✅ {key} = {display}")
    else:
        print(f"  ❌ {key} = MISSING")
        all_ok = False

# ── Special check: SNOWFLAKE_ACCOUNT format ────────────────────────────────────
account = os.getenv("SNOWFLAKE_ACCOUNT", "")
if account:
    print("\nAccount format check:")
    if "snowflakecomputing.com" in account:
        print("  ⚠️  SNOWFLAKE_ACCOUNT contains 'snowflakecomputing.com' — remove it")
        print(f"     Change:  {account}")
        print(f"     To:      {account.replace('.snowflakecomputing.com', '')}")
    elif "https" in account.lower():
        print("  ⚠️  SNOWFLAKE_ACCOUNT looks like a URL — should be just the account ID")
    else:
        print(f"  ✅ Format looks correct: {account}")

if all_ok:
    print("\n✅ All variables present — attempting connection...")
    try:
        from snowflake.snowpark import Session
        params = {k: os.getenv(k) for k in required}
        session = Session.builder.configs(params).create()
        result = session.sql("SELECT CURRENT_USER() AS u, CURRENT_ROLE() AS r, CURRENT_WAREHOUSE() AS w").collect()
        print(f"✅ Connected!")
        print(f"   User:      {result[0]['U']}")
        print(f"   Role:      {result[0]['R']}")
        print(f"   Warehouse: {result[0]['W']}")
        session.close()
    except Exception as e:
        print(f"❌ Connection failed: {e}")
else:
    print("\n❌ Fix the missing variables above first, then re-run.")
