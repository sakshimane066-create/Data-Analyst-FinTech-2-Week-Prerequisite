-- =====================================================================
-- Week 1 - SQL Practice Queries: Mutual Fund Analytics (PostgreSQL)
-- Tables: fund_master, nav_history, aum_by_fund_house, monthly_sip_inflows,
--         category_inflows, industry_folio_count, scheme_performance,
--         investor_transactions, portfolio_holdings, benchmark_indices
--
-- Definitions used below
--   "Revenue" / investment = SIP + Lumpsum amount (redemptions are outflows)
--   Net investment         = investments - redemptions
--   1 crore                = 10,000,000 rupees (1e7)
--   "Customer"             = investor (investor_id)
--   "Product"              = scheme (amfi_code / scheme_name)
--
-- Run all queries:  python sql/run_postgres_queries.py "postgresql://postgres:PASSWORD@localhost:5432/mf_analytics"
-- Or paste any single query into pgAdmin's Query Tool (after the tables are loaded).
-- =====================================================================


-- =====================================================================
-- PART 1: SELECT, WHERE, ORDER BY
-- =====================================================================

-- Q1: Top 10 largest lumpsum investments
-- Concepts: SELECT, JOIN, WHERE, ORDER BY, LIMIT
SELECT t.investor_id, t.transaction_date, f.scheme_name, t.state, t.amount_inr
FROM investor_transactions t
JOIN fund_master f ON f.amfi_code = t.amfi_code
WHERE t.transaction_type = 'Lumpsum'
ORDER BY t.amount_inr DESC
LIMIT 10;

-- Q2: Low-cost Direct equity schemes (expense ratio below 1%)
-- Concepts: WHERE with AND, ORDER BY
SELECT scheme_name, fund_house, sub_category, expense_ratio_pct, exit_load_pct
FROM fund_master
WHERE plan = 'Direct'
  AND category = 'Equity'
  AND expense_ratio_pct < 1.0
ORDER BY expense_ratio_pct ASC;

-- Q3: Large UPI SIPs from KYC-verified investors in T30 cities
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


-- =====================================================================
-- PART 2: AGGREGATE FUNCTIONS AND GROUP BY
-- =====================================================================

-- Q4: Transaction summary by type
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

-- Q5: Monthly investments, redemptions and net investment
-- Concepts: to_char, CASE inside SUM, GROUP BY
SELECT to_char(transaction_date, 'YYYY-MM') AS month,
       ROUND(SUM(CASE WHEN transaction_type <> 'Redemption' THEN amount_inr ELSE 0 END) / 1e7, 2) AS investment_rs_crore,
       ROUND(SUM(CASE WHEN transaction_type =  'Redemption' THEN amount_inr ELSE 0 END) / 1e7, 2) AS redemption_rs_crore,
       ROUND(SUM(CASE WHEN transaction_type =  'Redemption' THEN -amount_inr ELSE amount_inr END) / 1e7, 2) AS net_rs_crore
FROM investor_transactions
GROUP BY month
ORDER BY month;

-- Q6: Top 10 states by investment
-- Concepts: WHERE, GROUP BY, ORDER BY, LIMIT
SELECT state,
       COUNT(*)                        AS transactions,
       ROUND(SUM(amount_inr) / 1e7, 2) AS investment_rs_crore
FROM investor_transactions
WHERE transaction_type <> 'Redemption'
GROUP BY state
ORDER BY investment_rs_crore DESC
LIMIT 10;

-- Q7: SIP behaviour by city tier and age group
-- Concepts: GROUP BY on two columns
SELECT city_tier, age_group,
       COUNT(*)                        AS sip_count,
       ROUND(AVG(amount_inr), 0)       AS avg_sip_rs,
       ROUND(SUM(amount_inr) / 1e7, 2) AS total_rs_crore
FROM investor_transactions
WHERE transaction_type = 'SIP'
GROUP BY city_tier, age_group
ORDER BY city_tier, age_group;


-- =====================================================================
-- PART 3: HAVING
-- =====================================================================

-- Q8: Most active investors (10 or more transactions)
-- Concepts: GROUP BY, HAVING COUNT
SELECT investor_id,
       COUNT(*)                  AS transactions,
       ROUND(SUM(amount_inr), 0) AS total_rs
FROM investor_transactions
GROUP BY investor_id
HAVING COUNT(*) >= 10
ORDER BY transactions DESC, total_rs DESC
LIMIT 15;

-- Q9: Schemes that attracted more than Rs 5 crore of investment
-- Concepts: JOIN, GROUP BY, HAVING SUM
SELECT f.scheme_name, f.category,
       ROUND(SUM(t.amount_inr) / 1e7, 2) AS investment_rs_crore
FROM investor_transactions t
JOIN fund_master f ON f.amfi_code = t.amfi_code
WHERE t.transaction_type <> 'Redemption'
GROUP BY f.amfi_code, f.scheme_name, f.category
HAVING SUM(t.amount_inr) > 5e7
ORDER BY investment_rs_crore DESC;


