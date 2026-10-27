"""Saudi Exchange (Tadawul) MCP server. Scrapes saudiexchange.sa on demand, over stdio."""
import functools
import re
import threading
import time
from datetime import date, timedelta
from typing import Literal
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests
from mcp.server import MCPServer

ROOT = "https://www.saudiexchange.sa"
PORTAL = ROOT + "/wps/portal/saudiexchange"
HOME = PORTAL + "/home"
# The plain ?companySymbol= URL renders an empty template; only this encoded one works.
PROFILE = (PORTAL + "/hidden/company-profile-main/!ut/p/z1/04_Sj9CPykssy0xPLMnMz0vMAfIjo8ziTR3NDIw8LAz83d2MXA0C3SydAl1c3Q0"
           "NvE30I4EKzBEKDMKcTQzMDPxN3H19LAzdTU31w8syU8v1wwkpK8hOMgUA-oskdg!!/?companySymbol={}")
HISTORY = PORTAL + "/newsandreports/reports-publications/historical-reports?locale=en"
ANNOUNCE = PORTAL + "/newsandreports/issuer-news/issuer-announcements?locale=en"
WATCH = PORTAL + "/ourmarkets/main-market-watch?locale=en"
PERFORMANCE = PORTAL + "/ourmarkets/main-market-watch/main-market-performance?locale=en"
DIVIDEND_CALENDAR = PORTAL + "/newsandreports/issuer-financial-calendars/dividends?locale=en"
IPOS = PORTAL + "/listing/ipos?locale=en"
CHART = ROOT + "/tadawul.eportal.charts.v2/ChartGenerator"
STATEMENTS = "p0/IZ7_5A602H80O0VC4060O4GML81G57=CZ6_5A602H80OGF2E0QF9BQDEG10K4=NJstatementsTabData=/"
CORP_ACTIONS = "p0/IZ7_5A602H80O0VC4060O4GML81GV7=CZ6_5A602H80OGF2E0QF9BQDEG10K4=NJgetCorporateAction=/"
PRICES = "p0/IZ7_5A602H80O0HTC060SG6UT81216=CZ6_5A602H80O0HTC060SG6UT812E4=NJpopulateCompanyDetails=/"
ANNOUNCEMENTS = "p0/IZ7_5A602H80O0HTC060SG6UT81DI1=CZ6_5A602H80O0HTC060SG6UT81D26=NJgetAnnouncementListData=/"
FOREIGN = "p0/IZ7_5A602H80O0VC4060O4GML81G57=CZ6_5A602H80OGF2E0QF9BQDEG10K4=NJforeginOwnerShip=/"
HOLDERS = "p0/IZ7_5A602H80O0VC4060O4GML81G57=CZ6_5A602H80OGF2E0QF9BQDEG10K4=NJhistoryOfMajorShareHolder=/"
OPTIONS = "p0/IZ7_5A602H80O0VC4060O4GML81GV7=CZ6_5A602H80OGF2E0QF9BQDEG10K4=NJgetOptionsBySettlementDate=/"
WATCH_DATA = "p0/IZ7_IPG41I82KGASC06S67RB9A0080=CZ6_5A602H80O8DDC0QFK8HJ0O2067=NJgetMainNomucMarketDetails=/"
GAINERS = "p0/IZ7_5A602H80OOMQC0604RU6VD1021=CZ6_5A602H80OGSTA0QFSTBN9F10G0=NJgetMainMarketPerformanceDetails=/"
LOSERS = "p0/IZ7_5A602H80OOMQC0604RU6VD1021=CZ6_5A602H80OGSTA0QFSTBN9F10G0=NJgetMainMarketPerformanceLosersDetails=/"
DIVIDENDS = "p0/IZ7_5A602H80OOMQC0604RU6VD10J3=CZ6_5A602H80O8HH70QFKI8IRJ00P3=NJgetDividendsDetails=/"
LISTINGS = "p0/IZ7_5A602H80OOMQC0604RU6VD10F0=CZ6_5A602H80OO5JC0QFMU3NNK3852=NJgetALLListingDataId=/"

