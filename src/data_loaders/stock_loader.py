"""Stock price loader - refactored from load_sample_stock_data.py"""

import yfinance as yf
import pandas as pd
from .base_loader import BaseDataLoader

class StockPriceLoader(BaseDataLoader):
    """Load stock prices from Yahoo Finance"""

    def fetch_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """
        Fetch stock data with incremental loading
        Uses your exact pattern from original script
        """
        # Check for existing data (your incremental pattern)
        last_date = self.sf_client.get_last_loaded_date(
            'RAW.RAW_STOCK_PRICES', ticker, 'DATE'
        )

        yf_ticker = yf.Ticker(ticker)

        if last_date:
            self.logger.info(f"Incremental load from {last_date}")
            hist = yf_ticker.history(start=last_date)
        else:
            self.logger.info("Initial load - fetching 2 years")
            hist = yf_ticker.history(period="2y")

        if hist.empty:
            return pd.DataFrame()

        # Prepare data (your exact column mapping)
        hist = hist.reset_index()
        hist = hist.rename(columns={
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
            'Dividends': 'dividends',
            'Stock Splits': 'stock_splits'
        })

        hist['source'] = 'yahoo_finance'

        # Select columns in your order
        df = hist[['date', 'open', 'high', 'low', 'close', 'volume',
                   'dividends', 'stock_splits', 'source']].copy()

        # Format dates (your pattern)
        df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).dt.strftime('%Y-%m-%d')

        return df

    def validate_data(self, df: pd.DataFrame) -> bool:
        """Your exact validation logic"""
        # Check for negative prices
        if (df['open'] < 0).any() or (df['high'] < 0).any() or \
                (df['low'] < 0).any() or (df['close'] < 0).any():
            raise ValueError("Price columns cannot have negative values")

        # High >= Low
        if (df['high'] < df['low']).any():
            raise ValueError("High price cannot be less than low price")

        # Open within range
        if (df['open'] < df['low']).any() or (df['open'] > df['high']).any():
            raise ValueError("Open price must be between low and high")

        # Close within range
        if (df['close'] < df['low']).any() or (df['close'] > df['high']).any():
            raise ValueError("Close price must be between low and high")

        self.logger.info("✓ Price validation passed")
        return True

    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Your exact quality scoring logic"""
        score = 100.0

        # Deduct points for issues
        if (df['high'] < df['low']).any():
            score -= 20
        if (df['open'] < df['low']).any() or (df['open'] > df['high']).any():
            score -= 10
        if (df['close'] < df['low']).any() or (df['close'] > df['high']).any():
            score -= 10
        if df[['open', 'high', 'low', 'close']].isnull().any().any():
            score -= 30

        return score

    def get_target_table(self) -> str:
        return 'RAW.RAW_STOCK_PRICES'

    def get_merge_keys(self) -> list:
        return ['TICKER', 'DATE']

    def transform_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Add ticker and timestamp (your pattern)"""
        df = super().transform_data(df, ticker)
        # Format timestamp
        df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        return df