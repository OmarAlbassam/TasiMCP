# Argaam endpoints

Every argaam.com endpoint found so far, split into **used** (code calls it), **not used** (works, no tool yet) and **failed**. This file must stay **stateless**: no "verified" dates or "works as of" notes, because they go stale. Every claim must be **challengeable**: each row carries enough to replay it (path, params) and what a correct reply looks like, so anyone can re-run it and see whether it still holds. Nothing needs a login.

When a tool starts or stops calling an endpoint, move its row between sections.

## How to call

- `t.fetch(url)`: the shared `curl_cffi` session with `impersonate="chrome"`. Every reply below is HTML or RSS, so parse the body yourself.
- Lists give dates only: `dd/mm/yyyy` in English, `yyyy/mm/dd` in Arabic.

Shorthands used in the tables:
- `AR` = `https://www.argaam.com`.
- `{cid}` = Argaam company id: `argaam_id(symbol)`, from the company list row under Used.

## Used

| tool | path | params | returns |
|---|---|---|---|
| `argaam_id()` (live fallback when `argaam_ids.json` misses a symbol), `update_argaam_ids.py` (via `argaam_list()`) | `AR/en/rss`. Any page carries the list, e.g. `AR/en` or `AR/en/tadawul/tasi/saudi-aramco` | — | company search list: `data-company="{cid}" data-market="{m}"` then `relf-Stocksymbol="{symbol}"`. Market `3` main (about 290 rows, including some funds such as 4700 and 9400), `14` Nomu (about 120). Some symbols carry a trailing space: `"4082 "`. 1120 → 43, 2222 → 3509, 7020 → 31 |

## Not used

| path | params | returns |
|---|---|---|
| `AR/{en,ar}/article/entityarticles/sectionid/{S}/entityid/4/{cid}/pageno/{n}` | `S` English: 205 news, 204 disclosures, 203 analyst views. Arabic: 26 news, 25 disclosures, 24 analyst views, 1422 Argaam reports | HTML: 50 `.article-tbl` rows (`.date`, title link `articledetail/id/{N}`, `.source`) |
| `AR/{en,ar}/article/articledetail/id/{N}` | — | HTML article. `DMP_CompanySymbol = ["2222"]` names the company. A paid article shows a `loginSubsbtn` box (1923655); `DMP_IsArticleLocked` is `'False'` either way |
| `AR/en/rss/{feed}?sectionid={S}` (feed list at `AR/en/rss`) | `sectionid` | RSS. `ho-company-disclosures?sectionid=244`: 15 items. `ho-main-news?sectionid=1524`: 7 items |

## Failed / not useful

| path | why |
|---|---|
| `AR/en/rss/{feed}` without `?sectionid=` | 404 |
