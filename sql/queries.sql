-- =====================================================================
-- Bluestock MF Analytics - 10 analytical SQL queries (SQLite)
-- Database : bluestock_mf.db   (star schema in schema.sql)
-- Money    : 1 crore = 10,000,000 rupees (1e7)
-- Required (Q1-Q5) and my own choice (Q6-Q10)
-- =====================================================================

-- Q1: Top 5 funds by AUM
SELECT f.scheme_name, f.fund_house, f.sub_category, f.plan,
       p.aum_crore,
       ROUND(p.aum_crore / 1e5, 2) AS aum_lakh_crore
FROM fact_performance p
JOIN dim_fund f ON f.amfi_code = p.amfi_code
ORDER BY p.aum_crore DESC
LIMIT 5;

-- Q2: Average NAV per month - SBI Bluechip Fund Regular (119551), trading days only
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

-- Q3: SIP inflow year-over-year growth (calendar years)
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

-- Q4: Transactions by state - investments, redemptions and net flow
SELECT state,
       COUNT(*) AS transactions,
       ROUND(SUM(CASE WHEN transaction_type <> 'Redemption' THEN amount_inr ELSE 0 END) / 1e7, 2) AS investment_rs_crore,
       ROUND(SUM(CASE WHEN transaction_type =  'Redemption' THEN amount_inr ELSE 0 END) / 1e7, 2) AS redemption_rs_crore,
       ROUND(SUM(CASE WHEN transaction_type =  'Redemption' THEN -amount_inr ELSE amount_inr END) / 1e7, 2) AS net_rs_crore
FROM fact_transactions
GROUP BY state
ORDER BY investment_rs_crore DESC;

-- Q5: Funds with expense ratio below 1%
SELECT scheme_name, fund_house, category, sub_category, plan, expense_ratio_pct
FROM dim_fund
WHERE expense_ratio_pct < 1.0
ORDER BY expense_ratio_pct, scheme_name;

-- Q6: Net flow by category and sub-category
SELECT f.category, f.sub_category,
       COUNT(*) AS transactions,
       ROUND(SUM(CASE WHEN t.transaction_type <> 'Redemption' THEN t.amount_inr ELSE 0 END) / 1e7, 2) AS investment_rs_crore,
       ROUND(SUM(CASE WHEN t.transaction_type =  'Redemption' THEN t.amount_inr ELSE 0 END) / 1e7, 2) AS redemption_rs_crore,
       ROUND(SUM(CASE WHEN t.transaction_type =  'Redemption' THEN -t.amount_inr ELSE t.amount_inr END) / 1e7, 2) AS net_rs_crore
FROM fact_transactions t
JOIN dim_fund f ON f.amfi_code = t.amfi_code
GROUP BY f.category, f.sub_category
ORDER BY net_rs_crore DESC;

-- Q7: Top 10 funds by 1-year NAV return (30 May 2024 to 30 May 2025)
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

-- Q8: Monthly SIP, Lumpsum and Redemption with running net investment
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

-- Q9: Estimated units bought per scheme (amount / NAV on the transaction date), top 5
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

-- Q10: Share of transactions with KYC still pending, by city tier
SELECT city_tier,
       COUNT(*) AS transactions,
       SUM(CASE WHEN kyc_status = 'Pending' THEN 1 ELSE 0 END) AS kyc_pending,
       ROUND(100.0 * SUM(CASE WHEN kyc_status = 'Pending' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pending_pct
FROM fact_transactions
GROUP BY city_tier
ORDER BY pending_pct DESC;
