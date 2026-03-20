"""News loader - refactored from load_sample_news.py"""

import os
import httpx
import pandas as pd
import uuid
from .base_loader import BaseDataLoader

class NewsLoader(BaseDataLoader):
    """Load news articles from NewsAPI"""

    def __init__(self, sf_client):
        super().__init__(sf_client)
        self.api_key = os.getenv("NEWSAPI_KEY")
        if not self.api_key:
            self.logger.warning("⚠️  NEWSAPI_KEY not set - news loading will fail")

    def fetch_data(self, ticker: str, **kwargs) -> pd.DataFrame:
        """
        Fetch news with incremental loading
        Uses your exact pattern
        """
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

        # Fetch from API
        response = httpx.get(url)
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
        return ['ARTICLE_ID']

    def transform_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Add ticker and format timestamp"""
        df = super().transform_data(df, ticker)
        df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        return df