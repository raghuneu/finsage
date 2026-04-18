"""Load multi-quarter fundamentals data from Yahoo Finance into RAW table with quality checks.

Uses the modular FundamentalsLoader (which fetches both quarterly + annual
statements for 8+ quarters of history needed by fct_fundamentals_growth YoY).
"""

import sys
import time
from pathlib import Path

import yaml

# Ensure project root is on the path so we can import src.*
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.utils.snowflake_client import SnowflakeClient
from src.data_loaders.fundamentals_loader import FundamentalsLoader


def _load_tickers():
    """Load ticker list from config/tickers.yaml, falling back to defaults."""
    config_path = _PROJECT_ROOT / "config" / "tickers.yaml"
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
        tickers = config.get("tickers", [])
        if tickers:
            return tickers
    return ["AAPL", "MSFT", "GOOGL"]


def load_fundamentals():
    tickers = _load_tickers()
    print(f"Loading fundamentals for {len(tickers)} tickers...")

    sf = SnowflakeClient(component="fundamentals_reload")
    loader = FundamentalsLoader(sf)

    succeeded = 0
    failed = 0
    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] {ticker}...")
        try:
            ok = loader.load(ticker)
            if ok:
                succeeded += 1
            else:
                failed += 1
                print(f"  Warning: no data for {ticker}")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {ticker} failed: {e}")

        # Rate limit courtesy
        if i < len(tickers):
            time.sleep(0.5)

    sf.close()
    print(f"\nDone: {succeeded} succeeded, {failed} failed out of {len(tickers)} tickers.")


if __name__ == "__main__":
    load_fundamentals()
