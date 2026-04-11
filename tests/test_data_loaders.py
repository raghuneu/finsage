"""Unit tests for data loader validation and quality scoring logic."""

import pytest
import pandas as pd
from src.data_loaders.stock_loader import StockPriceLoader
from src.data_loaders.fundamentals_loader import FundamentalsLoader
from src.data_loaders.news_loader import NewsLoader


class TestStockPriceLoader:
    """Tests for StockPriceLoader validation and quality scoring."""

    def test_validate_data_passes_clean_data(self, mock_sf_client, sample_stock_df):
        loader = StockPriceLoader(mock_sf_client)
        assert loader.validate_data(sample_stock_df) is True

    def test_validate_data_fails_negative_prices(self, mock_sf_client):
        loader = StockPriceLoader(mock_sf_client)
        df = pd.DataFrame({
            "open": [-1.0], "high": [10.0], "low": [0.5],
            "close": [5.0], "volume": [100],
        })
        with pytest.raises(ValueError, match="negative"):
            loader.validate_data(df)

    def test_validate_data_fails_high_less_than_low(self, mock_sf_client):
        loader = StockPriceLoader(mock_sf_client)
        df = pd.DataFrame({
            "open": [5.0], "high": [3.0], "low": [4.0],
            "close": [3.5], "volume": [100],
        })
        with pytest.raises(ValueError, match="High price"):
            loader.validate_data(df)

    def test_validate_data_fails_open_out_of_range(self, mock_sf_client):
        loader = StockPriceLoader(mock_sf_client)
        df = pd.DataFrame({
            "open": [200.0], "high": [160.0], "low": [140.0],
            "close": [150.0], "volume": [100],
        })
        with pytest.raises(ValueError):
            loader.validate_data(df)

    def test_quality_score_perfect(self, mock_sf_client, sample_stock_df):
        loader = StockPriceLoader(mock_sf_client)
        score = loader.calculate_quality_score(sample_stock_df)
        assert score == 100.0

    def test_quality_score_deducts_for_nulls(self, mock_sf_client):
        loader = StockPriceLoader(mock_sf_client)
        df = pd.DataFrame({
            "open": [None, 150.0], "high": [155.0, 156.0],
            "low": [148.0, 149.0], "close": [153.0, 154.0],
        })
        score = loader.calculate_quality_score(df)
        assert score == 70.0  # -30 for null prices

    def test_get_target_table(self, mock_sf_client):
        loader = StockPriceLoader(mock_sf_client)
        assert loader.get_target_table() == "RAW.RAW_STOCK_PRICES"

    def test_get_merge_keys(self, mock_sf_client):
        loader = StockPriceLoader(mock_sf_client)
        assert loader.get_merge_keys() == ["TICKER", "DATE"]


class TestFundamentalsLoader:
    """Tests for FundamentalsLoader validation and quality scoring."""

    def test_validate_data_passes_clean_data(self, mock_sf_client, sample_fundamentals_df):
        loader = FundamentalsLoader(mock_sf_client)
        assert loader.validate_data(sample_fundamentals_df) is True

    def test_validate_data_fails_negative_market_cap(self, mock_sf_client):
        loader = FundamentalsLoader(mock_sf_client)
        df = pd.DataFrame({
            "market_cap": [-1000], "revenue": [1000], "net_income": [100],
            "eps": [1.0], "pe_ratio": [20.0],
        })
        with pytest.raises(ValueError, match="Market cap"):
            loader.validate_data(df)

    def test_validate_data_fails_negative_revenue(self, mock_sf_client):
        loader = FundamentalsLoader(mock_sf_client)
        df = pd.DataFrame({
            "market_cap": [1000], "revenue": [-500], "net_income": [100],
            "eps": [1.0], "pe_ratio": [20.0],
        })
        with pytest.raises(ValueError, match="Revenue"):
            loader.validate_data(df)

    def test_quality_score_perfect(self, mock_sf_client, sample_fundamentals_df):
        loader = FundamentalsLoader(mock_sf_client)
        score = loader.calculate_quality_score(sample_fundamentals_df)
        assert score == 100.0

    def test_quality_score_deducts_missing_revenue(self, mock_sf_client):
        loader = FundamentalsLoader(mock_sf_client)
        df = pd.DataFrame({
            "revenue": [None, None], "net_income": [100, 200],
            "eps": [1.0, 2.0], "pe_ratio": [20.0, 25.0],
        })
        score = loader.calculate_quality_score(df)
        assert score == 70.0  # -30 for all null revenue

    def test_quality_score_deducts_missing_eps(self, mock_sf_client):
        loader = FundamentalsLoader(mock_sf_client)
        df = pd.DataFrame({
            "revenue": [1000], "net_income": [100],
            "eps": [None], "pe_ratio": [20.0],
        })
        score = loader.calculate_quality_score(df)
        assert score == 90.0  # -10 for all null eps

    def test_get_target_table(self, mock_sf_client):
        loader = FundamentalsLoader(mock_sf_client)
        assert loader.get_target_table() == "RAW.RAW_FUNDAMENTALS"

    def test_get_merge_keys(self, mock_sf_client):
        loader = FundamentalsLoader(mock_sf_client)
        assert loader.get_merge_keys() == ["TICKER", "FISCAL_QUARTER"]


class TestNewsLoader:
    """Tests for NewsLoader validation and quality scoring."""

    def test_validate_data_passes_clean_data(self, mock_sf_client, sample_news_df):
        loader = NewsLoader(mock_sf_client)
        assert loader.validate_data(sample_news_df) is True

    def test_validate_data_fails_null_title(self, mock_sf_client):
        loader = NewsLoader(mock_sf_client)
        df = pd.DataFrame({
            "title": [None], "url": ["http://test.com"],
            "published_at": ["2024-01-01"],
        })
        with pytest.raises(ValueError, match="Title"):
            loader.validate_data(df)

    def test_validate_data_fails_null_url(self, mock_sf_client):
        loader = NewsLoader(mock_sf_client)
        df = pd.DataFrame({
            "title": ["Test"], "url": [None],
            "published_at": ["2024-01-01"],
        })
        with pytest.raises(ValueError, match="URL"):
            loader.validate_data(df)

    def test_quality_score_perfect(self, mock_sf_client, sample_news_df):
        loader = NewsLoader(mock_sf_client)
        score = loader.calculate_quality_score(sample_news_df)
        # One author is None, so -10
        assert score == 90.0

    def test_quality_score_all_present(self, mock_sf_client):
        loader = NewsLoader(mock_sf_client)
        df = pd.DataFrame({
            "title": ["Test"], "content": ["Content"],
            "author": ["Author"], "description": ["Desc"],
        })
        score = loader.calculate_quality_score(df)
        assert score == 100.0

    def test_quality_score_all_missing(self, mock_sf_client):
        loader = NewsLoader(mock_sf_client)
        df = pd.DataFrame({
            "title": [None], "content": [None],
            "author": [None], "description": [None],
        })
        score = loader.calculate_quality_score(df)
        # title null = -30, content null = -10, author null = -10, desc null = -10
        assert score == 40.0

    def test_get_target_table(self, mock_sf_client):
        loader = NewsLoader(mock_sf_client)
        assert loader.get_target_table() == "RAW.RAW_NEWS"

    def test_get_merge_keys(self, mock_sf_client):
        loader = NewsLoader(mock_sf_client)
        assert loader.get_merge_keys() == ["ARTICLE_ID"]
