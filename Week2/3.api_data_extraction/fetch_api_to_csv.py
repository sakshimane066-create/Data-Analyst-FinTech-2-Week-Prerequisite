"""
API Data Extraction Assignment
Calls the public CoinGecko API (no API key needed), saves the raw JSON,
flattens it with pandas and writes a CSV ready for analysis.

Run:  pip install requests pandas
      python fetch_api_to_csv.py
"""
import json
import sys
from datetime import datetime, timezone

import pandas as pd
import requests

URL = "https://api.coingecko.com/api/v3/coins/markets"
PARAMS = {                      # query parameters
    "vs_currency": "inr",       # prices in Indian rupees
    "order": "market_cap_desc",
    "per_page": 20,             # top 20 coins
    "page": 1,
    "sparkline": "false",
}
RAW_JSON = "raw_response.json"
OUT_CSV = "crypto_markets.csv"


def fetch(url=URL, params=PARAMS):
    """GET request with a timeout and basic error handling."""
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()          # raises on 4xx / 5xx
        return resp.json()               # JSON text -> Python list of dicts
    except requests.exceptions.HTTPError as e:
        sys.exit(f"HTTP error: {e} (429 means rate limited; wait a minute and retry)")
    except requests.exceptions.RequestException as e:
        sys.exit(f"Network error: {e}")


def to_dataframe(data):
    """Flatten nested JSON (e.g. the 'roi' object becomes roi.times, roi.currency ...)."""
    df = pd.json_normalize(data)
    keep = ["market_cap_rank", "id", "symbol", "name", "current_price",
            "market_cap", "total_volume", "high_24h", "low_24h",
            "price_change_percentage_24h", "last_updated"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df["last_updated"] = pd.to_datetime(df["last_updated"], errors="coerce")
    df["fetched_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return df


def main():
    data = fetch()
    with open(RAW_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)     # keep the raw response as evidence
    df = to_dataframe(data)
    df.to_csv(OUT_CSV, index=False)
    print(f"Saved {len(df)} rows to {OUT_CSV}")
    print(df.head())
    print("\nMissing values per column:\n", df.isna().sum())
    print("\nSummary:\n", df[["current_price", "market_cap", "total_volume"]].describe())


if __name__ == "__main__":
    main()
