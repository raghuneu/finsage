"""News loader - refactored from load_sample_news.py"""

import logging
import os
import time

import httpx
import pandas as pd
import uuid
from requests.exceptions import HTTPError, ConnectionError, Timeout
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception, before_sleep_log,
)

from .base_loader import BaseDataLoader

_logger = logging.getLogger(__name__)
_NEWS_RETRY_EXCEPTIONS = (HTTPError, ConnectionError, Timeout, httpx.HTTPError)


class NewsLoader(BaseDataLoader):
    """Load news articles from NewsAPI"""

    _last_request_ts = 0.0  # class-level rate limiter (5 req/min = 0.2s gap)

    def __init__(self, sf_client):
        super().__init__(sf_client)
        self.api_key = os.getenv("NEWSAPI_KEY")
        if not self.api_key:
            self.logger.warning("⚠️  NEWSAPI_KEY not set - news loading will fail")

    def _rate_limit(self):
        gap = time.monotonic() - NewsLoader._last_request_ts
        if gap < 0.2:
            time.sleep(0.2 - gap)
        NewsLoader._last_request_ts = time.monotonic()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception(lambda e: isinstance(e, _NEWS_RETRY_EXCEPTIONS)),
        before_sleep=before_sleep_log(_logger, logging.WARNING),
    )
    def fetch_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """
        Fetch news with incremental loading.
        Uses URL-based deduplication via MERGE on TICKER+URL.
        """
        if not self.api_key:
            self.logger.warning("NEWSAPI_KEY not set — skipping news fetch")
            return pd.DataFrame()

        # Check last loaded date
        last_date = self.sf_client.get_last_loaded_date(
            'RAW.RAW_NEWS', ticker, 'PUBLISHED_AT'
        )

        # Build query
        query = f"{ticker} stock"
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={self.api_key}&language=en&pageSize=10&sortBy=publishedAt"

        if last_date:
            from_date = last_date.strftime('%Y-%m-%d')
            url += f"&from={from_date}"
            self.logger.info(f"Incremental load from {from_date}")
        else:
            self.logger.info("Initial load - fetching recent articles")

        # Fetch from API with timeout (rate-limited: 5 req/min)
        self._rate_limit()
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Parse articles (your exact structure)
        articles = []
        for article in data.get('articles', []):
            articles.append({
                'article_id': str(uuid.uuid4()),
                'title': article.get('title'),
                'description': article.get('description'),
                'content': article.get('content'),
                'author': article.get('author'),
                'source_name': article.get('source', {}).get('name'),
                'url': article.get('url'),
                'published_at': article.get('publishedAt')
            })

        if not articles:
            return pd.DataFrame()

        df = pd.DataFrame(articles)

        # Format timestamps
        df['published_at'] = pd.to_datetime(df['published_at']).dt.strftime('%Y-%m-%d %H:%M:%S')

        return df

    def validate_data(self, df: pd.DataFrame) -> bool:
        """Your exact validation"""
        if df['title'].isnull().any():
            raise ValueError("Title cannot be null")
        if df['url'].isnull().any():
            raise ValueError("URL cannot be null")
        if df['published_at'].isnull().any():
            raise ValueError("Published date cannot be null")

        self.logger.info("✓ News validation passed")
        return True

    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Your exact quality scoring"""
        score = 100.0

        if df['title'].isnull().any():
            score -= 30
        if df['content'].isnull().any():
            score -= 10
        if df['author'].isnull().any():
            score -= 10
        if df['description'].isnull().any():
            score -= 10

        return score

    def get_target_table(self) -> str:
        return 'RAW.RAW_NEWS'

    def get_merge_keys(self) -> list:
        return ['TICKER', 'URL']

    def transform_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Add ticker and format timestamp"""
        df = super().transform_data(df, ticker)
        df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        return df