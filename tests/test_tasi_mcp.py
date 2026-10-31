import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from src import core, news, saudiexchange
from src.news import argaam_list
from src.saudiexchange import (clean, filings, profits, tables, ttm_profit, xbrl_quarter_profits,
                                    xbrl_sections)

FILINGS = """<table>
<tr><th><select><option>2025</option></select></th><th>2025</th><th>2024</th></tr>
<tr><td>Annual</td><td>-</td><td>2025-03-11 <a href="/Resources/fsPdf/433_0_2025-03-11_En.pdf">pdf</a></td></tr>
<tr><td>Q4</td><td>-</td><td>-</td></tr>
</table>"""


def test_filings_flattens_grid():
    assert filings(BeautifulSoup(FILINGS, "html.parser")) == [{
        "period": "Annual", "year": "2024", "date": "2025-03-11 pdf",
        "urls": ["https://www.saudiexchange.sa/Resources/fsPdf/433_0_2025-03-11_En.pdf"]}]


def test_tables_and_riyal_sign():
    html = "<table><tr><th>All Currency In</th><td> ^ </td></tr><tr><td>EPS</td><td>4.11</td></tr></table>"
    assert tables(BeautifulSoup(html, "html.parser")) == [[["All Currency In", "SAR"], ["EPS", "4.11"]]]
    assert clean("<div class='priceUp'>0.10<i></i></div>") == "0.10"


SUMMARY = [["Statement of Income", "2025-12-31", "2025-09-30", "2025-06-30", "2024-12-31"],
           ["Net Profit (Loss) Attributable to Shareholders of the Issuer", "100", "2", "3", "-"],
           ["All Figures in", "Thousands", "Millions", "Thousands", "Thousands"]]


def test_profits_applies_units_and_skips_blanks():
    assert profits(SUMMARY) == {date(2025, 12, 31): 100_000, date(2025, 9, 30): 2_000_000, date(2025, 6, 30): 3_000}


def test_ttm_profit():
    annual = {date(2025, 12, 31): 100, date(2024, 12, 31): 80}
    q = {date(2026, 6, 30): 30, date(2026, 3, 31): 20, date(2025, 6, 30): 25, date(2025, 3, 31): 15}
    assert ttm_profit(annual, q) == 100 + 30 + 20 - 25 - 15
    assert ttm_profit(annual, {d: v for d, v in q.items() if d != date(2025, 3, 31)}) is None
    assert ttm_profit(annual, {date(2025, 9, 30): 1}) == 100  # fiscal year just published


def test_xbrl_sections_groups_and_drops_empty_rows():
    html = """<table><tr><td>[300200] Statement of financial position</td></tr></table>
    <table><tr><td>Assets [abstract]</td><td></td></tr><tr><td>Term loans</td><td>564,793,854</td></tr></table>"""
    assert xbrl_sections(BeautifulSoup(html, "html.parser")) == {
        "[300200] Statement of financial position": [["Term loans", "564,793,854"]]}


def test_xbrl_quarter_profits_keeps_3_month_columns_and_scales():
    sections = {
        "[100010] Filing information": [["Description of presentation currency", "Saudi Arabia, Riyals"],
                                        ["Level of rounding used in financial statements", "Millions"]],
        "[300300] Statement of income, nature of expense": [
            ["Start Date", "2025-04-01", "2024-04-01", "2025-01-01", "Note No."],
            ["End Date", "2025-06-30", "2024-06-30", "2025-06-30"],
            ["Profit (loss), attributable to equity holders of parent company", "95,676", "", "200,000", ""]]}
    assert xbrl_quarter_profits(sections) == {date(2025, 6, 30): 95_676_000_000}


