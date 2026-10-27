# saudiexchange.sa data endpoints

Every endpoint found so far, split into **used** (a tool calls it), **not used** (works, no tool yet) and **failed**. Verified live 2026-10-26 unless a row says otherwise. Nothing needs a login or a JWT.

When a tool starts or stops calling an endpoint, move its row between sections.

## How to call

See `page()` / `xhr()` in `tasi_mcp.py`.
- `curl_cffi` `Session(impersonate="chrome")`. Akamai blocks other TLS fingerprints.
- Send the `XHR` headers from `tasi_mcp.py` plus `Referer` = the page URL. Without them you get 403 / "Access Denied".
- `p0/...` paths are relative to the `<base href>` of their page. GET the page first, then call `base + path`.
- Many JSON replies come back as `text/html`, so parse the body yourself. POST bodies are form-urlencoded.
- `/tadawul...` and `/Resources...` paths are relative to `https://www.saudiexchange.sa`, so no base href is needed. Any page works as referer.

Shorthands used in the tables:
- `P` = `https://www.saudiexchange.sa/wps/portal/saudiexchange`. Add `?locale=en` to every page except the profile.
- `PROFILE` = the company profile URL in `tasi_mcp.py`. The plain `?companySymbol=` URL renders an empty page.
- Profile prefixes: `A` = `p0/IZ7_5A602H80O0VC4060O4GML81G57=CZ6_5A602H80OGF2E0QF9BQDEG10K4=`, `B` = `p0/IZ7_5A602H80O0VC4060O4GML81GV7=CZ6_5A602H80OGF2E0QF9BQDEG10K4=`, `C` = `p0/IZ7_5A602H80O0VC4060O4GML81G55=CZ6_5A602H80OGF2E0QF9BQDEG10K4=`.
- Issuers-trading prefix: `I` = `p0/IZ7_5A602H80OOMQC0604RU6VD10D2=CZ6_5A602H80O8DDC0QFK8HJ0O20K4=` on `P/ourmarkets/main-market-watch/issuers-trading-information`.

## Used

