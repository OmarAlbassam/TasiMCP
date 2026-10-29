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
ISSUERS = PORTAL + "/ourmarkets/main-market-watch/issuers-trading-information?locale=en"
ANNOUNCEMENT = PORTAL + ("/newsandreports/issuer-news/issuer-announcements/issuer-announcements-details/"
                         "?anId={}&anCat=1&locale=en")
CHART = ROOT + "/tadawul.eportal.charts.v2/ChartGenerator"
REPORT = ROOT + "/Resources/Reports-v2/{}_en.html"
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
ISSUERS_DATA = "p0/IZ7_5A602H80OOMQC0604RU6VD10D2=CZ6_5A602H80O8DDC0QFK8HJ0O20K4=NJ{}=/"

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


def profile_xhr(symbol, path, /, **params):
    """Call a company-profile portlet endpoint; its path is relative to the profile page's <base href>."""
    url = PROFILE.format(symbol)
    _, base = page(url)
    return xhr(base + path, url, params=params)


def statements_html(symbol, statement_type):
    return profile_xhr(symbol, STATEMENTS, statementType=statement_type, reportType=0, requestLocale="en",
                       symbol=symbol).text


def report(name):
    """As-of date, header and rows of a daily market report under /Resources/Reports-v2."""
    soup = BeautifulSoup(fetch(REPORT.format(name)), "html.parser")
    head = [clean(th.get_text(" ")) for th in soup.find_all("th")]
    as_of = re.search(r"\d{4}[-/]\d\d[-/]\d\d", soup.get_text()).group().replace("/", "-")
    return as_of, head, [r for r in rows(soup.find("table")) if r != head]


def issuers(name, **params):
    """Rows from an issuers-trading-information endpoint, minus the long companyURL."""
    _, base = page(ISSUERS)
    return [{k: v for k, v in r.items() if k != "companyURL"}
            for r in xhr(base + ISSUERS_DATA.format(name), ISSUERS, params={**params, "requestLocale": "en"})
            .json()["data"]]


def pick_sector(sector, names):
    """The sector names containing `sector`, ignoring case. Raises with the valid names if none do."""
    found = {n for n in names if sector.lower() in n.lower()}
    if not found:
        raise ValueError(f"Unknown sector {sector!r}; use one of {sorted(set(names))}")
    return found


mcp = MCPServer("tasi", instructions=(
    "Saudi Exchange (Tadawul) data scraped live from saudiexchange.sa. Symbols are 4-digit codes, e.g. 2222 "
    "(Saudi Aramco), 4002 (Mouwasat). Financial table figures are SAR thousands unless the table says otherwise. "
    "For P/E and market cap use get_valuation, not price / the site's EPS, which is wrong after bonus issues. "
    "For debt, loans and finance costs read the XBRL filings with get_xbrl."))


