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


def render_sidebar():
    """Render the shared sidebar with ticker selector and connection indicators.

    Call this from every page to ensure the ticker dropdown is always visible.
    Returns the currently selected ticker.
    """
    session = get_snowflake()
    kb = get_kb()
    guardrail = get_guardrail()
    mm = get_multi_model()
    tickers = load_tickers()

    with st.sidebar:
        # Logo
        st.markdown(
            '<div style="padding:8px 0 4px 0">'
            '<span style="font-size:1.6rem;font-weight:800;color:#f9fafb">Fin</span>'
            '<span style="font-size:1.6rem;font-weight:800;color:#00d4ff">Sage</span>'
            '</div>'
            '<div style="color:#6b7280;font-size:0.75rem;letter-spacing:0.05em;margin-bottom:16px">'
            'AI-POWERED EQUITY RESEARCH</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        st.markdown(
            '<div style="color:#4b5563;font-size:0.7rem;font-weight:600;'
            'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Active Ticker</div>',
            unsafe_allow_html=True,
        )
        st.selectbox(
            "Ticker",
            tickers,
            key="ticker",
            label_visibility="collapsed",
        )

        st.markdown("---")

        # Connection indicators
        dot_g = '<span class="status-dot green pulse"></span>'
        dot_r = '<span class="status-dot red"></span>'
        st.markdown(
            '<div style="color:#4b5563;font-size:0.7rem;font-weight:600;'
            'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">Services</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"{dot_g if session else dot_r} Snowflake", unsafe_allow_html=True)
        st.markdown(f"{dot_g if kb else dot_r} Bedrock KB", unsafe_allow_html=True)
        st.markdown(f"{dot_g if guardrail else dot_r} Guardrails", unsafe_allow_html=True)
        st.markdown(f"{dot_g if mm else dot_r} Multi-Model", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(
            '<div style="color:#4b5563;font-size:0.7rem">v1.0 &middot; FinSage Platform</div>',
            unsafe_allow_html=True,
        )

    return st.session_state.get("ticker", "AAPL")