# Akamai blocks non-browser TLS fingerprints, and the JSON endpoints 403 without XHR-style headers.
S = requests.Session(impersonate="chrome")
XHR = {"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest",
       "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"}
LOCK = threading.Lock()  # one shared session; tool calls may run in worker threads
_cache = {}


def cached(ttl):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*args):
            hit = _cache.get((fn.__name__, args))
            if hit and time.time() - hit[0] < ttl:
                return hit[1]
            value = fn(*args)
            _cache[(fn.__name__, args)] = (time.time(), value)
            return value
        return wrap
    return deco


def request(method, url, **kw):
    with LOCK:
        r = S.request(method, url, timeout=40, **kw)
    r.raise_for_status()
    return r


@cached(600)
def page(url):
    """Fetch a portal page and its <base href>; portlet endpoint URLs are relative to it."""
    html = request("GET", url).text
    m = re.search(r'<base href="([^"]+)"', html)
    if not m:
        raise RuntimeError(f"No <base href> on {url}; the site layout may have changed")
    return html, m.group(1)


def xhr(url, referer, method="GET", **kw):
    return request(method, url, headers={**XHR, "Referer": referer}, **kw)


@cached(3600)
def fetch(url):
    return request("GET", url).text


@cached(60)
def servlet(name):
    return xhr(f"{ROOT}/tadawul.eportal.theme.helper/{name}", HOME).json()


def companies():
    return servlet("ThemeSearchUtilityServlet")


def check(symbol):
    if symbol not in {c["symbol"] for c in companies()}:
        raise ValueError(f"Unknown symbol {symbol!r}; use list_companies to find it")


def day(s, default):
    return date.fromisoformat(s) if s else default


def clean(s):
    # The site draws the riyal sign as '^' in a custom font.
    return " ".join(re.sub(r"<[^>]+>", " ", s).replace("^", "SAR").split())


def rows(table):
    return [[clean(c.get_text(" ")) for c in tr.find_all(["th", "td"])] for tr in table.find_all("tr")]


def tables(soup):
    """Every <table> as rows of cell text."""
    return [rows(t) for t in soup.find_all("table")]


UNITS = {"Actuals": 1, "Thousands": 1_000, "Millions": 1_000_000}


def profits(table):
    """{period end: net profit attributable to shareholders, in SAR} from a profile summary table."""
    by_label = {r[0]: r[1:] for r in table}
    cols = zip(table[0][1:], by_label["Net Profit (Loss) Attributable to Shareholders of the Issuer"],
               by_label["All Figures in"])
    return {date.fromisoformat(d): float(p.replace(",", "")) * UNITS[u] for d, p, u in cols if d and p not in ("", "-")}


# @deprecated: get_valuation now returns Tadawul's own P/E (matched this within 1%). Kept for reference.
def ttm_profit(annual, quarterly):
    """Last full year + this year's quarters - the same quarters a year earlier, or None if one is missing.
    Summing the last 4 listed quarters is wrong: the site never lists Q4 separately (it is inside the annual)."""
    fy_end = max(annual)
    later = [d for d in quarterly if d > fy_end]
    prior = [d.replace(year=d.year - 1) for d in later]
    if any(d not in quarterly for d in prior):
        return None
    return annual[fy_end] + sum(quarterly[d] for d in later) - sum(quarterly[d] for d in prior)


# @deprecated: get_valuation now returns Tadawul's own P/E (matched this within 1%). Kept for reference.
XBRL_PROFIT = "Profit (loss), attributable to equity holders of parent company"