@mcp.tool()
def list_companies(query: str = "", limit: int = 50, sector: str = "") -> list[dict]:
    """Find listed securities (stocks, funds, sukuk) by symbol, English or Arabic name, or ISIN.
    sector keeps Main market stocks whose sector contains it, e.g. "Banks" or "Insurance", and adds each one's sector."""
    q = query.lower()
    found = [c for c in companies() if q in " ".join(map(str, c.values())).lower()]
    if sector:
        of = {s: w["sectorName"] for s, w in market_watch().items()}
        keep = pick_sector(sector, of.values())
        found = [c | {"sector": of[c["symbol"]]} for c in found if of.get(c["symbol"]) in keep]
    return found[:limit]


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
    and sector; for Nomu these stay empty. Omit symbols for all ~400. Every row gets market_open: false
    when the site says the market is closed. A stock with no trade yet today has a price of 0 on the site:
    those rows get lastTradePrice = previousClosePrice and price_is_previous_close: true."""
    try:
        watch = market_watch()
    except Exception:  # extras only; a market-watch outage must not take down quotes and get_valuation
        watch = {}
    rows = [r | watch.get(r["pk_rf_company"], {}) for r in servlet("TickerServlet")["stockData"]
            if not symbols or r["pk_rf_company"] in symbols]
    try:
        # shortcut: only the known closed codes (0, 3, 4); open-session codes unconfirmed, map them when seen
        closed = servlet("RefreshTradeDetailsServlet")["marketStatusCode"] in (0, 3, 4)
    except Exception:  # extras only, like market watch
        closed = False
    for r in rows:
        if closed:
            r["market_open"] = False
        if not r.get("lastTradePrice", 1) and r.get("previousClosePrice"):  # 0 means no trade yet today
            r["lastTradePrice"], r["price_is_previous_close"] = r["previousClosePrice"], True
    return rows


MARKET_SECTIONS = {  # sections of RefreshTradeDetailsServlet, by its top-level keys; "indices" is everything else
    "main_movers": ["mainMarketActiveResultsBean"],
    "nomu_movers": ["nomuMarketActiveResultBean"],
    "sukuk": ["sokukMarketActiveResultBean", "sukukMarketBean"],
    "reits": ["reitMarketActiveResultBean", "reitMarketBean"],
    "etfs": ["etfMarketActiveResultBean", "etfMarketBean", "marketWatchETFsBeans"],
    "cefs": ["marketWatchCEFBeans", "cefMarketBean"],
}


@mcp.tool()
def get_market(sections: list[str] | None = None) -> dict:
    """Market summary, about 40k chars in full. breadth: Main market advancers (noOfUps), decliners (noOfDowns),
    unchanged, trades, volume and turnover, under the top-level `breadth` key.
    sections picks the rest, default all:
    indices (TASI, MT30, Nomu and sukuk index levels, 52-week and YTD figures, market status, listed counts),
    breadth, main_movers, nomu_movers, sukuk, reits, etfs, cefs (the last five are top gainers, losers, volume
    and value, and their rows). E.g. ["indices", "breadth", "main_movers"] is about a fifth of the size."""
    valid = ["indices", "breadth", *MARKET_SECTIONS]
    unknown = set(sections or []) - set(valid)
    if unknown:
        raise ValueError(f"Unknown sections {sorted(unknown)}; valid: {', '.join(valid)}")
    data = servlet("RefreshTradeDetailsServlet")
    owned = {k for keys in MARKET_SECTIONS.values() for k in keys} | {"marketBean"}
    want = lambda name: sections is None or name in sections
    out = {"breadth": data["marketBean"]} if want("breadth") else {}
    for name, keys in {"indices": [k for k in data if k not in owned], **MARKET_SECTIONS}.items():
        if want(name):
            out |= {k: data[k] for k in keys if k in data}
    return out


def profile_soup(symbol):
    return BeautifulSoup(page(PROFILE.format(symbol))[0], "html.parser")


@mcp.tool()
def get_profile(symbol: str) -> dict:
    """Company profile. info: overview, history, capital, issued shares, auditor, board and executives.
    subsidiaries: name, % owned, business and location, if the company lists any. Statements are in get_statements,
    dividends in get_dividends, options in get_options, P/E and market cap in get_valuation, and board and
    executive holdings in get_major_shareholders."""
    check(symbol)
    soup = profile_soup(symbol)
    subs = soup.select(".fundInfo table")
    subsidiaries = [dict(zip(t[0], r)) for t in map(rows, subs) for r in t[1:]]
    for t in subs:
        t.decompose()  # keep them out of info's text
    return {"info": [clean(e.get_text(" | ", strip=True)) for e in soup.select(".fundInfo, .company_management")],
            "subsidiaries": subsidiaries}


@mcp.tool()
def get_statements(symbol: str, sections: list[str] | None = None) -> dict:
    """Every financial statement the site has; each table's columns are newest first and its figures are in
    the table's 'All Figures in' unit. recent: balance sheet, income and cash flow summary for the last 3
    years and last 4 quarters. balance / income / cash_flow: full line items for 2019-2022 and mid-2022 to
    mid-2023 quarters. ratios: DPS, EPS and current ratio for 2011-2014. Line names differ between recent
    and older tables. Quarters from late 2023 to early 2025 and items such as loans are in get_xbrl.
    EPS is as published: not restated after bonus issues, and some quarters show year-to-date EPS.
    sections: names from the list above to return, e.g. ["recent"] skips the older tables and their requests;
    omit for all. Figures are as the site shows them today and can be restated, so the results announcement
    is the primary source."""
    older = {"balance": 0, "income": 1, "cash_flow": 2, "ratios": 3}
    unknown = set(sections or []) - {"recent", *older}
    if unknown:
        raise ValueError(f"Unknown sections {sorted(unknown)}; valid: recent, {', '.join(older)}")
    check(symbol)
    want = lambda name: sections is None or name in sections
    out = {}
    if want("recent"):  # the site keeps recent years on the profile page and older ones behind a separate tab
        out["recent"] = [t for t in tables(profile_soup(symbol)) if t and t[0][0] == "Balance Sheet" and
                         ["Cash Flows"] in [r[:1] for r in t]]
    return out | {name: tables(BeautifulSoup(statements_html(symbol, stype), "html.parser"))
                  for name, stype in older.items() if want(name)}


@mcp.tool()
def get_filings(symbol: str, kind: Literal["pdf", "xbrl"] = "pdf") -> list[dict]:
    """Filed reports with download links. pdf: financial statements, board and ESG reports.
    xbrl: full machine-readable statements (.html and .xls), 2021 onward, with line items like term loans."""
    check(symbol)
    return filings(BeautifulSoup(statements_html(symbol, 5 if kind == "pdf" else 4), "html.parser"))


@mcp.tool()
def get_xbrl(symbol: str = "", year: int = 0, period: Literal["Annual", "Q1", "Q2", "Q3"] = "Annual",
             section: str = "financial position", url: str = "") -> dict:
    """Full statements from one XBRL filing, 2021 onward: every line item, e.g. term loans, lease liabilities,
    finance costs. year is the fiscal year; omit it for the latest one filed. There is no Q4 filing: use Annual.
    section matches a title such as "financial position", "income", "cash flows" or "notes". Returns the filing's
    year and period, all section titles and the matching sections' rows. url (deprecated) reads an .html link
    from get_filings instead of symbol, year and period."""
    filing = {}
    if not url:  # url is the old interface; drop it next release
        check(symbol)
        found = {f["year"]: f for f in get_filings(symbol, "xbrl") if f["period"] == period}
        if not found or (year and str(year) not in found):
            raise ValueError(f"No {period} XBRL filing for {symbol} in {year or 'any year'}; years: {sorted(found)}")
        f = found[str(year) if year else max(found)]
        filing = {"year": int(f["year"]), "period": period}
        url = next(u for u in f["urls"] if u.endswith(".html"))
    if not (url.startswith(ROOT + "/Resources/XBRL_DOCS/") and url.endswith(".html")):
        raise ValueError("url must be an XBRL .html link from get_filings")
    sections = xbrl_sections(BeautifulSoup(fetch(url), "html.parser"))
    return filing | {"sections": list(sections),
                     "matches": {k: v for k, v in sections.items() if section.lower() in k.lower()}}


@mcp.tool()
def get_valuation(symbol: str) -> dict:
    """P/E, EPS and market cap on today's issued shares. Use this, not price / the site's EPS, which is not
    restated after bonus share issues. pe is the trailing P/E Tadawul shows on the profile's Peer Comparison tab;
    pe_fy is price / the last full fiscal year's profit per share. daily_report: Tadawul's end-of-day P/E, P/B,
    EPS, book value, net income and equity for the stock and its sector (money in SAR millions); None for Nomu.
    dividends_ttm_sar: cash dividends per share whose eligibility date (dueDate, what get_dividends returns) fell in
    the last 365 days, specials included. dividend_yield_pct: that / price. payout_ratio_pct: that / eps_fy;
    payout_above_100 flags it, which usually means a one-off special. All three are None if the dividend lookup fails (payout also if eps_fy <= 0).
    Warning: after a bonus issue or split in the window, old dividends are per old share and the yield is overstated."""
    check(symbol)
    try:
        daily = screen_valuations()
    except Exception:  # extras only, like market watch in get_quotes
        daily = {"as_of": None, "stocks": [], "sectors": []}
    stock = next((s for s in daily["stocks"] if s["Symbol"] == symbol), None)
    sector = next((s for s in daily["sectors"] if stock and s["sector"] == stock["sector"]), None)
    soup = profile_soup(symbol)
    shares = int(re.search(r"Total Issued Shares \| ([\d,]+)", soup.select_one(".fundInfo").get_text(" | ", strip=True))
                 .group(1).replace(",", ""))
    annual = profits(rows(soup.select_one("#unifiedSummaryFinancial table")))
    fy_end = max(annual)
    quote = get_quotes([symbol])
    price = quote[0]["lastTradePrice"] if quote else None
    today = date.today()
    try:  # shortcut: no bonus issue/split adjustment (get_corporate_actions), upgrade if yields after bonus issues matter
        divs = round(sum(d["amount"] for d in get_dividends(symbol, (today - timedelta(365)).isoformat(), today.isoformat())
                         if d["dueDate"] <= today.isoformat()), 4)
    except Exception:  # extras only, like the daily report
        divs = None
    site = next((td.select_one(".price") for td in soup.select("#peercompDT td") if "P/E" in td.get_text()), None)
    site = site.get_text(strip=True).replace(",", "") if site else ""
    payout = round(divs * shares / annual[fy_end] * 100, 1) if divs is not None and annual[fy_end] > 0 else None

    return {"price": price, "issued_shares": shares, "market_cap_sar": price * shares if price else None,
            "pe": float(site) if site not in ("", "-") else None,  # "-" for loss-making companies
            "fiscal_year_end": fy_end.isoformat(), "fy_net_profit_sar": annual[fy_end],
            "eps_fy": round(annual[fy_end] / shares, 2),
            "pe_fy": round(price * shares / annual[fy_end], 1) if price and annual[fy_end] > 0 else None,
            "dividends_ttm_sar": divs,
            "dividend_yield_pct": round(divs / price * 100, 2) if divs is not None and price else None,
            "payout_ratio_pct": payout, "payout_above_100": payout is not None and payout > 100,
            "daily_report": {"as_of": daily["as_of"], "stock": stock, "sector": sector} if stock else None,
            "note": "Profit is before Tier 1 sukuk payouts, so bank EPS can read a few % above reported."}


@mcp.tool()
def get_price_history(symbol: str, start: str = "", end: str = "", limit: int = 250) -> list[dict]:
    """Daily open, high, low, close, volume, turnover and trades, newest first. Dates are YYYY-MM-DD.
    symbol is a stock or a Main market index such as TASI, MT30 or TBNI (indices have no change fields, and
    MT30 has "-" for volume, turnover and trades). `close` is that day's close (the site calls it
    previousClosePrice, which is misleading). Returns at most `limit` days; history goes back to 2009."""
    stock = symbol in {c["symbol"] for c in companies()}
    if not stock and not re.fullmatch(r"[A-Za-z0-9]{2,8}", symbol):
        raise ValueError(f"Unknown symbol {symbol!r}; use list_companies to find it")
    _, base = page(HISTORY)
    rows = []
    # the endpoint returns nothing if the market is wrong; indices need the "M:" prefix
    for market in ("MAIN", "NOMUC") if stock else ("INDICES",):
        entity = symbol if stock else "M:" + symbol.upper()
        while len(rows) < limit:
            form = {"selectedMarket": market, "selectedSector": "", "selectedEntity": entity,
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
    if not rows and not stock:
        raise ValueError(f"No price history for {symbol!r} in that range; check the dates, or use a listed stock "
                         "or a Main market index such as TASI")
    # the site's previousClosePrice is that day's close, so rename it
    return [{("close" if k == "previousClosePrice" else k): clean(v) if isinstance(v, str) else v
             for k, v in r.items()} for r in rows[:limit]]


ANNOUNCEMENT_TYPES = {"all": "1_-1", "annual_results": "1_17", "interim_results": "1_18",
                      "bank_annual_results": "1_19", "bank_interim_results": "1_20", "insurer_annual_results": "1_21",
                      "insurer_interim_results": "1_22", "nomu_results": "1_95", "cash_dividend": "1_57",
                      "board_changes": "1_23", "assembly_invitation": "1_52", "assembly_results": "1_54",
                      "contract_award": "1_91", "buyback": "1_103", "accumulated_losses": "1_93"}


@mcp.tool()
def get_announcements(symbol: str = "", page_number: int = 1, page_size: int = 20,
                      announcement_type: Literal[tuple(ANNOUNCEMENT_TYPES)] | str = "all") -> dict:
    """Issuer announcements, newest first. Omit symbol for the whole market.
    Returns totalCount and announcementList (date, Hijri date, title, summary, link, announcementNumber).
    announcement_type filters by form. annual_results / interim_results are companies' results; banks, insurers
    and Nomu have their own. board_changes covers board or executive changes, buyback a share buy-back or sale,
    accumulated_losses losses of 20%+ of capital. The site has more types: a raw code such as 1_57 also works.
    Read one in full with get_announcement."""
    if symbol:
        check(symbol)
    code = ANNOUNCEMENT_TYPES.get(announcement_type, announcement_type)
    if not re.fullmatch(r"1_-?\d+", code):
        raise ValueError(f"announcement_type must be one of {list(ANNOUNCEMENT_TYPES)} or a code like 1_18, "
                         f"not {announcement_type!r}")
    _, base = page(ANNOUNCE)
    form = {"annoucmentType": code, "symbol": symbol, "sectorDpId": "", "searchType": "", "fromDate": "",
            "toDate": "", "datePeriod": "", "productType": "", "advisorsList": "", "textSearch": "",
            "pageNumberDb": str(page_number), "pageSize": str(page_size)}
    return xhr(base + ANNOUNCEMENTS, ANNOUNCE, method="POST", data=form).json()


@mcp.tool()
def get_corporate_actions(symbol: str):
    """Capital changes such as bonus shares and rights issues, with previous and new capital."""
    check(symbol)
    return profile_xhr(symbol, CORP_ACTIONS, indexSymbol=symbol, language="en", issueType="Corporate Action").json()


@mcp.tool()
def get_foreign_ownership(symbol: str) -> dict:
    """Foreign ownership: maximum allowed %, actual % (excluding strategic investors), strategic investors' %,
    and the as-of date."""
    check(symbol)
    soup = BeautifulSoup(profile_xhr(symbol, FOREIGN, symbol=symbol).text, "html.parser")
    max_pct, actual, strategic = (float(s.get_text(strip=True)) for s in soup.select(".foreign_ownership strong"))
    return {"max_limit_pct": max_pct, "actual_pct": actual, "strategic_pct": strategic,
            "as_of": soup.select_one(".last_update").get_text(strip=True).split(":")[-1].strip()}


@mcp.tool()
def get_major_shareholders(symbol: str, start: str = "", end: str = "") -> dict:
    """Holders of 5% or more, one row per holder per trading day: date, holder (often Arabic), % held that day,
    % the previous day, change. locked: holders under an IPO lock-up. Dates are YYYY-MM-DD, default the last 90 days.
    insiders: board members' and executives' holdings with their role, latest trading day only (ignores the dates)."""
    check(symbol)
    soup = BeautifulSoup(profile_xhr(symbol, HOLDERS, symbol=symbol, history="1",
                                     fromDate=day(start, date.today() - timedelta(90)).strftime("%Y/%m/%d"),
                                     toDate=day(end, date.today()).strftime("%Y/%m/%d")).text, "html.parser")
    keys = ("date", "holder", "pct", "prev_pct", "change")
    found = {k: [dict(zip(keys, r)) for r in rows(soup.select_one(t))[1:] if len(r) == 5]  # skips "No data" row
             for k, t in (("holders", "#majorShareHoldersTable"), ("locked", "#majorShareHoldersTableLock"))}
    # board and executive holdings are only on the profile page, not behind this endpoint
    board = [r for t in profile_soup(symbol).select("#boardOfDirector table") for r in rows(t)[1:] if len(r) == 6]
    return found | {"insiders": [dict(zip(("date", "holder", "role") + keys[2:], r)) for r in board]}


@mcp.tool()
def get_options(symbol: str, settlement_date: str = "") -> dict:
    """Options chain {settlement date: rows}, each row a strike with call and put contract codes, last price,
    change, best bid/offer, daily settlement price, volume and open interest. settlement_date is YYYY-MM-DD;
    omit it for every expiry. Empty if the stock has no listed options."""
    check(symbol)
    dates = [o["value"] for o in profile_soup(symbol).select("#actionSelectSettlementDate option[value]")]
    if settlement_date and settlement_date not in dates:
        raise ValueError(f"settlement_date must be one of {dates}")
    return {d: [{k: clean(v) for k, v in r.items()}  # every value is an HTML <td> fragment
                for r in profile_xhr(symbol, OPTIONS, symbol=symbol, language="en", settlement_date=d).json()]
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
    History goes back to at least 2010."""
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


