"""
build_excel_dashboard.py
Builds the Week 1 Excel sales dashboard from your investor transaction data.

Setup (once):   pip install xlsxwriter pandas
Usage:          python dashboard/build_excel_dashboard.py
                python dashboard/build_excel_dashboard.py "C:\\path\\to\\csv_folder"   (if your CSVs are elsewhere)

Output:         dashboard/Week1_Excel_Sales_Dashboard.xlsx

Sheets: Dashboard | Summary | Data | FundMaster | Performance | Lookup | About
Everything on Dashboard and Summary is a live formula (SUMIFS, COUNTIFS, AVERAGEIFS,
INDEX/MATCH) on the Data sheet, so it recalculates if the data changes.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xlsxwriter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT_FILE = HERE / "Week1_Excel_Sales_Dashboard.xlsx"
SEARCH_DIRS = [ROOT / "data" / "processed", ROOT / "data" / "raw", ROOT]

FILES = {  # table -> key in the raw file name
    "fund_master": "01_fund_master",
    "scheme_performance": "07_scheme_performance",
    "investor_transactions": "08_investor_transactions",
}
TX_COLUMNS = [
    "investor_id", "transaction_date", "amfi_code", "transaction_type", "amount_inr",
    "state", "city", "city_tier", "age_group", "gender", "annual_income_lakh",
    "payment_mode", "kyc_status",
]
FM_COLUMNS = [
    "amfi_code", "scheme_name", "fund_house", "category", "sub_category", "plan",
    "launch_date", "benchmark", "expense_ratio_pct", "exit_load_pct", "min_sip_amount",
    "fund_manager", "risk_category",
]
PERF_COLUMNS = [
    "amfi_code", "scheme_name", "return_1yr_pct", "return_3yr_pct", "return_5yr_pct",
    "benchmark_3yr_pct", "alpha", "beta", "sharpe_ratio", "std_dev_ann_pct",
    "max_drawdown_pct", "aum_crore", "expense_ratio_pct", "morningstar_rating", "risk_grade",
]
CRORE = 10_000_000

NAVY, BLUE, LIGHT, ORANGE, GREEN, RED, GREY = "#1F3864", "#2E75B6", "#DDEBF7", "#ED7D31", "#548235", "#C00000", "#595959"


# --------------------------------------------------------------------------- #
# Reading and cleaning the data
# --------------------------------------------------------------------------- #
def find_csv(table, key, extra_dir):
    places = ([(Path(extra_dir), True)] if extra_dir else []) + [(d, False) for d in SEARCH_DIRS]

    def matches(folder, pattern, recursive):
        if not folder.exists():
            return []
        return sorted(folder.rglob(pattern) if recursive else folder.glob(pattern))

    for folder, rec in places:  # cleaned file first
        found = matches(folder, f"{table}_clean.csv", rec)
        if found:
            return found[0]
    for folder, rec in places:  # then the original (long hashed names are fine)
        for pattern in (f"*{key}*.csv", f"{table}.csv"):
            found = matches(folder, pattern, rec)
            if found:
                return found[0]
    lines = "\n  ".join(
        f"{f}   <- {'does not exist' if not f.exists() else 'no matching CSV'}" for f, _ in places
    )
    sys.exit(f"Could not find the CSV for '{table}'. Searched:\n  {lines}\n"
             "Fix: pass the folder that contains your CSVs as the last argument.")


def strip_text(df):
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_datetime64_any_dtype(df[col]):
            mask = df[col].notna()
            df[col] = df[col].astype(object)
            df.loc[mask, col] = df.loc[mask, col].astype(str).str.strip()
    return df


def load_data(extra_dir):
    frames = {}
    for table, key in FILES.items():
        path = find_csv(table, key, extra_dir)
        print(f"  {table:<24} <- {path}")
        frames[table] = pd.read_csv(path)

    tx = strip_text(frames["investor_transactions"][TX_COLUMNS].copy())
    fm = strip_text(frames["fund_master"][FM_COLUMNS].copy())
    perf = strip_text(frames["scheme_performance"][PERF_COLUMNS].copy())

    # Cleaning: consistent fund house names, real dates, no duplicates / blanks
    fm["fund_house"] = fm["fund_house"].str.replace(r"\s+MF$", " Mutual Fund", regex=True)
    tx["transaction_date"] = pd.to_datetime(tx["transaction_date"], errors="coerce")
    fm["launch_date"] = pd.to_datetime(fm["launch_date"], errors="coerce")
    tx["amount_inr"] = pd.to_numeric(tx["amount_inr"], errors="coerce")
    before = len(tx)
    tx = tx.dropna(subset=["amfi_code", "transaction_date", "amount_inr", "transaction_type"]).drop_duplicates()
    if len(tx) != before:
        print(f"  cleaning: removed {before - len(tx)} blank/duplicate transaction rows")
    fm = fm.drop_duplicates(subset="amfi_code").reset_index(drop=True)
    perf = perf.drop_duplicates(subset="amfi_code").reset_index(drop=True)

    tx = tx.sort_values(["transaction_date", "investor_id"]).reset_index(drop=True)
    return tx, fm, perf


def serial(ts):
    """Excel date serial number."""
    return float((pd.Timestamp(ts) - pd.Timestamp("1899-12-30")).days)


def blank_if_nan(v):
    return None if pd.isna(v) else v


# --------------------------------------------------------------------------- #
# Workbook
# --------------------------------------------------------------------------- #
def build(tx, fm, perf, out_path):
    N, nfm, nperf = len(tx), len(fm), len(perf)
    last, fmlast, perflast = N + 1, nfm + 1, nperf + 1  # last Excel row numbers

    # ---- helper columns (also used as the cached values of the Excel formulas) ----
    fm_pos = pd.Series(range(1, nfm + 1), index=fm["amfi_code"])
    lookup = fm.set_index("amfi_code")[["scheme_name", "fund_house", "category", "sub_category"]]
    tx["month"] = tx["transaction_date"].dt.to_period("M").dt.to_timestamp()
    tx["fund_row"] = tx["amfi_code"].map(fm_pos)
    tx = tx.join(lookup, on="amfi_code")
    for c in ["scheme_name", "fund_house", "category", "sub_category"]:
        tx[c] = tx[c].fillna("Unknown")
    tx["signed"] = np.where(tx["transaction_type"] == "Redemption", -tx["amount_inr"], tx["amount_inr"])
    is_red = tx["transaction_type"] == "Redemption"
    inv = tx[~is_red]
    red = tx[is_red]

    wb = xlsxwriter.Workbook(str(out_path), {"default_format_properties": {"font_name": "Arial", "font_size": 10}})
    ws_dash = wb.add_worksheet("Dashboard")
    ws_sum = wb.add_worksheet("Summary")
    ws_data = wb.add_worksheet("Data")
    ws_fm = wb.add_worksheet("FundMaster")
    ws_perf = wb.add_worksheet("Performance")
    ws_look = wb.add_worksheet("Lookup")
    ws_about = wb.add_worksheet("About")

    # ---- formats ----
    def F(**kw):
        return wb.add_format(kw)

    f_title = F(bold=True, font_size=18, font_color="#FFFFFF", bg_color=NAVY, valign="vcenter")
    f_sub = F(italic=True, font_color="#FFFFFF", bg_color=NAVY, valign="vcenter")
    f_block = F(bold=True, font_size=12, font_color=NAVY)
    f_h = F(bold=True, font_color="#FFFFFF", bg_color=NAVY, border=1, align="center", valign="vcenter", text_wrap=True)
    f_txt = F(border=1)
    f_int = F(border=1, num_format="#,##0")
    f_n2 = F(border=1, num_format="#,##0.00")
    f_inr = F(border=1, num_format="#,##0")
    f_pct = F(border=1, num_format="0.0%")
    f_pct2 = F(border=1, num_format="0.00")
    f_mon = F(border=1, num_format="mmm yyyy", align="left")
    f_date = F(border=1, num_format="dd-mmm-yyyy", align="left")
    f_tot_t = F(bold=True, top=2, bg_color=LIGHT)
    f_tot_i = F(bold=True, top=2, bg_color=LIGHT, num_format="#,##0")
    f_tot_n = F(bold=True, top=2, bg_color=LIGHT, num_format="#,##0.00")
    f_tot_p = F(bold=True, top=2, bg_color=LIGHT, num_format="0.0%")
    f_note = F(italic=True, font_color=GREY)
    f_bold = F(bold=True)
    f_wrap = F(text_wrap=True, valign="top")
    f_input = F(bold=True, font_color="#0000FF", bg_color="#FFFF00", border=1)
    f_out = F(border=1, bg_color="#F2F2F2")
    f_out_n = F(border=1, bg_color="#F2F2F2", num_format="#,##0.00")
    f_out_i = F(border=1, bg_color="#F2F2F2", num_format="#,##0")
    f_code = F(font_name="Consolas", font_size=9, font_color=GREY, text_wrap=True, valign="top")
    f_red = F(font_color=RED)
    f_green = F(font_color=GREEN)
    f_redfill = F(bg_color="#FDE9E7")

    # ======================================================================= #
    # FundMaster and Performance sheets (lookup sources)
    # ======================================================================= #
    fm_hdr = ["AMFI Code", "Scheme Name", "Fund House", "Category", "Sub-Category", "Plan", "Launch Date",
              "Benchmark", "Expense Ratio (%)", "Exit Load (%)", "Min SIP (INR)", "Fund Manager", "Risk Category"]
    ws_fm.write_row(0, 0, fm_hdr, f_h)
    for i, row in enumerate(fm.itertuples(index=False, name=None), start=1):
        for j, v in enumerate(row):
            v = blank_if_nan(v)
            if v is None or v is pd.NaT:
                ws_fm.write_blank(i, j, None, f_txt)
            elif j == 6:
                ws_fm.write_datetime(i, j, pd.Timestamp(v).to_pydatetime(), f_date)
            elif isinstance(v, (int, float, np.integer, np.floating)):
                ws_fm.write_number(i, j, float(v), f_n2 if j in (8, 9) else f_inr if j in (0, 10) else f_txt)
            else:
                ws_fm.write_string(i, j, str(v), f_txt)
    ws_fm.set_column(0, 0, 11)
    ws_fm.set_column(1, 1, 48)
    ws_fm.set_column(2, 5, 17)
    ws_fm.set_column(6, 6, 13)
    ws_fm.set_column(7, 12, 18)
    ws_fm.freeze_panes(1, 2)
    ws_fm.autofilter(0, 0, nfm, len(fm_hdr) - 1)

    perf_hdr = ["AMFI Code", "Scheme Name", "1-Yr Return (%)", "3-Yr Return (%)", "5-Yr Return (%)",
                "Benchmark 3-Yr (%)", "Alpha", "Beta", "Sharpe Ratio", "Std Dev Ann. (%)",
                "Max Drawdown (%)", "AUM (crore)", "Expense Ratio (%)", "Morningstar Rating", "Risk Grade"]
    ws_perf.write_row(0, 0, perf_hdr, f_h)
    for i, row in enumerate(perf.itertuples(index=False, name=None), start=1):
        for j, v in enumerate(row):
            v = blank_if_nan(v)
            if v is None:
                ws_perf.write_blank(i, j, None, f_txt)
            elif isinstance(v, (int, float, np.integer, np.floating)):
                ws_perf.write_number(i, j, float(v), f_inr if j in (0, 11, 13) else f_n2)
            else:
                ws_perf.write_string(i, j, str(v), f_txt)
    ws_perf.set_column(0, 0, 11)
    ws_perf.set_column(1, 1, 48)
    ws_perf.set_column(2, 14, 14)
    ws_perf.set_row(0, 32)
    ws_perf.freeze_panes(1, 2)
    ws_perf.autofilter(0, 0, nperf, len(perf_hdr) - 1)
    ws_perf.conditional_format(1, 3, nperf, 3, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    ws_perf.conditional_format(1, 8, nperf, 8, {"type": "data_bar", "bar_color": "#9DC3E6", "bar_solid": True})
    ws_perf.conditional_format(1, 10, nperf, 10, {"type": "cell", "criteria": "<", "value": -20, "format": f_red})
    ws_perf.conditional_format(1, 13, nperf, 13, {"type": "icon_set", "icon_style": "5_ratings"})

    # ======================================================================= #
    # Data sheet: transactions + helper formula columns
    # ======================================================================= #
    data_hdr = ["Investor ID", "Transaction Date", "AMFI Code", "Transaction Type", "Amount (INR)", "State", "City",
                "City Tier", "Age Group", "Gender", "Annual Income (Lakh)", "Payment Mode", "KYC Status",
                "Month", "Fund Row", "Scheme Name", "Fund House", "Category", "Sub-Category", "Signed Amount (INR)"]
    ws_data.add_table(0, 0, N, len(data_hdr) - 1, {
        "columns": [{"header": h} for h in data_hdr], "style": "Table Style Light 9", "name": "Transactions"})
    f_d_date = wb.add_format({"num_format": "dd-mmm-yyyy"})
    f_d_inr = wb.add_format({"num_format": "#,##0"})
    f_d_n1 = wb.add_format({"num_format": "0.0"})
    f_d_mon = wb.add_format({"num_format": "mmm yyyy"})
    f_d_help = wb.add_format({"bg_color": "#F2F2F2"})
    f_d_help_inr = wb.add_format({"bg_color": "#F2F2F2", "num_format": "#,##0"})
    f_d_help_mon = wb.add_format({"bg_color": "#F2F2F2", "num_format": "mmm yyyy"})

    cols = TX_COLUMNS + ["month", "fund_row", "scheme_name", "fund_house", "category", "sub_category", "signed"]
    for i, t in enumerate(tx[cols].itertuples(index=False, name=None), start=1):
        ex = i + 1  # Excel row number
        (inv_id, dt, code, ttype, amt, state, city, tier, age, gender, income, pay, kyc,
         month, frow, sname, house, cat, sub, signed) = t
        ws_data.write_string(i, 0, str(inv_id))
        ws_data.write_datetime(i, 1, dt.to_pydatetime(), f_d_date)
        ws_data.write_number(i, 2, float(code))
        ws_data.write_string(i, 3, str(ttype))
        ws_data.write_number(i, 4, float(amt), f_d_inr)
        ws_data.write_string(i, 5, str(state))
        ws_data.write_string(i, 6, str(city))
        ws_data.write_string(i, 7, str(tier))
        ws_data.write_string(i, 8, str(age))
        ws_data.write_string(i, 9, str(gender))
        if pd.isna(income):
            ws_data.write_blank(i, 10, None, f_d_n1)
        else:
            ws_data.write_number(i, 10, float(income), f_d_n1)
        ws_data.write_string(i, 11, str(pay))
        ws_data.write_string(i, 12, str(kyc))
        ws_data.write_formula(i, 13, f"=DATE(YEAR(B{ex}),MONTH(B{ex}),1)", f_d_help_mon, serial(month))
        ws_data.write_formula(i, 14, f'=IFERROR(MATCH(C{ex},FundMaster!$A$2:$A${fmlast},0),"")', f_d_help, "" if pd.isna(frow) else float(frow))
        ws_data.write_formula(i, 15, f'=IFERROR(INDEX(FundMaster!$B$2:$B${fmlast},O{ex}),"Unknown")', f_d_help, sname)
        ws_data.write_formula(i, 16, f'=IFERROR(INDEX(FundMaster!$C$2:$C${fmlast},O{ex}),"Unknown")', f_d_help, house)
        ws_data.write_formula(i, 17, f'=IFERROR(INDEX(FundMaster!$D$2:$D${fmlast},O{ex}),"Unknown")', f_d_help, cat)
        ws_data.write_formula(i, 18, f'=IFERROR(INDEX(FundMaster!$E$2:$E${fmlast},O{ex}),"Unknown")', f_d_help, sub)
        ws_data.write_formula(i, 19, f'=IF(D{ex}="Redemption",-E{ex},E{ex})', f_d_help_inr, float(signed))
    widths = [12, 15, 11, 15, 13, 17, 14, 10, 10, 9, 13, 14, 11, 11, 9, 46, 24, 10, 16, 15]
    for j, w in enumerate(widths):
        ws_data.set_column(j, j, w)
    ws_data.set_row(0, 32)
    ws_data.freeze_panes(1, 2)
    ws_data.conditional_format(1, 3, N, 3, {"type": "cell", "criteria": "==", "value": '"Redemption"', "format": f_redfill})

    # named ranges used by every formula
    for name, col in {"tx_date": "B", "tx_code": "C", "tx_type": "D", "tx_amount": "E", "tx_state": "F",
                      "tx_tier": "H", "tx_age": "I", "tx_pay": "L", "tx_kyc": "M", "tx_month": "N",
                      "tx_scheme": "P", "tx_house": "Q", "tx_cat": "R", "tx_subcat": "S", "tx_signed": "T"}.items():
        wb.define_name(name, f"=Data!${col}$2:${col}${last}")

    # ======================================================================= #
    # Summary sheet: formula-driven "pivot style" tables
    # ======================================================================= #
    S = ws_sum
    S.write(0, 0, "Summary tables (live formulas on the Data sheet)", F(bold=True, font_size=14, font_color=NAVY))
    S.write(1, 0, "1 crore (rupees)", f_bold)
    S.write_number(1, 1, CRORE, F(bold=True, font_color="#0000FF", bg_color="#FFFF00", border=1, num_format="#,##0"))
    S.write(1, 2, "Assumption: 1 crore = 10,000,000 rupees. All '₹ crore' columns divide by this cell.", f_note)
    wb.define_name("crore", "=Summary!$B$2")
    S.set_column(0, 0, 46)
    S.set_column(1, 8, 17)
    pos = {}

    def header(r, title, hdrs):
        S.write(r, 0, title, f_block)
        S.write_row(r + 1, 0, hdrs, f_h)
        S.set_row(r + 1, 32)
        return r + 2

    # ---- A. transaction type ----
    r = header(3, "A. Transaction type summary", ["Transaction type", "Transactions", "Total amount (₹ crore)", "Average ticket (₹)", "Share of total value"])
    types = [t for t in ["SIP", "Lumpsum", "Redemption"] if t in set(tx["transaction_type"])]
    types += sorted(set(tx["transaction_type"]) - set(types))
    a0 = r
    all_val = tx["amount_inr"].sum() / CRORE
    for t in types:
        x = tx[tx["transaction_type"] == t]
        ex = r + 1
        S.write_string(r, 0, t, f_txt)
        S.write_formula(r, 1, f"=COUNTIFS(tx_type,$A{ex})", f_int, len(x))
        S.write_formula(r, 2, f"=SUMIFS(tx_amount,tx_type,$A{ex})/crore", f_n2, x["amount_inr"].sum() / CRORE)
        S.write_formula(r, 3, f"=IFERROR(AVERAGEIFS(tx_amount,tx_type,$A{ex}),0)", f_inr, float(x["amount_inr"].mean()))
        S.write_formula(r, 4, f"=C{ex}/SUM($C${a0 + 1}:$C${a0 + len(types)})", f_pct, x["amount_inr"].sum() / CRORE / all_val)
        r += 1
    S.write(r, 0, "Total", f_tot_t)
    S.write_formula(r, 1, f"=SUM(B{a0 + 1}:B{r})", f_tot_i, N)
    S.write_formula(r, 2, f"=SUM(C{a0 + 1}:C{r})", f_tot_n, all_val)
    S.write_blank(r, 3, None, f_tot_t)
    S.write_formula(r, 4, f"=SUM(E{a0 + 1}:E{r})", f_tot_p, 1.0)
    pos["type"] = (a0, r - 1)
    r += 3

    # ---- B. monthly ----
    r = header(r, "B. Monthly flows", ["Month", "Investment (₹ crore)", "Redemption (₹ crore)", "Net investment (₹ crore)",
                                       "Cumulative net (₹ crore)", "Change vs previous month (₹ crore)"])
    months = sorted(tx["month"].unique())
    m_inv = inv.groupby("month")["amount_inr"].sum() / CRORE
    m_red = red.groupby("month")["amount_inr"].sum() / CRORE
    b0, cum, prev_net = r, 0.0, None
    for k, m in enumerate(months):
        ex = r + 1
        iv, rd = float(m_inv.get(m, 0.0)), float(m_red.get(m, 0.0))
        net = iv - rd
        cum += net
        S.write_datetime(r, 0, pd.Timestamp(m).to_pydatetime(), f_mon)
        S.write_formula(r, 1, f'=SUMIFS(tx_amount,tx_type,"<>Redemption",tx_month,$A{ex})/crore', f_n2, iv)
        S.write_formula(r, 2, f'=SUMIFS(tx_amount,tx_type,"Redemption",tx_month,$A{ex})/crore', f_n2, rd)
        S.write_formula(r, 3, f"=B{ex}-C{ex}", f_n2, net)
        S.write_formula(r, 4, f"=SUM($D${b0 + 1}:D{ex})", f_n2, cum)
        if k == 0:
            S.write_string(r, 5, "n/a", f_txt)
        else:
            S.write_formula(r, 5, f"=D{ex}-D{ex - 1}", f_n2, net - prev_net)
        prev_net = net
        r += 1
    pos["month"] = (b0, r - 1)
    S.conditional_format(b0, 3, r - 1, 3, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    S.conditional_format(b0 + 1, 5, r - 1, 5, {"type": "cell", "criteria": "<", "value": 0, "format": f_red})
    S.conditional_format(b0 + 1, 5, r - 1, 5, {"type": "cell", "criteria": ">", "value": 0, "format": f_green})
    r += 2

    # ---- C. category / sub-category ----
    r = header(r, "C. Investment by category and sub-category", ["Category", "Sub-category", "Investment (₹ crore)",
                                                                  "Redemption (₹ crore)", "Net (₹ crore)", "Share of investment"])
    gi = (inv.groupby(["category", "sub_category"])["amount_inr"].sum() / CRORE)
    gr = (red.groupby(["category", "sub_category"])["amount_inr"].sum() / CRORE)
    keys = sorted(set(gi.index) | set(gr.index), key=lambda k: -float(gi.get(k, 0.0)))
    c0, tot_inv = r, float(gi.sum())
    for (cat, sub) in keys:
        ex = r + 1
        iv, rd = float(gi.get((cat, sub), 0.0)), float(gr.get((cat, sub), 0.0))
        S.write_string(r, 0, cat, f_txt)
        S.write_string(r, 1, sub, f_txt)
        S.write_formula(r, 2, f'=SUMIFS(tx_amount,tx_type,"<>Redemption",tx_cat,$A{ex},tx_subcat,$B{ex})/crore', f_n2, iv)
        S.write_formula(r, 3, f'=SUMIFS(tx_amount,tx_type,"Redemption",tx_cat,$A{ex},tx_subcat,$B{ex})/crore', f_n2, rd)
        S.write_formula(r, 4, f"=C{ex}-D{ex}", f_n2, iv - rd)
        S.write_formula(r, 5, f"=C{ex}/SUM($C${c0 + 1}:$C${c0 + len(keys)})", f_pct, iv / tot_inv)
        r += 1
    pos["cat"] = (c0, r - 1)
    S.conditional_format(c0, 2, r - 1, 2, {"type": "data_bar", "bar_color": "#9DC3E6", "bar_solid": True})
    r += 2

    # ---- D. state ----
    r = header(r, "D. Investment by state (sorted high to low when built)", ["State", "Transactions (all types)", "Investment (₹ crore)", "Share of investment"])
    s_inv = (inv.groupby("state")["amount_inr"].sum() / CRORE).sort_values(ascending=False)
    s_cnt = tx.groupby("state").size()
    d0 = r
    for st, iv in s_inv.items():
        ex = r + 1
        S.write_string(r, 0, st, f_txt)
        S.write_formula(r, 1, f"=COUNTIFS(tx_state,$A{ex})", f_int, int(s_cnt[st]))
        S.write_formula(r, 2, f'=SUMIFS(tx_amount,tx_type,"<>Redemption",tx_state,$A{ex})/crore', f_n2, float(iv))
        S.write_formula(r, 3, f"=C{ex}/SUM($C${d0 + 1}:$C${d0 + len(s_inv)})", f_pct, float(iv) / float(s_inv.sum()))
        r += 1
    pos["state"] = (d0, r - 1)
    S.conditional_format(d0, 2, r - 1, 2, {"type": "data_bar", "bar_color": "#F4B183", "bar_solid": True})
    r += 2

    # ---- E. city tier x age group (SIP) ----
    tiers = sorted(tx["city_tier"].unique())
    ages = sorted(tx["age_group"].unique())
    sip = tx[tx["transaction_type"] == "SIP"]
    r = header(r, "E1. Average SIP ticket (₹) by city tier and age group", ["City tier"] + list(ages))
    e0 = r
    for t in tiers:
        ex = r + 1
        S.write_string(r, 0, t, f_txt)
        for j, a in enumerate(ages, start=1):
            col = chr(ord("A") + j)
            x = sip[(sip["city_tier"] == t) & (sip["age_group"] == a)]["amount_inr"]
            S.write_formula(r, j, f'=IFERROR(AVERAGEIFS(tx_amount,tx_type,"SIP",tx_tier,$A{ex},tx_age,{col}${e0}),0)', f_inr, float(x.mean()) if len(x) else 0.0)
        r += 1
    pos["sipavg"] = (e0, r - 1, len(ages))
    S.conditional_format(e0, 1, r - 1, len(ages), {"type": "3_color_scale", "min_color": "#FFFFFF", "mid_color": "#BDD7EE", "max_color": "#2E75B6"})
    r += 2
    r = header(r, "E2. Total SIP amount (₹ crore) by city tier and age group", ["City tier"] + list(ages))
    e2 = r
    for t in tiers:
        ex = r + 1
        S.write_string(r, 0, t, f_txt)
        for j, a in enumerate(ages, start=1):
            col = chr(ord("A") + j)
            x = sip[(sip["city_tier"] == t) & (sip["age_group"] == a)]["amount_inr"]
            S.write_formula(r, j, f'=SUMIFS(tx_amount,tx_type,"SIP",tx_tier,$A{ex},tx_age,{col}${e2})/crore', f_n2, float(x.sum()) / CRORE)
        r += 1
    r += 2

    # ---- F. payment mode ----
    r = header(r, "F. Payment mode (all transaction types)", ["Payment mode", "Transactions", "Total amount (₹ crore)", "Share of value"])
    p_val = (tx.groupby("payment_mode")["amount_inr"].sum() / CRORE).sort_values(ascending=False)
    p_cnt = tx.groupby("payment_mode").size()
    f0 = r
    for pm, v in p_val.items():
        ex = r + 1
        S.write_string(r, 0, pm, f_txt)
        S.write_formula(r, 1, f"=COUNTIFS(tx_pay,$A{ex})", f_int, int(p_cnt[pm]))
        S.write_formula(r, 2, f"=SUMIFS(tx_amount,tx_pay,$A{ex})/crore", f_n2, float(v))
        S.write_formula(r, 3, f"=C{ex}/SUM($C${f0 + 1}:$C${f0 + len(p_val)})", f_pct, float(v) / float(p_val.sum()))
        r += 1
    pos["pay"] = (f0, r - 1)
    r += 2

    # ---- G. fund house ----
    r = header(r, "G. Fund house", ["Fund house", "Investment (₹ crore)", "Redemption (₹ crore)", "Net (₹ crore)", "Share of investment"])
    h_inv = (inv.groupby("fund_house")["amount_inr"].sum() / CRORE).sort_values(ascending=False)
    h_red = red.groupby("fund_house")["amount_inr"].sum() / CRORE
    g0 = r
    for h, iv in h_inv.items():
        ex = r + 1
        rd = float(h_red.get(h, 0.0))
        S.write_string(r, 0, h, f_txt)
        S.write_formula(r, 1, f'=SUMIFS(tx_amount,tx_type,"<>Redemption",tx_house,$A{ex})/crore', f_n2, float(iv))
        S.write_formula(r, 2, f'=SUMIFS(tx_amount,tx_type,"Redemption",tx_house,$A{ex})/crore', f_n2, rd)
        S.write_formula(r, 3, f"=B{ex}-C{ex}", f_n2, float(iv) - rd)
        S.write_formula(r, 4, f"=B{ex}/SUM($B${g0 + 1}:$B${g0 + len(h_inv)})", f_pct, float(iv) / float(h_inv.sum()))
        r += 1
    pos["house"] = (g0, r - 1)
    S.conditional_format(g0, 1, r - 1, 1, {"type": "data_bar", "bar_color": "#A9D18E", "bar_solid": True})
    r += 2

    # ---- H. scheme (product) performance vs money flows ----
    r = header(r, "H. Schemes: net money flow vs performance (sorted by net flow when built)",
               ["Scheme", "AMFI code", "Category", "Investment (₹ crore)", "Redemption (₹ crore)", "Net (₹ crore)",
                "1-yr return (%)", "3-yr return (%)", "Sharpe ratio"])
    sc_inv = inv.groupby("amfi_code")["amount_inr"].sum() / CRORE
    sc_red = red.groupby("amfi_code")["amount_inr"].sum() / CRORE
    codes = fm["amfi_code"].tolist()
    net_by = {c: float(sc_inv.get(c, 0.0)) - float(sc_red.get(c, 0.0)) for c in codes}
    codes.sort(key=lambda c: -net_by[c])
    fm_i = fm.set_index("amfi_code")
    pf_i = perf.set_index("amfi_code")
    h0 = r
    for c in codes:
        ex = r + 1
        S.write_number(r, 1, float(c), f_inr)
        S.write_formula(r, 0, f'=IFERROR(INDEX(FundMaster!$B$2:$B${fmlast},MATCH($B{ex},FundMaster!$A$2:$A${fmlast},0)),"Unknown")', f_txt, fm_i.loc[c, "scheme_name"])
        S.write_formula(r, 2, f'=IFERROR(INDEX(FundMaster!$D$2:$D${fmlast},MATCH($B{ex},FundMaster!$A$2:$A${fmlast},0)),"Unknown")', f_txt, fm_i.loc[c, "category"])
        iv, rd = float(sc_inv.get(c, 0.0)), float(sc_red.get(c, 0.0))
        S.write_formula(r, 3, f'=SUMIFS(tx_amount,tx_type,"<>Redemption",tx_code,$B{ex})/crore', f_n2, iv)
        S.write_formula(r, 4, f'=SUMIFS(tx_amount,tx_type,"Redemption",tx_code,$B{ex})/crore', f_n2, rd)
        S.write_formula(r, 5, f"=D{ex}-E{ex}", f_n2, iv - rd)
        for j, (pcol, pname) in enumerate([("C", "return_1yr_pct"), ("D", "return_3yr_pct"), ("I", "sharpe_ratio")], start=6):
            val = float(pf_i.loc[c, pname]) if c in pf_i.index else ""
            S.write_formula(r, j, f'=IFERROR(INDEX(Performance!${pcol}$2:${pcol}${perflast},MATCH($B{ex},Performance!$A$2:$A${perflast},0)),"")', f_n2, val)
        r += 1
    pos["scheme"] = (h0, r - 1)
    S.conditional_format(h0, 5, r - 1, 5, {"type": "data_bar", "bar_color": "#9DC3E6", "bar_solid": True})
    S.conditional_format(h0, 7, r - 1, 7, {"type": "3_color_scale", "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    S.freeze_panes(3, 1)
    S.set_landscape()
    S.fit_to_pages(1, 0)

    # ======================================================================= #
    # Dashboard
    # ======================================================================= #
    D = ws_dash
    D.hide_gridlines(2)
    D.set_column(0, 0, 2)
    D.set_column(1, 14, 11.5)
    D.set_column(15, 15, 2)
    D.set_row(0, 30)
    D.set_row(1, 30)
    D.merge_range(0, 1, 0, 14, "Mutual Fund Investor Transactions Dashboard", f_title)
    period = f"Period: {tx['transaction_date'].min():%b %Y} to {tx['transaction_date'].max():%b %Y}  |  {N:,} transactions  |  amounts in ₹ crore unless stated"
    D.merge_range(1, 1, 1, 14, "", f_sub)
    D.write_formula(1, 1, '="Period: "&TEXT(MIN(tx_date),"mmm yyyy")&" to "&TEXT(MAX(tx_date),"mmm yyyy")&"  |  "&TEXT(ROWS(tx_code),"#,##0")&" transactions  |  amounts in ₹ crore unless stated"', f_sub, period)

    total_inv = float(inv["amount_inr"].sum()) / CRORE
    total_red = float(red["amount_inr"].sum()) / CRORE
    sip_amt = float(sip["amount_inr"].sum()) / CRORE
    kpis = [
        ("Total investment (₹ crore)", '=SUMIFS(tx_amount,tx_type,"<>Redemption")/crore', total_inv, "#,##0.00"),
        ("Total redemptions (₹ crore)", '=SUMIFS(tx_amount,tx_type,"Redemption")/crore', total_red, "#,##0.00"),
        ("Net investment (₹ crore)", "=B7-D7", total_inv - total_red, "#,##0.00"),
        ("Total SIP amount (₹ crore)", '=SUMIFS(tx_amount,tx_type,"SIP")/crore', sip_amt, "#,##0.00"),
        ("Average SIP ticket (₹)", '=IFERROR(AVERAGEIFS(tx_amount,tx_type,"SIP"),0)', float(sip["amount_inr"].mean()), "#,##0"),
        ("Transactions", "=ROWS(tx_code)", float(N), "#,##0"),
        ("KYC verified", '=COUNTIF(tx_kyc,"Verified")/ROWS(tx_kyc)', float((tx["kyc_status"] == "Verified").mean()), "0.0%"),
    ]
    D.set_row(3, 6)
    D.set_row(4, 22)
    D.set_row(5, 6)
    D.set_row(6, 34)
    # KPI formulas: row 7 (Excel) holds the values; "Net" needs the investment (B7) and redemptions (D7)
    for k, (label, formula, value, nf) in enumerate(kpis):
        c0 = 1 + 2 * k
        f_lab = F(bold=True, font_size=9, font_color=GREY, bg_color=LIGHT, align="center", valign="vcenter", text_wrap=True, top=2, top_color=BLUE, left=1, right=1, left_color=LIGHT, right_color=LIGHT)
        f_val = F(bold=True, font_size=18, font_color=NAVY, bg_color=LIGHT, align="center", valign="vcenter", num_format=nf, left=1, right=1, bottom=1, left_color=LIGHT, right_color=LIGHT, bottom_color=LIGHT)
        D.merge_range(4, c0, 4, c0 + 1, label, f_lab)
        D.merge_range(6, c0, 6, c0 + 1, "", f_val)
        D.write_formula(6, c0, formula, f_val, value)
        if k == 2:
            D.conditional_format(6, c0, 6, c0, {"type": "cell", "criteria": ">=", "value": 0, "format": F(font_color=GREEN, bold=True)})
            D.conditional_format(6, c0, 6, c0, {"type": "cell", "criteria": "<", "value": 0, "format": F(font_color=RED, bold=True)})
    D.set_row(7, 8)

    # ---- charts ----
    def chart_base(ctype, subtype=None, title=""):
        ch = wb.add_chart({"type": ctype, **({"subtype": subtype} if subtype else {})})
        ch.set_title({"name": title, "name_font": {"name": "Arial", "size": 11, "bold": True, "color": NAVY}})
        ch.set_legend({"position": "bottom", "font": {"name": "Arial", "size": 9}})
        ch.set_size({"width": 598, "height": 300})
        ch.set_chartarea({"border": {"color": "#BFBFBF"}})
        return ch

    def rng(first, last, col):
        return ["Summary", first, col, last, col]

    axis_font = {"name": "Arial", "size": 9}
    mo0, mo1 = pos["month"]
    c1 = chart_base("column", title="Monthly investment vs redemption (₹ crore)")
    c1.add_series({"name": "Investment", "categories": rng(mo0, mo1, 0), "values": rng(mo0, mo1, 1), "fill": {"color": BLUE}, "gap": 60})
    c1.add_series({"name": "Redemption", "categories": rng(mo0, mo1, 0), "values": rng(mo0, mo1, 2), "fill": {"color": ORANGE}})
    ln = wb.add_chart({"type": "line"})
    ln.add_series({"name": "Net investment", "categories": rng(mo0, mo1, 0), "values": rng(mo0, mo1, 3),
                   "line": {"color": GREEN, "width": 2.25}, "marker": {"type": "circle", "size": 5, "fill": {"color": GREEN}, "border": {"color": GREEN}}})
    c1.combine(ln)
    c1.set_x_axis({"num_format": "mmm yy", "label_position": "low", "num_font": {"name": "Arial", "size": 8, "rotation": -45}})
    c1.set_y_axis({"num_font": axis_font, "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})

    ca0, ca1 = pos["cat"]
    c2 = chart_base("bar", title="Investment by sub-category (₹ crore)")
    c2.add_series({"name": "Investment", "categories": rng(ca0, ca1, 1), "values": rng(ca0, ca1, 2), "fill": {"color": BLUE}, "gap": 40,
                   "data_labels": {"value": True, "num_format": "0.0", "font": {"name": "Arial", "size": 8}}})
    c2.set_legend({"none": True})
    c2.set_y_axis({"reverse": True, "crossing": "max", "label_position": "low", "num_font": axis_font})
    c2.set_x_axis({"min": 0, "num_font": axis_font, "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})

    st0, st1 = pos["state"]
    top_n = min(10, st1 - st0 + 1)
    c3 = chart_base("bar", title="Top 10 states by investment (₹ crore)")
    c3.add_series({"name": "Investment", "categories": rng(st0, st0 + top_n - 1, 0), "values": rng(st0, st0 + top_n - 1, 2), "fill": {"color": ORANGE}, "gap": 40,
                   "data_labels": {"value": True, "num_format": "0.0", "font": {"name": "Arial", "size": 8}}})
    c3.set_legend({"none": True})
    c3.set_y_axis({"reverse": True, "crossing": "max", "label_position": "low", "num_font": axis_font})
    c3.set_x_axis({"min": 0, "num_font": axis_font, "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})

    hs0, hs1 = pos["house"]
    c4 = chart_base("bar", title="Investment by fund house (₹ crore)")
    c4.add_series({"name": "Investment", "categories": rng(hs0, hs1, 0), "values": rng(hs0, hs1, 1), "fill": {"color": GREEN}, "gap": 40,
                   "data_labels": {"value": True, "num_format": "0.0", "font": {"name": "Arial", "size": 8}}})
    c4.set_legend({"none": True})
    c4.set_y_axis({"reverse": True, "crossing": "max", "label_position": "low", "num_font": axis_font})
    c4.set_x_axis({"min": 0, "num_font": axis_font, "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})

    sa0, sa1, nage = pos["sipavg"]
    c5 = chart_base("column", title="Average SIP ticket by age group and city tier (₹)")
    palette = [BLUE, ORANGE, GREEN, "#7F7F7F"]
    for i, rrow in enumerate(range(sa0, sa1 + 1)):
        c5.add_series({"name": ["Summary", rrow, 0], "categories": ["Summary", sa0 - 1, 1, sa0 - 1, nage],
                       "values": ["Summary", rrow, 1, rrow, nage], "fill": {"color": palette[i % 4]}, "gap": 80})
    c5.set_x_axis({"num_font": axis_font})
    c5.set_y_axis({"min": 0, "num_font": axis_font, "num_format": "#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})

    py0, py1 = pos["pay"]
    c6 = chart_base("doughnut", title="Payment mode share of transaction value")
    c6.add_series({"categories": rng(py0, py1, 0), "values": rng(py0, py1, 2),
                   "points": [{"fill": {"color": col}} for col in [BLUE, ORANGE, GREEN, "#7F7F7F", "#FFC000", "#5B9BD5"][: py1 - py0 + 1]],
                   "data_labels": {"percentage": True, "font": {"name": "Arial", "size": 9, "color": "#FFFFFF", "bold": True}}})
    c6.set_hole_size(50)

    sc0, sc1 = pos["scheme"]
    top_s = min(10, sc1 - sc0 + 1)
    c7 = chart_base("bar", title="Top 10 schemes by net money flow (₹ crore)")
    c7.add_series({"name": "Net flow", "categories": rng(sc0, sc0 + top_s - 1, 0), "values": rng(sc0, sc0 + top_s - 1, 5), "fill": {"color": BLUE}, "gap": 40,
                   "data_labels": {"value": True, "num_format": "0.00", "font": {"name": "Arial", "size": 8}}})
    c7.set_legend({"none": True})
    c7.set_y_axis({"reverse": True, "crossing": "max", "label_position": "low", "num_font": {"name": "Arial", "size": 8}})
    c7.set_x_axis({"num_font": axis_font, "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})

    t0, t1 = pos["type"]
    c8 = chart_base("pie", title="Value by transaction type (₹ crore)")
    c8.add_series({"categories": rng(t0, t1, 0), "values": rng(t0, t1, 2),
                   "points": [{"fill": {"color": col}} for col in [BLUE, GREEN, ORANGE, "#7F7F7F"][: t1 - t0 + 1]],
                   "data_labels": {"category": True, "percentage": True, "separator": "\n", "position": "outside_end", "font": {"name": "Arial", "size": 9}}})
    c8.set_legend({"none": True})

    layout = [(c1, c2), (c3, c4), (c5, c6), (c7, c8)]
    for i, (left, right) in enumerate(layout):
        row = 8 + i * 16
        D.insert_chart(row, 1, left, {"x_offset": 0, "y_offset": 0})
        D.insert_chart(row, 8, right, {"x_offset": 0, "y_offset": 0})

    # ---- formula-driven takeaways ----
    r0 = 8 + 4 * 16 + 1
    D.merge_range(r0, 1, r0, 14, "Key takeaways (these sentences update with the data)", F(bold=True, font_size=12, font_color="#FFFFFF", bg_color=BLUE))
    f_take = F(text_wrap=True, valign="vcenter", border=1, border_color="#BFBFBF")

    top_state = s_inv.index[0]
    best_sub = keys[0][1]
    month_net = {m: float(m_inv.get(m, 0.0)) - float(m_red.get(m, 0.0)) for m in months}
    best_month = max(month_net, key=month_net.get)
    sip_share_tx = float((tx["transaction_type"] == "SIP").mean())
    sip_share_amt = sip_amt / total_inv
    red_ratio = total_red / total_inv

    st_rng_a, st_rng_c = f"Summary!$A${st0 + 1}:$A${st1 + 1}", f"Summary!$C${st0 + 1}:$C${st1 + 1}"
    ca_rng_b, ca_rng_c = f"Summary!$B${ca0 + 1}:$B${ca1 + 1}", f"Summary!$C${ca0 + 1}:$C${ca1 + 1}"
    mo_rng_a, mo_rng_d = f"Summary!$A${mo0 + 1}:$A${mo1 + 1}", f"Summary!$D${mo0 + 1}:$D${mo1 + 1}"
    takeaways = [
        (f'="1. Top state: "&INDEX({st_rng_a},MATCH(MAX({st_rng_c}),{st_rng_c},0))&" with ₹ "&TEXT(MAX({st_rng_c}),"0.00")&" crore of investment."',
         f"1. Top state: {top_state} with ₹ {s_inv.iloc[0]:.2f} crore of investment."),
        (f'="2. Top sub-category: "&INDEX({ca_rng_b},MATCH(MAX({ca_rng_c}),{ca_rng_c},0))&" with ₹ "&TEXT(MAX({ca_rng_c}),"0.00")&" crore of investment."',
         f"2. Top sub-category: {best_sub} with ₹ {float(gi.get(keys[0], 0.0)):.2f} crore of investment."),
        (f'="3. Best month for net investment: "&TEXT(INDEX({mo_rng_a},MATCH(MAX({mo_rng_d}),{mo_rng_d},0)),"mmm yyyy")&" (₹ "&TEXT(MAX({mo_rng_d}),"0.00")&" crore)."',
         f"3. Best month for net investment: {pd.Timestamp(best_month):%b %Y} (₹ {month_net[best_month]:.2f} crore)."),
        ('="4. SIP is "&TEXT(COUNTIFS(tx_type,"SIP")/ROWS(tx_type),"0.0%")&" of transactions but only "&TEXT(SUMIFS(tx_amount,tx_type,"SIP")/SUMIFS(tx_amount,tx_type,"<>Redemption"),"0.0%")&" of the amount invested."',
         f"4. SIP is {sip_share_tx:.1%} of transactions but only {sip_share_amt:.1%} of the amount invested."),
        ('="5. Redemptions equal "&TEXT(SUMIFS(tx_amount,tx_type,"Redemption")/SUMIFS(tx_amount,tx_type,"<>Redemption"),"0.0%")&" of investments; net investment "&IF(F7>=0,"stays positive at","is negative at")&" ₹ "&TEXT(F7,"0.00")&" crore."',
         f"5. Redemptions equal {red_ratio:.1%} of investments; net investment {'stays positive at' if total_inv - total_red >= 0 else 'is negative at'} ₹ {total_inv - total_red:.2f} crore."),
    ]
    for i, (formula, cached) in enumerate(takeaways):
        rr = r0 + 1 + i
        D.set_row(rr, 24)
        D.merge_range(rr, 1, rr, 14, "", f_take)
        D.write_formula(rr, 1, formula, f_take, cached)
    D.set_landscape()
    D.fit_to_pages(1, 0)
    D.set_paper(9)

    # ======================================================================= #
    # Lookup sheet
    # ======================================================================= #
    L = ws_look
    L.hide_gridlines(2)
    L.set_column(0, 0, 3)
    L.set_column(1, 1, 30)
    L.set_column(2, 2, 52)
    L.set_column(3, 3, 95)
    L.write(0, 1, "Lookup tools (INDEX / MATCH)", F(bold=True, font_size=16, font_color=NAVY))
    L.write(1, 1, "Yellow cells are inputs: pick a value from the drop-down and the grey cells update. Column D shows the same lookup written with XLOOKUP (Excel 365 / 2021).", f_note)

    default_code = 119551 if 119551 in set(fm["amfi_code"]) else fm["amfi_code"].iloc[0]
    L.write(3, 1, "Tool 1: Scheme finder", f_block)
    L.write(4, 1, "AMFI code (choose)", f_bold)
    L.write_number(4, 2, float(default_code), f_input)
    L.data_validation(4, 2, 4, 2, {"validate": "list", "source": f"=FundMaster!$A$2:$A${fmlast}"})
    L.write(4, 3, "<- yellow input cell: pick any AMFI code from the drop-down", f_note)
    L.write_row(5, 1, ["Field", "Result (INDEX / MATCH)", "Same lookup with XLOOKUP (shown as text)"], f_h)

    fr = fm_i.loc[default_code]
    pr = pf_i.loc[default_code] if default_code in pf_i.index else None
    dc_inv = float(sc_inv.get(default_code, 0.0))
    dc_red = float(sc_red.get(default_code, 0.0))
    fields = [
        ("Scheme name", "B", fr["scheme_name"], "fm"),
        ("Fund house", "C", fr["fund_house"], "fm"),
        ("Category", "D", fr["category"], "fm"),
        ("Sub-category", "E", fr["sub_category"], "fm"),
        ("Plan", "F", fr["plan"], "fm"),
        ("Expense ratio (%)", "I", float(fr["expense_ratio_pct"]), "fm"),
        ("Risk category", "M", fr["risk_category"], "fm"),
        ("3-year return (%)", "D", float(pr["return_3yr_pct"]) if pr is not None else "", "perf"),
        ("Sharpe ratio", "I", float(pr["sharpe_ratio"]) if pr is not None else "", "perf"),
        ("Morningstar rating", "N", float(pr["morningstar_rating"]) if pr is not None else "", "perf"),
    ]
    rr = 6
    for label, col, cached, src in fields:
        sheet, last_row = ("FundMaster", fmlast) if src == "fm" else ("Performance", perflast)
        L.write_string(rr, 1, label, f_txt)
        L.write_formula(rr, 2,
                        f'=IFERROR(INDEX({sheet}!${col}$2:${col}${last_row},MATCH($C$5,{sheet}!$A$2:$A${last_row},0)),"Not found")',
                        f_out_n if isinstance(cached, float) else f_out, cached)
        L.write_string(rr, 3, f'=XLOOKUP($C$5,{sheet}!$A$2:$A${last_row},{sheet}!${col}$2:${col}${last_row},"Not found")', f_code)
        rr += 1
    for label, formula, cached, fmt_ in [
        ("Number of transactions", "=COUNTIFS(tx_code,$C$5)", float((tx["amfi_code"] == default_code).sum()), f_out_i),
        ("Investment (₹ crore)", '=SUMIFS(tx_amount,tx_type,"<>Redemption",tx_code,$C$5)/crore', dc_inv, f_out_n),
        ("Redemptions (₹ crore)", '=SUMIFS(tx_amount,tx_type,"Redemption",tx_code,$C$5)/crore', dc_red, f_out_n),
    ]:
        L.write_string(rr, 1, label, f_txt)
        L.write_formula(rr, 2, formula, fmt_, cached)
        L.write_string(rr, 3, "SUMIFS / COUNTIFS on the Data sheet", f_code)
        rr += 1
    L.write_string(rr, 1, "Net investment (₹ crore)", f_txt)
    L.write_formula(rr, 2, f"=C{rr - 1}-C{rr}", f_out_n, dc_inv - dc_red)
    L.write_string(rr, 3, "Investment minus redemptions", f_code)

    t2 = rr + 3
    L.write(t2, 1, "Tool 2: Two-way lookup (INDEX / MATCH / MATCH)", f_block)
    L.write(t2 + 1, 1, "City tier (choose)", f_bold)
    L.write_string(t2 + 1, 2, tiers[0], f_input)
    L.data_validation(t2 + 1, 2, t2 + 1, 2, {"validate": "list", "source": list(tiers)})
    L.write(t2 + 2, 1, "Age group (choose)", f_bold)
    L.write_string(t2 + 2, 2, ages[0], f_input)
    L.data_validation(t2 + 2, 2, t2 + 2, 2, {"validate": "list", "source": list(ages)})
    L.write(t2 + 3, 1, "Average SIP ticket (₹)", f_txt)
    ae0, ae1, nag = pos["sipavg"]
    x0 = sip[(sip["city_tier"] == tiers[0]) & (sip["age_group"] == ages[0])]["amount_inr"]
    last_col = chr(ord("A") + nag)
    L.write_formula(t2 + 3, 2,
                    f"=INDEX(Summary!$B${ae0 + 1}:${last_col}${ae1 + 1},MATCH($C${t2 + 2},Summary!$A${ae0 + 1}:$A${ae1 + 1},0),MATCH($C${t2 + 3},Summary!$B${ae0}:${last_col}${ae0},0))",
                    f_out_i, float(x0.mean()) if len(x0) else 0.0)
    L.write_string(t2 + 3, 3, "Row number from the city tier, column number from the age group, both found with MATCH", f_code)

    # ======================================================================= #
    # About sheet
    # ======================================================================= #
    A = ws_about
    A.hide_gridlines(2)
    A.set_column(0, 0, 3)
    A.set_column(1, 1, 26)
    A.set_column(2, 2, 120)
    A.write(0, 1, "About this workbook", F(bold=True, font_size=16, font_color=NAVY))
    rows = [
        ("Purpose", "Week 1 sales dashboard for the Capstone Project (Mutual Fund Analytics). 'Sales' here means investor transactions: SIP and lumpsum investments less redemptions."),
        ("Data source", "The provided CSV datasets: investor_transactions, fund_master and scheme_performance (user-provided project data)."),
        ("Dashboard", "KPI cards, 8 charts and 5 sentences that update with the data."),
        ("Summary", "Pivot-style tables built with SUMIFS / COUNTIFS / AVERAGEIFS on the Data sheet (blocks A to H). The Dashboard charts read from here."),
        ("Data", "Cleaned transactions as an Excel Table with filter buttons (sorting and filtering). Grey columns N to T are formulas: month, a lookup row and INDEX/MATCH lookups to FundMaster."),
        ("FundMaster / Performance", "Lookup tables used by INDEX / MATCH. Performance has conditional formatting: colour scale on 3-year return, data bars on Sharpe, rating icons."),
        ("Lookup", "Interactive INDEX / MATCH tools. Column D shows the equivalent XLOOKUP formulas as text."),
        ("", ""),
        ("Definitions", "Investment = SIP + Lumpsum amounts. Redemption = Redemption amounts. Net investment = Investment - Redemption. 1 crore = 10,000,000 rupees (cell Summary!B2)."),
        ("Cleaning done", "Text trimmed; dates converted to real dates; fund house names standardised ('MF' -> 'Mutual Fund'); duplicate and blank rows removed; amounts stored as numbers."),
        ("If the data changes", "Formulas use named ranges (Formulas > Name Manager: tx_amount, tx_type, tx_month ...) that cover Data rows 2 to " + str(last) + ". If you add rows, extend those names."),
        ("Order of rows", "States, sub-categories, fund houses and schemes were sorted high to low when the file was built. The numbers are formulas; only the sort order is fixed."),
        ("", ""),
        ("Add a real PivotTable", "1) Click any cell in the Data sheet.  2) Insert > PivotTable > OK.  3) Drag 'State' to Rows, 'Transaction Type' to Columns, 'Amount (INR)' to Values (Sum).  4) Insert > Slicer > 'City Tier' and 'Age Group' to filter.  Compare it with Summary block D."),
    ]
    for i, (k, v) in enumerate(rows, start=2):
        A.write(i, 1, k, f_bold)
        A.write(i, 2, v, f_wrap)
        if len(v) > 120:
            A.set_row(i, 30)

    ws_dash.activate()
    wb.close()
    return N


def main():
    extra = sys.argv[1] if len(sys.argv) > 1 else None
    print("Reading data:")
    tx, fm, perf = load_data(extra)
    print(f"  {len(tx):,} transactions, {len(fm)} schemes")
    print("Building workbook (this can take up to a minute) ...")
    build(tx, fm, perf, OUT_FILE)
    print(f"\nDone. Open this file in Excel: {OUT_FILE}")


if __name__ == "__main__":
    main()