# @deprecated: get_valuation now returns Tadawul's own P/E (matched this within 1%). Kept for reference.
def xbrl_quarter_profits(sections):
    """{quarter end: net profit attributable to shareholders, in SAR} for every 3-month column of an XBRL report."""
    info = {r[0]: r[1] for title, rs in sections.items() if "Filing information" in title for r in rs}
    if info.get("Description of presentation currency") != "Saudi Arabia, Riyals":
        return {}
    scale = UNITS[info["Level of rounding used in financial statements"]]
    out = {}
    for title, rs in sections.items():
        by_label = {r[0]: r[1:] for r in rs}
        if "Statement of income" not in title or XBRL_PROFIT not in by_label:
            continue
        for start, end, profit in zip(by_label["Start Date"], by_label["End Date"], by_label[XBRL_PROFIT]):
            if not (re.fullmatch(r"\d{4}-\d\d-\d\d", start) and re.fullmatch(r"\d{4}-\d\d-\d\d", end) and profit):
                continue
            start, end = date.fromisoformat(start), date.fromisoformat(end)
            if 85 <= (end - start).days <= 95:
                out[end] = float(profit.replace(",", "")) * scale
    return out


# @deprecated: get_valuation now returns Tadawul's own P/E (matched this within 1%). Kept for reference.
def xbrl_profits(symbol, needed):
    """Quarter profits the profile no longer lists, read from the XBRL filings published after each quarter."""
    reports = sorted((f for f in get_filings(symbol, "xbrl") if f["period"] != "Annual"), key=lambda f: f["date"])
    found = {}
    for d in needed:
        for f in [f for f in reports if f["date"] > d.isoformat()][:3]:
            url = next(u for u in f["urls"] if u.endswith(".html"))
            found.update(xbrl_quarter_profits(xbrl_sections(BeautifulSoup(fetch(url), "html.parser"))))
            if d in found:
                break
    return found


def xbrl_sections(soup):
    """Group an XBRL report's tables under their '[300200] Statement of ...' title tables, minus empty rows."""
    sections, title = {}, None
    for t in tables(soup):
        if len(t) == 1 and len(t[0]) == 1:
            title = t[0][0] or title
        elif title:
            sections.setdefault(title, []).extend(r for r in t if any(r[1:]))
    return sections


def filings(soup):
    """Flatten the filings grid (rows = period, columns = year, cells = date + links)."""
    out = []
    for t in soup.find_all("table"):
        rows = t.find_all("tr")
        years = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])][1:]  # first cell is a dropdown
        for tr in rows[1:]:
            label, *cells = tr.find_all(["th", "td"])
            for year, c in zip(years, cells):
                urls = [urljoin(ROOT, a["href"]) for a in c.find_all("a", href=True)]
                if urls:
                    out.append({"period": label.get_text(strip=True), "year": year,
                                "date": c.get_text(" ", strip=True), "urls": urls})
    return out


def statements_html(symbol, statement_type):
    url = PROFILE.format(symbol)
    _, base = page(url)
    return xhr(base + STATEMENTS, url, params={"statementType": statement_type, "reportType": 0,
                                              "requestLocale": "en", "symbol": symbol}).text


mcp = MCPServer("tasi", instructions=(
    "Saudi Exchange (Tadawul) data scraped live from saudiexchange.sa. Symbols are 4-digit codes, e.g. 2222 "
    "(Saudi Aramco), 4002 (Mouwasat). Financial table figures are SAR thousands unless the table says otherwise. "
    "For P/E and market cap use get_valuation, not price / the site's EPS, which is wrong after bonus issues. "
    "For debt, loans and finance costs read the XBRL filings with get_xbrl."))


@mcp.tool()
def list_companies(query: str = "", limit: int = 50) -> list[dict]:
    """Find listed securities (stocks, funds, sukuk) by symbol, English or Arabic name, or ISIN."""
    q = query.lower()
    return [c for c in companies() if q in " ".join(map(str, c.values())).lower()][:limit]


