"""Stock price loader - refactored from your script"""

import yfinance as yf
import pandas as pd
from .base_loader import BaseDataLoader

class StockPriceLoader(BaseDataLoader):
    """Load stock prices from Yahoo Finance"""

    def fetch_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """Fetch stock data from Yahoo Finance"""
        # Check for incremental load
        last_date = self.sf_client.get_last_loaded_date(
            'RAW.RAW_STOCK_PRICES', ticker
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

        # Reset index and prepare
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

        return hist[['date', 'open', 'high', 'low', 'close', 'volume',
                     'dividends', 'stock_splits', 'source']]

    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate price data"""
        # Your existing validation logic
        if (df['open'] < 0).any() or (df['high'] < 0).any():
            raise ValueError("Prices cannot be negative")
        if (df['high'] < df['low']).any():
            raise ValueError("High < Low detected")
        if (df['open'] < df['low']).any() or (df['open'] > df['high']).any():
            raise ValueError("Open price out of range")
        if (df['close'] < df['low']).any() or (df['close'] > df['high']).any():
            raise ValueError("Close price out of range")

        self.logger.info("✓ Price validation passed")
        return True

    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate quality score"""
        score = 100.0

        # Deduct for issues
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

    def _load_to_snowflake(self, df: pd.DataFrame):
        """Load using MERGE pattern"""
        # Format dates
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')

        # Merge
        self.sf_client.merge_data(
            df=df,
            target_table='RAW.RAW_STOCK_PRICES',
            staging_table='TEMP_STOCK_STAGING',
            match_keys=['TICKER', 'DATE'],
            update_columns=['OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME',
                            'DIVIDENDS', 'STOCK_SPLITS', 'INGESTED_AT',
                            'DATA_QUALITY_SCORE']
        )