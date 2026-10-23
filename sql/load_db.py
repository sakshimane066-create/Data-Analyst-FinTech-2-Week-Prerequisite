"""
load_db.py  -  Day 2: build bluestock_mf.db
Runs schema.sql, builds dim_date, loads every cleaned CSV with SQLAlchemy + df.to_sql(),
then verifies row counts against the CSVs and checks foreign keys.

Usage (from the project root, after clean_data.py):   python load_db.py
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, event, text

ROOT = Path(__file__).resolve().parent
PROC = ROOT / "data" / "processed"
DB = ROOT / "bluestock_mf.db"
SCHEMA = ROOT / "schema.sql"


def csv(name):
    p = PROC / f"{name}_clean.csv"
    return pd.read_csv(p) if p.exists() else None


def date_key(s):
    return pd.to_datetime(s).dt.strftime("%Y%m%d").astype(int)


def build_dim_date(frames):
    dates = pd.concat([pd.to_datetime(s) for s in frames]).dropna()
    d = pd.date_range(dates.min().replace(day=1), dates.max() + pd.offsets.MonthEnd(0), freq="D")
    df = pd.DataFrame({"full_date": d})
    df["date_key"] = df["full_date"].dt.strftime("%Y%m%d").astype(int)
    df["year"], df["quarter"], df["month"] = d.year, d.quarter, d.month
    df["month_name"] = d.strftime("%B")
    df["year_month"] = d.strftime("%Y-%m")
    df["day"] = d.day
    df["day_of_week"] = d.dayofweek + 1
    df["day_name"] = d.strftime("%A")
    df["is_weekend"] = (d.dayofweek >= 5).astype(int)
    fy = d.year.where(d.month >= 4, d.year - 1)
    df["financial_year"] = "FY" + fy.astype(str) + "-" + ((fy + 1) % 100).astype(str).str.zfill(2)
    df["full_date"] = df["full_date"].dt.strftime("%Y-%m-%d")
    return df[["date_key", "full_date", "year", "quarter", "month", "month_name", "year_month",
               "day", "day_of_week", "day_name", "is_weekend", "financial_year"]]


def main():
    if DB.exists():
        DB.unlink()
    engine = create_engine(f"sqlite:///{DB}")

    @event.listens_for(engine, "connect")
    def fk_on(conn, _):
        conn.execute("PRAGMA foreign_keys = ON")

    raw = engine.raw_connection()
    raw.executescript(SCHEMA.read_text(encoding="utf-8"))
    raw.commit()
    raw.close()

    fm, nav, tx = csv("fund_master"), csv("nav_history"), csv("investor_transactions")
    aum, bm, ci = csv("aum_by_fund_house"), csv("benchmark_indices"), csv("category_inflows")
    sip, fol, ph, perf = csv("monthly_sip_inflows"), csv("industry_folio_count"), csv("portfolio_holdings"), csv("scheme_performance")

    dd = build_dim_date([nav["date"], tx["transaction_date"], aum["date"], bm["date"], ci["month"],
                         sip["month"], fol["month"], ph["portfolio_date"], fm["launch_date"].dropna()])
    # launch dates go back to 2006; keep dim_date to the analysis window instead
    dd = dd[dd["full_date"] >= "2022-01-01"]

    loaded = {}   # table -> (source rows, source name)

    def put(table, df, src_name=None, src_rows=None):
        df.to_sql(table, engine, if_exists="append", index=False, chunksize=5000)
        loaded[table] = (len(df) if src_rows is None else src_rows, src_name)

    put("dim_date", dd)
    put("dim_fund", fm.drop(columns=["expense_ratio_valid"], errors="ignore"), "fund_master")

    n = nav.assign(date_key=date_key(nav["date"]))[["amfi_code", "date_key", "nav", "is_filled"]]
    put("fact_nav", n, "nav_history")

    t = tx.assign(date_key=date_key(tx["transaction_date"]), is_amount_outlier=tx["is_amount_outlier"].astype(int))
    t = t[["investor_id", "date_key", "amfi_code", "transaction_type", "amount_inr", "state", "city", "city_tier",
           "age_group", "gender", "annual_income_lakh", "payment_mode", "kyc_status", "is_amount_outlier"]]
    put("fact_transactions", t, "investor_transactions")

    if perf is not None:
        drop = [c for c in ["scheme_name", "fund_house", "category", "sub_category", "plan", "benchmark", "risk_category"] if c in perf.columns]
        p = perf.drop(columns=drop)                               # descriptive columns live in dim_fund
        with engine.begin() as c:
            existing = {r[1] for r in c.execute(text("PRAGMA table_info(fact_performance)"))}
            for col in p.columns:
                if col not in existing:
                    typ = "REAL" if pd.api.types.is_numeric_dtype(p[col]) else "TEXT"
                    c.execute(text(f'ALTER TABLE fact_performance ADD COLUMN "{col}" {typ}'))
        put("fact_performance", p, "scheme_performance")
    else:
        print("!! scheme_performance_clean.csv not found: fact_performance left empty")

    a = aum.assign(date_key=date_key(aum["date"])).drop(columns=["date"])
    put("fact_aum", a[["date_key", "fund_house", "aum_lakh_crore", "aum_crore", "num_schemes"]], "aum_by_fund_house")
    put("benchmark_indices", bm.assign(date_key=date_key(bm["date"]))[["date_key", "index_name", "close_value"]], "benchmark_indices")
    put("category_inflows", ci.assign(date_key=date_key(ci["month"]))[["date_key", "category", "net_inflow_crore"]], "category_inflows")
    s = sip.assign(date_key=date_key(sip["month"]), is_outlier_new_accounts=sip["is_outlier_new_accounts"].astype(int)).drop(columns=["month"])
    put("monthly_sip_inflows", s[["date_key"] + [c for c in s.columns if c != "date_key"]], "monthly_sip_inflows")
    f = fol.assign(date_key=date_key(fol["month"])).drop(columns=["month"])
    put("industry_folio_count", f[["date_key"] + [c for c in f.columns if c != "date_key"]], "industry_folio_count")
    h = ph.assign(date_key=date_key(ph["portfolio_date"])).drop(columns=["portfolio_date"])
    put("portfolio_holdings", h[["amfi_code", "stock_symbol", "date_key", "stock_name", "sector", "weight_pct", "market_value_cr", "current_price_inr"]], "portfolio_holdings")

    # ----------------------------------------------------------- verification
    print(f"\n{'table':<22}{'csv rows':>10}{'db rows':>10}  status")
    ok = True
    with engine.connect() as c:
        for table, (src, name) in loaded.items():
            db_rows = c.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            good = db_rows == src
            ok &= good
            print(f"{table:<22}{src:>10,}{db_rows:>10,}  {'OK' if good else 'MISMATCH'}")
        fk = c.execute(text("PRAGMA foreign_key_check")).fetchall()
        print(f"\nForeign key violations: {len(fk)}")
        ok &= len(fk) == 0
    print("\nALL CHECKS PASSED" if ok else "\nCHECKS FAILED")
    print(f"Database written to {DB.name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
