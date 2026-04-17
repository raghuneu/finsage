---
name: sec-filing-pipeline
description: FinSage SEC EDGAR and AWS Bedrock integration — filing downloads, text extraction, knowledge base RAG, and guardrails
---

# SEC Filing Pipeline Guide

Reference for the SEC EDGAR data acquisition and AWS Bedrock analysis pipeline in FinSage.

## Pipeline Architecture

```
SEC EDGAR API                     AWS S3                      AWS Bedrock
├── Submissions API          →    sec-filings/                ├── Knowledge Base (RAG)
│   (company metadata)            ├── {CIK}/                  ├── Guardrails
├── Filing Documents API     →    │   ├── 10-K/               └── Multi-Model Inference
│   (filing downloads)            │   └── 10-Q/
└── XBRL CompanyFacts API    →    └── xbrl/
    (structured financials)
                                        ↓
                              Snowflake RAW tables
                              ├── RAW_SEC_FILINGS
                              ├── RAW_SEC_FILING_DOCUMENTS
                              └── RAW_SEC_FILING_TEXT
```

## SEC EDGAR API Patterns

### Rate Limits

SEC EDGAR requires:
- **10 requests per second** maximum
- **User-Agent header** with contact email (required by SEC fair use policy)
- No authentication needed

```python
HEADERS = {
    "User-Agent": "FinSage Pipeline contact@example.com",
    "Accept": "application/json"
}
```

### CIK Resolution

Tickers must be resolved to CIK (Central Index Key) numbers:

```python
# CIK lookup cascade:
# 1. Check local cache (config/cik_mapping.json)
# 2. Query SEC company tickers endpoint
# 3. Search SEC EDGAR full-text search

CIK_MAPPING = {
    "AAPL": "0000320193",
    "GOOGL": "0001652044",
    "JPM": "0000019617",
    "MSFT": "0000789019",
    "TSLA": "0001318605",
}
```

### Submissions API

```python
def fetch_submissions(cik: str) -> dict:
    """Fetch company filing history from SEC EDGAR."""
    url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    response = rate_limited_request(url)
    return response.json()

# Response contains:
# - entityType, name, tickers
# - filings.recent: {accessionNumber, filingDate, form, primaryDocument, ...}
# - filings.files: links to older filing pages
```

### XBRL CompanyFacts API

```python
def fetch_xbrl_facts(cik: str) -> dict:
    """Fetch structured financial data from XBRL API."""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
    response = rate_limited_request(url)
    return response.json()

# Response contains:
# - facts.us-gaap: {Revenue, NetIncomeLoss, Assets, ...}
# - Each fact has: units (USD, shares), quarterly values, filing references
```

### Filing Document Download

```python
def download_filing(accession: str, document: str) -> bytes:
    """Download a specific filing document."""
    accession_clean = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{document}"
    response = rate_limited_request(url)
    return response.content
```

## Text Extraction Pipeline

**Files**: `scripts/sec_filings/` (6 files)

1. **Download** filing HTML/XML from EDGAR
2. **Extract** text content (strip HTML tags, normalize whitespace)
3. **Upload** to S3 for Bedrock Knowledge Base ingestion
4. **Store** extracted text in `RAW_SEC_FILING_TEXT` table

```python
# Text extraction flow
html_content = download_filing(accession, primary_document)
clean_text = extract_text_from_html(html_content)  # BeautifulSoup + regex
s3_key = f"sec-filings/{cik}/{filing_type}/{accession}.txt"
upload_to_s3(clean_text, bucket, s3_key)
```

## AWS Bedrock Integration

### Knowledge Base RAG

The Bedrock Knowledge Base indexes SEC filing texts from S3:

