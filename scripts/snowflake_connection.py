"""Shared Snowflake connection module"""

import os
from dotenv import load_dotenv
from snowflake.snowpark import Session


def _build_connection_params() -> dict:
    """Build Snowflake connection parameters from environment variables."""
    load_dotenv()

    connection_params = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA"),
    }

    # Only add role if set (avoids sending None)
    role = os.getenv("SNOWFLAKE_ROLE")
    if role:
        connection_params["role"] = role

    # Validate required params
    required = ["account", "user", "warehouse", "database", "schema"]
    missing = [k for k in required if not connection_params.get(k)]
    if missing:
        raise ValueError(
            f"Missing Snowflake env vars: {', '.join('SNOWFLAKE_' + k.upper() for k in missing)}. "
            f"Check your .env file."
        )

    token = os.getenv("SNOWFLAKE_TOKEN")

    if token:
        connection_params["authenticator"] = "programmatic_access_token"
        connection_params["token"] = token
    else:
        password = os.getenv("SNOWFLAKE_PASSWORD")
        if not password:
            raise ValueError(
                "Neither SNOWFLAKE_TOKEN nor SNOWFLAKE_PASSWORD is set. "
                "Check your .env file."
            )
        connection_params["password"] = password

    return connection_params


def get_session() -> Session:
    """Create and return a Snowflake session.

    Auth priority:
        1. Programmatic Access Token (SNOWFLAKE_TOKEN)
        2. Password (for teammates without MFA)
    """
    return Session.builder.configs(_build_connection_params()).create()


def create_session_pool(size: int) -> list:
    """Create multiple independent Snowflake sessions for parallel work.

    Each session is fully independent and safe to use from a separate thread.
    Caller is responsible for closing all sessions when done.

    Args:
        size: Number of sessions to create.

    Returns:
        List of Snowflake Session objects.
    """
    params = _build_connection_params()
    return [Session.builder.configs(params).create() for _ in range(size)]