@cached(60)
def market_watch():
    """{symbol: open, high, low, previous close, best bid/ask with sizes, 52-week range, sector} for the Main market."""
    _, base = page(WATCH)
    form = {"sectorParameter": "all", "tableViewParameter": "1", "iswatchListSelected": "NO", "requestLocale": "en"}
    keys = ("sectorName", "highPrice", "lowPrice", "previousClosePrice", "bidPrice", "bidQuantity", "askPrice",
            "askQuantity", "high52WeekPrice", "low52WeekPrice")
    return {str(r["companyRef"]): {k: r[k] for k in keys} | {"todaysOpen": r["todayOpen"]}
            for r in xhr(base + WATCH_DATA, WATCH, method="POST", data=form).json()["data"]}


@mcp.tool()
def get_quotes(symbols: list[str] | None = None) -> list[dict]:
    """Latest price, change, volume, turnover and trade count for Main market and Nomu stocks.
    Main market rows also have open, high, low, previous close, best bid/ask with sizes, 52-week high/low
    and sector; for Nomu these stay empty. Omit symbols for all ~400."""
    try:
        watch = market_watch()
    except Exception:  # extras only; a market-watch outage must not take down quotes and get_valuation
        watch = {}
    return [r | watch.get(r["pk_rf_company"], {}) for r in servlet("TickerServlet")["stockData"]
            if not symbols or r["pk_rf_company"] in symbols]


@mcp.tool()
def get_market() -> dict:
    """Market summary: TASI, MT30, Nomu, sukuk, REIT and ETF indices, 52-week and YTD figures,
    top gainers and losers, and listed company counts."""
    return servlet("RefreshTradeDetailsServlet")


def profile_soup(symbol):
    return BeautifulSoup(page(PROFILE.format(symbol))[0], "html.parser")


@mcp.tool()
def get_profile(symbol: str) -> dict:
    """Company profile. info: overview, history, capital, issued shares, auditor, board and executives.
    tables: recent dividends; last 3 years and last 4 quarters of balance sheet, income and cash flow
    (incl. EPS); older 2019-2022 balance sheets; insider holdings; subsidiaries; peer comparison.
    EPS is as published: not restated after bonus issues, and some quarters show year-to-date EPS."""
    check(symbol)
    soup = profile_soup(symbol)
    return {"info": [clean(e.get_text(" | ", strip=True)) for e in soup.select(".fundInfo, .company_management")],
            "tables": tables(soup)}


@mcp.tool()
def get_statements(symbol: str, statement: Literal["balance", "income", "cash_flow", "ratios"] = "income") -> list:
    """Older statements: balance sheet, income or cash flow for 2019-2022 annual and mid-2022 to mid-2023
    quarters (SAR thousands); ratios gives DPS, EPS and current ratio for 2011-2014.
    Recent years are in get_profile; full line items such as loans are in get_xbrl."""
    check(symbol)
    stype = {"balance": 0, "income": 1, "cash_flow": 2, "ratios": 3}[statement]
    return tables(BeautifulSoup(statements_html(symbol, stype), "html.parser"))


@mcp.tool()
def get_filings(symbol: str, kind: Literal["pdf", "xbrl"] = "pdf") -> list[dict]:
    """Filed reports with download links. pdf: financial statements, board and ESG reports.
    xbrl: full machine-readable statements (.html and .xls), 2021 onward, with line items like term loans."""
    check(symbol)
    return filings(BeautifulSoup(statements_html(symbol, 5 if kind == "pdf" else 4), "html.parser"))


@mcp.tool()
def get_xbrl(url: str, section: str = "financial position") -> dict:
    """Read an XBRL filing (an .html link from get_filings kind="xbrl"): every line item, e.g. term loans,
    lease liabilities, finance costs. section matches a title such as "financial position", "income",
    "cash flows" or "notes". Returns all section titles and the matching sections' rows."""
    if not (url.startswith(ROOT + "/Resources/XBRL_DOCS/") and url.endswith(".html")):
        raise ValueError("url must be an XBRL .html link from get_filings")
    sections = xbrl_sections(BeautifulSoup(fetch(url), "html.parser"))
    return {"sections": list(sections), "matches": {k: v for k, v in sections.items() if section.lower() in k.lower()}}