```python
import boto3

bedrock_agent = boto3.client("bedrock-agent-runtime")

def retrieve_from_kb(query: str, kb_id: str, top_k: int = 5) -> list:
    """Retrieve relevant filing passages for a query."""
    response = bedrock_agent.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": top_k}
        }
    )
    return response["retrievalResults"]

def ask_kb(question: str, kb_id: str) -> str:
    """Ask a question with RAG over SEC filings."""
    response = bedrock_agent.retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet"
            }
        }
    )
    return response["output"]["text"]
```

### Cross-Ticker Analysis

```python
def cross_ticker_analysis(tickers: list, question: str, kb_id: str) -> dict:
    """Compare SEC filings across multiple tickers."""
    results = {}
    for ticker in tickers:
        scoped_query = f"For {ticker}: {question}"
        results[ticker] = ask_kb(scoped_query, kb_id)
    return results
```

### Guardrails

Bedrock Guardrails enforce content safety and grounding:

```python
bedrock_runtime = boto3.client("bedrock-runtime")

def invoke_with_guardrails(prompt: str, model_id: str, guardrail_id: str) -> str:
    """Invoke model with content safety guardrails."""
    response = bedrock_runtime.invoke_model(
        modelId=model_id,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000
        }),
        guardrailIdentifier=guardrail_id,
        guardrailVersion="DRAFT"
    )
    return json.loads(response["body"].read())
```

Guardrails check for:
- **Content safety**: No harmful financial advice framing
- **Grounding**: Responses must be grounded in retrieved SEC data
- **PII filtering**: Removes personal information from outputs

### Multi-Model Comparison

```python
MODELS = [
    "anthropic.claude-3-sonnet",
    "anthropic.claude-3-haiku",
    "amazon.titan-text-express-v1"
]

def multi_model_analysis(prompt: str) -> dict:
    """Get analysis from multiple models for consensus."""
    results = {}
    for model in MODELS:
        results[model] = invoke_with_guardrails(prompt, model, guardrail_id)
    return results
```

## Data Loader Integration

### SecLoader (`src/data_loaders/sec_loader.py`)

Fetches filing metadata and stores in RAW_SEC_FILINGS:

| Column | Type | Source |
|--------|------|--------|
| ACCESSION_NUMBER | VARCHAR | submissions API |
| TICKER | VARCHAR | config/tickers.yaml |
| FILING_TYPE | VARCHAR | 10-K, 10-Q, 8-K |
| FILING_DATE | DATE | submissions API |
| PRIMARY_DOCUMENT | VARCHAR | submissions API |
| SOURCE | VARCHAR | "sec_edgar" |
| INGESTED_AT | TIMESTAMP | Pipeline timestamp |

### XbrlLoader (`src/data_loaders/xbrl_loader.py`)

Fetches structured financial data and enriches RAW_SEC_FILINGS:

| Column | Type | Source |
|--------|------|--------|
| TICKER | VARCHAR | config/tickers.yaml |
| METRIC_NAME | VARCHAR | us-gaap taxonomy (Revenue, NetIncome, etc.) |
| VALUE | FLOAT | XBRL fact value |
| PERIOD_END | DATE | XBRL period reference |
| FILING_TYPE | VARCHAR | Derived from period length |

## Downstream Flow

```
RAW_SEC_FILINGS + RAW_SEC_FILING_TEXT
    → stg_sec_filings (dbt staging: validation + filtering)
    → fct_sec_financial_summary (dbt analytics: FINANCIAL_HEALTH derivation)
    → analysis_agent.py (cross-referencing with Bedrock KB)
    → report_agent.py (SEC section in PDF)
    → Streamlit SEC Analysis page
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| 403 from SEC EDGAR | Missing User-Agent header | Add required header |
| Rate limit (429) | >10 req/s | Check rate limiter, add sleep |
| Empty XBRL facts | Company not in us-gaap taxonomy | Check entity type, try ifrs |
| Bedrock KB stale | S3 files updated but KB not synced | Trigger KB sync job |
| Guardrail blocks | Overly restrictive content filter | Review guardrail config |
