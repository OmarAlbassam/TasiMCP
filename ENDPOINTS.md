# saudiexchange.sa data endpoints

Everything we know, verified live 2026-10-26 unless marked otherwise. Nothing needs a login or a JWT.

How to call (see `page()` / `xhr()` in `tasi_mcp.py`):
- `curl_cffi` `Session(impersonate="chrome")`. Akamai blocks other TLS fingerprints.
- Send the `XHR` headers from `tasi_mcp.py` plus `Referer` = the page URL. Without them you get 403 / "Access Denied".
- `p0/...` paths are relative to the `<base href>` of their page. GET the page first, then call `base + path`.
- Many JSON replies come back as `text/html`, so parse the body yourself. POST bodies are form-urlencoded.
- Pages: `P = https://www.saudiexchange.sa/wps/portal/saudiexchange`. Add `?locale=en` to every page except the profile.
- `/tadawul...` and `/Resources...` paths are relative to `https://www.saudiexchange.sa`, so no base href is needed for them.

## Site-wide (Referer: any page, e.g. `P/home`)

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| ThemeSearchUtilityServlet | `/tadawul.eportal.theme.helper/ThemeSearchUtilityServlet` | GET | every listed security: symbol, names, ISIN | `list_companies`, `check` |
| TickerServlet | `/tadawul.eportal.theme.helper/TickerServlet` | GET | `stockData`: last price, change, volume, turnover, trades (~400 stocks) | `get_quotes`, `get_valuation` |
| RefreshTradeDetailsServlet | `/tadawul.eportal.theme.helper/RefreshTradeDetailsServlet` | GET | index summaries, 52w/YTD, top gainers/losers, company counts | `get_market` |
| ThemeTASIUtilityServlet | `/tadawul.eportal.theme.helper/ThemeTASIUtilityServlet` | GET | header bar: TASI, MT30, Nomu values and changes, `marketStatusCode` | not used (seen in browser logs only) |
| ChartGenerator | `/tadawul.eportal.charts.v2/ChartGenerator?methodType=parsingMethod&chart-type=T&chart-parameter=X&pageName=N` (`format=json` optional) | GET | JSON `[{dateTime, indexPrice}]` | not used |
| XBRL report | `/Resources/XBRL_DOCS/...html` (links from statementsTabData type 4) | GET | full XBRL statements as HTML tables | `get_xbrl` |

ChartGenerator `chart-type` / `chart-parameter` values (`pageName` = what the page sends, e.g. `CompanyProfileMainMarket`, `MainMarketWatch`, `IndicesPerformance`, `MarketStatusHomeGraph`. Whether pageName is required was not checked):
- `SQL_CI_CV_COM` / symbol: daily closes for that stock since 2001.
- `SQL_CI_DV` / symbol: today's 1-minute prices for that stock.
- `SQL_T_IC_ALL_PER` / `tasi`: TASI daily closes since 1994.
- `SQL_T_IC_ALL_COM` / sector index (e.g. `tbni`): daily closes since 2016.
- `SQL_T_ID` / sector index: today's 1-minute prices for that index.
- `SQL_MI_MSPV` / `tasi` or `mt30`, `SQL_MI_MSPV_SME` / `nomuc`, `SQL_MI_MSPV_SUKUK` / `tsbi`: today's 1-minute index prices.

## Company profile (Referer: `PROFILE` URL in `tasi_mcp.py`. The plain `?companySymbol=` URL renders an empty page)

