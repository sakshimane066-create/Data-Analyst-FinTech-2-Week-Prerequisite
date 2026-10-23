# SQL Query Results (PostgreSQL)
Query file: `sql/week1_practice_queries_postgres.sql`

## Q1: Top 10 largest lumpsum investments

```sql
-- Concepts: SELECT, JOIN, WHERE, ORDER BY, LIMIT
SELECT t.investor_id, t.transaction_date, f.scheme_name, t.state, t.amount_inr
FROM investor_transactions t
JOIN fund_master f ON f.amfi_code = t.amfi_code
WHERE t.transaction_type = 'Lumpsum'
ORDER BY t.amount_inr DESC
LIMIT 10;
```

Result (10 rows):

```
investor_id transaction_date                                       scheme_name          state  amount_inr
  INV004871       2024-09-09         SBI Bluechip Fund - Regular Plan - Growth         Punjab      594649
  INV002689       2024-12-31               ABSL Liquid Fund - Regular - Growth Madhya Pradesh      593281
  INV004413       2024-08-23         HDFC Top 100 Fund - Regular Plan - Growth    Maharashtra      593268
  INV004096       2025-01-19 ICICI Pru Value Discovery Fund - Regular - Growth     Tamil Nadu      591658
  INV003815       2024-01-09        SBI Small Cap Fund - Regular Plan - Growth        Gujarat      591598
  INV004404       2025-03-10            ABSL Small Cap Fund - Regular - Growth      Telangana      590794
  INV001232       2024-08-27        DSP Top 100 Equity Fund - Regular - Growth  Uttar Pradesh      587530
  INV000789       2025-04-03          ICICI Pru Liquid Fund - Regular - Growth        Gujarat      586355
  INV001228       2025-03-07 ICICI Pru Value Discovery Fund - Regular - Growth      Karnataka      586007
  INV000850       2025-01-26              Kotak Liquid Fund - Regular - Growth    Maharashtra      582751
```

## Q2: Low-cost Direct equity schemes (expense ratio below 1%)

```sql
-- Concepts: WHERE with AND, ORDER BY
SELECT scheme_name, fund_house, sub_category, expense_ratio_pct, exit_load_pct
FROM fund_master
WHERE plan = 'Direct'
  AND category = 'Equity'
  AND expense_ratio_pct < 1.0
ORDER BY expense_ratio_pct ASC;
```

Result (8 rows):

```
                                      scheme_name          fund_house sub_category  expense_ratio_pct  exit_load_pct
         SBI Bluechip Fund - Direct Plan - Growth     SBI Mutual Fund    Large Cap               0.66            1.0
    Nippon India Large Cap Fund - Direct - Growth     Nippon India MF    Large Cap               0.72            1.0
        SBI Small Cap Fund - Direct Plan - Growth     SBI Mutual Fund    Small Cap               0.72            1.0
             Axis Bluechip Fund - Direct - Growth    Axis Mutual Fund    Large Cap               0.75            1.0
HDFC Mid-Cap Opportunities Fund - Direct - Growth    HDFC Mutual Fund      Mid Cap               0.78            1.0
        ICICI Pru Bluechip Fund - Direct - Growth ICICI Prudential MF    Large Cap               0.80            1.0
                   Nippon India ETF Nifty 50 BeES     Nippon India MF    Index/ETF               0.89            0.0
         HDFC Top 100 Fund - Direct Plan - Growth    HDFC Mutual Fund    Large Cap               0.92            1.0
```

## Q3: Large UPI SIPs from KYC-verified investors in T30 cities

```sql
-- Concepts: multiple WHERE conditions
SELECT investor_id, transaction_date, amount_inr, city, payment_mode
FROM investor_transactions
WHERE transaction_type = 'SIP'
  AND kyc_status = 'Verified'
  AND payment_mode = 'UPI'
  AND city_tier = 'T30'
  AND amount_inr >= 10000
ORDER BY amount_inr DESC
LIMIT 15;
```

Result (15 rows):

