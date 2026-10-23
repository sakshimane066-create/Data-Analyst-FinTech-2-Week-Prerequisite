"""
run_postgres_queries.py
Loads the cleaned CSVs into a PostgreSQL database, runs every query in
sql/week1_practice_queries_postgres.sql and saves the results to
sql/query_results_postgres.md.

Setup (once)
  1. Install the drivers:   pip install psycopg2-binary sqlalchemy pandas
  2. In pgAdmin, create an empty database named  mf_analytics
     (right-click Databases -> Create -> Database)

Usage (from the project root)
  python sql/run_postgres_queries.py "postgresql://postgres:YOUR_PASSWORD@localhost:5432/mf_analytics"

  If your CSVs are in another folder, add that folder as the last argument:
  python sql/run_postgres_queries.py "postgresql://postgres:YOUR_PASSWORD@localhost:5432/mf_analytics" "C:\\path\\to\\csv_folder"

Special characters in the password (such as @) are handled automatically.

Reads : the folder you pass, then data/processed (cleaned files), data/raw, then the project folder
Writes: PostgreSQL tables  +  sql/query_results_postgres.md
"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy import types as T

from run_sql_queries import TABLES, TX_COLUMNS, parse_queries, read_table  # same folder

SQL_DIR = Path(__file__).resolve().parent
ROOT = SQL_DIR.parent
DEFAULT_SQL_FILE = SQL_DIR / "week1_practice_queries_postgres.sql"
RESULTS_FILE = SQL_DIR / "query_results_postgres.md"

# Columns that must be real DATE columns in PostgreSQL
DATE_COLUMNS = {
    "fund_master": ["launch_date"],
    "nav_history": ["date"],
    "aum_by_fund_house": ["date"],
    "monthly_sip_inflows": ["month"],
    "category_inflows": ["month"],
    "industry_folio_count": ["month"],
    "investor_transactions": ["transaction_date"],
    "portfolio_holdings": ["portfolio_date"],
    "benchmark_indices": ["date"],
}


def normalise_url(url: str) -> str:
    """Accept passwords with a raw @ (or other special characters) by URL-encoding them."""
    m = re.match(r"^([\w+]+://)([^:/@]+):(.*)@([^@]+)$", url)
    if not m:
        return url
    scheme, user, password, rest = m.groups()
    return f"{scheme}{user}:{quote(unquote(password), safe='')}@{rest}"


def load_tables(engine, data_dir=None) -> None:
    print("Loading tables into PostgreSQL:")
    for table, key in TABLES.items():
        df, source = read_table(table, key, data_dir)
        if table == "investor_transactions":
            df = df[TX_COLUMNS]

        dtype = {}
        for col in DATE_COLUMNS.get(table, []):
            df[col] = pd.to_datetime(df[col]).dt.date
            dtype[col] = T.Date()
        for col in df.select_dtypes(include="float").columns:
            dtype[col] = T.Numeric(20, 6)  # NUMERIC so ROUND(x, n) works

        df.to_sql(table, engine, if_exists="replace", index=False, dtype=dtype, chunksize=2000, method="multi")
        print(f"  {table:<24} {len(df):>8,} rows  <- {source}")


def run_queries(engine, sql_file: Path, results_file: Path) -> int:
    queries = parse_queries(sql_file.read_text(encoding="utf-8"))
    print(f"\nRunning {len(queries)} queries from {sql_file.name}\n")

    report = ["# SQL Query Results (PostgreSQL)", f"Query file: `sql/{sql_file.name}`", ""]
    failed = 0

    with engine.connect() as conn:
        for q in queries:
            header = f"Q{q['id']}: {q['title']}"
            print("=" * 90)
            print(header)
            print("=" * 90)
            try:
                df = pd.read_sql_query(text(q["sql"]), conn)
                body = df.head(15).to_string(index=False) if len(df) else "(no rows)"
                print(body)
                if len(df) > 15:
                    print(f"... {len(df) - 15} more rows")
                print(f"[{len(df)} rows]\n")
                status = f"{len(df)} rows"
            except Exception as err:
                conn.rollback()  # PostgreSQL aborts the transaction after an error
                failed += 1
                body = "ERROR: " + str(err).strip().splitlines()[0]
                print(body, "\n")
                status = "error"

            report += [f"## {header}", "", "```sql", q["sql"], "```", "", f"Result ({status}):", "", "```", body, "```", ""]

    results_file.write_text("\n".join(report), encoding="utf-8")
    print(f"Done. {len(queries) - failed} of {len(queries)} queries ran successfully.")
    print(f"Results saved to {results_file.relative_to(ROOT) if results_file.is_relative_to(ROOT) else results_file}")
    return failed


def main(url: str, sql_file: Path = DEFAULT_SQL_FILE, results_file: Path = RESULTS_FILE, load: bool = True, data_dir=None) -> int:
    engine = create_engine(normalise_url(url))
    if load:
        load_tables(engine, data_dir)
    return run_queries(engine, sql_file, results_file)


if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PG_URL")
    if not db_url:
        sys.exit(
            "Usage: python sql/run_postgres_queries.py "
            '"postgresql://postgres:YOUR_PASSWORD@localhost:5432/mf_analytics" ["C:\\path\\to\\csv_folder"]'
        )
    main(db_url, data_dir=sys.argv[2] if len(sys.argv) > 2 else None)