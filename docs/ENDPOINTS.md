# saudiexchange.sa data endpoints

Every endpoint found so far, split into **used** (a tool calls it), **not used** (works, no tool yet) and **failed**. This file must stay **stateless**: no "verified" dates or "works as of" notes, because they go stale. Every claim must be **challengeable**: each row carries enough to replay it (page, path, params) and what a correct reply looks like, so anyone can re-run it and see whether it still holds. Nothing needs a login or a JWT.

When a tool starts or stops calling an endpoint, move its row between sections.

## How to call

See `page()` / `xhr()` in `src/saudiexchange.py`.
- `curl_cffi` `Session(impersonate="chrome")`. Akamai blocks other TLS fingerprints.
- Send the `XHR` headers from `src/saudiexchange.py` plus `Referer` = the page URL. Without them you get 403 / "Access Denied".
- `p0/...` paths are relative to the `<base href>` of their page. GET the page first, then call `base + path`.
- Many JSON replies come back as `text/html`, so parse the body yourself. POST bodies are form-urlencoded.
- `/tadawul...` and `/Resources...` paths are relative to `https://www.saudiexchange.sa`, so no base href is needed. Any page works as referer.

Shorthands used in the tables:
- `P` = `https://www.saudiexchange.sa/wps/portal/saudiexchange`. Add `locale=en` to every page, the profile included.
- `PROFILE` = the company profile URL in `src/saudiexchange.py`. The plain `?companySymbol=` URL renders an empty page.
- Profile prefixes: `A` = `p0/IZ7_5A602H80O0VC4060O4GML81G57=CZ6_5A602H80OGF2E0QF9BQDEG10K4=`, `B` = `p0/IZ7_5A602H80O0VC4060O4GML81GV7=CZ6_5A602H80OGF2E0QF9BQDEG10K4=`, `C` = `p0/IZ7_5A602H80O0VC4060O4GML81G55=CZ6_5A602H80OGF2E0QF9BQDEG10K4=`.
- Issuers-trading prefix: `I` = `p0/IZ7_5A602H80OOMQC0604RU6VD10D2=CZ6_5A602H80O8DDC0QFK8HJ0O20K4=` on `P/ourmarkets/main-market-watch/issuers-trading-information`.

## Used

