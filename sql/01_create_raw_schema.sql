-- Create database
CREATE DATABASE IF NOT EXISTS FINSAGE_DB;

-- Use the database
USE DATABASE FINSAGE_DB;

-- Create RAW schema
CREATE SCHEMA IF NOT EXISTS RAW;

-- Create raw_stock_prices table
CREATE OR REPLACE TABLE RAW.raw_stock_prices (
    ticker VARCHAR(10),
    date DATE,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume BIGINT,
    dividends FLOAT,
    stock_splits FLOAT,
    source VARCHAR(50),
    ingested_at TIMESTAMP,
    PRIMARY KEY (ticker, date)
);

-- Create raw_fundamentals table
CREATE OR REPLACE TABLE RAW.raw_fundamentals (
    ticker VARCHAR(10),
    fiscal_quarter VARCHAR(20),
    market_cap BIGINT,
    revenue FLOAT,
    net_income FLOAT,
    eps FLOAT,
    pe_ratio FLOAT,
    profit_margin FLOAT,
    debt_to_equity FLOAT,
    total_assets FLOAT,
    total_liabilities FLOAT,
    source VARCHAR(50),
    ingested_at TIMESTAMP,
    PRIMARY KEY (ticker, fiscal_quarter)
);

-- Create raw_news table
CREATE OR REPLACE TABLE RAW.raw_news (
    article_id VARCHAR(100),
    ticker VARCHAR(10),
    title TEXT,
    description TEXT,
    content TEXT,
    author VARCHAR(200),
    source_name VARCHAR(100),
    url VARCHAR(500),
    published_at TIMESTAMP,
    ingested_at TIMESTAMP,
    PRIMARY KEY (article_id)
);
