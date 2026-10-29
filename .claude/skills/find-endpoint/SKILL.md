---
name: find-endpoint
description: Find a saudiexchange.sa data endpoint by watching the live site in Chrome DevTools (chrome-devtools MCP), then replay it with curl_cffi and record it in ENDPOINTS.md. Use when adding a tool, when a tool breaks because the site changed, or when asked "where does the site get X".
---

# Find an endpoint on saudiexchange.sa

Needs the `chrome-devtools` MCP server (`claude mcp list` should show it). If it's missing: `claude mcp add chrome-devtools --scope user -- npx chrome-devtools-mcp@latest --no-usage-statistics --no-performance-crux`, then restart.

## 1. Check what's known

Read `ENDPOINTS.md` first. If the data is already mapped, skip the browser and go to step 3.

## 2. Watch the site

- Never pass `--headless`. Akamai returns "Access Denied" (403) to headless Chrome. A visible window works.
- `list_pages` first. Every other tool needs its `pageId`.
- `navigate_page` to the page that shows the data. Add `?locale=en` to every page except the company profile (see `PROFILE` in `tasi_mcp.py`).
- If the data only shows up after an action (tab, date picker, "load more"), `take_snapshot`, then `click` the element.
- `list_network_requests` with `resourceTypes: ["xhr", "fetch"]` and a big `pageSize` (it is paginated; requests fired after a click land on later pages). Skip analytics (google-analytics, go-mpulse) and `chat.tadawul.com.sa`.
- Quicker for GETs: `evaluate_script` with `() => performance.getEntriesByType('resource').map(e => e.name).filter(n => n.includes('NJ'))` gives every full URL and query in one call.
- `get_network_request` with the `reqid` gives the method, the POST body, headers and the response. It prints session cookies, so use it only for POST bodies. Its `responseFilePath` can't write outside the repo; save under `.claude/tmp_*` and delete it after.
- No XHR? The table may be in the page HTML. Grep `t.page(url)[0]` for the value, and for `NJ\w+=` to list every endpoint the page's JS knows, including ones no click fired.
- Allowed param values are usually the page's `<select>` options. Read them from `t.page(url)[0]` with BeautifulSoup.
- Big pages: `take_snapshot` with `filePath` and grep it. Some tabs are `<a href="#">`; click them with `evaluate_script` if `click` misses.
- `p0/IZ7_...=NJname=/` paths are relative to the page's `<base href>`. Read it with `evaluate_script`: `() => document.baseURI`.
- Page console logs print a JWT. Known endpoints don't need it, so don't copy it into code or docs.

## 3. Replay it without a browser

The endpoint is only usable if the existing helpers can call it:

```sh
uv run python -c "import tasi_mcp as t; _, base = t.page(PAGE_URL); print(t.xhr(base + PATH, PAGE_URL).text[:2000])"
```

POST: `t.xhr(base + PATH, PAGE_URL, method="POST", data={...})`. Use `t.servlet(name)` for `/tadawul.eportal.theme.helper/*`. A 403 almost always means a wrong `Referer` or missing XHR headers, not a dead endpoint.

## 4. Record it

- Add a row to `ENDPOINTS.md`: **Not used** (under its page) until a tool calls it, then move it to **Used**. Give path, method + params, what it returns, response size, and what a correct reply looks like (no verified dates; they go stale). Dead ends go under **Failed / not useful**.
- If you're adding a tool, follow the existing layers in `tasi_mcp.py` (`page`/`xhr`/`servlet`, `@cached`, `check()`/`day()` for input) and add an offline test in `test_tasi_mcp.py` using `fake(monkeypatch, reply)` with a trimmed real response as the fixture.
- `uv run pytest`.