Prefixes: `A = p0/IZ7_5A602H80O0VC4060O4GML81G57=CZ6_5A602H80OGF2E0QF9BQDEG10K4=`, `B = p0/IZ7_5A602H80O0VC4060O4GML81GV7=CZ6_5A602H80OGF2E0QF9BQDEG10K4=`, `C = p0/IZ7_5A602H80O0VC4060O4GML81G55=CZ6_5A602H80OGF2E0QF9BQDEG10K4=`.

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| profile page | the `PROFILE` URL itself | GET | static HTML: `.fundInfo` (shares, capital), `.company_management`, `#unifiedSummaryFinancial`, `#peercompDT` (Tadawul P/E), all other tables. Sub-tab clicks fire no requests | `get_profile`, `get_valuation` |
| statements | `A NJstatementsTabData=/` | GET `statementType` (0 balance, 1 income, 2 cash flow, 3 ratios, 4 XBRL links, 5 PDF links), `reportType=0`, `requestLocale=en`, `symbol` | HTML tables | `get_statements`, `get_filings` |
| statements type 6 | same | GET `statementType=6` | 149 KB HTML table, fired by the "Financial statements and reports" tab for 8010. Contents unverified | not used |
| corporate actions | `B NJgetCorporateAction=/` | GET `indexSymbol`, `language=en`, `issueType=Corporate Action` (`Dividends` also returns 200) | JSON capital changes | `get_corporate_actions` |
| options chain | `B NJgetOptionsBySettlementDate=/` | GET `settlement_date` (`YYYY-MM-DD` or `All Events`), `symbol`, `language=en` | JSON list whose values are HTML fragments (`calls_contract_code`, ...) | not used |
| foreign ownership | `A NJforeginOwnerShip=/` (typo is the site's) | GET `symbol` | HTML: maximum and actual foreign ownership (1120: 49.00% / 13.93%) | not used |
| major shareholders | `A NJhistoryOfMajorShareHolder=/` | GET `symbol`, `history=0` with `fromDate`/`toDate=undefined` for current holders. `history=1` with `fromDate`/`toDate` `YYYY/MM/DD` for history | HTML `#majorShareHoldersTable` | not used |
| board holdings history | `A NJhistoricalBoardMembersWithDates=/` | GET `symbol`, `fromDate`, `toDate` (`YYYY/MM/DD`; the browser sends `//`) | HTML. Huge: 1120 over 2015–2026 = 28.7 MB; 4002 over 1 year = 1.7 MB | not used |

## Historical reports `P/newsandreports/reports-publications/historical-reports`

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| price history | `p0/IZ7_5A602H80O0HTC060SG6UT81216=CZ6_5A602H80O0HTC060SG6UT812E4=NJpopulateCompanyDetails=/` | POST: see `get_price_history` (`selectedMarket` MAIN or NOMUC, `selectedEntity`, `startDate`/`endDate` `DD-MM-YYYY`, `start`/`length` up to 100) | JSON `data`: daily OHLC, volume, turnover, trades since 2009 | `get_price_history` |

## Issuer announcements `P/newsandreports/issuer-news/issuer-announcements`

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| announcements | `p0/IZ7_5A602H80O0HTC060SG6UT81DI1=CZ6_5A602H80O0HTC060SG6UT81D26=NJgetAnnouncementListData=/` | POST: see `get_announcements` (`symbol`, `pageNumberDb`, `pageSize`, ...) | JSON `totalCount`, `announcementList` | `get_announcements` |

## Home `P/home`

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| home graphs | `p0/IZ7_5A602H80OOF35068G2P8CG10H6=CZ6_5A602H80OGCJ40QNAM09E92001=N/` | GET | JSON `main_/parallel_/sukuk_market_graph`, each a JSON *string* of today's 1-minute `{dateTime, indexPrice}` | not used |
| financial calendar | `p0/IZ7_5A602H80OOMQC0604RU6VD1G21=CZ6_5A602H80OGCJ40QNAM09E92001=N/` | GET `year`, `month`, `requestLocale=en` | JSON `{date: [{companyCode, calendarType, summary, ...}]}` (dividends, new sessions). Seen in the browser only, not re-called with curl_cffi | not used |

## Main market watch `P/ourmarkets/main-market-watch`

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| market watch | `p0/IZ7_IPG41I82KGASC06S67RB9A0080=CZ6_5A602H80O8DDC0QFK8HJ0O2067=NJgetMainNomucMarketDetails=/` | POST `sectorParameter=all`, `tableViewParameter=1` (2 returns the same body), `iswatchListSelected=NO`, `requestLocale=en` | JSON `data`: 273 rows, price/change/volume per stock. PER/PBR/marketCap/yield are always 0 | not used |

## Market summary `P/ourmarkets/main-market-watch/marketsummary`

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| index | `p0/IZ7_IPG41I82KGASC06S67RB9A0001=CZ6_IPG41I82KGASC06S67RB9A0000=NJgetMarketIndexUrl=/` | GET | TASI `indexPrice`, `netChange`, `percentChange` | not used |
| top movers | `p0/IZ7_IPG41I82KGASC06S67RB9A00G2=CZ6_IPG41I82KGASC06S67RB9A0000=NJ{getTopGainersDetails,getTopLosersDetails,getMoversByVolumeDetails,getMoversByValueDetails}=/` | GET `requestLocale=en` | JSON `data`: price, change and 5-day performance per stock | not used |

## Main market performance `P/ourmarkets/main-market-watch/main-market-performance`

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| period gainers / losers | `p0/IZ7_5A602H80OOMQC0604RU6VD1021=CZ6_5A602H80OGSTA0QFSTBN9F10G0=NJ{getMainMarketPerformanceDetails,getMainMarketPerformanceLosersDetails}=/` | POST `reportFilter` (`gainers` by value, `gainersPercentage`), `sectorFilter=viewAllmarket`, `timeFrameFilter` (`1 Months`..`5 Years`), `isNonAdjusted=0`, `requestLocale=en` | JSON `data`: begin/end price, change %, high/low, value, volume. In our test the gainers call returned 21 rows and the losers call 270 | not used |

## Indices performance `P/ourmarkets/main-market-watch/indices-performance`

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| index price box | `p0/IZ7_5A602H80O0VC4060O4GML81G84=CZ6_5A602H80O0QU80QFSFB58028C7=NJupdatePriceBoxUrl=/` | GET `currentSector=TASI` (only TASI was tested) | JSON `tasiTodaysSummaryBean`: open, high, low, last, previous close, volume, turnover, trades | not used |

## Issuer directory `P/trading/participants-directory/issuer-directory`

Prefix `p0/IZ7_5A602H80OOMQC0604RU6VD10F2=CZ6_5A602H80OGSTA0QFSTBN9F10I5=`.

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| companies | `NJgetCompanyListByMarknetAndSectors=/` | POST `marketType=M`, `sector=All`, `symbol=`, `letter=` | JSON `data`: 273 rows with symbol, names, `isinCode`, profile URL | not used |
| sectors | `NJgetSectorsByMarketId=/` | POST `format=json`, `marketType=M` | `[{pk_rf_sector, name, symbol}]`: sector to index symbol (e.g. 31 Energy → TENI) | not used |

## Dividends calendar `P/newsandreports/issuer-financial-calendars/dividends`

Prefix `p0/IZ7_5A602H80OOMQC0604RU6VD10J3=CZ6_5A602H80O8HH70QFKI8IRJ00P3=`.

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| dividends | `NJgetDividendsDetails=/` | POST `symbolorcompany`, `bySymbol` (both = symbol), `start`/`end` `DD-MM-YYYY`, `marketsListId=M`, `period=CUSTOM`, `sector=`, `market=` | JSON `data`: announced, due and distribution dates, amount. Rows start in 2023 even when asked from 2021 (cause unknown) | not used |
| sectors | `NJgetSectors1=/` | GET `marketsListId=M` | `[{id, name}]` | not used |

## Corporate actions calendar `P/newsandreports/issuer-financial-calendars/corporate-actions`

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| corporate actions | `p0/IZ7_5A602H80OOMQC0604RU6VD10J0=CZ6_5A602H80O8HH70QFKI8IRJ00J3=NJgetCorpDetails=/` | POST `searchType=searchData`, `marketsListId=M`, `companySymbol` (blank = all), `start`/`end` `DD-MM-YYYY` | JSON `data`: issue type, announce and due dates, previous and new capital | not used |

## IPOs `P/listing/ipos`

Prefix `p0/IZ7_5A602H80OOMQC0604RU6VD10F0=CZ6_5A602H80OO5JC0QFMU3NNK3852=`.

| name | path | method + params | returns | used by |
|---|---|---|---|---|
| listings | `NJgetALLListingDataId=/`, `NJgetIPOListingDataId=/`, `NJgetTradableRightsDataId=/` | POST `listedType` (`ALL`, `IPO`, `TRADABLE-RIGHTS`), `market` (blank, `M`, `N`, `S`), `instrument=`, `fromDate`/`toDate` `DD/MM/YYYY` | JSON. ALL returns `ipoData` + `tradableData`; the others return `data`. Rows hold issuer details | not used |

## Failed / not useful

- `A NJpeerComparison=/` (`companySymbol`, `peerID`): returns "Request Rejected" or 500. Read the P/E from `#peercompDT` on the profile instead.
- `B NJgetAllEvents=/`: 500.
- `/wps/contenthandler/wcmrest/query/...`: `UNAUTHORISED_ACCESS`.
- `/Charts/ChartGenerator` (the old path): "Request Rejected". Use `/tadawul.eportal.charts.v2/`.
- `NJgetIndexDataURL=/` (`C` on the profile, `indexSymbol`; also on the indices page): `indexLastTradedPrice` is unreliable (gave -269.25, the change, for TBNI).
- `C NJupdatePriceBoxUrl=/` on the profile (`symbol`): only change and %. Redundant with TickerServlet.
- `NJgetJWTTokenUrl=/` (`C` on the profile, `pageName`; also on home, indices and market summary): returns a token for ChartGenerator's `jwtToken` param, which isn't needed.
- `/tadawul.eportal.theme.helper/getModuleStatus`: menu "updated" badges only.
- Equity screener (`NJaddcompany`, `NJcheckwatchlist`, `NJdeletecompany`) and `NJmfaauth`, `NJotpSent`, `NJvalidateLogindUser` on several pages: login only.
- Foreign-ownership report and market-reports pages: no data XHRs.
