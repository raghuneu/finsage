"""Base class for all data loaders - preserves your patterns"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional
from src.utils.logger import setup_logger

class BaseDataLoader(ABC):
    """Abstract base class for all data loaders"""

    def __init__(self, sf_client):
        self.sf_client = sf_client
        self.logger = setup_logger(self.__class__.__name__, f'{self.__class__.__name__}.log')

    @abstractmethod
    def fetch_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """Fetch data from source - implement in subclass"""
        pass

    @abstractmethod
    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate data quality - implement in subclass"""
        pass

    @abstractmethod
    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate quality score 0-100 - implement in subclass"""
        pass

    @abstractmethod
    def get_target_table(self) -> str:
        """Return target table name - implement in subclass"""
        pass

    @abstractmethod
    def get_merge_keys(self) -> list:
        """Return columns to match on for MERGE - implement in subclass"""
        pass

    def transform_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Common transformations - add ticker and timestamp"""
        df['ticker'] = ticker
        df['ingested_at'] = pd.Timestamp.now()
        return df

    def load(self, ticker: str, **kwargs) -> bool:
        """
        Main execution method - mirrors your script logic

        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"🔄 Processing {ticker}...")

        try:
            # 1. Fetch data
            df = self.fetch_data(ticker, **kwargs)

            if df.empty:
                self.logger.warning(f"⚠️  No data returned for {ticker}")
                return False

            # 2. Transform
            df = self.transform_data(df, ticker)

            # 3. Validate
            if not self.validate_data(df):
                raise ValueError(f"Validation failed for {ticker}")

            # 4. Quality score
            score = self.calculate_quality_score(df)
            df['data_quality_score'] = score

            # 5. Load to Snowflake using your MERGE pattern
            self._load_to_snowflake(df)

            self.logger.info(f"✅ {ticker} completed - {len(df)} rows, quality: {score:.1f}")
            return True

        except Exception as e:
            self.logger.error(f"❌ {ticker} failed: {e}")
            return False

    def _load_to_snowflake(self, df: pd.DataFrame):
        """Load using temp staging + MERGE pattern from your scripts"""
        target_table = self.get_target_table()
        staging_table = f"TEMP_{target_table.split('.')[-1]}_STAGING"

        # Get all columns except match keys for update
        match_keys = self.get_merge_keys()
        all_cols = df.columns.tolist()
        update_cols = [c for c in all_cols if c.upper() not in [k.upper() for k in match_keys]]

        # Use your MERGE pattern
        self.sf_client.merge_data(
            df=df,
            target_table=target_table,
            staging_table=staging_table,
            match_keys=match_keys,
            update_columns=update_cols
        )