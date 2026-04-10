"""Fundamentals loader - fetches multi-quarter data from Yahoo Finance"""

import yfinance as yf
import pandas as pd
from .base_loader import BaseDataLoader


class FundamentalsLoader(BaseDataLoader):
    """Load multi-quarter company fundamentals from Yahoo Finance"""

    @staticmethod
    def _quarter_label(date):
        """Convert a date to fiscal quarter label e.g. Q1 2024"""
        q = (date.month - 1) // 3 + 1
        return f"Q{q} {date.year}"

    def fetch_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """Fetch multi-quarter fundamentals from Yahoo Finance"""
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info

        try:
            income_q = yf_ticker.quarterly_income_stmt
            balance_q = yf_ticker.quarterly_balance_sheet
        except Exception as e:
            self.logger.warning(f"Could not fetch quarterly statements for {ticker}: {e}")
            return pd.DataFrame()

        if income_q is None or income_q.empty:
            self.logger.warning(f"No quarterly income data for {ticker}")
            return pd.DataFrame()

        rows = []
        for col in income_q.columns:
            try:
                date = pd.to_datetime(col)
                label = self._quarter_label(date)

                revenue = income_q.loc['Total Revenue', col] if 'Total Revenue' in income_q.index else None
                net_income = income_q.loc['Net Income', col] if 'Net Income' in income_q.index else None

                eps = None
                if 'Basic EPS' in income_q.index:
                    eps = income_q.loc['Basic EPS', col]
                elif 'Diluted EPS' in income_q.index:
                    eps = income_q.loc['Diluted EPS', col]

                total_assets = None
                total_liabilities = None
                if balance_q is not None and not balance_q.empty and col in balance_q.columns:
                    total_assets = balance_q.loc['Total Assets', col] if 'Total Assets' in balance_q.index else None
                    total_liabilities = balance_q.loc['Total Debt', col] if 'Total Debt' in balance_q.index else None

                rows.append({
                    'fiscal_quarter': label,
                    'market_cap': info.get('marketCap'),
                    'revenue': revenue,
                    'net_income': net_income,
                    'eps': eps,
                    'pe_ratio': info.get('trailingPE'),
                    'profit_margin': info.get('profitMargins'),
                    'debt_to_equity': info.get('debtToEquity'),
                    'total_assets': total_assets,
                    'total_liabilities': total_liabilities,
                    'source': 'yahoo_finance'
                })

            except Exception as e:
                self.logger.warning(f"Skipping column {col} for {ticker}: {e}")
                continue

        if not rows:
            return pd.DataFrame()

        self.logger.info(f"Fetched {len(rows)} quarters for {ticker}")
        return pd.DataFrame(rows)

    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate fundamentals data quality"""
        if df['market_cap'].dropna().lt(0).any():
            raise ValueError("Market cap cannot be negative")
        if df['revenue'].dropna().lt(0).any():
            raise ValueError("Revenue cannot be negative")

        self.logger.info("Fundamentals validation passed")
        return True

    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate average quality score across all rows"""
        score = 100.0
        if df['revenue'].isnull().all():
            score -= 30
        if df['net_income'].isnull().all():
            score -= 20
        if df['eps'].isnull().all():
            score -= 10
        if df['pe_ratio'].isnull().all():
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