```
investor_id transaction_date  amount_inr       city payment_mode
  INV000533       2025-04-06       59960     Jaipur          UPI
  INV000301       2025-02-22       59918  Ahmedabad          UPI
  INV003047       2024-06-23       59851     Mumbai          UPI
  INV004739       2024-04-10       59814   Gurugram          UPI
  INV002548       2024-01-06       59410   Gurugram          UPI
  INV000478       2024-01-01       59382      Surat          UPI
  INV003081       2024-12-06       59300   Gurugram          UPI
  INV001640       2024-10-23       59135     Jaipur          UPI
  INV003075       2024-12-21       59130   Gurugram          UPI
  INV003391       2025-01-01       58941    Kolkata          UPI
  INV004281       2024-09-27       58927     Jaipur          UPI
  INV002087       2025-03-17       58728   Gurugram          UPI
  INV002207       2024-04-09       58720     Indore          UPI
  INV002751       2025-01-19       58662  New Delhi          UPI
  INV003200       2024-09-05       58572 Chandigarh          UPI
```

## Q4: Transaction summary by type

```sql
-- Concepts: COUNT, SUM, AVG, MIN, MAX, GROUP BY
SELECT transaction_type,
       COUNT(*)                        AS transactions,
       ROUND(SUM(amount_inr) / 1e7, 2) AS total_rs_crore,
       ROUND(AVG(amount_inr), 0)       AS avg_ticket_rs,
       MIN(amount_inr)                 AS min_rs,
       MAX(amount_inr)                 AS max_rs
FROM investor_transactions
GROUP BY transaction_type
ORDER BY total_rs_crore DESC;
```

Result (3 rows):

```
transaction_type  transactions  total_rs_crore  avg_ticket_rs  min_rs  max_rs
         Lumpsum          8095          205.98       254456.0    4541  594649
      Redemption          4967          124.45       250559.0    4550  597498
             SIP         19716           21.72        11018.0     400   59998
```

## Q5: Monthly investments, redemptions and net investment

```sql
-- Concepts: to_char, CASE inside SUM, GROUP BY
SELECT to_char(transaction_date, 'YYYY-MM') AS month,
       ROUND(SUM(CASE WHEN transaction_type <> 'Redemption' THEN amount_inr ELSE 0 END) / 1e7, 2) AS investment_rs_crore,
       ROUND(SUM(CASE WHEN transaction_type =  'Redemption' THEN amount_inr ELSE 0 END) / 1e7, 2) AS redemption_rs_crore,
       ROUND(SUM(CASE WHEN transaction_type =  'Redemption' THEN -amount_inr ELSE amount_inr END) / 1e7, 2) AS net_rs_crore
FROM investor_transactions
GROUP BY month
ORDER BY month;
```

Result (17 rows):

```
  month  investment_rs_crore  redemption_rs_crore  net_rs_crore
2024-01                13.81                 7.95          5.86
2024-02                12.40                 6.99          5.41
2024-03                13.69                 7.66          6.03
2024-04                14.11                 6.74          7.36
2024-05                12.79                 7.72          5.07
2024-06                13.81                 8.41          5.40
2024-07                13.07                 6.71          6.36
2024-08                14.66                 8.12          6.53
2024-09                12.61                 6.25          6.36
2024-10                13.97                 7.39          6.58
2024-11                12.70                 7.00          5.70
2024-12                14.42                 7.08          7.34
2025-01                13.14                 7.53          5.61
2025-02                11.81                 6.48          5.33
2025-03                14.15                 7.82          6.33
```

## Q6: Top 10 states by investment

```sql
-- Concepts: WHERE, GROUP BY, ORDER BY, LIMIT
SELECT state,
       COUNT(*)                        AS transactions,
       ROUND(SUM(amount_inr) / 1e7, 2) AS investment_rs_crore
FROM investor_transactions
WHERE transaction_type <> 'Redemption'
GROUP BY state
ORDER BY investment_rs_crore DESC
LIMIT 10;
```

Result (10 rows):