def fake(monkeypatch, reply):
    """Serve every xhr() call from `reply` (a JSON or HTML string); no network."""
    monkeypatch.setattr(core, "_cache", {})
    monkeypatch.setattr(saudiexchange, "check", lambda symbol: None)
    monkeypatch.setattr(saudiexchange, "companies", lambda: [{"symbol": "1120"}])
    monkeypatch.setattr(saudiexchange, "page", lambda url: ("", ""))
    monkeypatch.setattr(saudiexchange, "fetch", lambda url: reply)
    monkeypatch.setattr(saudiexchange, "xhr", lambda *a, **kw: SimpleNamespace(text=reply, json=lambda: json.loads(reply)))


def test_foreign_ownership(monkeypatch):
    fake(monkeypatch, """<div class="foreign_ownership"><div class="max_limit"><span>Maximum Limit (%)</span>
    <strong>49.00</strong></div><div class="actual"><span>Actual (%)</span><strong>
    13.93 </strong></div><div class="max_limit"><span>Actual (%)</span><strong> 0.00 </strong></div>
    <div class="last_update">Last updated on :  2026-10-25</div></div>""")
    assert saudiexchange.get_foreign_ownership("1120") == {
        "max_limit_pct": 49.0, "actual_pct": 13.93, "strategic_pct": 0.0, "as_of": "2026-10-25"}


def test_major_shareholders(monkeypatch):
    head = "<thead><tr><th>Trading Date</th><th>Shareholders</th><th>a</th><th>b</th><th>c</th></tr></thead>"
    fake(monkeypatch, f"""<table id="majorShareHoldersTable">{head}<tbody><tr><td >2026-10-22 </td>
    <td>سليمان محمد سليمان السليم</td><td class="priceUp">14.817%</td><td>14.817%</td><td>0</td></tr></tbody></table>
    <table id="majorShareHoldersTableLock">{head}<tbody><tr class="no-records-found showTr">
    <td colspan="5">No data available in table</td></tr></tbody></table>""")
    monkeypatch.setattr(saudiexchange, "profile_soup", lambda s: BeautifulSoup(
        '<div id="boardOfDirector"><table><tr><th>Trading Date</th></tr><tr><td>2026-10-26</td><td>عبدالله</td>'
        '<td>Chairman</td><td>2.18%</td><td>2.18%</td><td>0</td></tr></table></div>', "html.parser"))
    assert saudiexchange.get_major_shareholders("4002") == {"locked": [], "holders": [
        {"date": "2026-10-22", "holder": "سليمان محمد سليمان السليم", "pct": "14.817%", "prev_pct": "14.817%",
         "change": "0"}], "insiders": [
        {"date": "2026-10-26", "holder": "عبدالله", "role": "Chairman", "pct": "2.18%", "prev_pct": "2.18%",
         "change": "0"}]}


def test_profile_keeps_info_and_subsidiaries(monkeypatch):
    fake(monkeypatch, "")
    monkeypatch.setattr(saudiexchange, "profile_soup", lambda s: BeautifulSoup(
        '<div class="fundInfo">Capital<table><tr><th>Name Of Subsidiary</th><th>%</th></tr>'
        '<tr><td>Jeddah Doctors Co.</td><td>51.00%</td></tr></table></div><table id="companyDividends"></table>',
        "html.parser"))
    assert saudiexchange.get_profile("4002") == {
        "info": ["Capital"], "subsidiaries": [{"Name Of Subsidiary": "Jeddah Doctors Co.", "%": "51.00%"}]}


def test_xbrl_finds_filing_by_year_and_period(monkeypatch):
    fake(monkeypatch, "<table><tr><td>[300200] Statement of financial position</td></tr></table>"
                      "<table><tr><td>Term loans</td><td>5</td></tr></table>")
    link = saudiexchange.ROOT + "/Resources/XBRL_DOCS/x.html"
    monkeypatch.setattr(saudiexchange, "get_filings", lambda s, kind: [
        {"period": p, "year": y, "urls": [link, link[:-4] + "xls"]} for p, y in
        (("Annual", "2024"), ("Annual", "2025"), ("Q1", "2026"))])
    latest = saudiexchange.get_xbrl("1120")
    assert (latest["year"], latest["period"]) == (2025, "Annual")
    assert latest["matches"] == {"[300200] Statement of financial position": [["Term loans", "5"]]}
    assert saudiexchange.get_xbrl("1120", 2024)["year"] == 2024
    assert "year" not in saudiexchange.get_xbrl(url=link)
    for bad in ({"year": 2023}, {"period": "Q3"}):
        with pytest.raises(ValueError):
            saudiexchange.get_xbrl("1120", **bad)


