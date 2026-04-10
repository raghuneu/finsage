"""Load multi-quarter fundamentals data from Yahoo Finance into RAW table with quality checks"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from snowflake_connection import get_session

TICKERS = ["AAPL", "MSFT", "TSLA"]

def validate_fundamentals(df):
    """Validate fundamentals data quality"""
    if (df['market_cap'].dropna() < 0).any():
        raise ValueError("Market cap cannot be negative")
    if (df['revenue'].dropna() < 0).any():
        raise ValueError("Revenue cannot be negative")
    print("Fundamentals validation passed.")

def calculate_quality_score(row):
    """Calculate data quality score for a single row (0-100)"""
    score = 100.0
    if pd.isnull(row.get('revenue')):      score -= 30
    if pd.isnull(row.get('net_income')):   score -= 20
    if pd.isnull(row.get('eps')):          score -= 10
    if pd.isnull(row.get('pe_ratio')):     score -= 10
    return score

def quarter_label(date):
    """Convert a date to fiscal quarter label e.g. Q1 2024"""
    q = (date.month - 1) // 3 + 1
    return f"Q{q} {date.year}"

def fetch_fundamentals(ticker_symbol: str) -> pd.DataFrame:
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info

    # Pull quarterly income statement + balance sheet
    try:
        income_q = ticker.quarterly_income_stmt
        balance_q = ticker.quarterly_balance_sheet
    except Exception as e:
        print(f"⚠️  Could not fetch quarterly statements for {ticker_symbol}: {e}")
        return pd.DataFrame()

    if income_q is None or income_q.empty:
        print(f"⚠️  No quarterly income data for {ticker_symbol}")
        return pd.DataFrame()

    rows = []
    for col in income_q.columns:
        try:
            date = pd.to_datetime(col)
            label = quarter_label(date)

            revenue = income_q.loc['Total Revenue', col] if 'Total Revenue' in income_q.index else None
            net_income = income_q.loc['Net Income', col] if 'Net Income' in income_q.index else None

            # EPS from income statement if available, else trailing from info
            eps = None
            if 'Basic EPS' in income_q.index:
                eps = income_q.loc['Basic EPS', col]
            elif 'Diluted EPS' in income_q.index:
                eps = income_q.loc['Diluted EPS', col]

            # Balance sheet items
            total_assets = None
            total_liabilities = None
            if balance_q is not None and not balance_q.empty and col in balance_q.columns:
                total_assets = balance_q.loc['Total Assets', col] if 'Total Assets' in balance_q.index else None
                total_liabilities = balance_q.loc['Total Debt', col] if 'Total Debt' in balance_q.index else None

            row = {
                'ticker': ticker_symbol,
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
                'source': 'yahoo_finance',
                'ingested_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            row['data_quality_score'] = calculate_quality_score(row)
            rows.append(row)

        except Exception as e:
            print(f"⚠️  Skipping column {col} for {ticker_symbol}: {e}")
            continue

    df = pd.DataFrame(rows)
    print(f"  Fetched {len(df)} quarters for {ticker_symbol}")
    return df


def load_fundamentals():
    session = get_session()

    for ticker_symbol in TICKERS:
        print(f"\nProcessing {ticker_symbol}...")

        df = fetch_fundamentals(ticker_symbol)
        if df.empty:
            print(f"  ⚠️  No data for {ticker_symbol}, skipping")
            continue

        validate_fundamentals(df)
        df.columns = df.columns.str.upper()

        # Recreate temp staging table
        session.sql("DROP TABLE IF EXISTS TEMP_FUNDAMENTALS_STAGING").collect()
        session.sql("CREATE TEMPORARY TABLE TEMP_FUNDAMENTALS_STAGING LIKE RAW.RAW_FUNDAMENTALS").collect()

        session.write_pandas(df, 'TEMP_FUNDAMENTALS_STAGING', auto_create_table=False, overwrite=True)

        merge_sql = """
        MERGE INTO RAW.RAW_FUNDAMENTALS target
        USING TEMP_FUNDAMENTALS_STAGING source
        ON target.TICKER = source.TICKER AND target.FISCAL_QUARTER = source.FISCAL_QUARTER
        WHEN MATCHED THEN
            UPDATE SET
                MARKET_CAP = source.MARKET_CAP,
                REVENUE = source.REVENUE,
                NET_INCOME = source.NET_INCOME,
                EPS = source.EPS,
                PE_RATIO = source.PE_RATIO,
                PROFIT_MARGIN = source.PROFIT_MARGIN,
                DEBT_TO_EQUITY = source.DEBT_TO_EQUITY,
                TOTAL_ASSETS = source.TOTAL_ASSETS,
                TOTAL_LIABILITIES = source.TOTAL_LIABILITIES,
                INGESTED_AT = source.INGESTED_AT,
                DATA_QUALITY_SCORE = source.DATA_QUALITY_SCORE
        WHEN NOT MATCHED THEN
            INSERT (TICKER, FISCAL_QUARTER, MARKET_CAP, REVENUE, NET_INCOME, EPS, PE_RATIO,
                    PROFIT_MARGIN, DEBT_TO_EQUITY, TOTAL_ASSETS, TOTAL_LIABILITIES, SOURCE,
                    INGESTED_AT, DATA_QUALITY_SCORE)
            VALUES (source.TICKER, source.FISCAL_QUARTER, source.MARKET_CAP, source.REVENUE,
                    source.NET_INCOME, source.EPS, source.PE_RATIO, source.PROFIT_MARGIN,
                    source.DEBT_TO_EQUITY, source.TOTAL_ASSETS, source.TOTAL_LIABILITIES,
                    source.SOURCE, source.INGESTED_AT, source.DATA_QUALITY_SCORE)
        """
        session.sql(merge_sql).collect()
        print(f"  ✅ Merged {len(df)} quarters for {ticker_symbol}")

    session.close()
    print("\n✅ All fundamentals loaded.")


if __name__ == "__main__":
    load_fundamentals()
