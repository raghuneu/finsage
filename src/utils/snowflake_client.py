"""Enhanced Snowflake client - refactored from your connection module"""

import os
from dotenv import load_dotenv
from snowflake.snowpark import Session
import pandas as pd
from typing import Optional, List
from .logger import setup_logger

class SnowflakeClient:
    """Reusable Snowflake client with helper methods"""

    def __init__(self):
        load_dotenv()
        self.session = None
        self.logger = setup_logger(__name__, 'snowflake.log')
        self._connect()

    def _connect(self):

        """Create Snowflake session using environment variables"""
        connection_params = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA"),
    }

        # Only add role if it's set in .env
        role = os.getenv("SNOWFLAKE_ROLE")
        if role:
            connection_params["role"] = role

        # Validate required params (role is optional)
        required = ["account", "user", "password", "warehouse", "database", "schema"]
        missing = [k for k in required if not connection_params.get(k)]

        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")

        self.session = Session.builder.configs(connection_params).create()
        self.logger.info("✅ Connected to Snowflake")

    def get_last_loaded_date(self, table: str, ticker: str,
                             date_column: str = 'DATE') -> Optional[pd.Timestamp]:
        """
        Get most recent date for a ticker
        Uses your existing pattern from scripts
        """
        result = self.session.sql(f"""
            SELECT MAX({date_column}) as last_date
            FROM {table}
            WHERE TICKER = '{ticker}'
        """).collect()

        if result and result[0]['LAST_DATE']:
            return result[0]['LAST_DATE']
        return None

    def merge_data(self, df: pd.DataFrame, target_table: str,
                   staging_table: str, match_keys: List[str],
                   update_columns: List[str]):
        """
        Generic MERGE operation - your temp staging + merge pattern

        Args:
            df: DataFrame to merge
            target_table: Target table (e.g., 'RAW.RAW_STOCK_PRICES')
            staging_table: Temp staging table name
            match_keys: Columns to match on
            update_columns: Columns to update
        """
        # Create temp staging table
        self.session.sql(f"""
            CREATE OR REPLACE TEMPORARY TABLE {staging_table} 
            LIKE {target_table}
        """).collect()

        # Ensure uppercase columns
        df.columns = df.columns.str.upper()

        # Load to staging
        self.session.write_pandas(
            df, staging_table,
            auto_create_table=False,
            overwrite=True
        )

        # Build MERGE SQL
        match_condition = " AND ".join([f"target.{k} = source.{k}" for k in match_keys])
        update_set = ", ".join([f"{c} = source.{c}" for c in update_columns])
        insert_cols = ", ".join(df.columns)
        insert_vals = ", ".join([f"source.{c}" for c in df.columns])

        merge_sql = f"""
        MERGE INTO {target_table} target
        USING {staging_table} source
        ON {match_condition}
        WHEN MATCHED THEN
            UPDATE SET {update_set}
        WHEN NOT MATCHED THEN
            INSERT ({insert_cols})
            VALUES ({insert_vals})
        """

        result = self.session.sql(merge_sql).collect()
        self.logger.info(f"✅ Merged {len(df)} rows into {target_table}")
        return result

    def execute(self, sql: str):
        """Execute SQL statement"""
        return self.session.sql(sql).collect()

    def query_to_dataframe(self, sql: str) -> pd.DataFrame:
        """Execute query and return as DataFrame"""
        return self.session.sql(sql).to_pandas()

    def close(self):
        """Close session"""
        if self.session:
            self.session.close()
            self.logger.info("Snowflake session closed")