NO_ACTIONS = {"upComingCorporateBeans": [], "pastCorporateBeans": []}


def test_valuation_adds_daily_report_rows(monkeypatch):
    fake(monkeypatch, "")
    monkeypatch.setattr(saudiexchange, "get_corporate_actions", lambda s: NO_ACTIONS)
    summary = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in SUMMARY)
    monkeypatch.setattr(saudiexchange, "profile_soup", lambda s: BeautifulSoup(
        f'<div class="fundInfo"><b>Total Issued Shares</b><b>4,000</b></div>'
        f'<div id="unifiedSummaryFinancial"><table>{summary}</table></div>', "html.parser"))
    monkeypatch.setattr(saudiexchange, "get_quotes", lambda s: [{"lastTradePrice": 10.0}])
    monkeypatch.setattr(saudiexchange, "screen_valuations", lambda: {
        "as_of": "2026-10-26", "stocks": [{"Symbol": "1120", "sector": "Banks"}],
        "sectors": [{"sector": "Energy"}, {"sector": "Banks", "P/E": "7.2"}]})
    assert saudiexchange.get_valuation("1120")["daily_report"] == {
        "as_of": "2026-10-26", "stock": {"Symbol": "1120", "sector": "Banks"}, "sector": {"sector": "Banks", "P/E": "7.2"}}
    assert saudiexchange.get_valuation("9564")["daily_report"] is None  # Nomu is not in the report
    monkeypatch.setattr(saudiexchange, "screen_valuations", lambda: 1 / 0)
    assert saudiexchange.get_valuation("1120")["daily_report"] is None


def test_valuation_sums_dividends_up_to_today(monkeypatch):
    fake(monkeypatch, "")
    summary = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in SUMMARY)
    monkeypatch.setattr(saudiexchange, "profile_soup", lambda s: BeautifulSoup(
        f'<div class="fundInfo"><b>Total Issued Shares</b><b>4,000</b></div>'
        f'<div id="unifiedSummaryFinancial"><table>{summary}</table></div>', "html.parser"))
    monkeypatch.setattr(saudiexchange, "get_quotes", lambda s: [{"lastTradePrice": 10.0}])
    monkeypatch.setattr(saudiexchange, "screen_valuations", lambda: {"as_of": None, "stocks": [], "sectors": []})
    today = date.today()
    rows = [{"dueDate": (today - timedelta(d)).isoformat(), "amount": a} for d, a in ((10, 0.5), (200, 0.25), (0, 0.25), (-5, 9.0), (50, 0))]
    monkeypatch.setattr(saudiexchange, "get_dividends", lambda s, start, end: rows)
    monkeypatch.setattr(saudiexchange, "get_corporate_actions", lambda s: NO_ACTIONS)
    v = saudiexchange.get_valuation("1120")
    assert (v["dividends_ttm_sar"], v["dividend_yield_pct"]) == (1.0, 10.0)  # the future row is left out
    assert v["payout_ratio_pct"] == round(4000 / v["fy_net_profit_sar"] * 100, 1)
    assert v["payout_above_100"] == (v["payout_ratio_pct"] > 100) and v["dividend_note"] is None
    # a bonus issue inside the window blanks the numbers; one 400 days ago does not; a failed lookup blanks them too
    def acts(days):
        due = (today - timedelta(days)).strftime("%d/%m/%Y")
        return {"upComingCorporateBeans": [], "pastCorporateBeans": [
            {"issueTypeDesc": "Bonus Shares", "dueDate": due}, {"issueTypeDesc": "Rights Issue", "dueDate": due}]}
    monkeypatch.setattr(saudiexchange, "get_corporate_actions", lambda s: acts(30))
    v = saudiexchange.get_valuation("1120")
    assert (v["dividends_ttm_sar"], v["dividend_yield_pct"], v["payout_ratio_pct"], v["payout_above_100"]) == (None,) * 4
    assert "Bonus Shares" in v["dividend_note"]
    monkeypatch.setattr(saudiexchange, "get_corporate_actions", lambda s: acts(400))
    assert saudiexchange.get_valuation("1120")["dividends_ttm_sar"] == 1.0
    monkeypatch.setattr(saudiexchange, "get_corporate_actions", lambda s: 1 / 0)
    v = saudiexchange.get_valuation("1120")
    assert (v["dividends_ttm_sar"], v["dividend_yield_pct"], v["payout_ratio_pct"], v["payout_above_100"]) == (None,) * 4
    assert v["dividend_note"]
    monkeypatch.setattr(saudiexchange, "get_corporate_actions", lambda s: NO_ACTIONS)
    monkeypatch.setattr(saudiexchange, "get_dividends", lambda s, start, end: 1 / 0)
    v = saudiexchange.get_valuation("1120")
    assert (v["dividends_ttm_sar"], v["dividend_yield_pct"], v["payout_ratio_pct"]) == (None, None, None)