```
         state  transactions  investment_rs_crore
Madhya Pradesh          2516                20.45
        Punjab          2513                20.43
       Gujarat          2365                19.93
    Tamil Nadu          2326                19.61
     Telangana          2328                19.30
     Rajasthan          2171                19.20
         Delhi          2283                19.18
 Uttar Pradesh          2291                18.31
       Haryana          2346                18.15
   Maharashtra          2151                18.07
```

## Q7: SIP behaviour by city tier and age group

```sql
-- Concepts: GROUP BY on two columns
SELECT city_tier, age_group,
       COUNT(*)                        AS sip_count,
       ROUND(AVG(amount_inr), 0)       AS avg_sip_rs,
       ROUND(SUM(amount_inr) / 1e7, 2) AS total_rs_crore
FROM investor_transactions
WHERE transaction_type = 'SIP'
GROUP BY city_tier, age_group
ORDER BY city_tier, age_group;
```

Result (10 rows):

```
city_tier age_group  sip_count  avg_sip_rs  total_rs_crore
      B30     18-25       1145     11232.0            1.29
      B30     26-35       2740     10980.0            3.01
      B30     36-45       1497     10933.0            1.64
      B30     46-55        702      9791.0            0.69
      B30       56+        509     12020.0            0.61
      T30     18-25       1804     10776.0            1.94
      T30     26-35       5323     10990.0            5.85
      T30     36-45       3429     10865.0            3.73
      T30     46-55       1598     11728.0            1.87
      T30       56+        969     11341.0            1.10
```

## Q8: Most active investors (10 or more transactions)

```sql
-- Concepts: GROUP BY, HAVING COUNT
SELECT investor_id,
       COUNT(*)                  AS transactions,
       ROUND(SUM(amount_inr), 0) AS total_rs
FROM investor_transactions
GROUP BY investor_id
HAVING COUNT(*) >= 10
ORDER BY transactions DESC, total_rs DESC
LIMIT 15;
```

Result (15 rows):

```
investor_id  transactions  total_rs
  INV003288            12 3480685.0
  INV001999            12 3179916.0
  INV002553            12 2668557.0
  INV002245            12 2623784.0
  INV003732            12 2556852.0
  INV002250            12 2556238.0
  INV000606            12 2504294.0
  INV004064            12 2485177.0
  INV002996            12 2445043.0
  INV000671            12 2333315.0
  INV004922            12 2293919.0
  INV004885            12 2290943.0
  INV004733            12 2290878.0
  INV002912            12 2286138.0
  INV003731            12 2277196.0
```

## Q9: Schemes that attracted more than Rs 5 crore of investment

```sql
-- Concepts: JOIN, GROUP BY, HAVING SUM
SELECT f.scheme_name, f.category,
       ROUND(SUM(t.amount_inr) / 1e7, 2) AS investment_rs_crore
FROM investor_transactions t
JOIN fund_master f ON f.amfi_code = t.amfi_code
WHERE t.transaction_type <> 'Redemption'
GROUP BY f.amfi_code, f.scheme_name, f.category
HAVING SUM(t.amount_inr) > 5e7
ORDER BY investment_rs_crore DESC;
```

Result (36 rows):

```
                                          scheme_name category  investment_rs_crore
               Axis Small Cap Fund - Regular - Growth   Equity                 6.54
Mirae Asset Emerging Bluechip Fund - Regular - Growth   Equity                 6.53
           UTI Nifty 50 Index Fund - Regular - Growth   Equity                 6.51
            SBI Bluechip Fund - Regular Plan - Growth   Equity                 6.25
             ICICI Pru Liquid Fund - Regular - Growth     Debt                 6.19
                  UTI Mid Cap Fund - Regular - Growth   Equity                 6.17
                UTI Flexi Cap Fund - Regular - Growth   Equity                 6.12
 Nippon India Gilt Securities Fund - Regular - Growth     Debt                 6.10
               ABSL Small Cap Fund - Regular - Growth   Equity                 6.09
    HDFC Mid-Cap Opportunities Fund - Direct - Growth   Equity                 6.08
                 Kotak Liquid Fund - Regular - Growth     Debt                 6.07
                Axis Bluechip Fund - Regular - Growth   Equity                 6.05
         HDFC Short Term Debt Fund - Regular - Growth     Debt                 5.98
    ICICI Pru Value Discovery Fund - Regular - Growth   Equity                 5.96
            HDFC Top 100 Fund - Regular Plan - Growth   Equity                 5.91
```