| tool | path | referer page | method + params | returns |
|---|---|---|---|---|
| `list_companies`, `check` | `/tadawul.eportal.theme.helper/ThemeSearchUtilityServlet` | any | GET | every listed security: symbol, names, ISIN |
| `get_quotes`, `get_valuation` | `/tadawul.eportal.theme.helper/TickerServlet` | any | GET | `stockData`: last price, change, volume, turnover, trades (~400 rows incl. funds) |
| `get_quotes` (via `market_watch()`) | `p0/IZ7_IPG41I82KGASC06S67RB9A0080=CZ6_5A602H80O8DDC0QFK8HJ0O2067=NJgetMainNomucMarketDetails=/` | `P/ourmarkets/main-market-watch` | POST `sectorParameter=all`, `tableViewParameter=1` (2 returns the same body), `iswatchListSelected=NO`, `requestLocale=en` | JSON `data`: 273 rows, price/change/volume, open/high/low, bid/ask, 52w. PER/PBR/marketCap/yield are always 0 |
| `get_market` | `/tadawul.eportal.theme.helper/RefreshTradeDetailsServlet` | any | GET | index summaries, 52w/YTD, top gainers/losers, company counts |
| `get_profile`, `get_valuation` | `PROFILE` itself | — | GET | static HTML: `.fundInfo` (shares, capital), `.company_management`, `#unifiedSummaryFinancial`, `#peercompDT` (Tadawul P/E), all other tables. Sub-tab clicks fire no requests |
| `get_statements`, `get_filings` | `A NJstatementsTabData=/` | `PROFILE` | GET `statementType` (0 balance, 1 income, 2 cash flow, 3 ratios, 4 XBRL links, 5 PDF links), `reportType=0`, `requestLocale=en`, `symbol` | HTML tables |
| `get_xbrl` | `/Resources/XBRL_DOCS/...html` (links from `statementType=4`) | any | GET | full XBRL statements as HTML tables |
| `get_corporate_actions` | `B NJgetCorporateAction=/` | `PROFILE` | GET `indexSymbol`, `language=en`, `issueType=Corporate Action` (`Dividends` also returns 200) | JSON capital changes |
| `get_options` | `B NJgetOptionsBySettlementDate=/` | `PROFILE` | GET `settlement_date` (`YYYY-MM-DD` or `All Events`), `symbol`, `language=en` | JSON list whose values are HTML fragments (`calls_contract_code`, ...) |
| `get_foreign_ownership` | `A NJforeginOwnerShip=/` (typo is the site's) | `PROFILE` | GET `symbol` | HTML: maximum and actual foreign ownership (1120: 49.00% / 13.93%) |
| `get_major_shareholders` | `A NJhistoryOfMajorShareHolder=/` | `PROFILE` | GET `symbol`, `history=0` with `fromDate`/`toDate=undefined` for current holders. `history=1` with `fromDate`/`toDate` `YYYY/MM/DD` for history | HTML `#majorShareHoldersTable` |
| `get_chart_series` | `/tadawul.eportal.charts.v2/ChartGenerator?methodType=parsingMethod&chart-type=T&chart-parameter=X&pageName=N` (`format=json` optional) | any | GET, see chart types below | JSON `[{dateTime, indexPrice}]` |
| `get_price_history` | `p0/IZ7_5A602H80O0HTC060SG6UT81216=CZ6_5A602H80O0HTC060SG6UT812E4=NJpopulateCompanyDetails=/` | `P/newsandreports/reports-publications/historical-reports` | POST: see `get_price_history` (`selectedMarket` MAIN or NOMUC, `selectedEntity`, `startDate`/`endDate` `DD-MM-YYYY`, `start`/`length` up to 100) | JSON `data`: daily OHLC, volume, turnover, trades since 2009 |
| `get_announcements` | `p0/IZ7_5A602H80O0HTC060SG6UT81DI1=CZ6_5A602H80O0HTC060SG6UT81D26=NJgetAnnouncementListData=/` | `P/newsandreports/issuer-news/issuer-announcements` | POST: see `get_announcements` (`symbol`, `pageNumberDb`, `pageSize`, ...) | JSON `totalCount`, `announcementList` |
| `get_dividends` | `p0/IZ7_5A602H80OOMQC0604RU6VD10J3=CZ6_5A602H80O8HH70QFKI8IRJ00P3=NJgetDividendsDetails=/` | `P/newsandreports/issuer-financial-calendars/dividends` | POST `symbolorcompany`, `bySymbol` (both = symbol), `start`/`end` `DD-MM-YYYY`, `marketsListId=M`, `period=CUSTOM`, `sector=`, `market=` | JSON `data`: announced, due and distribution dates, amount. Rows start in 2023 even when asked from 2021 (cause unknown) |
| `get_performance` | `p0/IZ7_5A602H80OOMQC0604RU6VD1021=CZ6_5A602H80OGSTA0QFSTBN9F10G0=NJ{getMainMarketPerformanceDetails,getMainMarketPerformanceLosersDetails}=/` | `P/ourmarkets/main-market-watch/main-market-performance` | POST `reportFilter` (`gainers` by value, `gainersPercentage`), `sectorFilter=viewAllmarket`, `timeFrameFilter` (`1 Months`..`5 Years`), `isNonAdjusted=0`, `requestLocale=en` | JSON `data`: begin/end price, change %, high/low, value, volume. In our test gainers returned 21 rows and losers 270 |
| `get_ipos` | `p0/IZ7_5A602H80OOMQC0604RU6VD10F0=CZ6_5A602H80OO5JC0QFMU3NNK3852=NJgetALLListingDataId=/` | `P/listing/ipos` | POST `listedType=ALL`, `market` (blank, `M`, `N`, `S`), `instrument=`, `fromDate`/`toDate` `DD/MM/YYYY` | JSON `ipoData` + `tradableData`, rows hold issuer details |

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
| mutual funds NAV | `p0/IZ7_5A602H80OOMQC0604RU6VD1067=CZ6_5A602H80OOE770QFTO1V1E24R6=NJgetMutualFundsData=/` | POST `isOptionSelected=Yes`, `assetClass`, `fundObjective`, `fundExposure`, `shariahcomplaint`, `fundManager`, `fundCurrency` (all `All`), `requestLocale=en` | JSON `data`: 358 funds, `fundName`, `fundCode`, `fundCategory` (= manager), `fundSubCategory` (Shariah), `fundClass`, `unitPrice` (NAV), `YTDPrecent`, `fundNav` (AUM), `valuationDateModified`. 416 KB, mostly `companyUrl`. Verified 2026-10-27 |
| funds top gainers | `p0/IZ7_5A602H80OOMQC0604RU6VD1093=CZ6_5A602H80O8DDC0QFK8HJ0O20J1=NJgetFundsTopGainersDetails=/` (referer `P/ourmarkets/funds-market-watch`) | GET `requestLocale=en` | JSON `data`: top mutual funds by YTD NAV change. Subset of the row above. Seen in the browser only |

### Main market issuers trading information `P/ourmarkets/main-market-watch/issuers-trading-information`

Prefix `I`. Verified 2026-10-27.

| name | path | method + params | returns |
|---|---|---|---|
| negotiated deals (block trades) | `I NJgetNegotiatedDetails=/` | GET `sector=All`, `company=All` (or symbol), `fromDate`/`toDate` `DD-MM-YYYY`, `requestLocale=en` | JSON `data`: `symbol`, `company`, `tradePrice`, `tradeVolume`, `turnOver`, `strDate`, `strTime`. 1 month = 332 rows, 306 KB (mostly `companyURL`) |
| accumulated losses | `I NJgetAccumulatedLossesDetails=/` | GET `percentage` (`All`, `50-MORE`, `35-50`, `20-35`), `requestLocale=en` | JSON `data`: `symbol`, `company`, `companyStatus` (1 = 20–35%, 2 = 35–50%, 3 = 50%+ of capital). 27 rows, 21 KB |
| suspended / delisted | `I NJgetSuspendedDelistedComp=/` | GET `renderType=onload`, `formType` (`Suspension`, `Delisting`, `Suspension_Funds`, `Delisted_Funds`), `fromDate`/`toDate` `DD-MM-YYYY`, `requestLocale=en` | JSON `data`: `symbol`, `name`, `fromDate`, `toDate`, `newsUrl`. 1 year of suspensions = 220 rows, 225 KB |
| others on the page, never called | `I NJgetListedTradableRightsDetails=/`, `I NJgetOtcTradingData=/`, `I NJgetMainMarketMinimumSizeRequirements=/`, `I NJgetCompaniesBySector=/` | ? | ? |

### General assembly meetings `P/newsandreports/issuer-financial-calendars/general-assembly-meetings`

| name | path | method + params | returns |
|---|---|---|---|
| general assemblies | `p0/IZ7_5A602H80OOMQC0604RU6VD10J2=CZ6_5A602H80O8HH70QFKI8IRJ00T0=NJgetGenAssemblyDetails=/` | POST `searchType=searchData`, `marketsListId=M`, `market=M`, `fromDate`/`toDate` `DD-MM-YYYY` (blank `toDate` = open-ended), `companySymbol` and `bySymbol` (both = symbol or blank), `sector=`, `type=`, `status=` | JSON `data`: `compSymbolCode`, `companyName`, `natureOfGenMetng` (Ordinary / Extraordinary), `status`, `holdingDt`, `holdingTime`, `holdingSite`. Upcoming = 14 rows, 18 KB. Verified 2026-10-27 |

### Derivatives market watch `P/ourmarkets/derivative-market-watch`

| name | path | method + params | returns |
|---|---|---|---|
| futures | `p0/IZ7_5A602H80OOMQC0604RU6VD10H3=CZ6_5A602H80O8DDC0QFK8HJ0O2097=NJgetDerivativesMarketDetails=/` | GET `iswatchListSelected=NO`, `sectorParameter=F`, `requestLocale=en`. Fired by the "Future Contract" tab | JSON `data`: 44 contracts (MT30 index futures + single-stock futures, all expiries): `contractName`, `contractRef`, last, change, bid/ask, `settlementPrice`, `openInterest`, volume, value, open/high/low. 67 KB. Verified 2026-10-27 |

### Sukuk market watch `P/ourmarkets/sukuk-market-watch`

| name | path | method + params | returns |
|---|---|---|---|
| sukuk and bonds | `p0/IZ7_5A602H80OOMQC0604RU6VD1091=CZ6_5A602H80O8DDC0QFK8HJ0O20D6=NJgetSukukMarketDetails=/` | GET `sectorParameter=all`, `iswatchListSelected=NO`, `requestLocale=en` | JSON `data`: 62 listed sukuk/bonds: `symbol`, `issuerName`, `isin`, `bondType` (G gov / corporate), `bondSubType`, `couponRate`, `couponFrequency`, `maturityDateStr`, `outstandingAmount`, `parValue`, plus trade fields. 123 KB. Verified 2026-10-27 |

### Board of directors sessions `P/newsandreports/issuer-financial-calendars/board-of-directors-sessions`

| name | path | method + params | returns |
|---|---|---|---|
| board nomination windows | `p0/IZ7_5A602H80OOMQC0604RU6VD1033=CZ6_5A602H80O8HH70QFKI8IRJ0036=NJgetDirSessionDetails=/` | POST `searchType=searchData`, `marketsListId=M`, `fromDate`/`toDate` `DD-MM-YYYY`, `companySymbol` | JSON `data`: `companySymbol`, `sessionType`, `noofBOD`, `sessionStartDate`/`EndDate`, `appStartDate`/`EndDate`, long `requirement` / `submissionMethod` text. Default 4-year window = 244 rows, 907 KB. Verified 2026-10-27 |

### Corporate actions calendar `P/newsandreports/issuer-financial-calendars/corporate-actions`

| name | path | method + params | returns |
|---|---|---|---|
| corporate actions, all companies | `p0/IZ7_5A602H80OOMQC0604RU6VD10J0=CZ6_5A602H80O8HH70QFKI8IRJ00J3=NJgetCorpDetails=/` | POST `searchType=searchData`, `marketsListId=M`, `companySymbol` (blank = all), `start`/`end` `DD-MM-YYYY` | JSON `data`: issue type, announce and due dates, previous and new capital |

### Company profile (referer `PROFILE`)

| name | path | method + params | returns |
|---|---|---|---|
| statements type 6 | `A NJstatementsTabData=/` | GET `statementType=6` | 149 KB HTML table, fired by the "Financial statements and reports" tab for 8010. Contents unverified |
| board holdings history | `A NJhistoricalBoardMembersWithDates=/` | GET `symbol`, `fromDate`, `toDate` (`YYYY/MM/DD`; the browser sends `//`) | HTML. Huge: 1120 over 2015–2026 = 28.7 MB; 4002 over 1 year = 1.7 MB |

### IPOs `P/listing/ipos`

| name | path | method + params | returns |
|---|---|---|---|
| IPO / rights only | same prefix as `get_ipos`, `NJgetIPOListingDataId=/`, `NJgetTradableRightsDataId=/` | POST as `get_ipos` with `listedType` `IPO` or `TRADABLE-RIGHTS` | JSON `data`. Subsets of the `ALL` call |

### Market data pages

| name | page | path | method + params | returns |
|---|---|---|---|---|
| header bar | any | `/tadawul.eportal.theme.helper/ThemeTASIUtilityServlet` | GET | TASI, MT30, Nomu values and changes, `marketStatusCode`. Seen in browser logs only |
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

## Failed / not useful

- ETF and REIT market watch (`P/ourmarkets/funds-market-watch/Etfsv2/etf-market-watch`, `.../reits`): no data XHR; tables are server-rendered in the page HTML. ETF adds `iNAV`; prices are already in TickerServlet. Parse with `page()` + `tables()` if iNAV is needed.
- Home financial calendar (`p0/IZ7_5A602H80OOMQC0604RU6VD1G21=CZ6_5A602H80OGCJ40QNAM09E92001=N/` on `P/home`, GET `year`, `month`, `requestLocale=en`): works with curl_cffi (2026-10-27), but it is only a month summary of the general-assembly, board-session and dividend calendars. Use those instead.
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

Not checked yet: Nomu market watch, theoretical market watch, holiday calendar, member trading reports.