def test_announcements_accept_names_and_codes(monkeypatch):
    fake(monkeypatch, "{}")
    sent = []
    monkeypatch.setattr(saudiexchange, "xhr", lambda *a, data, **kw: sent.append(data["annoucmentType"]) or
                        SimpleNamespace(json=dict))
    saudiexchange.get_announcements(announcement_type="cash_dividend")
    saudiexchange.get_announcements(announcement_type="1_200")
    assert sent == ["1_57", "1_200"]
    with pytest.raises(ValueError):
        saudiexchange.get_announcements(announcement_type="dividends")


def test_options_strips_html_and_checks_date(monkeypatch):
    fake(monkeypatch, json.dumps([{"strike": "<td>48.00</td>", "calls_contract_code":
                                   "<tr> <td> <a href='/x'>RJHO6X48C</a> </td>"}]))
    monkeypatch.setattr(saudiexchange, "profile_soup", lambda s: BeautifulSoup(
        '<select id="actionSelectSettlementDate"><option>All Events</option>'
        '<option value="2026-11-19">November 2026</option></select>', "html.parser"))
    assert saudiexchange.get_options("1120") == {"2026-11-19": [{"strike": "48.00", "calls_contract_code": "RJHO6X48C"}]}
    with pytest.raises(ValueError):
        saudiexchange.get_options("1120", "2026-12-01")


def test_chart_series_filters_intraday_by_day(monkeypatch):
    fake(monkeypatch, json.dumps([{"dateTime": d, "indexPrice": p} for d, p in
                                  (("2026-10-24 15:00:45", 1.0), ("2026-10-25 10:00:45", 2.0))]))
    assert saudiexchange.get_chart_series("tasi", True, end="2026-10-24") == [{"date": "2026-10-24 15:00:45", "close": 1.0}]
    with pytest.raises(ValueError):
        saudiexchange.get_chart_series("../x")


def test_quotes_merge_market_watch(monkeypatch):
    fake(monkeypatch, json.dumps({"data": [{"companyRef": 1120, "todayOpen": 59.3, **dict.fromkeys(
        ("sectorName", "highPrice", "lowPrice", "previousClosePrice", "bidPrice", "bidQuantity", "askPrice",
         "askQuantity", "high52WeekPrice", "low52WeekPrice"), 1)}]}))
    monkeypatch.setattr(saudiexchange, "servlet", lambda name: {"stockData": [
        {"pk_rf_company": "1120", "todaysOpen": None}, {"pk_rf_company": "9564", "todaysOpen": None}]})
    nomu, = saudiexchange.get_quotes(["9564"])
    rajhi, = saudiexchange.get_quotes(["1120"])
    assert nomu == {"pk_rf_company": "9564", "todaysOpen": None}
    assert rajhi["todaysOpen"] == 59.3 and rajhi["bidPrice"] == 1


