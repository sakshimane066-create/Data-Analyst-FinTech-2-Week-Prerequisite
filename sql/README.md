# Data Analyst FinTech: Bluestock Internship Project

**Author:** Sakshi Mane  |  Bluestock Fintech, Data Analyst Internship

Mutual fund analytics project: data ingestion, cleaning, SQL database design, analysis and dashboard, plus the 2-week FinTech prerequisite work.

## Repository structure
| Path | What it contains |
|---|---|
| `Week1/`, `Week2/` | 2-week prerequisite assignments |
| `notebooks/` | Analysis notebooks |
| `reports/` | Reports |
| `data_ingestion.py`, `live_nav_fetch.py`, `setup_project.py` | Day 1: project setup and data ingestion (ETL) |
| `clean_data.py`, `load_db.py`, `run_queries.py`, `make_dictionary.py` | Day 2: cleaning, database load, queries, data dictionary |
| `data/processed/` | 10 cleaned CSVs and `cleaning_day2_log.csv` |
| `schema.sql`, `queries.sql`, `query_results.md` | Day 2: SQLite star schema and 10 analytical queries with results |
| `bluestock_mf.db` | Day 2: SQLite database (star schema) |
| `data_dictionary.md` | Day 2: every column, type and business definition |

## Day 2: Data Cleaning + SQL Database Design
Put the original CSVs in `data/raw/`, then run from the repo root:
```
pip install pandas sqlalchemy
python clean_data.py        # cleans all 10 datasets -> data/processed/
python load_db.py           # builds bluestock_mf.db from schema.sql; checks row counts and foreign keys
python run_queries.py       # runs queries.sql -> query_results.md
python make_dictionary.py   # regenerates data_dictionary.md
```
Key cleaning rules: NAV forward-filled to a daily calendar (`is_filled = 1` marks carried-forward rows), transaction types standardised to SIP/Lumpsum/Redemption, amounts and NAV validated > 0, expense ratio checked against 0.1-2.5%.

## Notes
- For learning purposes only; not investment advice.
