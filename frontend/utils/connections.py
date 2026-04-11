"""Shared connection singletons for all Streamlit pages."""

import os
import sys
from pathlib import Path

# Compute project root: utils/ -> frontend/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Add import paths BEFORE any project imports
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "sec_filings"))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import yaml
import streamlit as st


def load_tickers():
    """Load ticker list from config/tickers.yaml."""
    config_path = PROJECT_ROOT / "config" / "tickers.yaml"
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return config.get("tickers", ["AAPL", "MSFT", "GOOGL"])
    return ["AAPL", "MSFT", "GOOGL"]


@st.cache_resource
def get_snowflake():
    try:
        from snowflake_connection import get_session
        return get_session()
    except Exception:
        return None


@st.cache_resource
def get_kb():
    if not os.getenv("BEDROCK_KB_ID"):
        return None
    try:
        from bedrock_kb import BedrockKB
        return BedrockKB()
    except Exception:
        return None


@st.cache_resource
def get_guardrail():
    if not os.getenv("BEDROCK_GUARDRAIL_ID"):
        return None
    try:
        from guardrails import GuardedLLM
        return GuardedLLM()
    except Exception:
        return None


@st.cache_resource
def get_multi_model():
    try:
        from multi_model import MultiModelAnalyzer
        return MultiModelAnalyzer()
    except Exception:
        return None


def get_ticker():
    """Get the currently selected ticker from session state."""
    return st.session_state.get("ticker", "AAPL")
