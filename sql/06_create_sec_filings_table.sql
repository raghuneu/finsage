-- Create SEC filings table for storing 10-K and 10-Q full text
-- CRITICAL for LLM analysis phase

CREATE TABLE IF NOT EXISTS RAW.RAW_SEC_FILINGS (
    ticker VARCHAR(10),
    cik VARCHAR(10),
    company_name VARCHAR(200),
    form_type VARCHAR(10),
    filing_date DATE,
    report_date DATE,
    accession_number VARCHAR(30),
    primary_document VARCHAR(200),
    filing_text VARIANT,  -- Stores large text as JSON/string
    source VARCHAR(50) DEFAULT 'sec_edgar',
    ingested_at TIMESTAMP,
    data_quality_score FLOAT DEFAULT 100.0,
    PRIMARY KEY (ticker, accession_number)
);

-- Add comment
COMMENT ON TABLE RAW.RAW_SEC_FILINGS IS 'SEC 10-K and 10-Q filings with full text for LLM analysis';