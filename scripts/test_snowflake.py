"""Basic Snowflake connection test using .env"""
 
import os
from dotenv import load_dotenv
from snowflake.snowpark import Session
 
# Load environment variables
load_dotenv()
 
# Build connection parameters from .env
connection_params = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
    "user": os.getenv("SNOWFLAKE_USER"),
    "password": os.getenv("SNOWFLAKE_PASSWORD"),
    "role": os.getenv("SNOWFLAKE_ROLE"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
    "database": os.getenv("SNOWFLAKE_DATABASE"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA"),
}

try:
    session = Session.builder.configs(connection_params).create()
    result = session.sql("SELECT CURRENT_TIMESTAMP() AS ts, CURRENT_USER() AS user_name, CURRENT_ROLE() AS role").collect()
    print("✅ Connected to Snowflake!")
    print(f"   Timestamp: {result[0]['TS']}")
    print(f"   User:      {result[0]['USER_NAME']}")
    print(f"   Role:      {result[0]['ROLE']}")
    session.close()
    print("✅ Session closed.")
except Exception as e:
    print(f"❌ Connection failed: {e}")