def test_quotes_zero_price_falls_back_to_previous_close(monkeypatch):
    fake(monkeypatch, json.dumps({"data": [{"companyRef": 2222, "todayOpen": 0, **dict.fromkeys(
        ("sectorName", "highPrice", "lowPrice", "bidPrice", "bidQuantity", "askPrice", "askQuantity",
         "high52WeekPrice", "low52WeekPrice"), 0), "previousClosePrice": 27.5}]}))
    ticker = {"stockData": [{"pk_rf_company": "2222", "lastTradePrice": 0},
                            {"pk_rf_company": "1120", "lastTradePrice": 59.75},
                            {"pk_rf_company": "9564", "lastTradePrice": 0}]}
    monkeypatch.setattr(saudiexchange, "servlet", lambda name: ticker | {"marketStatusCode": 3})
    row, traded, nomu = saudiexchange.get_quotes(["2222", "1120", "9564"])
    assert row["lastTradePrice"] == 27.5 and row["price_is_previous_close"] and row["market_open"] is False
    assert traded["lastTradePrice"] == 59.75 and "price_is_previous_close" not in traded
    assert traded["market_open"] is False
    assert nomu["lastTradePrice"] is None  # no previous close to fall back on
    monkeypatch.setattr(saudiexchange, "servlet", lambda name: ticker if name == "TickerServlet" else 1 / 0)
    row, = saudiexchange.get_quotes(["2222"])  # status lookup fails: still a quote
    assert row["lastTradePrice"] == 27.5 and "market_open" not in row


def test_price_history_drops_page_overlap(monkeypatch):
    fake(monkeypatch, "{}")
    days = [f"d{i:03}" for i in range(250)]

    def site(*a, data, **kw):  # like the site: every page after the first starts one row early
        s = int(data["start"]) - (data["start"] != "0")
        return SimpleNamespace(json=lambda: {"data": [{"transactionDateStr": d} for d in days[s:s + 100]]})
    monkeypatch.setattr(saudiexchange, "xhr", site)
    assert [r["transactionDateStr"] for r in saudiexchange.get_price_history("1120", limit=500)] == days


def test_price_history_index(monkeypatch):
    fake(monkeypatch, "{}")
    sent = []
    monkeypatch.setattr(saudiexchange, "xhr", lambda *a, data, **kw: sent.append(data) or SimpleNamespace(
        json=lambda: {"data": [{"transactionDateStr": "2026/10/29", "volumeTraded": "254,305,649",
                                                  "previousClosePrice": "9,921.50"}]}))
    row = saudiexchange.get_price_history("TASI")[0]
    assert row["volumeTraded"] == "254,305,649" and row["close"] == "9,921.50" and "previousClosePrice" not in row
    assert sent[0]["selectedMarket"] == "INDICES" and sent[0]["selectedEntity"] == "M:TASI"
    monkeypatch.setattr(saudiexchange, "xhr", lambda *a, **kw: SimpleNamespace(json=lambda: {"data": []}))
    with pytest.raises(ValueError):
        saudiexchange.get_price_history("NOPE")


