"""Load sample news data from NewsAPI into RAW table with quality checks"""

import os
from dotenv import load_dotenv
import httpx
import pandas as pd
from datetime import datetime
import uuid
from snowflake_connection import get_session

# NewsAPI configuration
load_dotenv()  # Load environment variables from .env file
API_KEY = os.getenv("NEWSAPI_KEY")  # Replace with your key
ticker_symbol = "AAPL"

def get_last_loaded_date(session, ticker):
    """Get the most recent published date we have for this ticker"""
    result = session.sql(f"""
        SELECT MAX(PUBLISHED_AT) as last_date 
        FROM RAW.RAW_NEWS 
        WHERE TICKER = '{ticker}'
    """).collect()
    
    if result and result[0]['LAST_DATE']:
        return result[0]['LAST_DATE']
    return None

def validate_news(df):
    """Validate news data quality"""
    if df['title'].isnull().any():
        raise ValueError("Title cannot be null")
    if df['url'].isnull().any():
        raise ValueError("URL cannot be null")
    if df['published_at'].isnull().any():
        raise ValueError("Published date cannot be null")
    print("News validation passed.")

def calculate_quality_score(df):
    """Calculate data quality score for news (0-100)"""
    score = 100.0
    
    # Deduct points for missing fields
    if df['title'].isnull().any():
        score -= 30
    if df['content'].isnull().any():
        score -= 10
    if df['author'].isnull().any():
        score -= 10
    if df['description'].isnull().any():
        score -= 10
        
    return score

# Create session
session = get_session()

# Check for incremental loading
last_date = get_last_loaded_date(session, ticker_symbol)

# Build query with date filter if incremental
query = f"{ticker_symbol} stock"
url = f"https://newsapi.org/v2/everything?q={query}&apiKey={API_KEY}&language=en&pageSize=10&sortBy=publishedAt"

if last_date:
    # Convert to string format for API
    from_date = last_date.strftime('%Y-%m-%d')
    url += f"&from={from_date}"
    print(f"Last loaded date: {last_date}, fetching incremental news...")
else:
    print("No existing news data, fetching recent articles...")

# Fetch news data
response = httpx.get(url)
data = response.json()

# Prepare data for Snowflake
articles = []
for article in data.get('articles', []):
    articles.append({
        'article_id': str(uuid.uuid4()),
        'ticker': ticker_symbol,
        'title': article.get('title'),
        'description': article.get('description'),
        'content': article.get('content'),
        'author': article.get('author'),
        'source_name': article.get('source', {}).get('name'),
        'url': article.get('url'),
        'published_at': article.get('publishedAt'),
        'ingested_at': pd.Timestamp.now()
    })

if not articles:
    print("No new articles found")
    session.close()
    exit()

df = pd.DataFrame(articles)

# Validate data
validate_news(df)

# Calculate quality score
df['data_quality_score'] = calculate_quality_score(df)

# Format timestamps
df['published_at'] = pd.to_datetime(df['published_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
df['ingested_at'] = pd.to_datetime(df['ingested_at']).dt.strftime('%Y-%m-%d %H:%M:%S')

df.columns = df.columns.str.upper()

# Create temporary staging table
session.sql("""
    CREATE TEMPORARY TABLE IF NOT EXISTS temp_news_staging LIKE RAW.RAW_NEWS
""").collect()

# Load to staging table
session.write_pandas(df, 'TEMP_NEWS_STAGING', auto_create_table=False, overwrite=True)

# MERGE from staging to raw
merge_sql = """
MERGE INTO RAW.RAW_NEWS target
USING TEMP_NEWS_STAGING source
ON target.ARTICLE_ID = source.ARTICLE_ID
WHEN MATCHED THEN 
    UPDATE SET 
        TITLE = source.TITLE,
        DESCRIPTION = source.DESCRIPTION,
        CONTENT = source.CONTENT,
        AUTHOR = source.AUTHOR,
        SOURCE_NAME = source.SOURCE_NAME,
        URL = source.URL,
        PUBLISHED_AT = source.PUBLISHED_AT,
        INGESTED_AT = source.INGESTED_AT,
        DATA_QUALITY_SCORE = source.DATA_QUALITY_SCORE
WHEN NOT MATCHED THEN
    INSERT (ARTICLE_ID, TICKER, TITLE, DESCRIPTION, CONTENT, AUTHOR, SOURCE_NAME, URL, PUBLISHED_AT, INGESTED_AT, DATA_QUALITY_SCORE)
    VALUES (source.ARTICLE_ID, source.TICKER, source.TITLE, source.DESCRIPTION, source.CONTENT, 
            source.AUTHOR, source.SOURCE_NAME, source.URL, source.PUBLISHED_AT, source.INGESTED_AT, source.DATA_QUALITY_SCORE)
"""

session.sql(merge_sql).collect()
print(f"✅ Merged {len(df)} news articles for {ticker_symbol}")

session.close()
