-- Add data quality score column to track data quality
ALTER TABLE RAW.RAW_STOCK_PRICES 
ADD COLUMN IF NOT EXISTS data_quality_score FLOAT DEFAULT 100.0;
