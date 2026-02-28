"""Load SEC EDGAR financial data into RAW table"""

import httpx
import pandas as pd
from snowflake_connection import get_session

# Company mapping: ticker → CIK
COMPANY_MAP = {
    'AAPL': '0000320193',
    'TSLA': '0001318605',
    'MSFT': '0000789019',
    'JPM':  '0000019617',
    'GOOGL': '0001652044'
}

# Key financial concepts to collect
KEY_CONCEPTS = [
    'Revenues',
    'NetIncomeLoss',
    'EarningsPerShareBasic',
    'EarningsPerShareDiluted',
    'Assets',
    'Liabilities',
    'StockholdersEquity',
    'OperatingIncomeLoss',
    'GrossProfit',
    'ResearchAndDevelopmentExpense'
]

HEADERS = {"User-Agent": "finsage testemail@northeastern.edu"}

def get_last_loaded_date(session, ticker):
    """Get most recent filing date for incremental loading"""
    result = session.sql(f"""
        SELECT MAX(FILED_DATE) as last_date
        FROM RAW.RAW_SEC_FILINGS
        WHERE TICKER = '{ticker}'
    """).collect()
    
    if result and result[0]['LAST_DATE']:
        return result[0]['LAST_DATE']
    return None

def validate_sec_data(df):
    """Validate SEC data quality"""
    if df['concept'].isnull().any():
        raise ValueError("Concept cannot be null")
    if df['value'].isnull().any():
        raise ValueError("Value cannot be null")
    if df['period_end'].isnull().any():
        raise ValueError("Period end cannot be null")
    print("SEC data validation passed.")

def calculate_quality_score(df):
    """Calculate quality score for SEC data"""
    score = 100.0
    if df['period_start'].isnull().any():
        score -= 10
    if df['fiscal_year'].isnull().any():
        score -= 20
    if df['accession_no'].isnull().any():
        score -= 10
    return score

def fetch_sec_data(ticker, cik, last_date=None):
    """Fetch financial data from SEC EDGAR"""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    response = httpx.get(url, headers=HEADERS)
    data = response.json()
    
    records = []
    us_gaap = data.get('facts', {}).get('us-gaap', {})
    
    for concept in KEY_CONCEPTS:
        if concept not in us_gaap:
            continue
            
        concept_data = us_gaap[concept]
        label = concept_data.get('label', concept)
        entries = concept_data.get('units', {}).get('USD', [])
        
        for entry in entries:
            # Incremental loading: skip old records
            if last_date and entry.get('filed', '') <= str(last_date):
                continue
                
            # Only quarterly and annual filings
            if entry.get('fp') not in ['Q1', 'Q2', 'Q3', 'FY']:
                continue
                
            records.append({
                'ticker': ticker,
                'cik': cik,
                'concept': concept,
                'label': label,
                'period_start': entry.get('start'),
                'period_end': entry.get('end'),
                'value': entry.get('val'),
                'unit': 'USD',
                'fiscal_year': entry.get('fy'),
                'fiscal_period': entry.get('fp'),
                'form_type': entry.get('form'),
                'filed_date': entry.get('filed'),
                'accession_no': entry.get('accn'),
                'source': 'sec_edgar',
                'ingested_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    
    return records

# Main execution
session = get_session()
ticker_symbol = 'AAPL'
cik = COMPANY_MAP[ticker_symbol]

# Incremental loading
last_date = get_last_loaded_date(session, ticker_symbol)
if last_date:
    print(f"Last loaded date: {last_date}, fetching incremental data...")
else:
    print("No existing data, fetching full history...")

# Fetch data
records = fetch_sec_data(ticker_symbol, cik, last_date)

if not records:
    print("No new records found")
    session.close()
    exit()

df = pd.DataFrame(records)

# Validate
validate_sec_data(df)

# Quality score
df['data_quality_score'] = calculate_quality_score(df)

# Format dates
df['period_start'] = pd.to_datetime(df['period_start'], errors='coerce').dt.strftime('%Y-%m-%d')
df['period_end'] = pd.to_datetime(df['period_end'], errors='coerce').dt.strftime('%Y-%m-%d')
df['filed_date'] = pd.to_datetime(df['filed_date'], errors='coerce').dt.strftime('%Y-%m-%d')

df.columns = df.columns.str.upper()

# Create staging table
session.sql("DROP TABLE IF EXISTS TEMP_SEC_STAGING").collect()
session.sql("CREATE TEMPORARY TABLE TEMP_SEC_STAGING LIKE RAW.RAW_SEC_FILINGS").collect()

# Load to staging
session.write_pandas(df, 'TEMP_SEC_STAGING', auto_create_table=False, overwrite=True)

# MERGE
merge_sql = """
MERGE INTO RAW.RAW_SEC_FILINGS target
USING TEMP_SEC_STAGING source
ON target.TICKER = source.TICKER 
   AND target.CONCEPT = source.CONCEPT 
   AND target.PERIOD_END = source.PERIOD_END 
   AND target.FISCAL_PERIOD = source.FISCAL_PERIOD
WHEN MATCHED THEN
    UPDATE SET
        VALUE = source.VALUE,
        FILED_DATE = source.FILED_DATE,
        INGESTED_AT = source.INGESTED_AT,
        DATA_QUALITY_SCORE = source.DATA_QUALITY_SCORE
WHEN NOT MATCHED THEN
    INSERT (TICKER, CIK, CONCEPT, LABEL, PERIOD_START, PERIOD_END, VALUE, UNIT,
            FISCAL_YEAR, FISCAL_PERIOD, FORM_TYPE, FILED_DATE, ACCESSION_NO, 
            SOURCE, INGESTED_AT, DATA_QUALITY_SCORE)
    VALUES (source.TICKER, source.CIK, source.CONCEPT, source.LABEL, 
            source.PERIOD_START, source.PERIOD_END, source.VALUE, source.UNIT,
            source.FISCAL_YEAR, source.FISCAL_PERIOD, source.FORM_TYPE, 
            source.FILED_DATE, source.ACCESSION_NO, source.SOURCE, 
            source.INGESTED_AT, source.DATA_QUALITY_SCORE)
"""

session.sql(merge_sql).collect()
print(f"✅ Loaded {len(df)} SEC records for {ticker_symbol}")
session.close()