"""Run migration 07: Create SEC filing documents table"""

import sys
sys.path.insert(0, ".")
from snowflake_connection import get_session


def run_migration():
    session = get_session()

    print("Running migration 07: SEC filing documents table...")

    session.sql("USE DATABASE FINSAGE_DB").collect()

    session.sql("""
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
        )
    """).collect()

    print("✅ Migration 07 complete: RAW.RAW_SEC_FILING_DOCUMENTS created")
    session.close()


if __name__ == "__main__":
    run_migration()