@mcp.tool()
def get_valuation(symbol: str) -> dict:
    """P/E, EPS and market cap on today's issued shares. Use this, not price / the site's EPS, which is not
    restated after bonus share issues. pe is the trailing P/E Tadawul shows on the profile's Peer Comparison tab;
    pe_fy is price / the last full fiscal year's profit per share."""
    check(symbol)
    soup = profile_soup(symbol)
    shares = int(re.search(r"Total Issued Shares \| ([\d,]+)", soup.select_one(".fundInfo").get_text(" | ", strip=True))
                 .group(1).replace(",", ""))
    annual = profits(rows(soup.select_one("#unifiedSummaryFinancial table")))
    fy_end = max(annual)
    quote = get_quotes([symbol])
    price = quote[0]["lastTradePrice"] if quote else None
    site = next((td.select_one(".price") for td in soup.select("#peercompDT td") if "P/E" in td.get_text()), None)
    site = site.get_text(strip=True).replace(",", "") if site else ""

    return {"price": price, "issued_shares": shares, "market_cap_sar": price * shares if price else None,
            "pe": float(site) if site not in ("", "-") else None,  # "-" for loss-making companies
            "fiscal_year_end": fy_end.isoformat(), "fy_net_profit_sar": annual[fy_end],
            "eps_fy": round(annual[fy_end] / shares, 2),
            "pe_fy": round(price * shares / annual[fy_end], 1) if price and annual[fy_end] > 0 else None,
            "note": "Profit is before Tier 1 sukuk payouts, so bank EPS can read a few % above reported."}


@mcp.tool()
def get_price_history(symbol: str, start: str = "", end: str = "", limit: int = 250) -> list[dict]:
    """Daily open, high, low, close, volume, turnover and trades, newest first. Dates are YYYY-MM-DD.
    Returns at most `limit` days; history goes back to 2009 for older listings."""
    check(symbol)
    _, base = page(HISTORY)
    rows = []
    for market in ("MAIN", "NOMUC"):  # the endpoint returns nothing if the market is wrong
        while len(rows) < limit:
            form = {"selectedMarket": market, "selectedSector": "", "selectedEntity": symbol,
                    "startDate": date.fromisoformat(start or "2000-01-01").strftime("%d-%m-%Y"),
                    "endDate": (date.fromisoformat(end) if end else date.today()).strftime("%d-%m-%Y"),
                    "tableTabId": "0", "draw": "1", "start": str(len(rows)), "startIndex": str(len(rows)),
                    "length": "100", "endIndex": str(len(rows) + 100)}  # the server caps pages at 100
            batch = xhr(base + PRICES, HISTORY, method="POST", data=form).json()["data"]
            seen = {r["transactionDateStr"] for r in rows}
            new = [r for r in batch if r["transactionDateStr"] not in seen]  # pages after the first start one row early
            rows += new
            if len(batch) < 100 or not new:
                break
        if rows:
            break
    return [{k: clean(v) if isinstance(v, str) else v for k, v in r.items()} for r in rows[:limit]]


@mcp.tool()
def get_announcements(symbol: str = "", page_number: int = 1, page_size: int = 20) -> dict:
    """Issuer announcements, newest first. Omit symbol for the whole market.
    Returns totalCount and announcementList (date, Hijri date, title, summary, link)."""
    if symbol:
        check(symbol)
    _, base = page(ANNOUNCE)
    form = {"annoucmentType": "1_-1", "symbol": symbol, "sectorDpId": "", "searchType": "", "fromDate": "",
            "toDate": "", "datePeriod": "", "productType": "", "advisorsList": "", "textSearch": "",
            "pageNumberDb": str(page_number), "pageSize": str(page_size)}
    return xhr(base + ANNOUNCEMENTS, ANNOUNCE, method="POST", data=form).json()


