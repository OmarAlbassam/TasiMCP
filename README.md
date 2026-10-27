# tasi-mcp

Local MCP server for the Saudi Exchange (Tadawul). It runs over stdio and pulls live data from saudiexchange.sa on each request. Results are cached in memory for 1–10 minutes.

## Add to Claude Code

```
claude mcp add tasi -- uv run --directory /Users/omar/workspace/TasiMCP tasi-mcp
```

## Tools

| Tool | What it returns |
|---|---|
| `list_companies` | Search ~1,950 securities by symbol, name or ISIN |
| `get_quotes` | Latest price, change, volume and turnover for ~400 stocks; Main market rows add open/high/low, bid/ask and 52-week range |
| `get_market` | TASI and other index levels, top gainers and losers |
| `get_profile` | Overview, capital, board, dividends, last 3 years and 4 quarters of financials |
| `get_valuation` | Tadawul's P/E, EPS and market cap on today's share count |
| `get_statements` | Older balance sheet, income and cash flow statements (2019–2022), and 2011–2014 ratios |
| `get_filings` | Links to PDF and XBRL filings |
| `get_xbrl` | Every line item from an XBRL filing, such as loans and finance costs |
| `get_price_history` | Daily price, volume and trade data, back to 2009 |
| `get_announcements` | Company announcements |
| `get_corporate_actions` | Bonus shares and other capital changes |
| `get_foreign_ownership` | Foreign ownership limit, actual and strategic % |
| `get_major_shareholders` | Daily history of 5%+ holders, incl. lock-up holders |
| `get_options` | Options chain per expiry: strikes, call/put prices, bid/offer, open interest |
| `get_chart_series` | Daily (TASI since 1994, sectors since 2016) or 1-minute intraday closes for indices and stocks |
| `get_dividends` | Dividend calendar for one company or the whole Main market |
| `get_performance` | Every Main market stock's change over 6 days to 5 years |
| `get_ipos` | IPOs, ETF/sukuk listings and rights issues in a date range |

## Notes

- The site uses Akamai bot protection. `curl_cffi` copies Chrome's TLS fingerprint to get past it. If the site changes its setup, expect 403 errors.
- Don't calculate P/E as price ÷ the site's EPS. Tadawul doesn't update EPS after bonus share issues, so Al Rajhi shows 5.85 when the true figure is 4.13. `get_valuation` divides net profit by today's share count instead.
- `get_valuation`'s `pe` is read from the profile's Peer Comparison tab. An older self-calculated 12-month P/E from XBRL (`ttm_profit`, `xbrl_profits`) is kept in the code, marked `@deprecated`.
- Run the tests with `uv run pytest`.
