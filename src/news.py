import json
import re
from pathlib import Path

from .core import fetch

# Every argaam.com page carries the full company search list; the RSS index is the smallest with no company slug.
ARGAAM = "https://www.argaam.com/en/rss"
ARGAAM_IDS = Path(__file__).with_name("argaam_ids.json")  # rewrite with update_argaam_ids.py


def argaam_list(html):
    """{Tadawul symbol: Argaam company id} for the Main market (data-market 3), from the search list on any
    argaam.com page. Nomu rows (market 14) are left out."""
    # some symbols carry a trailing space, e.g. "4082 "
    return {s: int(c) for c, s in re.findall(
        r'data-company="(\d+)" data-market="3">\s*<span[^>]*?relf-Stocksymbol="(\w+)\s*"', html)}


def argaam_ids():
    """The saved argaam_list(). A built wheel includes argaam_ids.json; if it is missing, argaam_id() looks every symbol up live."""
    try:
        return json.loads(ARGAAM_IDS.read_text())
    except FileNotFoundError:
        return {}


def argaam_id(symbol):
    """Argaam company id of a Main market symbol, or None if Argaam doesn't list it (news then comes from Mubasher
    only). A symbol missing from argaam_ids.json, such as a new IPO, is looked up on the live page."""
    return argaam_ids().get(symbol) or argaam_list(fetch(ARGAAM)).get(symbol)
