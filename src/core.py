import functools
import threading
import time
from datetime import date

from curl_cffi import requests
from mcp.server import MCPServer

# Akamai blocks non-browser TLS fingerprints, and the JSON endpoints 403 without XHR-style headers.
S = requests.Session(impersonate="chrome")
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


@cached(3600)
def fetch(url):
    return request("GET", url).text


def day(s, default):
    return date.fromisoformat(s) if s else default


mcp = MCPServer("tasi", instructions=(
    "Saudi Exchange (Tadawul) data scraped live from saudiexchange.sa. Symbols are 4-digit codes, e.g. 2222 "
    "(Saudi Aramco), 4002 (Mouwasat). Financial table figures are SAR thousands unless the table says otherwise. "
    "For P/E and market cap use get_valuation, not price / the site's EPS, which is wrong after bonus issues. "
    "For debt, loans and finance costs read the XBRL filings with get_xbrl."))