## Q10: Revenue (investment) by fund house

```sql
-- Concepts: INNER JOIN, GROUP BY
SELECT f.fund_house,
       COUNT(*)                          AS transactions,
       ROUND(SUM(t.amount_inr) / 1e7, 2) AS investment_rs_crore
FROM investor_transactions t
JOIN fund_master f ON f.amfi_code = t.amfi_code
WHERE t.transaction_type <> 'Redemption'
GROUP BY f.fund_house
ORDER BY investment_rs_crore DESC;
```

Result (10 rows):

```
              fund_house  transactions  investment_rs_crore
         SBI Mutual Fund          3405                28.77
        HDFC Mutual Fund          3499                28.39
     ICICI Prudential MF          3479                28.33
         Nippon India MF          3486                27.79
        Axis Mutual Fund          2856                23.74
       Kotak Mahindra MF          2702                22.02
         UTI Mutual Fund          2087                18.81
Aditya Birla Sun Life MF          2124                16.91
          Mirae Asset MF          2099                16.80
         DSP Mutual Fund          2074                16.14
```

## Q11: Investment, redemption and net flow by category and sub-category

```sql
-- Concepts: JOIN, conditional aggregation
SELECT f.category, f.sub_category,
       ROUND(SUM(CASE WHEN t.transaction_type <> 'Redemption' THEN t.amount_inr ELSE 0 END) / 1e7, 2) AS investment_rs_crore,
       ROUND(SUM(CASE WHEN t.transaction_type =  'Redemption' THEN t.amount_inr ELSE 0 END) / 1e7, 2) AS redemption_rs_crore,
       ROUND(SUM(CASE WHEN t.transaction_type =  'Redemption' THEN -t.amount_inr ELSE t.amount_inr END) / 1e7, 2) AS net_rs_crore
FROM investor_transactions t
JOIN fund_master f ON f.amfi_code = t.amfi_code
GROUP BY f.category, f.sub_category
ORDER BY net_rs_crore DESC;
```

Result (12 rows):

```
category    sub_category  investment_rs_crore  redemption_rs_crore  net_rs_crore
  Equity       Large Cap                76.78                42.39         34.38
  Equity         Mid Cap                39.56                22.95         16.61
  Equity       Small Cap                34.11                17.78         16.32
    Debt          Liquid                18.09                 9.12          8.97
  Equity       Flexi Cap                12.02                 6.16          5.87
    Debt            Gilt                11.83                 6.29          5.54
  Equity Large & Mid Cap                 6.53                 3.42          3.11
  Equity           Index                 6.51                 3.53          2.99
    Debt  Short Duration                 5.98                 3.24          2.73
  Equity           Value                 5.96                 3.38          2.58
  Equity       Index/ETF                 5.27                 3.17          2.10
  Equity            ELSS                 5.06                 3.02          2.05
```

## Q12: Product performance - top 10 equity schemes by 3-year return vs benchmark

```sql
-- Concepts: JOIN two tables, calculated column
SELECT f.scheme_name, f.plan,
       p.return_3yr_pct, p.benchmark_3yr_pct,
       ROUND((p.return_3yr_pct - p.benchmark_3yr_pct)::numeric, 2) AS excess_return_pct,
       p.sharpe_ratio, p.morningstar_rating
FROM scheme_performance p
JOIN fund_master f ON f.amfi_code = p.amfi_code
WHERE f.category = 'Equity'
ORDER BY p.return_3yr_pct DESC
LIMIT 10;
```

Result (10 rows):

