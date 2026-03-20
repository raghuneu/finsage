-- ──────────────────────────────────────────────────────────────
-- Migration 07: SEC Filing Documents table + S3 External Stage
-- Run after: 06_create_sec_table.sql
-- Prereqs : S3 bucket created via terraform/s3, IAM role configured
-- ──────────────────────────────────────────────────────────────

USE DATABASE FINSAGE_DB;

-- ──────────────────────────────────────────────────────────────
-- 1. Raw table for filing document metadata + extracted text
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS RAW.RAW_SEC_FILING_DOCUMENTS (
    filing_id           VARCHAR(100)  NOT NULL,
    ticker              VARCHAR(10)   NOT NULL,
    cik                 VARCHAR(20)   NOT NULL,
    form_type           VARCHAR(10)   NOT NULL,

    filing_date         DATE,
    period_of_report    DATE,
    fiscal_year         INTEGER,
    fiscal_period       VARCHAR(10),
    company_name        VARCHAR(200),

    s3_raw_key          VARCHAR(500),
    s3_mda_key          VARCHAR(500),
    s3_risk_key         VARCHAR(500),
    file_format         VARCHAR(10),
    file_size_bytes     BIGINT,

    mda_text            TEXT,
    risk_factors_text   TEXT,
    mda_word_count      INTEGER,
    risk_word_count     INTEGER,

    download_status     VARCHAR(20)   DEFAULT 'pending',
    extraction_status   VARCHAR(20)   DEFAULT 'pending',
    extraction_error    TEXT,

    data_quality_score  FLOAT         DEFAULT 100.0,
    source              VARCHAR(50)   DEFAULT 'sec_edgar',
    ingested_at         TIMESTAMP     DEFAULT CURRENT_TIMESTAMP(),
    updated_at          TIMESTAMP     DEFAULT CURRENT_TIMESTAMP(),

    PRIMARY KEY (filing_id, ticker)
);

-- ──────────────────────────────────────────────────────────────
-- 2. External stage pointing to S3 extracted-text folder
--    Uncomment after creating storage integration (step 3)
-- ──────────────────────────────────────────────────────────────
-- CREATE OR REPLACE STAGE RAW.S3_FILINGS_STAGE
--     STORAGE_INTEGRATION = finsage_s3_integration
--     URL = 's3://finsage-sec-filings/filings/extracted/'
--     FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY = '"');

-- ──────────────────────────────────────────────────────────────
-- 3. Storage integration (run by ACCOUNTADMIN once)
-- ──────────────────────────────────────────────────────────────
-- CREATE OR REPLACE STORAGE INTEGRATION finsage_s3_integration
--     TYPE = EXTERNAL_STAGE
--     STORAGE_PROVIDER = 'S3'
--     ENABLED = TRUE
--     STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/finsage-snowflake-role'
--     STORAGE_ALLOWED_LOCATIONS = ('s3://finsage-sec-filings/filings/');
--
-- DESC INTEGRATION finsage_s3_integration;
-- Use STORAGE_AWS_IAM_USER_ARN + STORAGE_AWS_EXTERNAL_ID
-- to configure the trust policy on the AWS IAM role.