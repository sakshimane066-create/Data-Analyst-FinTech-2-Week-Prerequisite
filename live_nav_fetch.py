"""
live_nav_fetch.py
Day 1 - Fetch live NAV data from mfapi.in and save as raw CSV.

Covers:
  Task 4: HDFC Top 100 Direct (125497)
  Task 5: SBI / ICICI / Nippon / Axis / Kotak large-cap (bluechip) schemes

Output (data/raw/live_nav/):
  nav_125497.csv                  -> HDFC Top 100 Direct
  nav_<code>.csv                  -> one file per key scheme
  nav_key_schemes_combined.csv    -> the 5 key schemes in one file
  <code>_raw.json                 -> untouched API response (audit trail)

Usage:  python live_nav_fetch.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://api.mfapi.in/mf"
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "raw" / "live_nav"

HDFC_TOP100 = {"125497": "HDFC Top 100 Direct"}

KEY_SCHEMES = {
    "119551": "SBI Bluechip",
    "120503": "ICICI Bluechip",
    "118632": "Nippon Large Cap",
    "119092": "Axis Bluechip",
    "120841": "Kotak Bluechip",
}


def fetch_scheme(code: str, retries: int = 3, timeout: int = 30) -> dict:
    """GET /mf/<code> with retries. Returns the parsed JSON payload."""
    url = f"{BASE_URL}/{code}"
    last_err: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("data"):
                raise ValueError(f"Empty 'data' in response for scheme {code}")
            return payload
        except (requests.RequestException, ValueError) as err:
            last_err = err
            print(f"  [retry {attempt}/{retries}] {code}: {err}")
            time.sleep(2 * attempt)

    raise RuntimeError(f"Failed to fetch scheme {code} after {retries} attempts") from last_err


def parse_payload(payload: dict, code: str, fallback_name: str) -> pd.DataFrame:
    """Turn the API JSON into a tidy DataFrame (date, nav + scheme metadata)."""
    meta = payload.get("meta", {})
    df = pd.DataFrame(payload["data"])

    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

    bad = int(df[["date", "nav"]].isna().any(axis=1).sum())
    if bad:
        print(f"  [warn] {code}: dropping {bad} rows with unparseable date/nav")
    df = df.dropna(subset=["date", "nav"]).sort_values("date").reset_index(drop=True)

    df.insert(0, "scheme_code", str(meta.get("scheme_code", code)))
    df.insert(1, "scheme_name", meta.get("scheme_name") or fallback_name)
    df.insert(2, "fund_house", meta.get("fund_house"))
    return df


def fetch_and_save(code: str, label: str) -> pd.DataFrame:
    print(f"Fetching {label} ({code}) ...")
    payload = fetch_scheme(code)

    # Re-create the folder right before writing (safe if it already exists)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / f"{code}_raw.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    df = parse_payload(payload, code, label)
    out_path = OUT_DIR / f"nav_{code}.csv"
    df.to_csv(out_path, index=False)
    print(f"  saved {len(df):,} rows -> {out_path.relative_to(ROOT)}")
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames: dict[str, pd.DataFrame] = {}

    print("=== Task 4: HDFC Top 100 Direct ===")
    for code, label in HDFC_TOP100.items():
        frames[code] = fetch_and_save(code, label)

    print("\n=== Task 5: Key large-cap schemes ===")
    for code, label in KEY_SCHEMES.items():
        try:
            frames[code] = fetch_and_save(code, label)
        except RuntimeError as err:
            print(f"  [error] {err}")
        time.sleep(1)  # be polite to the free API

    key_frames = [frames[c] for c in KEY_SCHEMES if c in frames]
    if key_frames:
        combined = pd.concat(key_frames, ignore_index=True)
        combined_path = OUT_DIR / "nav_key_schemes_combined.csv"
        combined.to_csv(combined_path, index=False)
        print(f"\nCombined key schemes -> {combined_path.relative_to(ROOT)} ({len(combined):,} rows)")

    print("\n=== Summary ===")
    rows = []
    for code, df in frames.items():
        rows.append(
            {
                "scheme_code": code,
                "scheme_name": df["scheme_name"].iloc[0],
                "rows": len(df),
                "first_date": df["date"].min().date(),
                "latest_date": df["date"].max().date(),
                "latest_nav": df.loc[df["date"].idxmax(), "nav"],
            }
        )
    print(pd.DataFrame(rows).to_string(index=False))

    missing = [c for c in list(HDFC_TOP100) + list(KEY_SCHEMES) if c not in frames]
    if missing:
        print(f"\n[warn] Not fetched: {missing}")


if __name__ == "__main__":
    main()