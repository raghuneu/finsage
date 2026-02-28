"""
Pre-fetch CIKs for all tickers in config
Creates a cache file so SEC loader doesn't need to fetch every time
"""

import requests
import json
import yaml
from pathlib import Path
import time

def fetch_all_ciks():
    """Fetch CIKs for all tickers in config"""

    # Read tickers from config
    config_path = Path('config') / 'tickers.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    tickers = config.get('tickers', [])
    print(f"📋 Fetching CIKs for {len(tickers)} tickers...")

    # Try to get full SEC mapping
    headers = {'User-Agent': 'University research@university.edu'}

    try:
        print("🔍 Fetching SEC company tickers JSON...")
        url = 'https://www.sec.gov/files/company_tickers.json'
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        data = response.json()

        # Build CIK mapping
        cik_map = {}
        for item in data.values():
            ticker = item['ticker'].upper()
            cik = str(item['cik_str']).zfill(10)
            cik_map[ticker] = cik

        print(f"✅ Fetched {len(cik_map)} total CIK mappings from SEC")

        # Filter to only our tickers
        our_ciks = {}
        missing = []

        for ticker in tickers:
            ticker_upper = ticker.upper()
            if ticker_upper in cik_map:
                our_ciks[ticker_upper] = cik_map[ticker_upper]
                print(f"  ✓ {ticker}: {cik_map[ticker_upper]}")
            else:
                missing.append(ticker)
                print(f"  ✗ {ticker}: NOT FOUND")

        # Save cache
        cache_file = Path('config') / 'cik_cache.json'
        cache_file.parent.mkdir(exist_ok=True)

        with open(cache_file, 'w') as f:
            json.dump(our_ciks, f, indent=2)

        print(f"\n✅ Saved {len(our_ciks)} CIKs to config/cik_cache.json")

        if missing:
            print(f"\n⚠️  Missing CIKs for: {', '.join(missing)}")
            print("These tickers might be invalid or delisted")

        return our_ciks

    except Exception as e:
        print(f"❌ Failed to fetch CIK mapping: {e}")
        print("\n💡 You can manually add CIKs to config/cik_cache.json")
        print("Format: {\"TICKER\": \"0000123456\"}")
        return {}

if __name__ == "__main__":
    fetch_all_ciks()