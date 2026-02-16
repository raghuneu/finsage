"""Shared Snowflake connection module"""

import os
from dotenv import load_dotenv
from snowflake.snowpark import Session

def get_session():
    """Create and return a Snowflake session"""
    load_dotenv()
    
    connection_params = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "role": os.getenv("SNOWFLAKE_ROLE"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA"),
    }
    
    return Session.builder.configs(connection_params).create()
