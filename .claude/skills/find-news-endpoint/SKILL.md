---
name: find-news-endpoint
description: Find an argaam.com or mubasher.info news endpoint by watching the live site in Chrome DevTools (chrome-devtools MCP), then replay it with curl_cffi and record it in news_endpoints/argaam.md or news_endpoints/mubasher.md. Use when adding or fixing a news tool, or when asked "where does Argaam or Mubasher get X".
---

# Find a news endpoint on Argaam or Mubasher

Goal: find where the site gets a piece of news or data, call it from Python with the helpers in `tasi_mcp.py`, and record it in that site's file: `news_endpoints/argaam.md` or `news_endpoints/mubasher.md`.

Start with that file. If the data is already mapped, go straight to the replay. Its "How to call" section has the rules every request needs.

## Finding it

The sites are built for people, not scripts, so assume the data hides behind something a person would do: lazy loads on scroll, "load more", sub-tabs, sub-pages, date filters. Explore the live site with the `chrome-devtools` MCP first, do those things, and watch the XHR/fetch requests each one fires. Raw HTML misses what loads later. Only one agent drives Chrome at a time. If the MCP is missing: `claude mcp add chrome-devtools --scope user -- npx chrome-devtools-mcp@latest --no-usage-statistics --no-performance-crux`, then restart.

What you can't guess about Argaam:
- Every page carries the full company search list, which maps symbol to Argaam's company id: `data-company="3509" data-market="3"` then `relf-Stocksymbol="2222"`.
- Arabic section ids differ from English: news `26`/`205`, disclosures `25`/`204`, analyst views `24`/`203`.
- RSS feeds 404 without their `?sectionid=`. The feed list is at `/en/rss`.
- A paid article shows a `loginSubsbtn` box. `DMP_IsArticleLocked` says `'False'` even then.

What you can't guess about Mubasher:
- It takes the Tadawul symbol directly: `/markets/TDWL/stocks/{symbol}/news`. `english.` is English, `www.` is Arabic.
- The article body is in `window.midata.article`. Its `publishedAt` is Riyadh time marked `Z`; the RSS `pubDate` is real GMT.
- robots.txt says `Disallow: /api/` and `Crawl-delay: 5`.

## Done when

- It replays without a browser through `t.fetch(url)`.
- The site's robots.txt and terms allow it.
- The site's file has a row that follows the rules at the top of that file. Dead ends go under "Failed / not useful".
- If you added a tool, it follows `CLAUDE.md` and `uv run pytest` passes.

## Known issues

One line per real failure: what broke and the fix that worked, or "unresolved" plus what was tried. Add a line only after the user approves it. If a line above caused the failure, fix that line instead. Delete a line once a step, test or code covers it.

- Chrome says "The browser is already running for .../chrome-profile": another Claude session has it open. Don't kill it. Work from the page HTML (`t.fetch(url)`) or wait until it's free.
