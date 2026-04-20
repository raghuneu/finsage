"""One-time backfill: reload XBRL data for all 50 tickers to pick up
newly-added revenue concepts (SalesRevenueNet, SalesRevenueGoodsNet,
RevenuesNetOfInterestExpense) and fix per-concept watermark gaps.

Run from project root:
    PYTHONPATH=. python scripts/backfill_xbrl_revenue.py
"""

import time
import yaml
from pathlib import Path
from src.utils.snowflake_client import SnowflakeClient
from src.data_loaders.xbrl_loader import XBRLLoader


def main():
    config_path = Path('config/tickers.yaml')
    with open(config_path) as f:
        tickers = yaml.safe_load(f).get('tickers', [])

    print(f"Backfilling XBRL data for {len(tickers)} tickers...")

    sf = SnowflakeClient(component="xbrl_backfill")
    loader = XBRLLoader(sf)

    success = 0
    failed = 0

    for i, ticker in enumerate(tickers, 1):
        try:
            result = loader.load(ticker)
            if result:
                success += 1
            else:
                print(f"  [{i}/{len(tickers)}] {ticker}: no new data")
        except Exception as e:
            print(f"  [{i}/{len(tickers)}] {ticker}: FAILED - {e}")
            failed += 1

        # SEC EDGAR rate limit: 10 requests/sec, be conservative
        if i % 5 == 0:
            time.sleep(2)

    print(f"\nBackfill complete: {success} loaded, {failed} failed, "
          f"{len(tickers) - success - failed} no new data")
    sf.close()


if __name__ == '__main__':
    main()
