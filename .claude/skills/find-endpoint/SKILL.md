---
name: find-endpoint
description: Find a saudiexchange.sa data endpoint by watching the live site in Chrome DevTools (chrome-devtools MCP), then replay it with curl_cffi and record it in docs/ENDPOINTS.md. Use when adding a tool, when a tool breaks because the site changed, or when asked "where does the site get X".
---

# Find an endpoint on saudiexchange.sa

Goal: find where the site gets a piece of data, call it from Python with the helpers in `src/saudiexchange.py`, and record it in `docs/ENDPOINTS.md`.

Start with `docs/ENDPOINTS.md`. If the data is already mapped, go straight to the replay. Its "How to call" section has the rules every request needs.

## Finding it

The site is built for people, not scripts, so assume the data hides behind something a person would do: lazy loads on scroll, "load more", downloads, sub-tabs, sub-pages, date pickers. Explore the live site with the `chrome-devtools` MCP first, do those things, and watch the XHR/fetch requests each one fires. Raw HTML misses what loads later. Only one agent drives Chrome at a time. If the MCP is missing: `claude mcp add chrome-devtools --scope user -- npx chrome-devtools-mcp@latest --no-usage-statistics --no-performance-crux`, then restart.

What you can't guess about this site:
- Akamai blocks headless Chrome. Use a visible window.
- Add `locale=en` to every page URL, the company profile included.
- Pages name their portlet endpoints (`p0/IZ7_...=NJname=/`) in their own HTML, including ones no click fires.
- Allowed parameter values are usually the page's `<select>` options.
- The page logs a JWT and the browser holds session cookies. No endpoint needs them, so keep them out of code and docs.

## Done when

- It replays without a browser through `saudiexchange.xhr(base + path, page_url, ...)`, `saudiexchange.servlet(name)` or `core.fetch(url)`. A 403 almost always means a wrong Referer or missing XHR headers, not a dead endpoint.
- `docs/ENDPOINTS.md` has a row that follows the rules at the top of that file. Dead ends go under "Failed / not useful".
- If you added a tool, it follows `CLAUDE.md` and `uv run pytest` passes.

## Known issues

One line per real failure: what broke and the fix that worked, or "unresolved" plus what was tried. Add a line only after the user approves it. If a line above caused the failure, fix that line instead. Delete a line once a step, test or code covers it.

- Chrome says "The browser is already running for .../chrome-profile": another Claude session has it open. Don't kill it. Work from the page HTML (`saudiexchange.page(url)`, its `<select>` options and JS) or wait until it's free.