def test_screen_valuations_tags_sectors(monkeypatch):
    fake(monkeypatch, """<p>Main Market 2026/10/26</p><table><thead><th>Symbol</th><th>Company</th><th>Close</th>
    <th>Shares</th><th>NI</th><th>Equity</th><th>Cap</th><th>%</th><th>EPS</th><th>P/E</th><th>BV</th><th>P/B</th></thead>
    <tr><td>2030</td><td>SARCO</td><td>46.26</td><td>15</td><td>-41</td><td>278</td><td>693</td><td>0.01</td><td>-2.7</td>
    <td>M</td><td>18.5</td><td>2.49</td></tr>
    <tr><td colspan="2">Energy</td><td></td><td>15</td><td>-41</td><td>278</td><td>693</td><td>0.01</td><td>-2.7</td>
    <td>M</td><td>18.5</td><td>2.49</td></tr>
    <tr><td>1010</td><td>RIBL</td><td>19.3</td><td>4000</td><td>10590</td><td>67498</td><td>77200</td><td>0.86</td>
    <td>2.6</td><td>7.2</td><td>16.8</td><td>1.14</td></tr>
    <tr><td colspan="2">Banks</td><td></td><td>4000</td><td>10590</td><td>67498</td><td>77200</td><td>0.86</td><td>2.6</td>
    <td>7.2</td><td>16.8</td><td>1.14</td></tr>
    <tr><td>Market</td><td></td><td></td><td>4015</td><td>10549</td><td>67776</td><td>77893</td><td></td><td>2.6</td>
    <td>7.4</td><td>16.8</td><td>1.15</td></tr></table>""")
    banks = saudiexchange.screen_valuations("bank")
    assert banks["as_of"] == "2026-10-26"
    assert [(s["Symbol"], s["P/E"], s["sector"]) for s in banks["stocks"]] == [("1010", "7.2", "Banks")]
    assert banks["sectors"] == [{"sector": "Banks", "Shares": "4000", "NI": "10590", "Equity": "67498", "Cap": "77200",
                                 "%": "0.86", "EPS": "2.6", "P/E": "7.2", "BV": "16.8", "P/B": "1.14"}]
    assert saudiexchange.screen_valuations()["sectors"][-1]["P/E"] == "7.4"
    with pytest.raises(ValueError):
        saudiexchange.screen_valuations("Mining")


def test_short_interest_filters_symbol(monkeypatch):
    fake(monkeypatch, """Last Update Date : 2026-10-26<table><tr><th>Symbol</th><th>Company</th><th>% lent</th></tr>
    <tr><td>1010</td><td>Riyad Bank</td><td>0.01</td></tr><tr><td>1020</td><td>Bank Aljazira</td><td>0.26</td></tr></table>""")
    assert saudiexchange.get_short_interest("1020")["lending"] == {
        "as_of": "2026-10-26", "rows": [{"Symbol": "1020", "Company": "Bank Aljazira", "% lent": "0.26"}]}


def test_risk_flags(monkeypatch):
    fake(monkeypatch, "{}")
    data = {"getAccumulatedLossesDetails": [{"symbol": "6090", "company": "Jazan", "companyStatus": 3}],
            "getSuspendedDelistedComp": [{"symbol": "8190", "fromDate": "2026-09-13"}],
            "getMainMarketMinimumSizeRequirements": [
                {"col1": {"symbolCode": "6090", "tierValue": 1}, "col2": {"symbolCode": "", "tierValue": 0}, "col3": None}]}
    monkeypatch.setattr(saudiexchange, "issuers", lambda name, **kw: data[name])
    assert saudiexchange.get_risk_flags("6090") == {
        "accumulated_losses": [{"symbol": "6090", "company": "Jazan", "losses_of_capital": "50%+"}],
        "suspensions": [], "liquidity_tier": {"6090": 1}}


def test_announcement_splits_tables_from_text(monkeypatch):
    fake(monkeypatch, """<div class="article_body"><table><tr><td>Sales</td><td>450.77</td></tr></table>
    <p>All figures are in (Billions)</p><a href="/Resources/fsPdf/1_en.pdf">report</a></div>""")
    assert saudiexchange.get_announcement(97212) == {
        "tables": [[["Sales", "450.77"]]], "text": "All figures are in (Billions)\nreport",
        "attachments": ["https://www.saudiexchange.sa/Resources/fsPdf/1_en.pdf"]}
    fake(monkeypatch, "<div></div>")
    with pytest.raises(ValueError):
        saudiexchange.get_announcement(1)


