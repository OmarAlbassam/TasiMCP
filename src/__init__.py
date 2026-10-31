"""Saudi Exchange (Tadawul) MCP server. Scrapes saudiexchange.sa on demand, over stdio."""
from . import core, news, saudiexchange  # noqa: F401  (importing registers the @mcp.tool() functions)
from .core import mcp


def main():
    mcp.run()
