-- =====================================================================
-- Bluestock MF Analytics - SQLite star schema
-- Dimensions : dim_fund, dim_date
-- Facts      : fact_nav, fact_transactions, fact_performance, fact_aum
-- Supporting : benchmark_indices, category_inflows, monthly_sip_inflows,
--              industry_folio_count, portfolio_holdings
-- Run with   : PRAGMA foreign_keys = ON;  (load_db.py does this automatically)
-- =====================================================================
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS portfolio_holdings;
DROP TABLE IF EXISTS industry_folio_count;
DROP TABLE IF EXISTS monthly_sip_inflows;
DROP TABLE IF EXISTS category_inflows;
DROP TABLE IF EXISTS benchmark_indices;
DROP TABLE IF EXISTS fact_aum;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS fact_nav;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_fund;

-- ---------------------------------------------------------------- DIMENSIONS
CREATE TABLE dim_fund (
    amfi_code           INTEGER PRIMARY KEY,           -- AMFI scheme code
    fund_house          TEXT    NOT NULL,
    scheme_name         TEXT    NOT NULL,
    category            TEXT    NOT NULL,              -- Equity / Debt
    sub_category        TEXT    NOT NULL,
    plan                TEXT    NOT NULL CHECK (plan IN ('Regular','Direct')),
    launch_date         TEXT,                          -- YYYY-MM-DD
    benchmark           TEXT,
    expense_ratio_pct   REAL    CHECK (expense_ratio_pct BETWEEN 0.1 AND 2.5),
    exit_load_pct       REAL    CHECK (exit_load_pct >= 0),
    min_sip_amount      INTEGER CHECK (min_sip_amount >= 0),
    min_lumpsum_amount  INTEGER CHECK (min_lumpsum_amount >= 0),
    fund_manager        TEXT,
    risk_category       TEXT,
    sebi_category_code  TEXT
);

CREATE TABLE dim_date (
    date_key        INTEGER PRIMARY KEY,               -- YYYYMMDD, e.g. 20240131
    full_date       TEXT    NOT NULL UNIQUE,           -- YYYY-MM-DD
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month           INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name      TEXT    NOT NULL,
    year_month      TEXT    NOT NULL,                  -- YYYY-MM
    day             INTEGER NOT NULL,
    day_of_week     INTEGER NOT NULL,                  -- 1 = Monday ... 7 = Sunday
    day_name        TEXT    NOT NULL,
    is_weekend      INTEGER NOT NULL CHECK (is_weekend IN (0,1)),
    financial_year  TEXT    NOT NULL                   -- Indian FY (Apr-Mar), e.g. FY2024-25
);

-- --------------------------------------------------------------------- FACTS
CREATE TABLE fact_nav (
    amfi_code   INTEGER NOT NULL,
    date_key    INTEGER NOT NULL,
    nav         REAL    NOT NULL CHECK (nav > 0),
    is_filled   INTEGER NOT NULL DEFAULT 0 CHECK (is_filled IN (0,1)),  -- 1 = weekend/holiday carried forward
    PRIMARY KEY (amfi_code, date_key),
    FOREIGN KEY (amfi_code) REFERENCES dim_fund (amfi_code),
    FOREIGN KEY (date_key)  REFERENCES dim_date (date_key)
);

CREATE TABLE fact_transactions (
    transaction_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_id         TEXT    NOT NULL,
    date_key            INTEGER NOT NULL,
    amfi_code           INTEGER NOT NULL,
    transaction_type    TEXT    NOT NULL CHECK (transaction_type IN ('SIP','Lumpsum','Redemption')),
    amount_inr          REAL    NOT NULL CHECK (amount_inr > 0),
    state               TEXT,
    city                TEXT,
    city_tier           TEXT    CHECK (city_tier IN ('T30','B30')),
    age_group           TEXT,
    gender              TEXT,
    annual_income_lakh  REAL,
    payment_mode        TEXT,
    kyc_status          TEXT    NOT NULL CHECK (kyc_status IN ('Verified','Pending','Rejected')),
    is_amount_outlier   INTEGER NOT NULL DEFAULT 0 CHECK (is_amount_outlier IN (0,1)),
    FOREIGN KEY (amfi_code) REFERENCES dim_fund (amfi_code),
    FOREIGN KEY (date_key)  REFERENCES dim_date (date_key)
);
CREATE INDEX idx_tx_date     ON fact_transactions (date_key);
CREATE INDEX idx_tx_fund     ON fact_transactions (amfi_code);
CREATE INDEX idx_tx_investor ON fact_transactions (investor_id);