@mcp.tool()
def get_corporate_actions(symbol: str):
    """Capital changes such as bonus shares and rights issues, with previous and new capital."""
    check(symbol)
    url = PROFILE.format(symbol)
    _, base = page(url)
    return xhr(base + CORP_ACTIONS, url,
               params={"indexSymbol": symbol, "language": "en", "issueType": "Corporate Action"}).json()


@mcp.tool()
def get_foreign_ownership(symbol: str) -> dict:
    """Foreign ownership: maximum allowed %, actual % (excluding strategic investors), strategic investors' %,
    and the as-of date."""
    check(symbol)
    url = PROFILE.format(symbol)
    _, base = page(url)
    soup = BeautifulSoup(xhr(base + FOREIGN, url, params={"symbol": symbol}).text, "html.parser")
    max_pct, actual, strategic = (float(s.get_text(strip=True)) for s in soup.select(".foreign_ownership strong"))
    return {"max_limit_pct": max_pct, "actual_pct": actual, "strategic_pct": strategic,
            "as_of": soup.select_one(".last_update").get_text(strip=True).split(":")[-1].strip()}


@mcp.tool()
def get_major_shareholders(symbol: str, start: str = "", end: str = "") -> dict:
    """Holders of 5% or more, one row per holder per trading day: date, holder (often Arabic), % held that day,
    % the previous day, change. locked: holders under an IPO lock-up. Dates are YYYY-MM-DD, default the last 90 days."""
    check(symbol)
    url = PROFILE.format(symbol)
    _, base = page(url)
    params = {"symbol": symbol, "fromDate": day(start, date.today() - timedelta(90)).strftime("%Y/%m/%d"),
              "toDate": day(end, date.today()).strftime("%Y/%m/%d"), "history": "1"}
    soup = BeautifulSoup(xhr(base + HOLDERS, url, params=params).text, "html.parser")
    keys = ("date", "holder", "pct", "prev_pct", "change")
    return {k: [dict(zip(keys, r)) for r in rows(soup.select_one(t))[1:] if len(r) == 5]  # skips "No data" row
            for k, t in (("holders", "#majorShareHoldersTable"), ("locked", "#majorShareHoldersTableLock"))}


@mcp.tool()
def get_options(symbol: str, settlement_date: str = "") -> dict:
    """Options chain {settlement date: rows}, each row a strike with call and put contract codes, last price,
    change, best bid/offer, daily settlement price, volume and open interest. settlement_date is YYYY-MM-DD;
    omit it for every expiry. Empty if the stock has no listed options."""
    check(symbol)
    url = PROFILE.format(symbol)
    _, base = page(url)
    dates = [o["value"] for o in profile_soup(symbol).select("#actionSelectSettlementDate option[value]")]
    if settlement_date and settlement_date not in dates:
        raise ValueError(f"settlement_date must be one of {dates}")
    params = {"symbol": symbol, "language": "en"}
    return {d: [{k: clean(v) for k, v in r.items()}  # every value is an HTML <td> fragment
                for r in xhr(base + OPTIONS, url, params={**params, "settlement_date": d}).json()]
            for d in ([settlement_date] if settlement_date else dates)}


@mcp.tool()
def get_chart_series(symbol: str = "TASI", intraday: bool = False, start: str = "", end: str = "") -> list[dict]:
    """Closing values, oldest first: daily, or every minute of the latest session if intraday. symbol is a Main
    market index (TASI from 1994, MT30, sector indices such as TBNI from 2016) or a stock (daily back to 2001).
    Dates are YYYY-MM-DD; daily defaults to the last year. For stock open/high/low/volume use get_price_history."""
    # shortcut: Nomu and sukuk indices need other chart types (SQL_MI_MSPV_SME/_SUKUK); add if asked for.
    if not re.fullmatch(r"[A-Za-z0-9]{2,8}", symbol):
        raise ValueError(f"Unknown symbol {symbol!r}")
    stock = symbol in {c["symbol"] for c in companies()}
    chart_type, page_name = {(True, False): ("SQL_CI_CV_COM", "CompanyProfileMainMarket"),
                             (True, True): ("SQL_CI_DV", "CompanyProfileMainMarket"),
                             (False, False): ("SQL_T_IC_ALL_PER", "MainMarketWatch"),
                             (False, True): ("SQL_MI_MSPV", "MainMarketWatch")}[stock, intraday]
    lo = day(start, date.min if intraday else date.today() - timedelta(365)).isoformat()
    hi = day(end, date.max).isoformat()
    data = xhr(CHART, HOME, params={"methodType": "parsingMethod", "chart-type": chart_type,
                                    "chart-parameter": symbol.lower(), "pageName": page_name}).json()
    if not data:
        raise ValueError(f"No chart data for {symbol!r}; use a Main market stock or index such as TASI or TBNI")
    return [{"date": r["dateTime"], "close": r["indexPrice"]} for r in data if lo <= r["dateTime"][:10] <= hi]