def test_list_companies_by_sector(monkeypatch):
    fake(monkeypatch, "{}")
    monkeypatch.setattr(saudiexchange, "companies", lambda: [{"symbol": "1120"}, {"symbol": "8010"}, {"symbol": "X1"}])
    monkeypatch.setattr(saudiexchange, "market_watch", lambda: {"1120": {"sectorName": "Banks"},
                                                         "8010": {"sectorName": "Insurance"}})
    assert saudiexchange.list_companies(sector="bank") == [{"symbol": "1120", "sector": "Banks"}]
    assert len(saudiexchange.list_companies()) == 3
    with pytest.raises(ValueError):
        saudiexchange.list_companies(sector="Mining")


def test_statements_joins_recent_summary_and_older_tabs(monkeypatch):
    fake(monkeypatch, "")
    summary = "<tr><th>Balance Sheet</th><th>2025-12-31</th></tr><tr><td>Cash Flows</td><td></td></tr>"
    monkeypatch.setattr(saudiexchange, "profile_soup", lambda s: BeautifulSoup(
        f"<table></table><table>{summary}</table><table><tr><th>Balance Sheet</th><th>2022-12-31</th></tr></table>",
        "html.parser"))
    monkeypatch.setattr(saudiexchange, "statements_html", lambda s, t: f"<table><tr><td>type {t}</td></tr></table>")
    assert saudiexchange.get_statements("1120") == {
        "recent": [[["Balance Sheet", "2025-12-31"], ["Cash Flows", ""]]], "balance": [[["type 0"]]],
        "income": [[["type 1"]]], "cash_flow": [[["type 2"]]], "ratios": [[["type 3"]]]}
    assert list(saudiexchange.get_statements("1120", sections=["income", "recent"])) == ["recent", "income"]
    with pytest.raises(ValueError, match="balance"):
        saudiexchange.get_statements("1120", sections=["recnt"])


def test_market_sections(monkeypatch):
    reply = {"tasiValue": "9,921.50", "marketBean": {"noOfUps": 53, "noOfDowns": 212},
             "mainMarketActiveResultsBean": [1], "etfMarketBean": {"x": 1}, "marketWatchETFsBeans": [2]}
    fake(monkeypatch, json.dumps(reply))
    assert saudiexchange.get_market(["indices", "breadth"]) == {"breadth": reply["marketBean"], "tasiValue": "9,921.50"}
    assert saudiexchange.get_market(["etfs"]) == {"etfMarketBean": {"x": 1}, "marketWatchETFsBeans": [2]}
    assert saudiexchange.get_market() == {"breadth": reply["marketBean"]} | {k: v for k, v in reply.items() if k != "marketBean"}
    with pytest.raises(ValueError, match="valid: indices"):
        saudiexchange.get_market(["etf"])


ARGAAM_LIST = """<li class="Labelssearch_main" data-company="3509" data-market="3">
    <span class="searchingElements"id="3509_companylist" relf-Stocksymbol="2222" relf-fav="False" value="3509">
<li class="Labelssearch_main" data-company="4696" data-market="3">
    <span class="searchingElements"id="4696_companylist" relf-Stocksymbol="4082 " relf-fav="False" value="4696">
<li class="Labelssearch_main" data-company="4433" data-market="14">
    <span class="searchingElements"id="4433_companylist" relf-Stocksymbol="9564" relf-fav="False" value="4433">"""


def test_argaam_list_keeps_main_market_only():
    assert argaam_list(ARGAAM_LIST) == {"2222": 3509, "4082": 4696}


def test_argaam_id_reads_map_then_live_page(monkeypatch):
    fake(monkeypatch, ARGAAM_LIST)
    monkeypatch.setattr(news, "fetch", lambda url: ARGAAM_LIST)
    monkeypatch.setattr(news, "argaam_ids", lambda: {"1120": 43})
    assert news.argaam_id("4082") == 4696  # a new IPO missing from the map
    assert news.argaam_id("9564") is None  # Argaam lists it under Nomu only
    assert news.argaam_id("0000") is None
    monkeypatch.setattr(news, "fetch", lambda url: 1 / 0)
    assert news.argaam_id("1120") == 43  # a hit never reads the live page