@mcp.tool()
def get_announcement(announcement_id: int) -> dict:
    """Full text of one announcement (announcementNumber from get_announcements). For financial results: tables of
    this quarter vs the same quarter last year vs the previous quarter and year to date, a units line such as
    "All figures are in (Billions)", then management's reasons for each change. attachments links the filed report."""
    body = BeautifulSoup(fetch(ANNOUNCEMENT.format(announcement_id)), "html.parser").select_one(".article_body")
    if not body:
        raise ValueError(f"No announcement {announcement_id}; use announcementNumber from get_announcements")
    found = tables(body)
    attachments = [urljoin(ROOT, a["href"]) for a in body.find_all("a", href=True)]
    for table in body.find_all("table"):
        table.decompose()
    return {"tables": found, "text": body.get_text("\n", strip=True), "attachments": attachments}


@mcp.tool()
def screen_valuations(sector: str = "") -> dict:
    """Tadawul's daily P/E, P/B, EPS, book value per share, market cap, net income and equity for every Main market
    stock, with the same figures for each sector and the whole market ("Market"), to screen and compare stocks with
    their sector. sector keeps sectors whose name contains it, e.g. "Banks". Money in SAR millions, shares in
    millions. P/E "M" means loss-making. as_of is the trading day."""
    as_of, head, found = report("DailyFinancialIndicators")
    stocks, sectors, group = [], [], []
    for r in found:
        if r[0].isdigit():
            group.append(dict(zip(head, r)))
        else:  # a subtotal after its sector's stocks, or the market total; their last 9 cells line up with head[3:]
            stocks += [s | {"sector": r[0]} for s in group]
            sectors.append({"sector": r[0], **dict(zip(head[3:], r[-9:]))})
            group = []
    if sector:
        keep = pick_sector(sector, [s["sector"] for s in sectors])
        stocks, sectors = ([s for s in rs if s["sector"] in keep] for rs in (stocks, sectors))
    return {"as_of": as_of, "stocks": stocks, "sectors": sectors}


