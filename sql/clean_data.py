"""
clean_data.py  -  Day 2: Data Cleaning
Reads the 10 datasets, applies the cleaning rules from the task, and writes
data/processed/<name>_clean.csv plus data/processed/cleaning_day2_log.csv.

Usage (from the project root):
    python clean_data.py                       # looks in data/raw, then the project folder
    python clean_data.py "C:\\path\\to\\csv_folder"
Accepted file names for each dataset, e.g. nav_history: nav_history.csv, nav_history_clean.csv,
nav_history_clean.xls (a CSV saved with an .xls name), or a long name containing nav_history.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
NAMES = ["fund_master", "nav_history", "aum_by_fund_house", "monthly_sip_inflows", "category_inflows",
         "industry_folio_count", "scheme_performance", "investor_transactions", "portfolio_holdings",
         "benchmark_indices"]
LOG = []


def log(dataset, action, n):
    LOG.append({"dataset": dataset, "action": action, "rows_affected": int(n)})
    print(f"  [{dataset}] {action}: {int(n)}")


def find_file(name, extra=None):
    folders = ([Path(extra)] if extra else []) + [RAW, ROOT]
    for pat in (f"{name}_clean.csv", f"{name}_clean.xls", f"{name}.csv", f"{name}.xls", f"*{name}*.csv", f"*{name}*.xls"):
        for f in folders:
            hits = sorted(f.glob(pat)) if f.exists() else []
            if hits:
                return hits[0]
    return None


def read_any(path):
    try:
        return pd.read_csv(path)          # CSV, including CSV files saved with an .xls name
    except Exception:
        return pd.read_excel(path)


def to_date(s):
    return pd.to_datetime(s, errors="coerce", format="mixed")


def num(df, cols, ds):
    for c in cols:
        before = df[c].isna().sum()
        df[c] = pd.to_numeric(df[c], errors="coerce")
        log(ds, f"non-numeric '{c}' values set to NaN", df[c].isna().sum() - before)
    return df


def std_house(df, ds):
    """'ICICI Prudential MF' -> 'ICICI Prudential Mutual Fund'; trims stray spaces."""
    if "fund_house" in df.columns:
        new = (df["fund_house"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
               .str.replace(r"\bMF$", "Mutual Fund", regex=True))
        log(ds, "fund_house names standardised ('MF' -> 'Mutual Fund')", (new != df["fund_house"]).sum())
        df = df.assign(fund_house=new)
    return df


def drop_dups(df, ds, subset=None):
    n = len(df)
    df = df.drop_duplicates(subset=subset, keep="last")
    log(ds, "duplicate rows removed" + (f" (key {subset})" if subset else ""), n - len(df))
    return df


def drop_bad(df, mask, ds, why):
    log(ds, f"rows removed: {why}", mask.sum())
    return df[~mask]


# ---------------------------------------------------------------- per dataset
def clean_nav(df):
    ds = "nav_history"
    df = df.copy()
    df["date"] = to_date(df["date"])
    df = num(df, ["nav"], ds)
    df = drop_bad(df, df["date"].isna() | df["nav"].isna() | df["amfi_code"].isna(), ds, "unparseable date / missing NAV")
    df = drop_dups(df, ds, ["amfi_code", "date"])
    df = drop_bad(df, df["nav"] <= 0, ds, "NAV <= 0")
    df = df.sort_values(["amfi_code", "date"])
    parts = []
    for code, g in df.groupby("amfi_code"):
        s = g.set_index("date")["nav"]
        full = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))
        filled = full.isna()
        parts.append(pd.DataFrame({"amfi_code": code, "date": full.index, "nav": full.ffill().values,
                                   "is_filled": filled.values.astype(int)}))
    out = pd.concat(parts, ignore_index=True)
    out["nav"] = out["nav"].round(4)
    log(ds, "weekend/holiday NAV rows forward-filled (is_filled=1)", out["is_filled"].sum())
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out


TX_MAP = {"sip": "SIP", "systematic investment plan": "SIP", "lumpsum": "Lumpsum", "lump sum": "Lumpsum",
          "lump-sum": "Lumpsum", "one time": "Lumpsum", "redemption": "Redemption", "redeem": "Redemption",
          "withdrawal": "Redemption", "sell": "Redemption"}
KYC_OK = {"verified": "Verified", "pending": "Pending", "rejected": "Rejected"}


def clean_tx(df):
    ds = "investor_transactions"
    df = df.copy()
    t = df["transaction_type"].astype(str).str.strip().str.lower()
    df["transaction_type"] = t.map(TX_MAP)
    df = drop_bad(df, df["transaction_type"].isna(), ds, "unknown transaction_type")
    df["transaction_date"] = to_date(df["transaction_date"])
    df = drop_bad(df, df["transaction_date"].isna(), ds, "unparseable transaction_date")
    df = num(df, ["amount_inr"], ds)
    df = drop_bad(df, ~(df["amount_inr"] > 0), ds, "amount <= 0 or missing")
    k = df["kyc_status"].astype(str).str.strip().str.lower().map(KYC_OK)
    df = df.assign(kyc_status=k)
    df = drop_bad(df, df["kyc_status"].isna(), ds, "kyc_status not in Verified/Pending/Rejected")
    df = drop_dups(df, ds)
    if "is_amount_outlier" not in df.columns:        # 3 x IQR within each transaction type (matches Week 1 flags)
        df["is_amount_outlier"] = df.groupby("transaction_type")["amount_inr"].transform(lambda s: flag_iqr(s)).astype(bool)
        log(ds, "amount outliers flagged (3 x IQR per type, kept)", df["is_amount_outlier"].sum())
    df = df.sort_values(["transaction_date", "investor_id"])
    df["transaction_date"] = df["transaction_date"].dt.strftime("%Y-%m-%d")
    return df


def clean_fund_master(df):
    ds = "fund_master"
    df = std_house(df.copy(), ds)
    df["launch_date"] = to_date(df["launch_date"])
    df = num(df, ["expense_ratio_pct", "exit_load_pct", "min_sip_amount", "min_lumpsum_amount"], ds)
    df = drop_dups(df, ds, ["amfi_code"])
    bad = ~df["expense_ratio_pct"].between(0.1, 2.5)
    log(ds, "expense_ratio_pct outside 0.1-2.5 (flagged, kept)", bad.sum())
    df["expense_ratio_valid"] = (~bad).astype(int)
    df["launch_date"] = df["launch_date"].dt.strftime("%Y-%m-%d")
    return df


def flag_iqr(s, k=3.0):
    q1, q3 = s.quantile([0.25, 0.75])
    i = q3 - q1
    return (s < q1 - k * i) | (s > q3 + k * i)


def clean_perf(df, groups=None):
    ds = "scheme_performance"
    df = std_house(df.copy(), ds)
    id_text = {"amfi_code", "scheme_name", "fund_house", "category", "sub_category", "plan", "benchmark", "risk_category"}
    numeric = []
    for c in df.columns:
        if c in id_text:
            continue
        conv = pd.to_numeric(df[c], errors="coerce")
        if conv.notna().sum() >= 0.5 * df[c].notna().sum():       # mostly numeric -> treat as numeric
            log(ds, f"non-numeric '{c}' values set to NaN", conv.isna().sum() - df[c].isna().sum())
            df[c] = conv
            numeric.append(c)
    df = drop_dups(df, ds, ["amfi_code"])
    # Flag outliers within each asset class (Equity vs Debt): debt funds naturally have very different
    # beta/Sharpe values, so comparing them with equity funds would flag every debt fund.
    grp = df["amfi_code"].map(groups) if groups is not None else pd.Series("all", index=df.index)
    grp = grp.fillna("unknown")
    cols = [c for c in numeric if "rating" not in c and "expense" not in c and df[c].notna().sum() > 4]
    flags = pd.DataFrame(False, index=df.index, columns=cols)
    for _, idx in df.groupby(grp).groups.items():
        if len(idx) >= 5:
            for c in cols:
                flags.loc[idx, c] = flag_iqr(df.loc[idx, c].dropna()).reindex(idx, fill_value=False)
    df["has_anomaly"] = flags.any(axis=1).astype(int) if len(flags.columns) else 0
    df["anomaly_columns"] = flags.apply(lambda r: ",".join(r.index[r.values]), axis=1) if len(flags.columns) else ""
    log(ds, "rows with anomalous values (flagged, kept)", df["has_anomaly"].sum())
    for c in [c for c in numeric if "expense" in c]:
        bad = ~df[c].between(0.1, 2.5)
        df["expense_ratio_valid"] = (~bad).astype(int)
        log(ds, f"'{c}' outside 0.1-2.5 (flagged, kept)", bad.sum())
    return df


def clean_generic(name, df, date_cols=(), numeric_cols=(), key=None, non_negative=()):
    df = std_house(df.copy(), name)
    for c in date_cols:
        df[c] = to_date(df[c])
        df = drop_bad(df, df[c].isna(), name, f"unparseable {c}")
    df = num(df, list(numeric_cols), name)
    for c in non_negative:
        df = drop_bad(df, df[c] < 0, name, f"negative {c}")
    df = drop_dups(df, name, key)
    for c in date_cols:
        df[c] = df[c].dt.strftime("%Y-%m-%d")
    return df


def main(extra=None):
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for name in NAMES:
        path = find_file(name, extra)
        print(f"\n{name}")
        if path is None:
            print(f"  !! file not found, skipped (add it and re-run)")
            summary.append((name, None, None, "NOT FOUND"))
            continue
        df = read_any(path)
        n0 = len(df)
        if name == "nav_history": out = clean_nav(df)
        elif name == "investor_transactions": out = clean_tx(df)
        elif name == "fund_master": out = clean_fund_master(df)
        elif name == "scheme_performance":
            fmp = find_file("fund_master", extra)
            groups = read_any(fmp).set_index("amfi_code")["category"] if fmp else None
            out = clean_perf(df, groups)
        elif name == "aum_by_fund_house":
            out = clean_generic(name, df, ["date"], ["aum_lakh_crore", "aum_crore", "num_schemes"], ["date", "fund_house"], ["aum_crore"])
        elif name == "monthly_sip_inflows":
            out = clean_generic(name, df, ["month"], [c for c in df.columns if c not in ("month", "is_outlier_new_accounts")], ["month"], ["sip_inflow_crore"])
            if "is_outlier_new_accounts" not in out.columns:
                out["is_outlier_new_accounts"] = flag_iqr(out["new_sip_accounts_lakh"]).astype(bool)
                log(name, "new-account outliers flagged (3 x IQR, kept)", out["is_outlier_new_accounts"].sum())
            if "yoy_growth_pct" not in out.columns:
                s = out.sort_values("month")
                out["yoy_growth_pct"] = (s["sip_inflow_crore"].pct_change(12) * 100).round(2)
        elif name == "category_inflows":
            out = clean_generic(name, df, ["month"], ["net_inflow_crore"], ["month", "category"])
        elif name == "industry_folio_count":
            out = clean_generic(name, df, ["month"], [c for c in df.columns if c != "month"], ["month"])
        elif name == "portfolio_holdings":
            out = clean_generic(name, df, ["portfolio_date"], ["weight_pct", "market_value_cr", "current_price_inr"], ["amfi_code", "stock_symbol", "portfolio_date"], ["weight_pct"])
        elif name == "benchmark_indices":
            out = clean_generic(name, df, ["date"], ["close_value"], ["date", "index_name"])
            out = drop_bad(out, out["close_value"] <= 0, name, "close_value <= 0")
        out.to_csv(OUT / f"{name}_clean.csv", index=False)
        summary.append((name, n0, len(out), str(path.name)))
    pd.DataFrame(LOG).to_csv(OUT / "cleaning_day2_log.csv", index=False)
    print("\n" + "=" * 70 + "\nSUMMARY  (source rows -> cleaned rows)")
    for n, a, b, p in summary:
        print(f"  {n:<24} {str(a):>8} -> {str(b):>8}   {p}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
