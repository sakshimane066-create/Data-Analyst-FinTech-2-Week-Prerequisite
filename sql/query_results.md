# Query Results
Database: `bluestock_mf.db`

## Q1: Top 5 funds by AUM

```sql
SELECT f.scheme_name, f.fund_house, f.sub_category, f.plan,
       p.aum_crore,
       ROUND(p.aum_crore / 1e5, 2) AS aum_lakh_crore
FROM fact_performance p
JOIN dim_fund f ON f.amfi_code = p.amfi_code
ORDER BY p.aum_crore DESC
LIMIT 5;
```

Result (5 rows, first 15 shown):

```
                                          scheme_name                 fund_house    sub_category    plan  aum_crore  aum_lakh_crore
Mirae Asset Emerging Bluechip Fund - Regular - Growth    Mirae Asset Mutual Fund Large & Mid Cap Regular      49046            0.49
        Kotak Emerging Equity Fund - Regular - Growth Kotak Mahindra Mutual Fund         Mid Cap Regular      47469            0.47
       Nippon India Small Cap Fund - Regular - Growth   Nippon India Mutual Fund       Small Cap Regular      43630            0.44
           DSP Top 100 Equity Fund - Regular - Growth            DSP Mutual Fund       Large Cap Regular      41828            0.42
                  UTI Mid Cap Fund - Regular - Growth            UTI Mutual Fund         Mid Cap Regular      41728            0.42
```

## Q2: Average NAV per month - SBI Bluechip Fund Regular (119551), trading days only

```sql
-- Filled weekend rows (is_filled = 1) are excluded so Fridays are not counted three times.
SELECT d.year_month,
       ROUND(AVG(n.nav), 4) AS avg_nav,
       ROUND(MIN(n.nav), 4) AS min_nav,
       ROUND(MAX(n.nav), 4) AS max_nav,
       COUNT(*)             AS trading_days
FROM fact_nav n
JOIN dim_date d ON d.date_key = n.date_key
WHERE n.amfi_code = 119551
  AND n.is_filled = 0
GROUP BY d.year_month
ORDER BY d.year_month;
```

Result (53 rows, first 15 shown):

```
year_month  avg_nav  min_nav  max_nav  trading_days
   2022-01  55.0884  53.0538  56.5926            21
   2022-02  52.4818  51.0323  53.7522            20
   2022-03  50.8359  50.0295  51.6126            23
   2022-04  52.0363  50.5972  53.3273            21
   2022-05  51.8883  50.7075  52.9653            22
   2022-06  52.6814  51.1928  54.3735            22
   2022-07  52.6937  52.0093  53.5518            21
   2022-08  53.7734  52.4768  55.6967            23
   2022-09  56.5458  54.6797  57.6821            22
   2022-10  57.8837  55.8386  61.4337            21
   2022-11  60.8502  60.1517  62.0841            22
   2022-12  61.3497  60.0187  62.9784            22
   2023-01  60.2697  59.4887  62.4979            22
   2023-02  61.1346  60.3269  62.2579            20
   2023-03  64.5890  62.0024  67.3286            23
```

## Q3: SIP inflow year-over-year growth (calendar years)

```sql
WITH yearly AS (
    SELECT d.year, SUM(s.sip_inflow_crore) AS sip_inflow_crore
    FROM monthly_sip_inflows s
    JOIN dim_date d ON d.date_key = s.date_key
    GROUP BY d.year
)
SELECT year,
       sip_inflow_crore,
       LAG(sip_inflow_crore) OVER (ORDER BY year) AS prev_year_crore,
       ROUND(100.0 * (sip_inflow_crore - LAG(sip_inflow_crore) OVER (ORDER BY year))
             / LAG(sip_inflow_crore) OVER (ORDER BY year), 1) AS yoy_growth_pct
FROM yearly
ORDER BY year;
```

Result (4 rows, first 15 shown):

```
 year  sip_inflow_crore  prev_year_crore  yoy_growth_pct
 2022            149437              NaN             NaN
 2023            184763         149437.0            23.6
 2024            269781         184763.0            46.0
 2025            335740         269781.0            24.4
```

