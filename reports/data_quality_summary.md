# Data Quality Summary - Day 1
_Generated: 2026-10-10 11:47_

## Files loaded

| File | Rows | Columns | Null cells | Duplicate rows | Issues |
|---|---:|---:|---:|---:|---:|
| 1788499980509-304c1255-08_investor_transactions.csv | 32,778 | 13 | 0 | 0 | 0 |
| 1788499982117-e3d6ab98-09_portfolio_holdings.csv | 322 | 8 | 0 | 0 | 1 |
| 1788499982615-f9647ab2-10_benchmark_indices.csv | 8,050 | 3 | 0 | 0 | 0 |
| 1788499983024-b042c300-01_fund_master.csv | 40 | 15 | 0 | 0 | 1 |
| 1788499983331-4389156d-02_nav_history.csv | 46,000 | 3 | 0 | 0 | 0 |
| 1788499984134-b0cbf625-03_aum_by_fund_house.csv | 90 | 5 | 0 | 0 | 0 |
| 1788499984405-d702a6c6-04_monthly_sip_inflows (1).csv | 48 | 6 | 12 | 0 | 1 |
| 1788499984721-4b860901-05_category_inflows.csv | 144 | 3 | 0 | 0 | 0 |
| 1788499985036-da4a0c4a-06_industry_folio_count.csv | 21 | 6 | 0 | 0 | 0 |
| 1788499985420-bb134abf-07_scheme_performance.csv | 40 | 19 | 0 | 0 | 1 |

## Anomalies by file

**1788499980509-304c1255-08_investor_transactions.csv**
- none detected

**1788499982117-e3d6ab98-09_portfolio_holdings.csv**
- Column 'portfolio_date' has a single constant value

**1788499982615-f9647ab2-10_benchmark_indices.csv**
- none detected

**1788499983024-b042c300-01_fund_master.csv**
- Column 'min_sip_amount' has a single constant value

**1788499983331-4389156d-02_nav_history.csv**
- none detected

**1788499984134-b0cbf625-03_aum_by_fund_house.csv**
- none detected

**1788499984405-d702a6c6-04_monthly_sip_inflows (1).csv**
- Column 'yoy_growth_pct': 12 nulls (25.0%)

**1788499984721-4b860901-05_category_inflows.csv**
- none detected

**1788499985036-da4a0c4a-06_industry_folio_count.csv**
- none detected

**1788499985420-bb134abf-07_scheme_performance.csv**
- Column 'max_drawdown_pct': 40 negative values (check if valid)

## AMFI code validation (fund_master -> nav_history)

- fund_master codes: 40
- nav_history codes: 40
- In fund_master but missing from nav_history: 0
- In nav_history but missing from fund_master: 0
- Result: PASS
