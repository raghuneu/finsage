"""Shared Snowflake connection module"""

import os
from dotenv import load_dotenv
from snowflake.snowpark import Session


def get_session():
    """Create and return a Snowflake session.
    
    Auth priority:
        1. Programmatic Access Token (SNOWFLAKE_TOKEN)
        2. Password (for teammates without MFA)
    """
    load_dotenv()

    connection_params = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "role": os.getenv("SNOWFLAKE_ROLE"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA"),
    }

    token = os.getenv("SNOWFLAKE_TOKEN")

    if token:
        connection_params["authenticator"] = "programmatic_access_token"
        connection_params["token"] = token
    else:
        connection_params["password"] = os.getenv("SNOWFLAKE_PASSWORD")

    return Session.builder.configs(connection_params).create()