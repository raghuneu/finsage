-- Create SEC EDGAR filings table
CREATE TABLE IF NOT EXISTS RAW.RAW_SEC_FILINGS (
    ticker VARCHAR(10),
    cik VARCHAR(20),
    concept VARCHAR(100),
    label VARCHAR(200),
    period_start DATE,
    period_end DATE,
    value FLOAT,
    unit VARCHAR(10),
    fiscal_year INTEGER,
    fiscal_period VARCHAR(10),
    form_type VARCHAR(10),
    filed_date DATE,
    accession_no VARCHAR(50),
    source VARCHAR(50),
    ingested_at TIMESTAMP,
    data_quality_score FLOAT DEFAULT 100.0,
    PRIMARY KEY (ticker, concept, period_end, fiscal_period)
);