"""Shared dependencies for FastAPI routers."""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Add project root to path so we can import existing modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "sec_filings"))
sys.path.insert(0, str(PROJECT_ROOT / "agents"))
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from snowflake_connection import get_session


def get_snowpark_session():
    """Create a fresh Snowpark session for each request."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def get_tickers() -> list[str]:
    """Load ticker list from config/tickers.yaml or return defaults."""
    import yaml

    tickers_path = PROJECT_ROOT / "config" / "tickers.yaml"
    if tickers_path.exists():
        with open(tickers_path) as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict) and "tickers" in data:
                return data["tickers"]
            if isinstance(data, list):
                return data
    return ["AAPL", "GOOGL", "JPM", "MSFT", "TSLA"]