```
                                       scheme_name    plan  return_3yr_pct  benchmark_3yr_pct  excess_return_pct  sharpe_ratio  morningstar_rating
        SBI Small Cap Fund - Regular Plan - Growth Regular           23.39              22.16               1.23          0.94                   5
         SBI Small Cap Fund - Direct Plan - Growth  Direct           23.14              22.01               1.13          0.93                   4
            ABSL Small Cap Fund - Regular - Growth Regular           22.38              20.54               1.84          0.90                   5
            Axis Small Cap Fund - Regular - Growth Regular           20.98              20.47               0.51          0.84                   4
    Nippon India Small Cap Fund - Regular - Growth Regular           20.15              19.35               0.80          0.81                   4
             DSP Small Cap Fund - Regular - Growth Regular           20.08              19.39               0.69          0.80                   4
     Kotak Emerging Equity Fund - Regular - Growth Regular           18.23              16.32               1.91          0.96                   4
          ICICI Pru Midcap Fund - Regular - Growth Regular           18.08              17.19               0.89          0.95                   3
                DSP Midcap Fund - Regular - Growth Regular           17.16              16.14               1.02          0.90                   4
HDFC Mid-Cap Opportunities Fund - Regular - Growth Regular           16.58              15.63               0.95          0.87                   5
```

## Q13: Schemes with no stock holdings (expected: debt schemes)

```sql
-- Concepts: LEFT JOIN, IS NULL
SELECT f.amfi_code, f.scheme_name, f.category, f.sub_category
FROM fund_master f
LEFT JOIN portfolio_holdings h ON h.amfi_code = f.amfi_code
WHERE h.amfi_code IS NULL
ORDER BY f.sub_category, f.scheme_name;
```

Result (6 rows):

```
 amfi_code                                          scheme_name category   sub_category
    118636 Nippon India Gilt Securities Fund - Regular - Growth     Debt           Gilt
    119120         SBI Magnum Gilt Fund - Regular Plan - Growth     Debt           Gilt
    101208                  ABSL Liquid Fund - Regular - Growth     Debt         Liquid
    120507             ICICI Pru Liquid Fund - Regular - Growth     Debt         Liquid
    120844                 Kotak Liquid Fund - Regular - Growth     Debt         Liquid
    100025         HDFC Short Term Debt Fund - Regular - Growth     Debt Short Duration
```

## Q14: Do the best-performing schemes attract the most net money?

```sql
-- Concepts: three-table JOIN
SELECT f.scheme_name, p.return_1yr_pct, p.sharpe_ratio,
       ROUND(SUM(CASE WHEN t.transaction_type = 'Redemption' THEN -t.amount_inr ELSE t.amount_inr END) / 1e7, 2) AS net_rs_crore
FROM investor_transactions t
JOIN fund_master f ON f.amfi_code = t.amfi_code
JOIN scheme_performance p ON p.amfi_code = t.amfi_code
GROUP BY f.amfi_code, f.scheme_name, p.return_1yr_pct, p.sharpe_ratio
ORDER BY net_rs_crore DESC
LIMIT 10;
```

Result (10 rows):

```
                                          scheme_name  return_1yr_pct  sharpe_ratio  net_rs_crore
             ICICI Pru Liquid Fund - Regular - Growth            8.89          7.68          3.57
               Axis Small Cap Fund - Regular - Growth           21.97          0.84          3.38
    HDFC Mid-Cap Opportunities Fund - Direct - Growth           19.98          0.80          3.33
             SBI Bluechip Fund - Direct Plan - Growth           15.25          0.81          3.30
               ABSL Small Cap Fund - Regular - Growth           24.93          0.90          3.24
       Nippon India Large Cap Fund - Regular - Growth           15.84          1.00          3.20
                UTI Flexi Cap Fund - Regular - Growth           17.43          0.96          3.16
                Axis Bluechip Fund - Regular - Growth           11.82          0.85          3.12
Mirae Asset Emerging Bluechip Fund - Regular - Growth           14.91          0.91          3.11
                  UTI Mid Cap Fund - Regular - Growth           16.30          0.82          3.10
```

## Q15: Investors who invested more than the average investor

