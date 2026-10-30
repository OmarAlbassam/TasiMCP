# Mubasher endpoints

Every mubasher.info endpoint found so far, split into **used** (code calls it), **not used** (works, no tool yet) and **failed**. This file must stay **stateless**: no "verified" dates or "works as of" notes, because they go stale. Every claim must be **challengeable**: each row carries enough to replay it (path, params) and what a correct reply looks like, so anyone can re-run it and see whether it still holds. Nothing needs a login.

When a tool starts or stops calling an endpoint, move its row between sections.

## How to call

- `t.fetch(url)`: the shared `curl_cffi` session with `impersonate="chrome"`. Every reply below is HTML or RSS, so parse the body yourself.
- robots.txt has `Crawl-delay: 5` and `Disallow: /api/`. Keep 5 s between requests.
- Article `publishedAt` is Riyadh time marked `Z`. The RSS `pubDate` of the same article is real GMT, 3 h earlier.

Shorthands used in the tables:
- `MU` = `https://english.mubasher.info`. The Arabic site `https://www.mubasher.info` takes the same paths.

## Used

No tool calls these yet.

## Not used

| path | params | returns |
|---|---|---|
| `MU/markets/TDWL/stocks/{symbol}/news` and `.../news/{N}` | page `N` from 2 | HTML: 25 `.mi-article-media-block` per page (date, title link `/news/{id}/...`, section tag, summary). JS `numPages` (2222: 17 English, 65 Arabic) |
| `MU/news/sa/now/latest` and `.../latest/{N}` | page `N` from 2 | same blocks for the whole Saudi market, `numPages` 212 in English |
| `MU/news/{id}/` | — | HTML. `window.midata.article` holds `body` (HTML) and `publishedAt` |
| `https://feeds.mubasher.info/{en,ar}/TDWL/news` | — | RSS, 50 newest items, `pubDate` in GMT. Some items carry a wrong year at the source: 4581496 is `24 Mar 2426` in the feed and the article, so it sorts first |

## Failed / not useful

| path | why |
|---|---|
| `MU/api/1/...` (fair values, earnings, corporate actions, events, IPOs) | robots.txt `Disallow: /api/` |
