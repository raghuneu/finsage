"""Fundamentals loader - refactored from load_sample_fundamentals.py"""

import yfinance as yf
import pandas as pd
from .base_loader import BaseDataLoader

class FundamentalsLoader(BaseDataLoader):
    """Load company fundamentals from Yahoo Finance"""

    def fetch_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """Fetch fundamentals from Yahoo Finance"""
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info

        # Your exact data structure
        data = {
            'fiscal_quarter': 'Q4 2024',  # Could make this dynamic
            'market_cap': info.get('marketCap'),
            'revenue': info.get('totalRevenue'),
            'net_income': info.get('netIncomeToCommon'),
            'eps': info.get('trailingEps'),
            'pe_ratio': info.get('trailingPE'),
            'profit_margin': info.get('profitMargins'),
            'debt_to_equity': info.get('debtToEquity'),
            'total_assets': info.get('totalAssets'),
            'total_liabilities': info.get('totalDebt'),
            'source': 'yahoo_finance'
        }

        return pd.DataFrame([data])

    def validate_data(self, df: pd.DataFrame) -> bool:
        """Your exact validation logic"""
        if (df['market_cap'] < 0).any():
            raise ValueError("Market cap cannot be negative")
        if (df['revenue'] < 0).any():
            raise ValueError("Revenue cannot be negative")

        self.logger.info("✓ Fundamentals validation passed")
        return True

    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Your exact quality scoring"""
        score = 100.0

        # Deduct for missing critical fields
        if df['revenue'].isnull().any():
            score -= 30
        if df['net_income'].isnull().any():
            score -= 20
        if df['eps'].isnull().any():
            score -= 10
        if df['pe_ratio'].isnull().any():
            score -= 10

        return score

    def get_target_table(self) -> str:
        return 'RAW.RAW_FUNDAMENTALS'

    def get_merge_keys(self) -> list:
        return ['TICKER', 'FISCAL_QUARTER']

    def transform_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Format timestamp"""
        df = super().transform_data(df, ticker)
        df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        return df