## Q4: Transactions by state - investments, redemptions and net flow

```sql
SELECT state,
       COUNT(*) AS transactions,
       ROUND(SUM(CASE WHEN transaction_type <> 'Redemption' THEN amount_inr ELSE 0 END) / 1e7, 2) AS investment_rs_crore,
       ROUND(SUM(CASE WHEN transaction_type =  'Redemption' THEN amount_inr ELSE 0 END) / 1e7, 2) AS redemption_rs_crore,
       ROUND(SUM(CASE WHEN transaction_type =  'Redemption' THEN -amount_inr ELSE amount_inr END) / 1e7, 2) AS net_rs_crore
FROM fact_transactions
GROUP BY state
ORDER BY investment_rs_crore DESC;
```

Result (12 rows, first 15 shown):

```
         state  transactions  investment_rs_crore  redemption_rs_crore  net_rs_crore
Madhya Pradesh          2931                20.45                10.38         10.07
        Punjab          2965                20.43                11.15          9.27
       Gujarat          2780                19.93                 9.90         10.03
    Tamil Nadu          2806                19.61                11.91          7.71
     Telangana          2718                19.30                 9.73          9.57
     Rajasthan          2577                19.20                10.66          8.54
         Delhi          2677                19.18                 9.78          9.40
 Uttar Pradesh          2695                18.31                10.22          8.09
       Haryana          2736                18.15                 9.81          8.34
   Maharashtra          2524                18.07                 8.88          9.18
   West Bengal          2748                17.86                11.86          6.00
     Karnataka          2621                17.21                10.16          7.05
```

## Q5: Funds with expense ratio below 1%

```sql
SELECT scheme_name, fund_house, category, sub_category, plan, expense_ratio_pct
FROM dim_fund
WHERE expense_ratio_pct < 1.0
ORDER BY expense_ratio_pct, scheme_name;
```

Result (14 rows, first 15 shown):

```
                                         scheme_name                        fund_house category   sub_category    plan  expense_ratio_pct
Nippon India Gilt Securities Fund - Regular - Growth          Nippon India Mutual Fund     Debt           Gilt Regular               0.55
        HDFC Short Term Debt Fund - Regular - Growth                  HDFC Mutual Fund     Debt Short Duration Regular               0.56
                Kotak Liquid Fund - Regular - Growth        Kotak Mahindra Mutual Fund     Debt         Liquid Regular               0.60
            SBI Bluechip Fund - Direct Plan - Growth                   SBI Mutual Fund   Equity      Large Cap  Direct               0.66
       Nippon India Large Cap Fund - Direct - Growth          Nippon India Mutual Fund   Equity      Large Cap  Direct               0.72
           SBI Small Cap Fund - Direct Plan - Growth                   SBI Mutual Fund   Equity      Small Cap  Direct               0.72
            ICICI Pru Liquid Fund - Regular - Growth      ICICI Prudential Mutual Fund     Debt         Liquid Regular               0.74
                Axis Bluechip Fund - Direct - Growth                  Axis Mutual Fund   Equity      Large Cap  Direct               0.75
        SBI Magnum Gilt Fund - Regular Plan - Growth                   SBI Mutual Fund     Debt           Gilt Regular               0.77
   HDFC Mid-Cap Opportunities Fund - Direct - Growth                  HDFC Mutual Fund   Equity        Mid Cap  Direct               0.78
                 ABSL Liquid Fund - Regular - Growth Aditya Birla Sun Life Mutual Fund     Debt         Liquid Regular               0.79
           ICICI Pru Bluechip Fund - Direct - Growth      ICICI Prudential Mutual Fund   Equity      Large Cap  Direct               0.80
                      Nippon India ETF Nifty 50 BeES          Nippon India Mutual Fund   Equity      Index/ETF  Direct               0.89
            HDFC Top 100 Fund - Direct Plan - Growth                  HDFC Mutual Fund   Equity      Large Cap  Direct               0.92
```

## Q6: Net flow by category and sub-category

