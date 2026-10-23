# API Data Extraction Assignment

**API used:** CoinGecko public API, `/coins/markets` (free, no API key)
**Goal:** call a public API, inspect the JSON, and convert it into a CSV for analysis.

## 1. What is being called
- **Method:** GET
- **URL:** `https://api.coingecko.com/api/v3/coins/markets`
- **Query parameters:** `vs_currency=inr`, `order=market_cap_desc`, `per_page=20`, `page=1`, `sparkline=false`
- **Authentication:** none for this endpoint (public). Paid or private APIs usually need an API key sent in a header, e.g. `Authorization: Bearer <token>`.
- **Documentation:** https://docs.coingecko.com (see the "Coins List with Market Data" endpoint)

## 2. Test in Postman (or Bruno)
1. New request, method **GET**, paste the URL above.
2. Open the **Params** tab and add the query parameters from section 1 (the URL updates automatically).
3. Click **Send**. Check that status is **200 OK**.
4. Look at the **Body** tab, "Pretty" view: the response is a JSON **array** of objects, one per coin.
5. Take a screenshot of the request and response and save it as `postman_screenshot.png`.

## 3. Understanding the JSON
- Top level is a list `[ {...}, {...} ]`; each object is one coin.
- Most fields are simple values (`current_price`, `market_cap`, `total_volume`).
- Some fields are nested objects, e.g. `roi` has `times`, `currency`, `percentage`, and it is `null` for many coins.
- Nested fields are flattened by `pandas.json_normalize()` into columns such as `roi.times`.

## 4. Run the script
```
pip install requests pandas
python fetch_api_to_csv.py
```
Outputs: `raw_response.json` (raw API response) and `crypto_markets.csv` (flat table, one row per coin, plus a `fetched_at_utc` timestamp).

## 5. Findings (fill in after running)
- Rows / columns in the CSV: ___
- Coin with highest market cap: ___
- Biggest 24h gainer and loser (`price_change_percentage_24h`): ___
- Missing values found and how handled: ___
- One observation useful for analysis: ___

## 6. Challenges and notes
- Free tier is rate-limited; HTTP 429 means wait and retry.
- Prices change every minute, so the `fetched_at_utc` column records when the snapshot was taken.