@mcp.tool()
def get_short_interest(symbol: str = "") -> dict:
    """Short selling from Tadawul's daily Main market reports. net_short: net short position as % of outstanding
    shares and of free float, and the ratio to 60-day average daily volume (days to cover); only stocks with a
    position are listed. lending: shares lent out under securities borrowing and lending, and % of issued shares.
    Omit symbol for every stock."""
    if symbol:
        check(symbol)
    out = {}
    for key, name in (("net_short", "NetShortPositions"), ("lending", "SBLReport")):
        as_of, head, found = report(name)
        out[key] = {"as_of": as_of, "rows": [dict(zip(head, r)) for r in found if not symbol or r[0] == symbol]}
    return out


@mcp.tool()
def get_risk_flags(symbol: str = "") -> dict:
    """Main market red flags and liquidity. accumulated_losses: companies whose losses reached 20-35%, 35-50% or 50%+
    of capital, which brings CMA disclosure rules and, at 50%, a vote on dissolving. suspensions: trading
    suspensions in the last year with the news link. liquidity_tier: {symbol: 1-4} by 6-month average daily traded
    value (1 >= SAR 50M, 2 = 5-50M, 3 = 1-5M, 4 < 1M), which also sets the minimum block-trade size. Omit symbol
    for every company."""
    if symbol:
        check(symbol)
    bands = {1: "20-35%", 2: "35-50%", 3: "50%+"}
    losses = [{"symbol": r["symbol"], "company": r["company"], "losses_of_capital": bands[r["companyStatus"]]}
              for r in issuers("getAccumulatedLossesDetails", percentage="All")]
    suspensions = issuers("getSuspendedDelistedComp", renderType="onload", formType="Suspension",
                          fromDate=(date.today() - timedelta(365)).strftime("%d-%m-%Y"),
                          toDate=date.today().strftime("%d-%m-%Y"))
    tiers = {c["symbolCode"]: c["tierValue"] for r in issuers("getMainMarketMinimumSizeRequirements")
             for c in (r.get(f"col{i}") for i in range(1, 5)) if c and c["tierValue"]}  # tierValue 0 = empty cell
    mine = lambda rs: [r for r in rs if not symbol or r["symbol"] == symbol]
    return {"accumulated_losses": mine(losses), "suspensions": mine(suspensions),
            "liquidity_tier": {s: t for s, t in tiers.items() if not symbol or s == symbol}}


@mcp.tool()
def get_block_trades(symbol: str = "", start: str = "", end: str = "") -> list[dict]:
    """Main market negotiated deals (block trades agreed off the order book): date, time, price, volume and value.
    Omit symbol for the whole market. Dates are YYYY-MM-DD, default the last 30 days."""
    if symbol:
        check(symbol)
    found = issuers("getNegotiatedDetails", sector="All", company=symbol or "All",
                    fromDate=day(start, date.today() - timedelta(30)).strftime("%d-%m-%Y"),
                    toDate=day(end, date.today()).strftime("%d-%m-%Y"))
    return [r for r in found if r["symbol"]]  # the last row is a blank-symbol total


def main():
    mcp.run()


if __name__ == "__main__":
    main()
