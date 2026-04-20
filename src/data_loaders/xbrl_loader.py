"""SEC XBRL structured data loader — loads financial concepts from SEC EDGAR companyfacts API.

Populates RAW.RAW_SEC_FILINGS which feeds stg_sec_filings -> fct_sec_financial_summary.
Ported from the legacy scripts/load_sec_data.py into the BaseDataLoader pattern.
"""

import json
import os
import time
from pathlib import Path

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from .base_loader import BaseDataLoader


class XBRLLoader(BaseDataLoader):
    """Load structured XBRL financial data from SEC EDGAR into RAW_SEC_FILINGS"""

    KEY_CONCEPTS = [
        # Revenue — companies report under different taxonomy concepts
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet',                  # legacy concept used by AAPL, WMT, HD, etc.
        'SalesRevenueGoodsNet',             # retail / manufacturing companies
        'RevenuesNetOfInterestExpense',     # banks: GS, JPM, BAC, C, MS, WFC
        # Income & EPS
        'NetIncomeLoss',
        'EarningsPerShareBasic',
        'EarningsPerShareDiluted',
        # Balance sheet
        'Assets',
        'Liabilities',
        'StockholdersEquity',
        # Operations
        'OperatingIncomeLoss',
        'GrossProfit',
        'CashAndCashEquivalentsAtCarryingValue',
        'ResearchAndDevelopmentExpense',
    ]

    VALID_PERIODS = {'Q1', 'Q2', 'Q3', 'FY'}

    def __init__(self, sf_client):
        super().__init__(sf_client)
        self.user_agent = os.getenv(
            'SEC_USER_AGENT', 'FinSage NEU vedanarayanan.s@northeastern.edu'
        )
        self.headers = {"User-Agent": self.user_agent}
        self.cik_cache = {}
        self.cik_cache_file = Path('config') / 'cik_cache.json'
        self._load_cik_cache()

    # ── CIK lookup ──────────────────────────────────────────

    def _load_cik_cache(self):
        if self.cik_cache_file.exists():
            try:
                with open(self.cik_cache_file) as f:
                    self.cik_cache = json.load(f)
            except Exception:
                pass

    def _save_cik_cache(self):
        try:
            self.cik_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cik_cache_file, 'w') as f:
                json.dump(self.cik_cache, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Could not save CIK cache: {e}")

    def _get_cik(self, ticker: str):
        ticker = ticker.upper()
        if ticker in self.cik_cache:
            return self.cik_cache[ticker]

        # Hardcoded fallbacks for common tickers
        fallback = {
            'AAPL': '0000320193',
            'MSFT': '0000789019',
            'GOOGL': '0001652044',
            'TSLA': '0001318605',
            'JPM': '0000019617',
        }
        if ticker in fallback:
            self.cik_cache[ticker] = fallback[ticker]
            self._save_cik_cache()
            return fallback[ticker]

        # Fetch from SEC
        try:
            url = 'https://www.sec.gov/files/company_tickers.json'
            resp = httpx.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                for item in resp.json().values():
                    t = item['ticker'].upper()
                    c = str(item['cik_str']).zfill(10)
                    self.cik_cache[t] = c
                self._save_cik_cache()
        except Exception as e:
            self.logger.warning(f"SEC ticker lookup failed: {e}")

        return self.cik_cache.get(ticker)

    # ── BaseDataLoader implementation ───────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def fetch_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """Fetch XBRL companyfacts from SEC EDGAR"""
        cik = self._get_cik(ticker)
        if not cik:
            self.logger.error(f"CIK not found for {ticker}")
            return pd.DataFrame()

        # Incremental: per-concept watermarks so newly-added concepts
        # aren't skipped by a global ticker-level watermark.
        concept_watermarks: dict[str, str] = {}
        try:
            rows = self.sf_client.session.sql(f"""
                SELECT CONCEPT, MAX(FILED_DATE) AS LAST_DATE
                FROM RAW.RAW_SEC_FILINGS
                WHERE TICKER = '{ticker}'
                GROUP BY CONCEPT
            """).collect()
            for row in rows:
                if row['LAST_DATE']:
                    concept_watermarks[row['CONCEPT']] = str(row['LAST_DATE'])
        except Exception:
            pass  # Table may not exist yet

        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        try:
            resp = httpx.get(url, headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.logger.error(f"Failed to fetch XBRL data for {ticker}: {e}")
            return pd.DataFrame()

        records = []
        us_gaap = data.get('facts', {}).get('us-gaap', {})

        # EPS concepts are reported in USD/shares, not USD
        EPS_CONCEPTS = {
            'EarningsPerShareBasic',
            'EarningsPerShareDiluted',
        }

        for concept in self.KEY_CONCEPTS:
            if concept not in us_gaap:
                continue

            concept_data = us_gaap[concept]
            label = concept_data.get('label', concept)

            # Pick correct unit key based on concept type
            unit_key = 'USD/shares' if concept in EPS_CONCEPTS else 'USD'
            entries = concept_data.get('units', {}).get(unit_key, [])

            # Per-concept watermark: only skip entries for concepts
            # that already have data loaded
            last_date = concept_watermarks.get(concept)

            for entry in entries:
                # Incremental: skip already-loaded records for THIS concept
                if last_date and entry.get('filed', '') <= last_date:
                    continue

                # Only quarterly and annual filings
                if entry.get('fp') not in self.VALID_PERIODS:
                    continue

                records.append({
                    'cik': cik,
                    'concept': concept,
                    'label': label,
                    'period_start': entry.get('start'),
                    'period_end': entry.get('end'),
                    'value': entry.get('val'),
                    'unit': unit_key,
                    'fiscal_year': entry.get('fy'),
                    'fiscal_period': entry.get('fp'),
                    'form_type': entry.get('form'),
                    'filed_date': entry.get('filed'),
                    'accession_no': entry.get('accn'),
                    'source': 'sec_edgar',
                })

        if records:
            self.logger.info(f"Fetched {len(records)} XBRL records for {ticker}")
        else:
            self.logger.warning(f"No new XBRL records for {ticker}")

        return pd.DataFrame(records) if records else pd.DataFrame()

    def validate_data(self, df: pd.DataFrame) -> bool:
        if df.empty:
            return False
        nulls = df[['concept', 'value', 'period_end']].isnull().any()
        if nulls.any():
            bad_cols = nulls[nulls].index.tolist()
            self.logger.warning(f"Null values found in required columns: {bad_cols}")
            # Drop rows with nulls in required columns instead of failing
            df.dropna(subset=['concept', 'value', 'period_end'], inplace=True)
            if df.empty:
                raise ValueError("All rows had null required fields")
        self.logger.info("XBRL data validation passed")
        return True

    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        score = 100.0
        if df['period_start'].isnull().any():
            score -= 10
        if df['fiscal_year'].isnull().any():
            score -= 20
        if df['accession_no'].isnull().any():
            score -= 10
        return score

    def get_target_table(self) -> str:
        return 'RAW.RAW_SEC_FILINGS'

    def get_merge_keys(self) -> list:
        return ['TICKER', 'CONCEPT', 'PERIOD_END', 'FISCAL_PERIOD']

    def transform_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        df = super().transform_data(df, ticker)
        # Format dates as strings for Snowflake
        for col in ['period_start', 'period_end', 'filed_date']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')
        df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        # Deduplicate on merge keys — keep latest filed record to prevent MERGE failures
        merge_keys = [k.lower() for k in self.get_merge_keys()]
        if 'filed_date' in df.columns:
            df = df.sort_values('filed_date', ascending=False).drop_duplicates(
                subset=merge_keys, keep='first'
            )
        return df
