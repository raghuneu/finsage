"""Shared pytest fixtures for FinSage tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "sec_filings"))
sys.path.insert(0, str(PROJECT_ROOT / "agents"))


@pytest.fixture
def mock_sf_client():
    """Mock Snowflake client for data loader tests."""
    client = MagicMock()
    client.get_last_loaded_date.return_value = None
    client.merge_data.return_value = None
    return client


@pytest.fixture
def sample_stock_df():
    """Sample stock price DataFrame."""
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=5),
        "open": [150.0, 151.0, 152.0, 153.0, 154.0],
        "high": [155.0, 156.0, 157.0, 158.0, 159.0],
        "low": [148.0, 149.0, 150.0, 151.0, 152.0],
        "close": [153.0, 154.0, 155.0, 156.0, 157.0],
        "volume": [1000000, 1100000, 1200000, 1300000, 1400000],
        "dividends": [0.0, 0.0, 0.0, 0.0, 0.0],
        "stock_splits": [0.0, 0.0, 0.0, 0.0, 0.0],
        "source": ["yahoo_finance"] * 5,
        "ticker": ["AAPL"] * 5,
        "ingested_at": [pd.Timestamp.now()] * 5,
    })


@pytest.fixture
def sample_fundamentals_df():
    """Sample fundamentals DataFrame."""
    return pd.DataFrame({
        "fiscal_quarter": ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"],
        "market_cap": [3000000000000] * 4,
        "revenue": [90000000000, 95000000000, 85000000000, 120000000000],
        "net_income": [23000000000, 24000000000, 22000000000, 33000000000],
        "eps": [1.46, 1.53, 1.40, 2.10],
        "pe_ratio": [30.0] * 4,
        "profit_margin": [0.25] * 4,
        "debt_to_equity": [1.5] * 4,
        "total_assets": [350000000000] * 4,
        "total_liabilities": [280000000000] * 4,
        "source": ["yahoo_finance"] * 4,
        "ticker": ["AAPL"] * 4,
        "ingested_at": [pd.Timestamp.now()] * 4,
    })


@pytest.fixture
def sample_news_df():
    """Sample news DataFrame."""
    return pd.DataFrame({
        "article_id": ["id1", "id2", "id3"],
        "title": ["Apple stock rises", "AAPL earnings beat", "Apple launches new product"],
        "description": ["Desc 1", "Desc 2", "Desc 3"],
        "content": ["Content 1", "Content 2", "Content 3"],
        "author": ["Author 1", "Author 2", None],
        "source_name": ["Reuters", "Bloomberg", "CNBC"],
        "url": ["https://example.com/1", "https://example.com/2", "https://example.com/3"],
        "published_at": ["2024-01-01 10:00:00", "2024-01-02 11:00:00", "2024-01-03 12:00:00"],
        "ticker": ["AAPL"] * 3,
        "ingested_at": [pd.Timestamp.now()] * 3,
    })


@pytest.fixture
def sample_chart_result():
    """Sample chart result dict as produced by chart_agent."""
    return {
        "chart_id": "price_sma",
        "title": "Price & Moving Averages",
        "file_path": "/tmp/test_chart.png",
        "data_summary": {
            "current_price": 185.50,
            "sma_7d": 184.20,
            "sma_30d": 180.10,
            "sma_90d": 175.00,
            "trend_signal": "BULLISH",
            "date_range": "2024-01-01 to 2024-03-31",
        },
        "validated": True,
        "refinement_count": 2,
    }