```sql
-- Concepts: subquery in HAVING, nested subquery
SELECT investor_id,
       ROUND(SUM(amount_inr), 0) AS total_invested_rs
FROM investor_transactions
WHERE transaction_type <> 'Redemption'
GROUP BY investor_id
HAVING SUM(amount_inr) > (
    SELECT AVG(total)
    FROM (
        SELECT SUM(amount_inr) AS total
        FROM investor_transactions
        WHERE transaction_type <> 'Redemption'
        GROUP BY investor_id
    ) AS investor_totals
)
ORDER BY total_invested_rs DESC
LIMIT 15;
```

Result (15 rows):

```
investor_id  total_invested_rs
  INV001771          2695710.0
  INV000604          2567253.0
  INV001528          2546199.0
  INV002707          2533904.0
  INV002250          2465102.0
  INV000988          2330846.0
  INV002039          2265918.0
  INV002996          2172258.0
  INV003288          2169468.0
  INV000481          2143420.0
  INV001692          2073396.0
  INV002472          2048739.0
  INV000994          2035761.0
  INV000966          2029090.0
  INV001999          2009484.0
```

## Q16: Schemes whose Sharpe ratio beats their own category average

```sql
-- Concepts: correlated subquery
SELECT p.scheme_name, p.category, p.sharpe_ratio,
       ROUND((SELECT AVG(p2.sharpe_ratio) FROM scheme_performance p2 WHERE p2.category = p.category)::numeric, 2) AS category_avg_sharpe
FROM scheme_performance p
WHERE p.sharpe_ratio > (SELECT AVG(p2.sharpe_ratio) FROM scheme_performance p2 WHERE p2.category = p.category)
ORDER BY p.category, p.sharpe_ratio DESC;
```

Result (15 rows):

```
                                   scheme_name  category  sharpe_ratio  category_avg_sharpe
        Kotak Flexicap Fund - Regular - Growth Flexi Cap          0.98                 0.97
  SBI Magnum Gilt Fund - Regular Plan - Growth      Gilt          1.52                 1.43
 Mirae Asset Large Cap Fund - Regular - Growth Large Cap          1.06                 0.93
     HDFC Top 100 Fund - Regular Plan - Growth Large Cap          1.06                 0.93
     ICICI Pru Bluechip Fund - Direct - Growth Large Cap          1.03                 0.93
Nippon India Large Cap Fund - Regular - Growth Large Cap          1.00                 0.93
 ABSL Frontline Equity Fund - Regular - Growth Large Cap          0.98                 0.93
      HDFC Top 100 Fund - Direct Plan - Growth Large Cap          0.96                 0.93
      ICICI Pru Liquid Fund - Regular - Growth    Liquid          7.68                 6.33
 Kotak Emerging Equity Fund - Regular - Growth   Mid Cap          0.96                 0.87
      ICICI Pru Midcap Fund - Regular - Growth   Mid Cap          0.95                 0.87
            DSP Midcap Fund - Regular - Growth   Mid Cap          0.90                 0.87
    SBI Small Cap Fund - Regular Plan - Growth Small Cap          0.94                 0.87
     SBI Small Cap Fund - Direct Plan - Growth Small Cap          0.93                 0.87
        ABSL Small Cap Fund - Regular - Growth Small Cap          0.90                 0.87
```

## Q17: Latest NAV of each scheme

```sql
-- Concepts: subquery with MAX
SELECT f.scheme_name, n.date AS latest_date, n.nav AS latest_nav
FROM nav_history n
JOIN fund_master f ON f.amfi_code = n.amfi_code
WHERE n.date = (SELECT MAX(n2.date) FROM nav_history n2 WHERE n2.amfi_code = n.amfi_code)
ORDER BY f.scheme_name
LIMIT 15;
```

Result (15 rows):