@mcp.tool()
def get_dividends(symbol: str = "", start: str = "", end: str = "") -> list[dict]:
    """Main market cash dividends: company, announced, eligibility (dueDate) and distribution dates, amount per share
    in SAR. Omit symbol for the whole market. Dates are YYYY-MM-DD, default a year back to a year ahead.
    Rows seem to start around 2023."""
    if symbol:
        check(symbol)
    _, base = page(DIVIDEND_CALENDAR)
    form = {"symbolorcompany": symbol, "bySymbol": symbol, "marketsListId": "M", "sector": "", "market": "",
            "period": "CUSTOM", "start": day(start, date.today() - timedelta(365)).strftime("%d-%m-%Y"),
            "end": day(end, date.today() + timedelta(365)).strftime("%d-%m-%Y")}
    return [{k: v for k, v in r.items() if k != "companyUrl"}
            for r in xhr(base + DIVIDENDS, DIVIDEND_CALENDAR, method="POST", data=form).json()["data"]]


@mcp.tool()
def get_performance(period: Literal["7 Days", "14 Days", "1 Months", "3 Months", "6 Months", "9 Months", "1 Years",
                                    "2 Years", "3 Years", "5 Years"] = "1 Months") -> list[dict]:
    """Every Main market stock's move over a period, best to worst: begin and end price, high, low, change,
    % change, value and volume traded, sector. Prices are adjusted for corporate actions."""
    _, base = page(PERFORMANCE)
    form = {"reportFilter": "gainersPercentage", "sectorFilter": "viewAllmarket", "timeFrameFilter": period,
            "isNonAdjusted": "0", "requestLocale": "en"}
    keys = ("companyRef", "acrynomName", "sectorName", "beginPrice", "endPrice", "highPrice", "lowPrice",
            "changeValue", "ChangePrecent", "value", "volumeTraded")
    found = [r for path in (GAINERS, LOSERS)  # the site splits the list in two
             for r in xhr(base + path, PERFORMANCE, method="POST", data=form).json()["data"]]
    return sorted(({k: r[k] for k in keys} for r in found), key=lambda r: r["ChangePrecent"], reverse=True)


@mcp.tool()
def get_ipos(start: str = "", end: str = "") -> dict:
    """New listings between start and end (YYYY-MM-DD, default the last year). ipoData: IPOs, ETFs and sukuk with
    market, offer price, shares offered, capital, managers, offering and closing dates. tradableData: rights issues."""
    noise = {"companyURL", "uploadCompanyLogoFileName", "address", "phoneNo", "fax", "issuerId", "issueType"}
    _, base = page(IPOS)
    form = {"listedType": "ALL", "market": "", "instrument": "",
            "fromDate": day(start, date.today() - timedelta(365)).strftime("%d/%m/%Y"),
            "toDate": day(end, date.today()).strftime("%d/%m/%Y")}
    return {k: [{f: clean(v) if isinstance(v, str) else v for f, v in r.items() if f not in noise} for r in rs]
            for k, rs in xhr(base + LISTINGS, IPOS, method="POST", data=form).json().items()}


def main():
    mcp.run()


if __name__ == "__main__":
    main()