```sql
SELECT f.category, f.sub_category,
       COUNT(*) AS transactions,
       ROUND(SUM(CASE WHEN t.transaction_type <> 'Redemption' THEN t.amount_inr ELSE 0 END) / 1e7, 2) AS investment_rs_crore,
       ROUND(SUM(CASE WHEN t.transaction_type =  'Redemption' THEN t.amount_inr ELSE 0 END) / 1e7, 2) AS redemption_rs_crore,
       ROUND(SUM(CASE WHEN t.transaction_type =  'Redemption' THEN -t.amount_inr ELSE t.amount_inr END) / 1e7, 2) AS net_rs_crore
FROM fact_transactions t
JOIN dim_fund f ON f.amfi_code = t.amfi_code
GROUP BY f.category, f.sub_category
ORDER BY net_rs_crore DESC;
```

Result (12 rows, first 15 shown):

```
category    sub_category  transactions  investment_rs_crore  redemption_rs_crore  net_rs_crore
  Equity       Large Cap         11445                76.78                42.39         34.38
  Equity         Mid Cap          5733                39.56                22.95         16.61
  Equity       Small Cap          4860                34.11                17.78         16.32
    Debt          Liquid          2497                18.09                 9.12          8.97
  Equity       Flexi Cap          1657                12.02                 6.16          5.87
    Debt            Gilt          1634                11.83                 6.29          5.54
  Equity Large & Mid Cap           883                 6.53                 3.42          3.11
  Equity           Index           833                 6.51                 3.53          2.99
    Debt  Short Duration           794                 5.98                 3.24          2.73
  Equity           Value           828                 5.96                 3.38          2.58
  Equity       Index/ETF           820                 5.27                 3.17          2.10
  Equity            ELSS           794                 5.06                 3.02          2.05
```

## Q7: Top 10 funds by 1-year NAV return (30 May 2024 to 30 May 2025)

```sql
-- Uses the forward-filled NAV, so the start date works even if it fell on a non-trading day.
SELECT f.scheme_name, f.category,
       n0.nav AS nav_start,
       n1.nav AS nav_end,
       ROUND(100.0 * (n1.nav / n0.nav - 1), 2) AS return_1yr_pct
FROM dim_fund f
JOIN fact_nav n0 ON n0.amfi_code = f.amfi_code AND n0.date_key = 20240530
JOIN fact_nav n1 ON n1.amfi_code = f.amfi_code AND n1.date_key = 20250530
ORDER BY return_1yr_pct DESC
LIMIT 10;
```

Result (10 rows, first 15 shown):

```
                                  scheme_name category  nav_start  nav_end  return_1yr_pct
           DSP Midcap Fund - Regular - Growth   Equity   124.1535 204.0973           64.39
Mirae Asset Large Cap Fund - Regular - Growth   Equity   118.5558 192.7250           62.56
        UTI Flexi Cap Fund - Regular - Growth   Equity   240.3575 337.9722           40.61
          Axis Midcap Fund - Regular - Growth   Equity   118.1049 165.9347           40.50
       Axis Small Cap Fund - Regular - Growth   Equity    72.0746 100.5124           39.46
       Kotak Flexicap Fund - Regular - Growth   Equity    94.9373 128.6019           35.46
Nippon India Large Cap Fund - Direct - Growth   Equity    55.4909  73.3850           32.25
Mirae Asset Tax Saver Fund - Regular - Growth   Equity    54.7748  69.6736           27.20
     ICICI Pru Midcap Fund - Regular - Growth   Equity   289.4694 363.3941           25.54
    ICICI Pru Bluechip Fund - Direct - Growth   Equity   106.3147 133.3051           25.39
```

## Q8: Monthly SIP, Lumpsum and Redemption with running net investment

