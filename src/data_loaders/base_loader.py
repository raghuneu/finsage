"""Base class for all data loaders"""

from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd
import logging

class BaseDataLoader(ABC):
    """Abstract base class for data loaders"""

    def __init__(self, sf_client, logger=None):
        self.sf_client = sf_client
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def fetch_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """Fetch data from source - must implement"""
        pass

    @abstractmethod
    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate data quality - must implement"""
        pass

    @abstractmethod
    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate quality score - must implement"""
        pass

    @abstractmethod
    def get_target_table(self) -> str:
        """Return target table name - must implement"""
        pass

    def transform_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Common transformations"""
        df['ticker'] = ticker
        df['ingested_at'] = pd.Timestamp.now()
        return df

    def load(self, ticker: str, **kwargs):
        """Main execution method"""
        self.logger.info(f"🔄 Loading {ticker}...")

        try:
            # Fetch
            df = self.fetch_data(ticker, **kwargs)
            if df.empty:
                self.logger.warning(f"⚠️ No data for {ticker}")
                return

            # Transform
            df = self.transform_data(df, ticker)

            # Validate
            if not self.validate_data(df):
                raise ValueError(f"Validation failed for {ticker}")

            # Quality score
            df['data_quality_score'] = self.calculate_quality_score(df)

            # Load to Snowflake
            self._load_to_snowflake(df)

            self.logger.info(f"✅ {ticker} loaded successfully")

        except Exception as e:
            self.logger.error(f"❌ {ticker} failed: {e}")
            raise

    @abstractmethod
    def _load_to_snowflake(self, df: pd.DataFrame):
        """Load data to Snowflake - must implement"""
        pass