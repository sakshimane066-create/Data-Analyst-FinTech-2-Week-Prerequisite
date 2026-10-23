"""run_queries.py - runs every query in queries.sql against bluestock_mf.db and saves query_results.md"""
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
conn = sqlite3.connect(ROOT / "bluestock_mf.db")
conn.execute("PRAGMA foreign_keys = ON")
text = (ROOT / "queries.sql").read_text(encoding="utf-8")

queries, cur = [], None
for line in text.splitlines():
    m = re.match(r"^--\s*Q(\d+):\s*(.+)$", line)
    if m:
        cur = {"id": m.group(1), "title": m.group(2), "lines": []}
        queries.append(cur)
    elif cur is not None and not line.startswith("-- ="):
        cur["lines"].append(line)

report, failed = ["# Query Results", "Database: `bluestock_mf.db`", ""], 0
for q in queries:
    sql = "\n".join(q["lines"]).strip()
    try:
        df = pd.read_sql_query(sql, conn)
        body = df.head(15).to_string(index=False) if len(df) else "(no rows)"
        status = f"{len(df)} rows"
    except Exception as e:
        failed += 1
        body, status = f"ERROR: {e}", "error"
    print(f"Q{q['id']}: {q['title']}  [{status}]")
    report += [f"## Q{q['id']}: {q['title']}", "", "```sql", sql, "```", "", f"Result ({status}, first 15 shown):", "", "```", body, "```", ""]
(ROOT / "query_results.md").write_text("\n".join(report), encoding="utf-8")
print(f"\n{len(queries) - failed} of {len(queries)} queries ran successfully. Saved query_results.md")
