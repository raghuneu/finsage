"""
SEC EDGAR Filing Loader - Dynamic CIK lookup
Reads tickers from config and fetches CIKs dynamically
"""

import requests
import time
import pandas as pd
from bs4 import BeautifulSoup
from .base_loader import BaseDataLoader
import os
from typing import Optional, Dict
import json
from pathlib import Path

class SECFilingLoader(BaseDataLoader):
    """Load SEC filings from EDGAR for LLM analysis"""

    def __init__(self, sf_client):
        super().__init__(sf_client)
        self.base_url = 'https://data.sec.gov'
        self.user_agent = os.getenv('SEC_USER_AGENT', 'University research@university.edu')
        self.headers = {
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
        }
        self.cik_cache = {}
        self.cik_cache_file = Path('config') / 'cik_cache.json'

        # Load cached CIKs if available
        self._load_cik_cache()

    def _load_cik_cache(self):
        """Load CIK cache from file if exists"""
        if self.cik_cache_file.exists():
            try:
                with open(self.cik_cache_file, 'r') as f:
                    self.cik_cache = json.load(f)
                self.logger.info(f"✓ Loaded {len(self.cik_cache)} CIKs from cache")
            except Exception as e:
                self.logger.warning(f"Could not load CIK cache: {e}")

    def _save_cik_cache(self):
        """Save CIK cache to file for reuse"""
        try:
            self.cik_cache_file.parent.mkdir(exist_ok=True)
            with open(self.cik_cache_file, 'w') as f:
                json.dump(self.cik_cache, f, indent=2)
            self.logger.info(f"✓ Saved {len(self.cik_cache)} CIKs to cache")
        except Exception as e:
            self.logger.warning(f"Could not save CIK cache: {e}")

    def get_cik(self, ticker: str) -> Optional[str]:
        """
        Get CIK for ticker - tries multiple methods

        Methods:
        1. Check local cache
        2. Fetch from SEC company tickers JSON
        3. Try alternate SEC endpoint
        4. Search SEC website directly

        Returns:
            CIK string or None if not found
        """
        ticker = ticker.upper()

        # Method 1: Check cache
        if ticker in self.cik_cache:
            self.logger.info(f"CIK for {ticker}: {self.cik_cache[ticker]} (cached)")
            return self.cik_cache[ticker]

        # Method 2: Fetch from SEC JSON endpoint
        try:
            url = 'https://www.sec.gov/files/company_tickers.json'
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Build cache from response
                for item in data.values():
                    t = item['ticker'].upper()
                    c = str(item['cik_str']).zfill(10)
                    self.cik_cache[t] = c

                # Save cache for future use
                self._save_cik_cache()

                if ticker in self.cik_cache:
                    self.logger.info(f"CIK for {ticker}: {self.cik_cache[ticker]} (fetched)")
                    return self.cik_cache[ticker]

        except Exception as e:
            self.logger.warning(f"SEC JSON endpoint failed: {e}")

        # Method 3: Try SEC search (more reliable but slower)
        try:
            search_url = f'https://www.sec.gov/cgi-bin/browse-edgar'
            params = {
                'action': 'getcompany',
                'CIK': ticker,
                'type': '10-K',
                'dateb': '',
                'owner': 'exclude',
                'count': '1',
                'output': 'atom'
            }

            response = requests.get(search_url, params=params, headers=self.headers, timeout=10)

            if response.status_code == 200:
                # Parse XML to extract CIK
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.text)

                # Find CIK in the response
                for elem in root.iter():
                    if 'cik' in elem.tag.lower():
                        cik = elem.text.strip().zfill(10)
                        self.cik_cache[ticker] = cik
                        self._save_cik_cache()
                        self.logger.info(f"CIK for {ticker}: {cik} (searched)")
                        return cik

        except Exception as e:
            self.logger.warning(f"SEC search failed: {e}")

        # Method 4: Hardcoded fallback for common stocks
        common_ciks = {
            'AAPL': '0000320193',
            'MSFT': '0000789019',
            'GOOGL': '0001652044'
        }

        if ticker in common_ciks:
            cik = common_ciks[ticker]
            self.cik_cache[ticker] = cik
            self._save_cik_cache()
            self.logger.info(f"CIK for {ticker}: {cik} (fallback)")
            return cik

        self.logger.error(f"❌ Could not find CIK for {ticker}")
        return None

    def fetch_data(self, ticker: str, form_types=None, max_filings=3, **kwargs) -> pd.DataFrame:
        """Fetch recent SEC filings for a ticker"""
        if form_types is None:
            form_types = ['10-K', '10-Q']

        # Get CIK
        cik = self.get_cik(ticker)
        if not cik:
            self.logger.error(f"Cannot fetch SEC data for {ticker} - CIK not found")
            return pd.DataFrame()

        # Get submissions
        url = f'{self.base_url}/submissions/CIK{cik}.json'

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch submissions for {ticker}: {e}")
            return pd.DataFrame()

        company_name = data.get('name', ticker)
        recent = data.get('filings', {}).get('recent', {})

        if not recent or not recent.get('form'):
            self.logger.warning(f"No recent filings found for {ticker}")
            return pd.DataFrame()

        # Parse filings
        filings = []
        for i in range(len(recent['form'])):
            if recent['form'][i] in form_types:
                filing = {
                    'cik': cik,
                    'company_name': company_name,
                    'form_type': recent['form'][i],
                    'filing_date': recent['filingDate'][i],
                    'report_date': recent['reportDate'][i],
                    'accession_number': recent['accessionNumber'][i],
                    'primary_document': recent['primaryDocument'][i],
                }

                # Fetch full text
                self.logger.info(f"  Fetching {filing['form_type']} from {filing['filing_date']}...")
                filing_text = self._fetch_filing_text(
                    cik, filing['accession_number'], filing['primary_document']
                )

                if filing_text:
                    filing['filing_text'] = filing_text
                    filings.append(filing)
                else:
                    self.logger.warning(f"  Skipping - could not fetch text")

                if len(filings) >= max_filings:
                    break

                time.sleep(0.3)  # Be respectful with rate limiting

        if not filings:
            self.logger.warning(f"No valid filings fetched for {ticker}")
            return pd.DataFrame()

        return pd.DataFrame(filings)

    def _fetch_filing_text(self, cik: str, accession: str, document: str) -> Optional[str]:
        """Fetch full text of a filing with error handling"""
        try:
            accession_no_dashes = accession.replace('-', '')
            url = f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{document}'

            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style
            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text(separator='\n', strip=True)

            # Limit size for Snowflake VARIANT (16MB max, but keep reasonable)
            return text[:500000]  # 500KB

        except Exception as e:
            self.logger.error(f"Failed to fetch filing text: {e}")
            return None

    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate SEC filing data"""
        if df.empty:
            self.logger.warning("No data to validate")
            return False

        if 'filing_text' not in df.columns:
            self.logger.error("filing_text column missing")
            return False

        if df['filing_text'].isnull().any():
            null_count = df['filing_text'].isnull().sum()
            self.logger.warning(f"{null_count} filings have NULL text")
            # Don't fail - just filter them out
            return True

        min_length = df['filing_text'].str.len().min()
        if min_length < 1000:
            self.logger.warning(f"Short filing detected: {min_length} chars")

        self.logger.info("✓ SEC filing validation passed")
        return True

    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Quality score based on completeness"""
        if df.empty:
            return 0.0

        score = 100.0

        # Check average text length
        avg_length = df['filing_text'].str.len().mean()

        # Typical 10-K: 100K-500K chars, 10-Q: 50K-200K chars
        if avg_length < 10000:
            score -= 40
        elif avg_length < 50000:
            score -= 20

        # Check for nulls
        null_pct = df['filing_text'].isnull().sum() / len(df) * 100
        score -= null_pct * 0.5

        return max(score, 0.0)

    def get_target_table(self) -> str:
        return 'RAW.RAW_SEC_FILING_TEXT'  # ← NEW TABLE NAME

    def get_merge_keys(self) -> list:
        return ['TICKER', 'ACCESSION_NUMBER']  # ← Simple key

    def transform_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Transform to match RAW_SEC_FILING_TEXT schema"""
        if df.empty:
            return df

        df = super().transform_data(df, ticker)
        df = df[df['filing_text'].notna()].copy()

        if df.empty:
            return df

        # Format dates
        df['filing_date'] = pd.to_datetime(df['filing_date']).dt.strftime('%Y-%m-%d')
        df['report_date'] = pd.to_datetime(df['report_date']).dt.strftime('%Y-%m-%d')
        df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')

        # Extract fiscal info from report date
        df['fiscal_year'] = pd.to_datetime(df['report_date']).dt.year
        df['fiscal_period'] = df['form_type']  # "10-K" or "10-Q"

        # Build filing URL for reference
        df['filing_url'] = df.apply(
            lambda row: f"https://www.sec.gov/cgi-bin/viewer?action=view&cik={row['cik']}&accession_number={row['accession_number']}&xbrl_type=v",
            axis=1
        )

        df['source'] = 'sec_edgar'

        return df