```
                                       scheme_name latest_date  latest_nav
     ABSL Frontline Equity Fund - Regular - Growth  2026-05-29    773.2939
               ABSL Liquid Fund - Regular - Growth  2026-05-29    410.1021
            ABSL Small Cap Fund - Regular - Growth  2026-05-29     53.9836
              Axis Bluechip Fund - Direct - Growth  2026-05-29     58.4203
             Axis Bluechip Fund - Regular - Growth  2026-05-29     50.8387
               Axis Midcap Fund - Regular - Growth  2026-05-29    203.8581
            Axis Small Cap Fund - Regular - Growth  2026-05-29     56.1319
                DSP Midcap Fund - Regular - Growth  2026-05-29    245.3651
             DSP Small Cap Fund - Regular - Growth  2026-05-29    279.7511
        DSP Top 100 Equity Fund - Regular - Growth  2026-05-29    606.2349
 HDFC Mid-Cap Opportunities Fund - Direct - Growth  2026-05-29    188.3619
HDFC Mid-Cap Opportunities Fund - Regular - Growth  2026-05-29    342.0072
      HDFC Short Term Debt Fund - Regular - Growth  2026-05-29     31.8843
          HDFC Top 100 Fund - Direct Plan - Growth  2026-05-29   1204.9571
         HDFC Top 100 Fund - Regular Plan - Growth  2026-05-29    583.6113
```

## Q18: Investors who use both SIP and Lumpsum

```sql
-- Concepts: IN subquery, COUNT DISTINCT
SELECT COUNT(DISTINCT investor_id) AS investors_with_sip_and_lumpsum
FROM investor_transactions
WHERE transaction_type = 'SIP'
  AND investor_id IN (
      SELECT investor_id
      FROM investor_transactions
      WHERE transaction_type = 'Lumpsum'
  );
```

Result (1 rows):

```
 investors_with_sip_and_lumpsum
                           3579
```

## Q19: Top 3 schemes by investment inside each category

```sql
-- Concepts: CTE, RANK() OVER (PARTITION BY ...)
WITH scheme_totals AS (
    SELECT f.category, f.scheme_name, SUM(t.amount_inr) AS investment_rs
    FROM investor_transactions t
    JOIN fund_master f ON f.amfi_code = t.amfi_code
    WHERE t.transaction_type <> 'Redemption'
    GROUP BY f.category, f.scheme_name
),
ranked AS (
    SELECT category, scheme_name,
           ROUND(investment_rs / 1e7, 2) AS investment_rs_crore,
           RANK() OVER (PARTITION BY category ORDER BY investment_rs DESC) AS rank_in_category
    FROM scheme_totals
)
SELECT *
FROM ranked
WHERE rank_in_category <= 3
ORDER BY category, rank_in_category;
```

Result (6 rows):

```
category                                           scheme_name  investment_rs_crore  rank_in_category
    Debt              ICICI Pru Liquid Fund - Regular - Growth                 6.19                 1
    Debt  Nippon India Gilt Securities Fund - Regular - Growth                 6.10                 2
    Debt                  Kotak Liquid Fund - Regular - Growth                 6.07                 3
  Equity                Axis Small Cap Fund - Regular - Growth                 6.54                 1
  Equity Mirae Asset Emerging Bluechip Fund - Regular - Growth                 6.53                 2
  Equity            UTI Nifty 50 Index Fund - Regular - Growth                 6.51                 3
```

## Q20: Monthly net investment with running total and month-over-month change

```sql
-- Concepts: SUM() OVER (ORDER BY ...), LAG()
WITH monthly AS (
    SELECT to_char(transaction_date, 'YYYY-MM') AS month,
           SUM(CASE WHEN transaction_type = 'Redemption' THEN -amount_inr ELSE amount_inr END) AS net_rs
    FROM investor_transactions
    GROUP BY month
)
SELECT month,
       ROUND(net_rs / 1e7, 2) AS net_rs_crore,
       ROUND(SUM(net_rs) OVER (ORDER BY month) / 1e7, 2) AS running_net_rs_crore,
       ROUND((net_rs - LAG(net_rs) OVER (ORDER BY month)) / 1e7, 2) AS change_vs_prev_month_rs_crore
FROM monthly
ORDER BY month;
```

Result (17 rows):

