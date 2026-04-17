"""Tests for configuration files and project structure."""

import os
import json
from pathlib import Path

import yaml
import pytest

PROJECT_ROOT = Path(__file__).parent.parent


class TestTickerConfig:
    """Test ticker configuration."""

    def test_tickers_yaml_exists(self):
        assert (PROJECT_ROOT / "config" / "tickers.yaml").exists()

    def test_tickers_yaml_has_tickers(self):
        with open(PROJECT_ROOT / "config" / "tickers.yaml") as f:
            config = yaml.safe_load(f)
        tickers = config.get("tickers", [])
        assert len(tickers) >= 3, "Should have at least 3 tickers configured"

    def test_tickers_are_uppercase(self):
        with open(PROJECT_ROOT / "config" / "tickers.yaml") as f:
            config = yaml.safe_load(f)
        for ticker in config["tickers"]:
            assert ticker == ticker.upper(), f"Ticker {ticker} should be uppercase"

    def test_tickers_are_valid_format(self):
        with open(PROJECT_ROOT / "config" / "tickers.yaml") as f:
            config = yaml.safe_load(f)
        import re
        for ticker in config["tickers"]:
            assert re.match(r"^[A-Z]{1,5}$", ticker), f"Invalid ticker: {ticker}"


class TestCIKCache:
    """Test CIK cache completeness."""

    def test_cik_cache_exists(self):
        assert (PROJECT_ROOT / "config" / "cik_cache.json").exists()

    def test_cik_cache_is_valid_json(self):
        with open(PROJECT_ROOT / "config" / "cik_cache.json") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_cik_cache_covers_all_tickers(self):
        with open(PROJECT_ROOT / "config" / "tickers.yaml") as f:
            config = yaml.safe_load(f)
        with open(PROJECT_ROOT / "config" / "cik_cache.json") as f:
            cache = json.load(f)

        for ticker in config["tickers"]:
            assert ticker in cache, f"CIK cache missing entry for {ticker}"

    def test_cik_values_are_padded(self):
        with open(PROJECT_ROOT / "config" / "cik_cache.json") as f:
            cache = json.load(f)
        for ticker, cik in cache.items():
            assert len(cik) == 10, f"CIK for {ticker} should be zero-padded to 10 digits"
            assert cik.isdigit(), f"CIK for {ticker} should be all digits"


class TestProjectStructure:
    """Test that essential project files exist."""

    @pytest.mark.parametrize("path", [
        "agents/orchestrator.py",
        "agents/chart_agent.py",
        "agents/validation_agent.py",
        "agents/analysis_agent.py",
        "agents/report_agent.py",
        "src/data_loaders/base_loader.py",
        "src/data_loaders/stock_loader.py",
        "src/data_loaders/fundamentals_loader.py",
        "src/data_loaders/news_loader.py",
        "src/data_loaders/sec_loader.py",
        "src/data_loaders/xbrl_loader.py",
        "src/orchestration/data_pipeline.py",
        "frontend/app.py",
        "config/tickers.yaml",
        "config/cik_cache.json",
        "requirements.txt",
    ])
    def test_file_exists(self, path):
        assert (PROJECT_ROOT / path).exists(), f"Missing: {path}"

    def test_env_file_in_gitignore(self):
        gitignore = (PROJECT_ROOT / ".gitignore").read_text()
        assert ".env" in gitignore, ".env must be listed in .gitignore"
