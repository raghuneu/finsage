"""
SEC EDGAR Filing Loader
CRITICAL: Loads 10-K and 10-Q full text for LLM analysis
"""

import requests
import time
import pandas as pd
from bs4 import BeautifulSoup
from .base_loader import BaseDataLoader
import os

class SECFilingLoader(BaseDataLoader):
    """Load SEC filings from EDGAR for LLM analysis"""

    def __init__(self, sf_client):
        super().__init__(sf_client)
        self.base_url = 'https://data.sec.gov'
        self.user_agent = os.getenv('SEC_USER_AGENT', 'University research@university.edu')
        self.headers = {'User-Agent': self.user_agent}
        self.cik_cache = {}

    def get_cik(self, ticker: str) -> str:
        """Convert ticker to CIK (SEC company ID)"""
        if ticker in self.cik_cache:
            return self.cik_cache[ticker]

        url = f'{self.base_url}/files/company_tickers.json'
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        data = response.json()
        for item in data.values():
            if item['ticker'].upper() == ticker.upper():
                cik = str(item['cik_str']).zfill(10)
                self.cik_cache[ticker] = cik
                self.logger.info(f"CIK for {ticker}: {cik}")
                return cik

        raise ValueError(f"CIK not found for {ticker}")

    def fetch_data(self, ticker: str, form_types=None, max_filings=3, **kwargs) -> pd.DataFrame:
        """
        Fetch recent SEC filings

        Args:
            ticker: Stock ticker
            form_types: List of form types (default: ['10-K', '10-Q'])
            max_filings: Maximum number of filings to fetch
        """
        if form_types is None:
            form_types = ['10-K', '10-Q']

        cik = self.get_cik(ticker)

        # Get submissions index
        url = f'{self.base_url}/submissions/CIK{cik}.json'
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        data = response.json()
        company_name = data['name']
        recent = data['filings']['recent']

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
                filing['filing_text'] = self._fetch_filing_text(
                    cik, filing['accession_number'], filing['primary_document']
                )

                filings.append(filing)

                if len(filings) >= max_filings:
                    break

                time.sleep(0.2)  # SEC rate limiting

        return pd.DataFrame(filings)

    def _fetch_filing_text(self, cik: str, accession: str, document: str) -> str:
        """Fetch full text of a filing"""
        accession_no_dashes = accession.replace('-', '')
        url = f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{document}'

        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        # Parse HTML and extract text
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text(separator='\n', strip=True)

        # Limit size (Snowflake VARIANT max 16MB, but we'll keep it reasonable)
        # Average 10-K is 100K-300K chars
        return text[:500000]  # 500K chars max

    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate SEC filing data"""
        if df['filing_text'].isnull().any():
            raise ValueError("NULL filing text detected")

        # Check minimum text length
        min_length = df['filing_text'].str.len().min()
        if min_length < 1000:
            self.logger.warning(f"Short filing detected: {min_length} chars")

        self.logger.info("✓ SEC filing validation passed")
        return True

    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Quality score based on completeness"""
        score = 100.0

        avg_length = df['filing_text'].str.len().mean()

        # Typical 10-K is 100K-500K chars
        if avg_length < 10000:
            score -= 40
        elif avg_length < 50000:
            score -= 20

        return score

    def get_target_table(self) -> str:
        return 'RAW.RAW_SEC_FILINGS'

    def get_merge_keys(self) -> list:
        return ['TICKER', 'ACCESSION_NUMBER']

    def transform_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Format dates and timestamps"""
        df = super().transform_data(df, ticker)
        df['filing_date'] = pd.to_datetime(df['filing_date']).dt.strftime('%Y-%m-%d')
        df['report_date'] = pd.to_datetime(df['report_date']).dt.strftime('%Y-%m-%d')
        df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df['source'] = 'sec_edgar'
        return df