| tool | path | referer page | method + params | returns |
|---|---|---|---|---|
| `list_companies`, `check` | `/tadawul.eportal.theme.helper/ThemeSearchUtilityServlet` | any | GET | every listed security: symbol, names, ISIN |
| `get_quotes`, `get_valuation` | `/tadawul.eportal.theme.helper/TickerServlet` | any | GET | `stockData`: last price, change, volume, turnover, trades (~400 rows incl. funds) |
| `get_quotes`, `list_companies` sector filter (via `market_watch()`) | `p0/IZ7_IPG41I82KGASC06S67RB9A0080=CZ6_5A602H80O8DDC0QFK8HJ0O2067=NJgetMainNomucMarketDetails=/` | `P/ourmarkets/main-market-watch` | POST `sectorParameter=all`, `tableViewParameter=1` (2 returns the same body), `iswatchListSelected=NO`, `requestLocale=en` | JSON `data`: 273 rows, price/change/volume, open/high/low, bid/ask, 52w. PER/PBR/marketCap/yield are always 0 |
| `get_market` | `/tadawul.eportal.theme.helper/RefreshTradeDetailsServlet` | any | GET | JSON sent as text/html. Index summaries, 52w/YTD, `marketBean` (Main breadth: noOfUps, noOfDowns, noOfNoChanges, turnover), top gainers/losers per market, ETF/CEF rows, company counts. ~40k chars; `get_market` filters the top-level keys by `sections` |
| `get_profile`, `get_valuation`, `get_statements` (recent), `get_major_shareholders` (insiders), `get_options` (expiries) | `PROFILE` itself | — | GET | static HTML: `.fundInfo` (shares, capital, subsidiaries table on some companies), `.company_management`, `#unifiedSummaryFinancial`, `#peercompDT` (Tadawul P/E, price, market cap of this company only), `#boardOfDirector` (board and executive holdings, latest day), `#actionSelectSettlementDate`. Sub-tab clicks fire no requests |
| `get_statements`, `get_filings` | `A NJstatementsTabData=/` | `PROFILE` | GET `statementType` (0 balance, 1 income, 2 cash flow, 3 ratios, 4 XBRL links, 5 PDF links), `reportType=0`, `requestLocale=en`, `symbol` | HTML tables |
| `get_xbrl` | `/Resources/XBRL_DOCS/...html` (links from `statementType=4`) | any | GET | full XBRL statements as HTML tables |
| `get_corporate_actions` | `B NJgetCorporateAction=/` | `PROFILE` | GET `indexSymbol`, `language=en`, `issueType=Corporate Action` (`Dividends` also returns 200) | JSON capital changes |
| `get_options` | `B NJgetOptionsBySettlementDate=/` | `PROFILE` | GET `settlement_date` (`YYYY-MM-DD` or `All Events`), `symbol`, `language=en` | JSON list whose values are HTML fragments (`calls_contract_code`, ...) |
| `get_foreign_ownership` | `A NJforeginOwnerShip=/` (typo is the site's) | `PROFILE` | GET `symbol` | HTML: maximum and actual foreign ownership (1120: 49.00% / 13.93%) |
| `get_major_shareholders` | `A NJhistoryOfMajorShareHolder=/` | `PROFILE` | GET `symbol`, `history=0` with `fromDate`/`toDate=undefined` for current holders. `history=1` with `fromDate`/`toDate` `YYYY/MM/DD` for history | HTML `#majorShareHoldersTable` |
| `get_chart_series` | `/tadawul.eportal.charts.v2/ChartGenerator?methodType=parsingMethod&chart-type=T&chart-parameter=X&pageName=N` (`format=json` optional) | any | GET, see chart types below | JSON `[{dateTime, indexPrice}]` |
| `get_price_history` | `p0/IZ7_5A602H80O0HTC060SG6UT81216=CZ6_5A602H80O0HTC060SG6UT812E4=NJpopulateCompanyDetails=/` | `P/newsandreports/reports-publications/historical-reports` | POST: see `get_price_history` (`selectedMarket` MAIN or NOMUC with the bare symbol, or INDICES with `M:`+code such as `M:TASI`, `M:MT30`, `M:TBNI`; bare `TASI` or `MAIN`+`M:TASI` return `data: []`; `selectedEntity`, `startDate`/`endDate` `DD-MM-YYYY`, `start`/`length` up to 100) | JSON `data`: daily OHLC, volume, turnover, trades since 2009. Index rows have no `change` fields; MT30 has `"-"` for volume, turnover and trades. In every row (stocks and indices) `previousClosePrice` is that day's close, not the previous day's; `get_price_history` renames it to `close` |
| `get_announcements` | `p0/IZ7_5A602H80O0HTC060SG6UT81DI1=CZ6_5A602H80O0HTC060SG6UT81D26=NJgetAnnouncementListData=/` | `P/newsandreports/issuer-news/issuer-announcements` | POST: see `get_announcements` (`symbol`, `pageNumberDb`, `pageSize`, ...) | JSON `totalCount`, `announcementList` |
| `get_dividends` | `p0/IZ7_5A602H80OOMQC0604RU6VD10J3=CZ6_5A602H80O8HH70QFKI8IRJ00P3=NJgetDividendsDetails=/` | `P/newsandreports/issuer-financial-calendars/dividends` | POST `symbolorcompany`, `bySymbol` (both = symbol), `start`/`end` `DD-MM-YYYY`, `marketsListId=M`, `period=CUSTOM`, `sector=`, `market=` | JSON `data`: announced, due and distribution dates, amount. Goes back to at least 2010 (4002), whole market 2021 = 213 rows |
| `get_performance` | `p0/IZ7_5A602H80OOMQC0604RU6VD1021=CZ6_5A602H80OGSTA0QFSTBN9F10G0=NJ{getMainMarketPerformanceDetails,getMainMarketPerformanceLosersDetails}=/` | `P/ourmarkets/main-market-watch/main-market-performance` | POST `reportFilter` (`gainers` by value, `gainersPercentage`), `sectorFilter=viewAllmarket`, `timeFrameFilter` (`1 Months`..`5 Years`), `isNonAdjusted=0`, `requestLocale=en` | JSON `data`: begin/end price, change %, high/low, value, volume. In our test gainers returned 21 rows and losers 270 |
| `get_ipos` | `p0/IZ7_5A602H80OOMQC0604RU6VD10F0=CZ6_5A602H80OO5JC0QFMU3NNK3852=NJgetALLListingDataId=/` | `P/listing/ipos` | POST `listedType=ALL`, `market` (blank, `M`, `N`, `S`), `instrument=`, `fromDate`/`toDate` `DD/MM/YYYY` | JSON `ipoData` + `tradableData`, rows hold issuer details |
| `get_block_trades` | `I NJgetNegotiatedDetails=/` | `P/ourmarkets/main-market-watch/issuers-trading-information` | GET `sector=All`, `company` (`All` or symbol), `fromDate`/`toDate` `DD-MM-YYYY`, `requestLocale=en` | JSON `data`: `symbol`, `company`, `tradePrice`, `tradeVolume`, `turnOver`, `strDate`, `strTime`. The last row is a blank-symbol total. 1 month = 332 rows, 306 KB (mostly `companyURL`) |
| `get_risk_flags` | `I NJgetAccumulatedLossesDetails=/` | `P/ourmarkets/main-market-watch/issuers-trading-information` | GET `percentage` (`All`, `50-MORE`, `35-50`, `20-35`), `requestLocale=en` | JSON `data`: `symbol`, `company`, `companyStatus` (1 = 20–35%, 2 = 35–50%, 3 = 50%+ of capital). 27 rows, 21 KB |
| `get_risk_flags` | `I NJgetSuspendedDelistedComp=/` | `P/ourmarkets/main-market-watch/issuers-trading-information` | GET `renderType=onload`, `formType` (`Suspension`, `Delisting`, `Suspension_Funds`, `Delisted_Funds`), `fromDate`/`toDate` `DD-MM-YYYY`, `requestLocale=en` | JSON `data`: `symbol`, `name`, `fromDate`, `toDate`, `newsUrl`. 1 year of suspensions = 220 rows, 225 KB |
| `get_risk_flags` | `I NJgetMainMarketMinimumSizeRequirements=/` | `P/ourmarkets/main-market-watch/issuers-trading-information` | GET `requestLocale=en` | JSON `data`: 138 rows, each `col1`..`col4` = tier 1..4 `{symbolCode, symbol, tierValue, isNewlyListed}` (`tierValue` 0 = empty cell). Tier by last-6-month ADTV: 1 ≥ SAR 50M (min deal SAR 5M), 2 = 5–50M (3M), 3 = 1–5M (1M), 4 < 1M (300K). 229 KB |
| `get_announcement` | `P/newsandreports/issuer-news/issuer-announcements/issuer-announcements-details/?anId=ID&anCat=1&locale=en` (`cs=SYMBOL` is optional) | — | GET with `fetch()` | Server-rendered, 609 KB page. Body in `.article_body`: for results, tables of current quarter vs year-ago quarter vs previous quarter, year to date, a units line ("All figures are in (Billions)..."), management's reasons, attachment links. An unknown `anId` has no `.article_body` |
| `screen_valuations`, `get_valuation` (`daily_report`) | `/Resources/Reports-v2/DailyFinancialIndicators_en.html` | — | GET with `fetch()` (no XHR headers) | 1 table, `<th>` straight under `<thead>`. Stock rows, then a sector subtotal after each sector's stocks (Symbol and Company merged, so 11 cells), then `Market`. Close, issued shares (mn), net income, equity, market cap (SAR mn), EPS, P/E (`M` = loss-making), book value, P/B. P/E equals `get_valuation`'s. Date `YYYY/MM/DD` in the text. 285 KB |
| `get_short_interest` | `/Resources/Reports-v2/NetShortPositions_en.html`, `.../SBLReport_en.html` | — | GET with `fetch()` | Net short % of outstanding shares and of free float, ratio to 60-day average volume (174 rows, 85 KB); issued shares, lent quantity, % lent (271 rows, 165 KB). "Last Update Date : YYYY-MM-DD" in the text |

ChartGenerator `chart-type` / `chart-parameter` values (`pageName` = what the page sends, e.g. `CompanyProfileMainMarket`, `MainMarketWatch`, `IndicesPerformance`, `MarketStatusHomeGraph`. Whether pageName is required was not checked). `get_chart_series` uses the first two and the TASI ones:
- `SQL_CI_CV_COM` / symbol: daily closes for that stock since 2001.
- `SQL_CI_DV` / symbol: today's 1-minute prices for that stock.
- `SQL_T_IC_ALL_PER` / `tasi`: TASI daily closes since 1994.
- `SQL_T_IC_ALL_COM` / sector index (e.g. `tbni`): daily closes since 2016.
- `SQL_T_ID` / sector index: today's 1-minute prices for that index.
- `SQL_MI_MSPV` / `tasi` or `mt30`, `SQL_MI_MSPV_SME` / `nomuc`, `SQL_MI_MSPV_SUKUK` / `tsbi`: today's 1-minute index prices.

## Not used

Grouped by page. The referer is the page in the heading.

### Mutual funds `P/ourmarkets/funds-market-watch/mutual-funds`

| name | path | method + params | returns |
|---|---|---|---|
| mutual funds NAV | `p0/IZ7_5A602H80OOMQC0604RU6VD1067=CZ6_5A602H80OOE770QFTO1V1E24R6=NJgetMutualFundsData=/` | POST `isOptionSelected=Yes`, `assetClass`, `fundObjective`, `fundExposure`, `shariahcomplaint`, `fundManager`, `fundCurrency` (all `All`), `requestLocale=en` | JSON `data`: 358 funds, `fundName`, `fundCode`, `fundCategory` (= manager), `fundSubCategory` (Shariah), `fundClass`, `unitPrice` (NAV), `YTDPrecent`, `fundNav` (AUM), `valuationDateModified`. 416 KB, mostly `companyUrl`. |
| funds top gainers | `p0/IZ7_5A602H80OOMQC0604RU6VD1093=CZ6_5A602H80O8DDC0QFK8HJ0O20J1=NJgetFundsTopGainersDetails=/` (referer `P/ourmarkets/funds-market-watch`) | GET `requestLocale=en` | JSON `data`: top mutual funds by YTD NAV change. Subset of the row above. Seen in the browser only |

### Main market issuers trading information `P/ourmarkets/main-market-watch/issuers-trading-information`

Prefix `I`.

| name | path | method + params | returns |
|---|---|---|---|
| listed tradable rights | `I NJgetListedTradableRightsDetails=/` | GET `requestLocale=en` | JSON `data`: rights trading now: `acrynomName`, last price, change, open/high/low, trades, volume. `[]` (11 B) when no rights are trading |
| companies by sector | `I NJgetCompaniesBySector=/` | GET `format=json`, `sector` = numeric id from `#sectorsList` (31 Energy, 32, ...; `TBNI` → 500) | `[{symbol, longName, shortName, Acronym}]`. 631 B. Redundant with the issuer directory |
| OTC trading | `I NJgetOtcTradingData=/` | GET `requestLocale=en` | JSON `data`: 272 rows, `symbol`, `companyName`, `lastTradeValue/Volume/Price/Date`. Last trades are 2022–2024, so stale. 224 KB |

### General assembly meetings `P/newsandreports/issuer-financial-calendars/general-assembly-meetings`

| name | path | method + params | returns |
|---|---|---|---|
| general assemblies | `p0/IZ7_5A602H80OOMQC0604RU6VD10J2=CZ6_5A602H80O8HH70QFKI8IRJ00T0=NJgetGenAssemblyDetails=/` | POST `searchType=searchData`, `marketsListId=M`, `market=M`, `fromDate`/`toDate` `DD-MM-YYYY` (blank `toDate` = open-ended), `companySymbol` and `bySymbol` (both = symbol or blank), `sector=`, `type=`, `status=` | JSON `data`: `compSymbolCode`, `companyName`, `natureOfGenMetng` (Ordinary / Extraordinary), `status`, `holdingDt`, `holdingTime`, `holdingSite`. Upcoming = 14 rows, 18 KB. |

### Derivatives market watch `P/ourmarkets/derivative-market-watch`

| name | path | method + params | returns |
|---|---|---|---|
| futures | `p0/IZ7_5A602H80OOMQC0604RU6VD10H3=CZ6_5A602H80O8DDC0QFK8HJ0O2097=NJgetDerivativesMarketDetails=/` | GET `iswatchListSelected=NO`, `sectorParameter=F`, `requestLocale=en`. Fired by the "Future Contract" tab | JSON `data`: 44 contracts (MT30 index futures + single-stock futures, all expiries): `contractName`, `contractRef`, last, change, bid/ask, `settlementPrice`, `openInterest`, volume, value, open/high/low. 67 KB. |

### Sukuk market watch `P/ourmarkets/sukuk-market-watch`

| name | path | method + params | returns |
|---|---|---|---|
| sukuk and bonds | `p0/IZ7_5A602H80OOMQC0604RU6VD1091=CZ6_5A602H80O8DDC0QFK8HJ0O20D6=NJgetSukukMarketDetails=/` | GET `sectorParameter=all`, `iswatchListSelected=NO`, `requestLocale=en` | JSON `data`: 62 listed sukuk/bonds: `symbol`, `issuerName`, `isin`, `bondType` (G gov / corporate), `bondSubType`, `couponRate`, `couponFrequency`, `maturityDateStr`, `outstandingAmount`, `parValue`, plus trade fields. 123 KB. |

### Board of directors sessions `P/newsandreports/issuer-financial-calendars/board-of-directors-sessions`

| name | path | method + params | returns |
|---|---|---|---|
| board nomination windows | `p0/IZ7_5A602H80OOMQC0604RU6VD1033=CZ6_5A602H80O8HH70QFKI8IRJ0036=NJgetDirSessionDetails=/` | POST `searchType=searchData`, `marketsListId=M`, `fromDate`/`toDate` `DD-MM-YYYY`, `companySymbol` | JSON `data`: `companySymbol`, `sessionType`, `noofBOD`, `sessionStartDate`/`EndDate`, `appStartDate`/`EndDate`, long `requirement` / `submissionMethod` text. Default 4-year window = 244 rows, 907 KB. |

### Corporate actions calendar `P/newsandreports/issuer-financial-calendars/corporate-actions`

| name | path | method + params | returns |
|---|---|---|---|
| corporate actions, all companies | `p0/IZ7_5A602H80OOMQC0604RU6VD10J0=CZ6_5A602H80O8HH70QFKI8IRJ00J3=NJgetCorpDetails=/` | POST `searchType=searchData`, `marketsListId=M`, `companySymbol` (blank = all), `start`/`end` `DD-MM-YYYY` | JSON `data`: issue type, announce and due dates, previous and new capital |

### Company profile (referer `PROFILE`)

| name | path | method + params | returns |
|---|---|---|---|
| statements type 6 | `A NJstatementsTabData=/` | GET `statementType=6` | 133–149 KB HTML table, fired by the "Financial statements and reports" tab. Types 4 and 5 merged: PDF, XBRL `.html`/`.xls`, board report and ESG report links. For 2222 its 59 links are exactly the union of types 4 and 5, so nothing new. |
| board holdings history | `A NJhistoricalBoardMembersWithDates=/` | GET `symbol`, `fromDate`, `toDate` (`YYYY/MM/DD`; the browser sends `//`) | HTML. Huge: 1120 over 2015–2026 = 28.7 MB; 4002 over 1 year = 1.7 MB |

### IPOs `P/listing/ipos`

| name | path | method + params | returns |
|---|---|---|---|
| IPO / rights only | same prefix as `get_ipos`, `NJgetIPOListingDataId=/`, `NJgetTradableRightsDataId=/` | POST as `get_ipos` with `listedType` `IPO` or `TRADABLE-RIGHTS` | JSON `data`. Subsets of the `ALL` call |

### Market data pages

| name | page | path | method + params | returns |
|---|---|---|---|---|
| header bar | any | `/tadawul.eportal.theme.helper/ThemeTASIUtilityServlet` | GET (`servlet()` works) | TASI, MT30, Nomu, sukuk values and changes; `marketStatusCode`, `smeMarketStatusCode`, `sukukmarketStatusCode`. The page JS only maps codes to colours: 0/3/4 red (closed), 1/6/9 orange, 10 yellow, anything else green (open). There are no text labels. 3 at 07:44 before the open. |
| home graphs | `P/home` | `p0/IZ7_5A602H80OOF35068G2P8CG10H6=CZ6_5A602H80OGCJ40QNAM09E92001=N/` | GET | JSON `main_/parallel_/sukuk_market_graph`, each a JSON *string* of today's 1-minute `{dateTime, indexPrice}` |
| TASI index | `P/ourmarkets/main-market-watch/marketsummary` | `p0/IZ7_IPG41I82KGASC06S67RB9A0001=CZ6_IPG41I82KGASC06S67RB9A0000=NJgetMarketIndexUrl=/` | GET | TASI `indexPrice`, `netChange`, `percentChange` |
| top movers | `P/ourmarkets/main-market-watch/marketsummary` | `p0/IZ7_IPG41I82KGASC06S67RB9A00G2=CZ6_IPG41I82KGASC06S67RB9A0000=NJ{getTopGainersDetails,getTopLosersDetails,getMoversByVolumeDetails,getMoversByValueDetails}=/` | GET `requestLocale=en` | JSON `data`: price, change and 5-day performance per stock |
| index price box | `P/ourmarkets/main-market-watch/indices-performance` | `p0/IZ7_5A602H80O0VC4060O4GML81G84=CZ6_5A602H80O0QU80QFSFB58028C7=NJupdatePriceBoxUrl=/` | GET `currentSector=TASI` (only TASI was tested) | JSON `tasiTodaysSummaryBean`: open, high, low, last, previous close, volume, turnover, trades |

### Issuer directory `P/trading/participants-directory/issuer-directory`

Prefix `p0/IZ7_5A602H80OOMQC0604RU6VD10F2=CZ6_5A602H80OGSTA0QFSTBN9F10I5=`.

| name | path | method + params | returns |
|---|---|---|---|
| companies | `NJgetCompanyListByMarknetAndSectors=/` | POST `marketType=M`, `sector=All`, `symbol=`, `letter=` | JSON `data`: 273 rows with symbol, names, `isinCode`, profile URL |
| sectors | `NJgetSectorsByMarketId=/` | POST `format=json`, `marketType=M` | `[{pk_rf_sector, name, symbol}]`: sector to index symbol (e.g. 31 Energy → TENI) |
| dividend-page sectors | `p0/IZ7_5A602H80OOMQC0604RU6VD10J3=CZ6_5A602H80O8HH70QFKI8IRJ00P3=NJgetSectors1=/` (referer: dividends page) | GET `marketsListId=M` | `[{id, name}]` |

### Market reports: static files `/Resources/Reports-v2/<name>_en.html`

Listed on `P/newsandreports/reports-publications/market-reports` with a "Last Updated" date for each report. The page fires no data XHR. Plain `fetch()` works (no XHR headers needed). Each file is one HTML page; parse with `tables()`. `<name>-HTML-en.zip` holds the same HTML. Nomu variants: `Sme` / `_SME` / `_sme` / `_NOMU` suffixes.

| name | file | returns |
|---|---|---|
| substantial shareholders | `MajorStakeHoldersPage` (`_SME`) | 735 rows, market-wide: company (header row), holder, % today, % previous day, change, % managed by an authorised person. Daily. 245–258 KB |
| treasury shares (buy-backs) | `ShareBuyback` (`_sme`) | 254 rows: `Symbol`, `Company`, shares and % held for employee plans, for other buy-backs, total. Monthly (30-09-2026). 202 KB |
| periodic market reports | `DetailedDaily`, `Weekly`, `Monthly`, `Quarterly`, `Yearly` (+`Sme`, `_Derivatives`) | Market summary, top 5 gainers/losers/most active, per-company list (close, WTD/MTD/QTD/YTD %, volume, value, trades, market cap). Monthly and later add turnover by industry group. Yearly adds 10-year and by-month statistics. 216–262 KB. Nothing on investor type or nationality |
| funds and fixed income | `ETF_Monthly/Quarterly/Annually`, `MutualFundsMonthly/SemiAnnual/Annual`, `CEF_Monthly/Quarterly`, `FI_Monthly/Quarterly/Annually` | Not opened |

### Foreign ownership, all stocks

| name | page | path | method + params | returns |
|---|---|---|---|---|
| foreign headroom | `P/newsandreports/reports-publications/market-reports/foreign-headroom-main` | `p0/IZ7_5A602H80O8SP006ONUTEIO0021=CZ6_5A602H80O80CC06GULC7F720G5=NJgetForeignHeadRoomDetails=/` | POST, empty body | JSON `data`: 253 rows: `symbol`, `sectorName`, `companyNameEn`, `allowedForeignOwnershipForTotalOwnerShipAsString`, `actualForeignOwnershipForTotalOwnerShipAsString`, `foreignOwnershipRoom`, `lastUpdateDate`. 277 KB. The `-nomuc` page uses another portlet, not replayed. |
| foreign ownership table | `P/newsandreports/reports-publications/foreign-ownership` | page HTML | GET | One server-rendered table, 413 rows: symbol, company, max limit, actual, foreign strategic investors. "Last updated" date in the page text. 758 KB page, no XHR. |

### Issuer announcements `P/newsandreports/issuer-news/issuer-announcements`

| name | path | method + params | returns |
|---|---|---|---|
| announcement types | `p0/IZ7_5A602H80O0HTC060SG6UT81DI1=CZ6_5A602H80O0HTC060SG6UT81D26=NJgetFormTypeList=/` | GET `format=json`, `productType` (`MAIN_MARKET`, `NOMU_MARKET`, `REITs`, `ETFs`, `CEFs`, `MF`) | `[{newsType, nameEN, nameAr}]`, 66 types for the main market, 14.7 KB. `newsType` is the `annoucmentType` value for `get_announcements`: `1_-1` all, `1_17`/`1_18` annual/interim results, `1_19`/`1_20` banks, `1_21`/`1_22` insurers, `1_95` Nomu interim, `1_23` board changes, `1_46` bonus-share recommendation. For 2222, `1_18` gives 20 rows against 137 for all. |

### Other market watches

| name | page | path | method + params | returns |
|---|---|---|---|---|
| theoretical opening (pre-open auction) | `P/ourmarkets/main-market-watch/theoritical-market-watch-today` (site spelling) | `p0/IZ7_5A602H80OOMQC0604RU6VD1053=CZ6_5A602H80OOE770QFTO1V1E2OK7=NJgetTheoreticalOpeningDetails=/` | POST `sector=All`, `requestLocale=en` | JSON `data`: 273 rows: `symbol`, `sectorName`, `prev_close`, `top` (theoretical opening price), `tov` (theoretical opening volume). All zero outside the auction (checked at 07:50, closed). 295 KB. |
| Nomu market watch | `P/ourmarkets/nomuc-market-watch` | `p0/IZ7_IPG41I82KGASC06S67RB9A0041=CZ6_5A602H80O8DDC0QFK8HJ0O2010=NJgetMainNomucMarketDetails=/` | **GET** `sectorParameter=all`, `tableViewParameter=1`, `iswatchListSelected=NO`, `requestLocale=en` | JSON `data`: 123 Nomu rows with the same fields as the main market watch (open/high/low, bid/ask, 52w). PER/PBR/yield/marketCap all 0. `get_quotes` returns `None` open/high/low for Nomu today; this would fill them. 272 KB. |

### Calendars and trading hours

| name | page | returns |
|---|---|---|
| exchange holidays | `P/about-saudi-exchange/exchange-media-centre/saudi-exchange-holiday-calendar` | Server-rendered table, 55 rows up to 2029: date range, text (last trading day, resume day). 586 KB page, no XHR. |
| trading hours | `P/rules-guidance/capital-market-overview/trading-cycle-and-times` | Static table: opening auction 9:30–10:00, continuous 10:00–15:00, closing auction 15:00–15:10, trade at last 15:10–15:20, negotiated deals until 16:00 |

### Member (broker) trading reports `P/newsandreports/reports-publications/member-trading-reports`

Monthly PDFs, `/wps/wcm/connect/<uuid>/<n>.+Members+Trading++Activity+-+<Month>+<YYYY>+EN.pdf`. The UUID means the URL can't be guessed, so scrape the page's links. Latest: August 2026, 475 KB, text-extractable: member, value, value %, rank, volume, volume %, rank. Parsing needs a PDF library (none installed).

## Failed / not useful

- ETF and REIT market watch (`P/ourmarkets/funds-market-watch/Etfsv2/etf-market-watch`, `.../reits`): no data XHR; tables are server-rendered in the page HTML. ETF adds `iNAV`; prices are already in TickerServlet. Parse with `page()` + `tables()` if iNAV is needed.
- Home financial calendar (`p0/IZ7_5A602H80OOMQC0604RU6VD1G21=CZ6_5A602H80OGCJ40QNAM09E92001=N/` on `P/home`, GET `year`, `month`, `requestLocale=en`): works with curl_cffi, but it is only a month summary of the general-assembly, board-session and dividend calendars. Use those instead.
- `A NJpeerComparison=/` (`companySymbol`, `peerID`): returns "Request Rejected" or 500. Read the P/E from `#peercompDT` on the profile instead.
- `B NJgetAllEvents=/`: 500.
- `/wps/contenthandler/wcmrest/query/...`: `UNAUTHORISED_ACCESS`.
- `/Charts/ChartGenerator` (the old path): "Request Rejected". Use `/tadawul.eportal.charts.v2/`.
- `NJgetIndexDataURL=/` (`C` on the profile, `indexSymbol`; also on the indices page): `indexLastTradedPrice` is unreliable (gave -269.25, the change, for TBNI).
- `C NJupdatePriceBoxUrl=/` on the profile (`symbol`): only change and %. Redundant with TickerServlet.
- `NJgetJWTTokenUrl=/` (`C` on the profile, `pageName`; also on home, indices and market summary): returns a token for ChartGenerator's `jwtToken` param, which isn't needed.
- `/tadawul.eportal.theme.helper/getModuleStatus`: menu "updated" badges only.
- Equity screener (`NJaddcompany`, `NJcheckwatchlist`, `NJdeletecompany`) and `NJmfaauth`, `NJotpSent`, `NJvalidateLogindUser` on several pages: login only.
- Foreign-ownership report and market-reports pages: no data XHRs. Their data is in the page HTML or in static files (see above).
- Trading flows by nationality and investor type: "Weekly/Monthly Trading and Ownership By Nationality Report" PDFs (weekly since 2016) are listed only on `P/newsandreports/reports-publications/annual-reports`. That page is 1.6 MB HTML with `li.reportTypeMnthYear` items, id `YYYY_MM_SA-TradingByNationality`, and filters client-side with no XHR. PDF URLs are `/wps/wcm/connect/<uuid>/...pdf`, so they must be scraped. curl_cffi fetches them (latest 22-10-2026, 1.85 MB, 10 pages, a PowerPoint export). Every figure is drawn as an image mask, and only the glossary page has text, so reading it needs OCR. The weekly/monthly HTML market reports have no investor-type data.
- Index weights, free float and index P/E or yield: the indices-performance "Key Constituents" tab lists only symbol, name and sector for TASI and the sector indices. MT30 lists none and points to the MSCI factsheet PDF (`/wps/wcm/connect/0a11743b-.../msci-TADAWUL30-TASI-en+%28SAR%29.pdf`), which is stale (as of 31 Mar 2024). The `P/rules-guidance/indices/*` pages are prose plus a methodology PDF.
- Earnings calendar (expected results dates): none. `P/newsandreports/issuer-financial-calendars` has only dividends, general assemblies, board sessions and corporate actions.

Not checked yet: Nomu foreign headroom portlet, Nomu/derivatives/funds/sukuk issuers-trading-information pages, unlisted sukuk market watch, contents of the statistical-report and debt-market PDFs.
