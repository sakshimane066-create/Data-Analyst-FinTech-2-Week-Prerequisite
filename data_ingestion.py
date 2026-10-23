"""
data_ingestion.py
Day 1 - Load all provided CSVs, profile them, explore fund_master,
validate AMFI scheme codes against nav_history, and write a short
data quality summary.

Expects:  data/raw/*.csv   (your 10 provided datasets, incl. fund_master + nav_history)
Writes:   reports/data_quality_summary.md

Usage:  python data_ingestion.py
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "reports"

pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 200)

# Column-name candidates (normalised: lowercase, underscores). Edit if your CSVs differ.
COLUMN_CANDIDATES = {
    "scheme_code": ["scheme_code", "amfi_code", "amfi_scheme_code", "schemecode", "code"],
    "fund_house": ["fund_house", "amc", "amc_name", "fund_house_name", "fundhouse"],
    "category": ["category", "scheme_category", "fund_category"],
    "sub_category": ["sub_category", "subcategory", "scheme_sub_category", "sub_cat"],
    "risk_grade": ["risk_grade", "riskometer", "risk_level", "risk_category", "risk"],
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def find_col(df: pd.DataFrame, key: str) -> str | None:
    """Find the real column name for a logical field (scheme_code, fund_house, ...)."""
    cols = {norm(c): c for c in df.columns}
    for cand in COLUMN_CANDIDATES[key]:
        if cand in cols:
            return cols[cand]
    for cand in COLUMN_CANDIDATES[key]:
        if len(cand) <= 4:  # skip generic substrings like "code"
            continue
        for n, original in cols.items():
            if cand in n and not (key == "category" and "sub" in n):
                return original
    return None


def read_csv_safe(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Could not decode {path.name}")


def clean_code(series: pd.Series) -> pd.Series:
    """Normalise scheme codes to clean strings (strip spaces, drop '.0')."""
    return series.dropna().astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def detect_anomalies(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []

    if df.empty:
        return ["File is empty"]

    dups = int(df.duplicated().sum())
    if dups:
        issues.append(f"{dups:,} fully duplicated rows")

    for col in df.columns:
        s = df[col]
        nulls = int(s.isna().sum())
        pct = nulls / len(df) * 100

        if str(col).startswith("Unnamed"):
            issues.append(f"Unnamed column '{col}' (likely a stray index column)")
        if nulls == len(df):
            issues.append(f"Column '{col}' is completely empty")
            continue
        if nulls:
            flag = " (HIGH)" if pct > 30 else ""
            issues.append(f"Column '{col}': {nulls:,} nulls ({pct:.1f}%){flag}")
        if s.nunique(dropna=True) == 1 and len(df) > 1:
            issues.append(f"Column '{col}' has a single constant value")

        if pd.api.types.is_numeric_dtype(s):
            if (s < 0).any():
                issues.append(f"Column '{col}': {int((s < 0).sum()):,} negative values (check if valid)")
            if any(k in norm(col) for k in ("nav", "price", "aum", "units")) and (s == 0).any():
                issues.append(f"Column '{col}': {int((s == 0).sum()):,} zero values")
        elif pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
            non_null = s.dropna().astype(str)
            stripped = non_null.str.strip()
            ws = int((non_null != stripped).sum())
            if ws:
                issues.append(f"Column '{col}': {ws:,} values with leading/trailing whitespace")
            as_num = pd.to_numeric(stripped, errors="coerce")
            ratio = as_num.notna().mean()
            if 0.9 <= ratio < 1.0:
                issues.append(
                    f"Column '{col}': mostly numeric but {int(as_num.isna().sum()):,} non-numeric values (mixed types)"
                )
            if "date" in norm(col):
                parsed = pd.to_datetime(stripped, errors="coerce", dayfirst=True, format="mixed")
                bad = int(parsed.isna().sum())
                if bad:
                    issues.append(f"Column '{col}': {bad:,} unparseable dates")

    return issues


def profile_file(name: str, df: pd.DataFrame) -> list[str]:
    print("\n" + "=" * 90)
    print(f"{name}")
    print("=" * 90)
    print(f"shape: {df.shape}")
    print("\ndtypes:")
    print(df.dtypes.to_string())
    print("\nhead():")
    print(df.head().to_string())

    issues = detect_anomalies(df)
    print("\nanomalies:")
    if issues:
        for i in issues:
            print(f"  - {i}")
    else:
        print("  - none detected")
    return issues


def find_file(datasets: dict[str, pd.DataFrame], keyword: str) -> str | None:
    for name in datasets:
        if keyword in norm(Path(name).stem):
            return name
    return None


# --------------------------------------------------------------------------- #
# fund_master exploration + AMFI code validation
# --------------------------------------------------------------------------- #
def explore_fund_master(df: pd.DataFrame) -> None:
    print("\n" + "=" * 90)
    print("FUND MASTER EXPLORATION")
    print("=" * 90)

    for key, label in [
        ("fund_house", "Fund houses"),
        ("category", "Categories"),
        ("sub_category", "Sub-categories"),
        ("risk_grade", "Risk grades"),
    ]:
        col = find_col(df, key)
        if col is None:
            print(f"\n[!] {label}: no matching column found. Columns are: {list(df.columns)}")
            print(f"    -> add the right name to COLUMN_CANDIDATES['{key}'] at the top of this file")
            continue
        counts = df[col].astype(str).str.strip().value_counts(dropna=False)
        print(f"\n{label} (column '{col}') - {len(counts)} unique:")
        print(counts.head(40).to_string())
        if len(counts) > 40:
            print(f"  ... and {len(counts) - 40} more")

    code_col = find_col(df, "scheme_code")
    print("\nAMFI scheme code structure:")
    print("  - A numeric ID assigned by AMFI to every scheme plan/option (e.g. 119551).")
    print("  - Direct/Regular and Growth/IDCW variants each get their own code.")
    print("  - Codes carry no embedded meaning, so treat them as unique keys (join on them as-is).")
    if code_col is None:
        print(f"  [!] No scheme code column found. Columns are: {list(df.columns)}")
        return
    codes = clean_code(df[code_col])
    print(f"\n  column '{code_col}': {codes.nunique():,} unique codes, {len(codes) - codes.nunique():,} duplicates")
    print("  code length distribution:")
    print(codes.str.len().value_counts().sort_index().to_string())
    non_numeric = codes[~codes.str.fullmatch(r"\d+")]
    if len(non_numeric):
        print(f"  [!] {len(non_numeric):,} non-numeric codes, e.g. {non_numeric.head(5).tolist()}")


def validate_codes(master: pd.DataFrame, nav: pd.DataFrame) -> dict | None:
    m_col, n_col = find_col(master, "scheme_code"), find_col(nav, "scheme_code")
    if m_col is None or n_col is None:
        print(f"\n[!] Cannot validate codes. fund_master code col: {m_col}, nav_history code col: {n_col}")
        return None

    master_codes = set(clean_code(master[m_col]))
    nav_codes = set(clean_code(nav[n_col]))
    missing_in_nav = sorted(master_codes - nav_codes)
    extra_in_nav = sorted(nav_codes - master_codes)

    print("\n" + "=" * 90)
    print("AMFI CODE VALIDATION (fund_master -> nav_history)")
    print("=" * 90)
    print(f"fund_master codes : {len(master_codes):,}")
    print(f"nav_history codes : {len(nav_codes):,}")
    print(f"in fund_master but NOT in nav_history: {len(missing_in_nav):,}  {missing_in_nav[:10]}")
    print(f"in nav_history but NOT in fund_master: {len(extra_in_nav):,}  {extra_in_nav[:10]}")
    print("RESULT:", "PASS - every fund_master code exists in nav_history" if not missing_in_nav else "FAIL - see missing codes above")

    return {
        "master_count": len(master_codes),
        "nav_count": len(nav_codes),
        "missing_in_nav": missing_in_nav,
        "extra_in_nav": extra_in_nav,
    }


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def write_summary(stats: list[dict], issues_by_file: dict[str, list[str]], validation: dict | None) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Data Quality Summary - Day 1",
        f"_Generated: {datetime.now():%Y-%m-%d %H:%M}_",
        "",
        "## Files loaded",
        "",
        "| File | Rows | Columns | Null cells | Duplicate rows | Issues |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for s in stats:
        lines.append(
            f"| {s['file']} | {s['rows']:,} | {s['cols']} | {s['nulls']:,} | {s['dups']:,} | {len(issues_by_file[s['file']])} |"
        )

    lines += ["", "## Anomalies by file", ""]
    for fname, issues in issues_by_file.items():
        lines.append(f"**{fname}**")
        lines += [f"- {i}" for i in issues] if issues else ["- none detected"]
        lines.append("")

    lines += ["## AMFI code validation (fund_master -> nav_history)", ""]
    if validation is None:
        lines.append("Not run (fund_master / nav_history not found or scheme code column missing).")
    else:
        lines += [
            f"- fund_master codes: {validation['master_count']:,}",
            f"- nav_history codes: {validation['nav_count']:,}",
            f"- In fund_master but missing from nav_history: {len(validation['missing_in_nav']):,}",
            f"- In nav_history but missing from fund_master: {len(validation['extra_in_nav']):,}",
            "- Result: " + ("PASS" if not validation["missing_in_nav"] else "FAIL"),
        ]
        if validation["missing_in_nav"]:
            lines.append(f"- Missing codes (first 20): {validation['missing_in_nav'][:20]}")

    path = REPORT_DIR / "data_quality_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        print(f"No CSV files found in {RAW_DIR}. Copy your 10 provided datasets there and re-run.")
        sys.exit(1)

    print(f"Found {len(files)} CSV files in {RAW_DIR.relative_to(ROOT)}/")
    if len(files) != 10:
        print(f"[note] Expected 10 datasets, found {len(files)}.")

    datasets: dict[str, pd.DataFrame] = {}
    stats: list[dict] = []
    issues_by_file: dict[str, list[str]] = {}

    for path in files:
        df = read_csv_safe(path)
        datasets[path.name] = df
        issues_by_file[path.name] = profile_file(path.name, df)
        stats.append(
            {
                "file": path.name,
                "rows": len(df),
                "cols": df.shape[1],
                "nulls": int(df.isna().sum().sum()),
                "dups": int(df.duplicated().sum()),
            }
        )

    validation = None
    master_name = find_file(datasets, "fund_master")
    nav_name = find_file(datasets, "nav_history")

    if master_name:
        explore_fund_master(datasets[master_name])
    else:
        print("\n[!] fund_master file not found (looking for a filename containing 'fund_master').")

    if master_name and nav_name:
        validation = validate_codes(datasets[master_name], datasets[nav_name])
    else:
        print("\n[!] Skipping code validation - need both a fund_master and a nav_history file.")

    report_path = write_summary(stats, issues_by_file, validation)
    print(f"\nData quality summary written to {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