-- One row per scheme (source: scheme_performance_clean.csv). Descriptive columns
-- (scheme_name, fund_house, category, plan) live in dim_fund and are not repeated here.
CREATE TABLE fact_performance (
    amfi_code            INTEGER PRIMARY KEY,
    return_1yr_pct       REAL,
    return_3yr_pct       REAL,
    return_5yr_pct       REAL,
    benchmark_3yr_pct    REAL,
    alpha                REAL,
    beta                 REAL,
    sharpe_ratio         REAL,
    sortino_ratio        REAL,
    std_dev_ann_pct      REAL    CHECK (std_dev_ann_pct >= 0),
    max_drawdown_pct     REAL    CHECK (max_drawdown_pct <= 0),
    aum_crore            INTEGER CHECK (aum_crore >= 0),
    expense_ratio_pct    REAL,
    morningstar_rating   INTEGER CHECK (morningstar_rating BETWEEN 1 AND 5),
    risk_grade           TEXT,
    expense_ratio_valid  INTEGER CHECK (expense_ratio_valid IN (0,1)),   -- 1 = within 0.1-2.5%
    has_anomaly          INTEGER CHECK (has_anomaly IN (0,1)),           -- 1 = a metric was an outlier (kept)
    anomaly_columns      TEXT,
    FOREIGN KEY (amfi_code) REFERENCES dim_fund (amfi_code)
);

CREATE TABLE fact_aum (
    date_key         INTEGER NOT NULL,
    fund_house       TEXT    NOT NULL,
    aum_lakh_crore   REAL    CHECK (aum_lakh_crore >= 0),
    aum_crore        INTEGER CHECK (aum_crore >= 0),
    num_schemes      INTEGER,
    PRIMARY KEY (date_key, fund_house),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key)
);

-- ---------------------------------------------------------------- SUPPORTING
CREATE TABLE benchmark_indices (
    date_key     INTEGER NOT NULL,
    index_name   TEXT    NOT NULL,
    close_value  REAL    NOT NULL CHECK (close_value > 0),
    PRIMARY KEY (date_key, index_name),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key)
);

CREATE TABLE category_inflows (
    date_key          INTEGER NOT NULL,                -- first day of the month
    category          TEXT    NOT NULL,
    net_inflow_crore  REAL,
    PRIMARY KEY (date_key, category),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key)
);

CREATE TABLE monthly_sip_inflows (
    date_key                   INTEGER PRIMARY KEY,    -- first day of the month
    sip_inflow_crore           INTEGER CHECK (sip_inflow_crore >= 0),
    active_sip_accounts_crore  REAL,
    new_sip_accounts_lakh      REAL,
    sip_aum_lakh_crore         REAL,
    yoy_growth_pct             REAL,                   -- NULL for the first 12 months
    is_outlier_new_accounts    INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key)
);

CREATE TABLE industry_folio_count (
    date_key             INTEGER PRIMARY KEY,          -- first day of the month
    total_folios_crore   REAL,
    equity_folios_crore  REAL,
    debt_folios_crore    REAL,
    hybrid_folios_crore  REAL,
    others_folios_crore  REAL,
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key)
);

CREATE TABLE portfolio_holdings (
    amfi_code          INTEGER NOT NULL,
    stock_symbol       TEXT    NOT NULL,
    date_key           INTEGER NOT NULL,               -- portfolio date
    stock_name         TEXT,
    sector             TEXT,
    weight_pct         REAL    CHECK (weight_pct >= 0),
    market_value_cr    REAL,
    current_price_inr  REAL,
    PRIMARY KEY (amfi_code, stock_symbol, date_key),
    FOREIGN KEY (amfi_code) REFERENCES dim_fund (amfi_code),
    FOREIGN KEY (date_key)  REFERENCES dim_date (date_key)
);
