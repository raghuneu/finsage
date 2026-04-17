"""Fundamentals loader - fetches multi-quarter data from Yahoo Finance"""

import logging
import time

import yfinance as yf
import pandas as pd
from requests.exceptions import HTTPError, ConnectionError, Timeout
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception, before_sleep_log,
)

from .base_loader import BaseDataLoader

_logger = logging.getLogger(__name__)
_RETRY_EXCEPTIONS = (HTTPError, ConnectionError, Timeout)


class FundamentalsLoader(BaseDataLoader):
    """Load multi-quarter company fundamentals from Yahoo Finance"""

    @staticmethod
    def _quarter_label(date):
        """Convert a date to fiscal quarter label e.g. Q1 2024"""
        q = (date.month - 1) // 3 + 1
        return f"Q{q} {date.year}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception(lambda e: isinstance(e, _RETRY_EXCEPTIONS)),
        before_sleep=before_sleep_log(_logger, logging.WARNING),
    )
    def fetch_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """Fetch multi-quarter fundamentals from Yahoo Finance.

        Fetches both quarterly and annual statements, then merges to
        maximise historical depth (need 8+ quarters for YoY growth).
        """
        # yfinance rate-limit courtesy: 0.5s gap between ticker fetches
        time.sleep(0.5)
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info

        try:
            income_q = yf_ticker.quarterly_income_stmt
            balance_q = yf_ticker.quarterly_balance_sheet
        except Exception as e:
            self.logger.warning(f"Could not fetch quarterly statements for {ticker}: {e}")
            return pd.DataFrame()

        # Also fetch annual statements for additional history
        try:
            income_a = yf_ticker.income_stmt
            balance_a = yf_ticker.balance_sheet
        except Exception as e:
            self.logger.warning(f"Could not fetch annual statements for {ticker}: {e}")
            income_a = None
            balance_a = None

        if income_q is None or income_q.empty:
            self.logger.warning(f"No quarterly income data for {ticker}")
            return pd.DataFrame()

        rows = []
        seen_quarters = set()

        # First pass: quarterly data (more precise)
        for col in income_q.columns:
            try:
                date = pd.to_datetime(col)
                label = self._quarter_label(date)
                seen_quarters.add(label)

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

        # Second pass: derive quarterly approximations from annual data
        # for fiscal years not already covered by quarterly data.
        # Annual revenue / 4 gives a rough per-quarter figure — better
        # than nothing for YoY growth trend computation.
        if income_a is not None and not income_a.empty:
            for col in income_a.columns:
                try:
                    date = pd.to_datetime(col)
                    fy = date.year
                    # Generate Q1-Q4 labels for this fiscal year
                    for q in range(1, 5):
                        label = f"Q{q} {fy}"
                        if label in seen_quarters:
                            continue

                        revenue_annual = income_a.loc['Total Revenue', col] if 'Total Revenue' in income_a.index else None
                        net_income_annual = income_a.loc['Net Income', col] if 'Net Income' in income_a.index else None
                        eps_annual = None
                        if 'Basic EPS' in income_a.index:
                            eps_annual = income_a.loc['Basic EPS', col]
                        elif 'Diluted EPS' in income_a.index:
                            eps_annual = income_a.loc['Diluted EPS', col]

                        # Approximate quarterly values from annual
                        revenue_q = float(revenue_annual) / 4 if revenue_annual is not None and pd.notna(revenue_annual) else None
                        net_income_q = float(net_income_annual) / 4 if net_income_annual is not None and pd.notna(net_income_annual) else None
                        eps_q = float(eps_annual) / 4 if eps_annual is not None and pd.notna(eps_annual) else None

                        total_assets = None
                        total_liabilities = None
                        if balance_a is not None and not balance_a.empty and col in balance_a.columns:
                            total_assets = balance_a.loc['Total Assets', col] if 'Total Assets' in balance_a.index else None
                            total_liabilities = balance_a.loc['Total Debt', col] if 'Total Debt' in balance_a.index else None

                        rows.append({
                            'fiscal_quarter': label,
                            'market_cap': info.get('marketCap'),
                            'revenue': revenue_q,
                            'net_income': net_income_q,
                            'eps': eps_q,
                            'pe_ratio': info.get('trailingPE'),
                            'profit_margin': info.get('profitMargins'),
                            'debt_to_equity': info.get('debtToEquity'),
                            'total_assets': total_assets,
                            'total_liabilities': total_liabilities,
                            'source': 'yahoo_finance_annual_approx'
                        })
                        seen_quarters.add(label)

                except Exception as e:
                    self.logger.warning(f"Skipping annual column {col} for {ticker}: {e}")
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