-- =====================================================================
-- PART 4: JOINS
-- =====================================================================

-- Q10: Revenue (investment) by fund house
-- Concepts: INNER JOIN, GROUP BY
SELECT f.fund_house,
       COUNT(*)                          AS transactions,
       ROUND(SUM(t.amount_inr) / 1e7, 2) AS investment_rs_crore
FROM investor_transactions t
JOIN fund_master f ON f.amfi_code = t.amfi_code
WHERE t.transaction_type <> 'Redemption'
GROUP BY f.fund_house
ORDER BY investment_rs_crore DESC;

-- Q11: Investment, redemption and net flow by category and sub-category
-- Concepts: JOIN, conditional aggregation
SELECT f.category, f.sub_category,
       ROUND(SUM(CASE WHEN t.transaction_type <> 'Redemption' THEN t.amount_inr ELSE 0 END) / 1e7, 2) AS investment_rs_crore,
       ROUND(SUM(CASE WHEN t.transaction_type =  'Redemption' THEN t.amount_inr ELSE 0 END) / 1e7, 2) AS redemption_rs_crore,
       ROUND(SUM(CASE WHEN t.transaction_type =  'Redemption' THEN -t.amount_inr ELSE t.amount_inr END) / 1e7, 2) AS net_rs_crore
FROM investor_transactions t
JOIN fund_master f ON f.amfi_code = t.amfi_code
GROUP BY f.category, f.sub_category
ORDER BY net_rs_crore DESC;

-- Q12: Product performance - top 10 equity schemes by 3-year return vs benchmark
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

-- Q13: Schemes with no stock holdings (expected: debt schemes)
-- Concepts: LEFT JOIN, IS NULL
SELECT f.amfi_code, f.scheme_name, f.category, f.sub_category
FROM fund_master f
LEFT JOIN portfolio_holdings h ON h.amfi_code = f.amfi_code
WHERE h.amfi_code IS NULL
ORDER BY f.sub_category, f.scheme_name;

-- Q14: Do the best-performing schemes attract the most net money?
-- Concepts: three-table JOIN
SELECT f.scheme_name, p.return_1yr_pct, p.sharpe_ratio,
       ROUND(SUM(CASE WHEN t.transaction_type = 'Redemption' THEN -t.amount_inr ELSE t.amount_inr END) / 1e7, 2) AS net_rs_crore
FROM investor_transactions t
JOIN fund_master f ON f.amfi_code = t.amfi_code
JOIN scheme_performance p ON p.amfi_code = t.amfi_code
GROUP BY f.amfi_code, f.scheme_name, p.return_1yr_pct, p.sharpe_ratio
ORDER BY net_rs_crore DESC
LIMIT 10;


-- =====================================================================
-- PART 5: SUBQUERIES
-- =====================================================================

-- Q15: Investors who invested more than the average investor
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

-- Q16: Schemes whose Sharpe ratio beats their own category average
-- Concepts: correlated subquery
SELECT p.scheme_name, p.category, p.sharpe_ratio,
       ROUND((SELECT AVG(p2.sharpe_ratio) FROM scheme_performance p2 WHERE p2.category = p.category)::numeric, 2) AS category_avg_sharpe
FROM scheme_performance p
WHERE p.sharpe_ratio > (SELECT AVG(p2.sharpe_ratio) FROM scheme_performance p2 WHERE p2.category = p.category)
ORDER BY p.category, p.sharpe_ratio DESC;

-- Q17: Latest NAV of each scheme
-- Concepts: subquery with MAX
SELECT f.scheme_name, n.date AS latest_date, n.nav AS latest_nav
FROM nav_history n
JOIN fund_master f ON f.amfi_code = n.amfi_code
WHERE n.date = (SELECT MAX(n2.date) FROM nav_history n2 WHERE n2.amfi_code = n.amfi_code)
ORDER BY f.scheme_name
LIMIT 15;

-- Q18: Investors who use both SIP and Lumpsum
-- Concepts: IN subquery, COUNT DISTINCT
SELECT COUNT(DISTINCT investor_id) AS investors_with_sip_and_lumpsum
FROM investor_transactions
WHERE transaction_type = 'SIP'
  AND investor_id IN (
      SELECT investor_id
      FROM investor_transactions
      WHERE transaction_type = 'Lumpsum'
  );


-- =====================================================================
-- PART 6: WINDOW FUNCTIONS
-- =====================================================================

-- Q19: Top 3 schemes by investment inside each category
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

-- Q20: Monthly net investment with running total and month-over-month change
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

-- Q21: Biggest one-day NAV moves across all schemes
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

-- Q22: Share of total investment by category
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

-- Q23: 30-day moving average of NAV for SBI Bluechip Regular (119551)
-- Concepts: AVG() OVER (ROWS BETWEEN ...)
SELECT date, nav,
       ROUND((AVG(nav) OVER (ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW))::numeric, 4) AS nav_30d_avg
FROM nav_history
WHERE amfi_code = 119551
ORDER BY date DESC
LIMIT 10;