```
  month  net_rs_crore  running_net_rs_crore  change_vs_prev_month_rs_crore
2024-01          5.86                  5.86                            NaN
2024-02          5.41                 11.28                          -0.45
2024-03          6.03                 17.31                           0.62
2024-04          7.36                 24.67                           1.33
2024-05          5.07                 29.74                          -2.30
2024-06          5.40                 35.14                           0.33
2024-07          6.36                 41.49                           0.96
2024-08          6.53                 48.03                           0.18
2024-09          6.36                 54.38                          -0.18
2024-10          6.58                 60.96                           0.22
2024-11          5.70                 66.66                          -0.88
2024-12          7.34                 74.01                           1.64
2025-01          5.61                 79.62                          -1.73
2025-02          5.33                 84.94                          -0.28
2025-03          6.33                 91.27                           1.00
```

## Q21: Biggest one-day NAV moves across all schemes

```sql
-- Concepts: LAG() OVER (PARTITION BY ...), daily return
WITH daily AS (
    SELECT amfi_code, date, nav,
           LAG(nav) OVER (PARTITION BY amfi_code ORDER BY date) AS prev_nav
    FROM nav_history
)
SELECT f.scheme_name, d.date, d.nav,
       ROUND(((d.nav / d.prev_nav - 1) * 100)::numeric, 2) AS daily_return_pct
FROM daily d
JOIN fund_master f ON f.amfi_code = d.amfi_code
WHERE d.prev_nav IS NOT NULL
ORDER BY ABS(d.nav / d.prev_nav - 1) DESC
LIMIT 10;
```

Result (10 rows):

```
                                   scheme_name       date      nav  daily_return_pct
    SBI Small Cap Fund - Regular Plan - Growth 2024-04-15 189.0742              6.47
Nippon India Small Cap Fund - Regular - Growth 2024-03-19 110.5401              5.93
Nippon India Small Cap Fund - Regular - Growth 2022-06-24  67.2534             -5.81
        ABSL Small Cap Fund - Regular - Growth 2024-05-01  65.5882              5.49
     SBI Small Cap Fund - Direct Plan - Growth 2023-01-10 153.2221              5.33
        ABSL Small Cap Fund - Regular - Growth 2023-03-22  56.8326             -5.18
     SBI Small Cap Fund - Direct Plan - Growth 2024-01-17 136.8239              5.18
    SBI Small Cap Fund - Regular Plan - Growth 2022-01-10  96.0964              5.11
Nippon India Small Cap Fund - Regular - Growth 2023-03-01 113.5801             -5.03
    SBI Small Cap Fund - Regular Plan - Growth 2022-11-08 123.9704              4.91
```

## Q22: Share of total investment by category

```sql
-- Concepts: SUM() OVER () for a percentage of total
WITH cat AS (
    SELECT f.category, SUM(t.amount_inr) AS investment_rs
    FROM investor_transactions t
    JOIN fund_master f ON f.amfi_code = t.amfi_code
    WHERE t.transaction_type <> 'Redemption'
    GROUP BY f.category
)
SELECT category,
       ROUND(investment_rs / 1e7, 2) AS investment_rs_crore,
       ROUND(100.0 * investment_rs / SUM(investment_rs) OVER (), 1) AS share_pct
FROM cat
ORDER BY share_pct DESC;
```

Result (2 rows):

```
category  investment_rs_crore  share_pct
  Equity               191.81       84.2
    Debt                35.89       15.8
```

## Q23: 30-day moving average of NAV for SBI Bluechip Regular (119551)

```sql
-- Concepts: AVG() OVER (ROWS BETWEEN ...)
SELECT date, nav,
       ROUND((AVG(nav) OVER (ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW))::numeric, 4) AS nav_30d_avg
FROM nav_history
WHERE amfi_code = 119551
ORDER BY date DESC
LIMIT 10;
```

Result (10 rows):

```
      date      nav  nav_30d_avg
2026-05-29 149.3216     146.6609
2026-05-28 150.3635     146.3324
2026-05-27 148.1874     145.9240
2026-05-26 150.0040     145.5775
2026-05-25 151.3832     145.1705
2026-05-22 151.2843     144.6188
2026-05-21 151.4373     144.0537
2026-05-20 151.1916     143.4752
2026-05-19 151.3138     142.8831
2026-05-18 149.4120     142.2507
```
