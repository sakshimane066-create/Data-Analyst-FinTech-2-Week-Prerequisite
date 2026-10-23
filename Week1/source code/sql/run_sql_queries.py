"""
run_sql_queries.py
Loads the cleaned CSVs into a SQLite database, runs every query in
sql/week1_practice_queries.sql, prints the results and saves them to
sql/query_results.md (evidence for the submission).

Usage (from the project root):
  python sql/run_sql_queries.py
  python sql/run_sql_queries.py "C:\\path\\to\\folder\\with\\csvs"      (optional: point to your CSV folder)

Looks for the CSVs in this order: the folder you pass, data/processed (cleaned files),
data/raw, then the project folder. Long names like 1788...-01_fund_master.csv are fine.
Writes: data/processed/mf_analytics.db  and  sql/query_results.md
"""
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

SQL_DIR = Path(__file__).resolve().parent
ROOT = SQL_DIR.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
SQL_FILE = SQL_DIR / "week1_practice_queries.sql"
RESULTS_FILE = SQL_DIR / "query_results.md"
DB_PATH = PROCESSED_DIR / "mf_analytics.db"

# table name -> key in the raw filename
TABLES = {
    "fund_master": "01_fund_master",
    "nav_history": "02_nav_history",
    "aum_by_fund_house": "03_aum_by_fund_house",
    "monthly_sip_inflows": "04_monthly_sip_inflows",
    "category_inflows": "05_category_inflows",
    "industry_folio_count": "06_industry_folio_count",
    "scheme_performance": "07_scheme_performance",
    "investor_transactions": "08_investor_transactions",
    "portfolio_holdings": "09_portfolio_holdings",
    "benchmark_indices": "10_benchmark_indices",
}

# investor_transactions: keep only the original columns (the notebook adds extra ones)
TX_COLUMNS = [
    "investor_id", "transaction_date", "amfi_code", "transaction_type", "amount_inr",
    "state", "city", "city_tier", "age_group", "gender", "annual_income_lakh",
    "payment_mode", "kyc_status",
]


SEARCH_DIRS = [PROCESSED_DIR, RAW_DIR, ROOT]  # default places to look for the CSVs


def _matches(folder: Path, pattern: str, recursive: bool) -> list:
    if not folder.exists():
        return []
    return sorted(folder.rglob(pattern) if recursive else folder.glob(pattern))


def find_csv(table: str, raw_key: str, extra_dir=None) -> Path:
    # The folder you pass is searched including all its subfolders
    places = ([(Path(extra_dir), True)] if extra_dir else []) + [(d, False) for d in SEARCH_DIRS]

    # 1) cleaned file saved by the notebook
    for folder, recursive in places:
        found = _matches(folder, f"{table}_clean.csv", recursive)
        if found:
            return found[0]
    # 2) original file, including long names such as 1788...-01_fund_master.csv
    for folder, recursive in places:
        for pattern in (f"*{raw_key}*.csv", f"{table}.csv"):
            found = _matches(folder, pattern, recursive)
            if found:
                return found[0]

    lines = []
    for folder, recursive in places:
        if not folder.exists():
            lines.append(f"  {folder}   <- this folder does not exist")
        else:
            csvs = sorted(p.name for p in (folder.rglob("*.csv") if recursive else folder.glob("*.csv")))
            note = f"{len(csvs)} CSV files found" + (": " + ", ".join(csvs[:6]) if csvs else "")
            lines.append(f"  {folder}   <- {note}")
    raise FileNotFoundError(
        f"Could not find the CSV for '{table}'. Searched:\n" + "\n".join(lines) + "\n"
        "Fix: pass the folder that contains your CSVs as the last argument "
        "(subfolders are searched too)."
    )


def read_table(table: str, raw_key: str, extra_dir=None) -> tuple[pd.DataFrame, str]:
    path = find_csv(table, raw_key, extra_dir)
    return pd.read_csv(path), str(path)


def build_database(extra_dir=None) -> sqlite3.Connection:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)

    print("Loading tables into SQLite:")
    for table, key in TABLES.items():
        df, source = read_table(table, key, extra_dir)
        if table == "investor_transactions":
            df = df[TX_COLUMNS]
        df.to_sql(table, conn, index=False)
        print(f"  {table:<24} {len(df):>8,} rows  <- {source}")
    return conn


def parse_queries(text: str) -> list[dict]:
    """Split the .sql file into queries. Each starts with a '-- Qn: title' line."""
    queries = []
    current = None
    for line in text.splitlines():
        m = re.match(r"^--\s*Q(\d+):\s*(.+)$", line)
        if m:
            if current:
                queries.append(current)
            current = {"id": int(m.group(1)), "title": m.group(2).strip(), "lines": []}
        elif current is not None:
            if re.match(r"^-- =+", line) or re.match(r"^-- PART", line):
                continue  # section banners
            current["lines"].append(line)
    if current:
        queries.append(current)

    for q in queries:
        q["sql"] = "\n".join(q["lines"]).strip()
    return queries


def main(extra_dir=None) -> None:
    conn = build_database(extra_dir)
    queries = parse_queries(SQL_FILE.read_text(encoding="utf-8"))
    print(f"\nRunning {len(queries)} queries from {SQL_FILE.name}\n")

    report = ["# SQL Query Results", f"Database: `data/processed/{DB_PATH.name}`", ""]
    failed = 0

    for q in queries:
        header = f"Q{q['id']}: {q['title']}"
        print("=" * 90)
        print(header)
        print("=" * 90)
        try:
            df = pd.read_sql_query(q["sql"], conn)
            shown = df.head(15)
            body = shown.to_string(index=False) if len(df) else "(no rows)"
            print(body)
            if len(df) > 15:
                print(f"... {len(df) - 15} more rows")
            print(f"[{len(df)} rows]\n")
            status = f"{len(df)} rows"
        except Exception as err:  # keep going so one bad query does not stop the run
            failed += 1
            body = f"ERROR: {err}"
            print(body, "\n")
            status = "error"

        report += [f"## {header}", "", "```sql", q["sql"], "```", "", f"Result ({status}):", "", "```", body, "```", ""]

    RESULTS_FILE.write_text("\n".join(report), encoding="utf-8")
    conn.close()
    print(f"Done. {len(queries) - failed} of {len(queries)} queries ran successfully.")
    print(f"Results saved to {RESULTS_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)