```sql
WITH monthly AS (
    SELECT d.year_month,
           SUM(CASE WHEN t.transaction_type = 'SIP'        THEN t.amount_inr ELSE 0 END) AS sip,
           SUM(CASE WHEN t.transaction_type = 'Lumpsum'    THEN t.amount_inr ELSE 0 END) AS lumpsum,
           SUM(CASE WHEN t.transaction_type = 'Redemption' THEN t.amount_inr ELSE 0 END) AS redemption
    FROM fact_transactions t
    JOIN dim_date d ON d.date_key = t.date_key
    GROUP BY d.year_month
)
SELECT year_month,
       ROUND(sip / 1e7, 2)        AS sip_rs_crore,
       ROUND(lumpsum / 1e7, 2)    AS lumpsum_rs_crore,
       ROUND(redemption / 1e7, 2) AS redemption_rs_crore,
       ROUND((sip + lumpsum - redemption) / 1e7, 2) AS net_rs_crore,
       ROUND(SUM(sip + lumpsum - redemption) OVER (ORDER BY year_month) / 1e7, 2) AS running_net_rs_crore
FROM monthly
ORDER BY year_month;
```

Result (17 rows, first 15 shown):

```
year_month  sip_rs_crore  lumpsum_rs_crore  redemption_rs_crore  net_rs_crore  running_net_rs_crore
   2024-01          1.26             12.55                 7.95          5.86                  5.86
   2024-02          1.26             11.14                 6.99          5.41                 11.28
   2024-03          1.21             12.48                 7.66          6.03                 17.31
   2024-04          1.35             12.75                 6.74          7.36                 24.67
   2024-05          1.32             11.47                 7.72          5.07                 29.74
   2024-06          1.31             12.50                 8.41          5.40                 35.14
   2024-07          1.35             11.71                 6.71          6.36                 41.49
   2024-08          1.25             13.40                 8.12          6.53                 48.03
   2024-09          1.23             11.38                 6.25          6.36                 54.38
   2024-10          1.25             12.72                 7.39          6.58                 60.96
   2024-11          1.23             11.47                 7.00          5.70                 66.66
   2024-12          1.29             13.13                 7.08          7.34                 74.01
   2025-01          1.31             11.83                 7.53          5.61                 79.62
   2025-02          1.14             10.67                 6.48          5.33                 84.94
   2025-03          1.34             12.80                 7.82          6.33                 91.27
```

## Q9: Estimated units bought per scheme (amount / NAV on the transaction date), top 5

```sql
-- Weekend transactions use the forward-filled NAV; the last column counts how many did.
SELECT f.scheme_name,
       COUNT(*) AS purchases,
       ROUND(SUM(t.amount_inr / n.nav), 0) AS est_units_bought,
       SUM(n.is_filled) AS purchases_on_filled_nav
FROM fact_transactions t
JOIN fact_nav n ON n.amfi_code = t.amfi_code AND n.date_key = t.date_key
JOIN dim_fund f ON f.amfi_code = t.amfi_code
WHERE t.transaction_type <> 'Redemption'
GROUP BY f.amfi_code, f.scheme_name
ORDER BY est_units_bought DESC
LIMIT 5;
```

Result (5 rows, first 15 shown):

```
                                         scheme_name  purchases  est_units_bought  purchases_on_filled_nav
        HDFC Short Term Debt Fund - Regular - Growth        664         2057719.0                      170
Nippon India Gilt Securities Fund - Regular - Growth        728         1841675.0                      206
               Axis Bluechip Fund - Regular - Growth        716         1215656.0                      210
                Axis Bluechip Fund - Direct - Growth        705         1142556.0                      203
        SBI Magnum Gilt Fund - Regular Plan - Growth        662         1130336.0                      191
```

## Q10: Share of transactions with KYC still pending, by city tier

```sql
SELECT city_tier,
       COUNT(*) AS transactions,
       SUM(CASE WHEN kyc_status = 'Pending' THEN 1 ELSE 0 END) AS kyc_pending,
       ROUND(100.0 * SUM(CASE WHEN kyc_status = 'Pending' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pending_pct
FROM fact_transactions
GROUP BY city_tier
ORDER BY pending_pct DESC;
```

Result (2 rows, first 15 shown):

```
city_tier  transactions  kyc_pending  pending_pct
      T30         21719         1747         8.04
      B30         11059          885         8.00
```
