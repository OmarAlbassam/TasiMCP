# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Local stdio MCP server for the Saudi Exchange (Tadawul). It scrapes saudiexchange.sa live on each tool call. No hosting, no database, no login.

## Commands

- Run the server: `uv run tasi-mcp` (entry point `src:main`).
- All tests: `uv run pytest`. One test: `uv run pytest tests/test_tasi_mcp.py::test_options_strips_html_and_checks_date`.
- Register with Claude Code: `claude mcp add tasi -- uv run --directory /Users/omar/workspace/TasiMCP tasi-mcp`. Tools added in a running session only load after `/mcp` reconnect or a restart.
- Quick live check of one tool without MCP: `uv run python -c "import src; print(src.saudiexchange.get_quotes(['1120']))"`.

## Architecture

A package, `src/` (MCP Python SDK v2, `MCPServer` + `@mcp.tool()`). Imports go one way: `news` and `saudiexchange` import from `core`; `core` imports neither.

- `__init__.py`: imports the three submodules so every `@mcp.tool()` registers, and defines `main()` (the `tasi-mcp` entry point).
- `core.py`: `mcp`, the shared session `S` and `LOCK`, `request()`, `fetch()`, `cached`/`_cache`, `day()`.
- `saudiexchange.py`: everything for saudiexchange.sa, including all the tools.
- `news.py`: the Argaam company-id map (`argaam_id`). `argaam_ids.json` sits beside it.

Layers, bottom up:

- `request()`: one shared `curl_cffi` session with `impersonate="chrome"`, behind a lock. Akamai blocks other TLS fingerprints.
- `xhr(url, referer)`: adds the `XHR` headers and a `Referer`. JSON endpoints return 403 without both.
- `page(url)`: fetches a portal page and its `<base href>`. The `p0/IZ7_...=NJname=/` portlet constants are relative to that base, so call `base + CONST` with the page URL as referer. `profile_xhr(symbol, CONST, **params)` does this for the company-profile portlets.
- `servlet(name)`: site-wide `/tadawul.eportal.theme.helper/*` JSON (ticker, company list, market summary).
- `@cached(ttl)`: in-memory cache keyed by function name and args. Tests reset `_cache`.
- Tools: thin functions that call the layers above, validate input (`check(symbol)`, `day()` for ISO dates) and parse HTML with BeautifulSoup / `clean()` / `tables()`.

Many replies are JSON sent as `text/html`, so parse the body yourself. `docs/ENDPOINTS.md` maps every known saudiexchange.sa endpoint (path, params, referer page, which tool uses it, and what failed). News endpoints have one file per site: `docs/news_endpoints/argaam.md` and `docs/news_endpoints/mubasher.md`. Read the right file before adding a tool or hunting for a new endpoint.

## Data-accuracy rules

- Never compute P/E as price ÷ site EPS. Tadawul doesn't restate EPS after bonus issues. `get_valuation` uses Tadawul's own P/E from the profile's Peer Comparison table (`"-"` means loss-making → `None`).
- The self-computed TTM P/E code (`ttm_profit`, `xbrl_profits`, `xbrl_quarter_profits`) is marked `@deprecated` but kept on purpose. Don't delete it.
- `get_quotes` merges market-watch extras (open/high/low, bid/ask, 52w) into TickerServlet rows. A market-watch failure must fall back to the plain ticker, not fail the call.

## Tests

`tests/test_tasi_mcp.py` is offline. Pure parsers get HTML/JSON fixtures directly. Tools use `fake(monkeypatch, reply)`, which stubs `xhr`, `page`, `fetch`, `check`, `companies` and the cache so every request returns `reply`. Patch a name on the module that looks it up: `_cache` on `core` (the `cached` wrapper reads core's global), the rest on `saudiexchange`, and Argaam tests on `news`. `from .core import fetch` makes a separate `fetch` binding in each module, so patching one leaves the other live.
