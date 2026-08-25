"""InspireHEP MCP Server - main entry point."""

import json
from typing import Any
import logging

from mcp.server.mcpserver import MCPServer

from . import __version__
from .api_client import InspireHEPClient
from .config import settings
from .tools import get_author_papers as _get_author_papers
from .tools import get_bibtex as _get_bibtex
from .tools import get_citations as _get_citations
from .tools import get_paper_details as _get_paper_details
from .tools import get_paper_figures as _get_paper_figures
from .tools import get_references as _get_references
from .tools import search_by_collaboration as _search_by_collaboration
from .tools import search_papers as _search_papers

logger = logging.getLogger(__name__)

mcp = MCPServer(
    "InspireHEP",
    title="InspireHEP Literature Server",
    description="Search and retrieve high-energy physics literature from InspireHEP",
    instructions=(
        "MCP server for searching and retrieving high-energy physics literature "
        "from InspireHEP. Use search_papers to find papers, then get_paper_details, "
        "get_citations, get_references, or get_bibtex with a resolved identifier."
    ),
    version=__version__,
)

# Shared API client instance
api_client = InspireHEPClient()

# All tools are pure read-only lookups against the public InspireHEP API.
_READ_ONLY = {"readOnlyHint": True, "idempotentHint": True}


def _structured(result: str) -> dict:
    """Decode a JSON payload from the tools layer into structured output."""
    return json.loads(result)


# ------------------------------------------------------------------
# Tool registrations
# ------------------------------------------------------------------


@mcp.tool(title="Ping", annotations=_READ_ONLY)
async def ping() -> str:
    """Check that the InspireHEP MCP server is running."""
    return "InspireHEP MCP server is running."


@mcp.tool(title="Server Stats", annotations=_READ_ONLY)
async def server_stats() -> dict[str, Any]:
    """Return cache and request performance statistics for the server.

    Useful for monitoring cache hit rates, request counts, and
    average response times. No parameters required.
    """
    return _structured(json.dumps(api_client.full_stats))


@mcp.tool(title="Search Papers", annotations=_READ_ONLY)
async def search_papers(
    query: str,
    sort: str = "bestmatch",
    size: int = 10,
) -> dict[str, Any]:
    """Search InspireHEP for papers matching a query.

    Supports free-text and field-specific queries such as:
    - "dark matter direct detection"
    - "author:ellis title:higgs"
    - "collaboration:ATLAS supersymmetry"
    - "find a weinberg and t electroweak"

    Args:
        query: Search query string.
        sort: Sort order — "bestmatch", "mostrecent", or "mostcited".
        size: Number of results to return (1-100, default 10).
    """
    return _structured(await _search_papers(api_client, query, sort=sort, size=size))


@mcp.tool(title="Get Paper Details", annotations=_READ_ONLY)
async def get_paper_details(
    inspire_id: str | None = None,
    arxiv_id: str | None = None,
    doi: str | None = None,
) -> dict[str, Any]:
    """Retrieve detailed metadata for a specific paper.

    Provide at least one identifier. Accepts multiple formats:
    - inspire_id: "3456"
    - arxiv_id: "arxiv:2301.12345", "arxiv:hep-ph/0123456", or full URL
    - doi: "10.1103/PhysRevLett.123.456789" or full URL

    Returns title, authors, abstract, citations, references count,
    publication info, keywords, URLs, and more.
    """
    return _structured(
        await _get_paper_details(
            api_client, inspire_id=inspire_id, arxiv_id=arxiv_id, doi=doi
        )
    )


@mcp.tool(title="Get Paper Figures", annotations=_READ_ONLY)
async def get_paper_figures(
    inspire_id: str | None = None,
    arxiv_id: str | None = None,
    doi: str | None = None,
) -> dict[str, Any]:
    """Retrieve figures for a specific paper.

    Provide at least one identifier. Accepts multiple formats:
    - inspire_id: "3456"
    - arxiv_id: "arxiv:2301.12345", "arxiv:hep-ph/0123456", or full URL
    - doi: "10.1103/PhysRevLett.123.456789" or full URL

    Returns title, inspire url, and a list of figures with their captions,
    descriptions and direct download URLs.
    """
    return _structured(
        await _get_paper_figures(
            api_client, inspire_id=inspire_id, arxiv_id=arxiv_id, doi=doi
        )
    )


@mcp.tool(title="Get Author Papers", annotations=_READ_ONLY)
async def get_author_papers(
    author_name: str | None = None,
    author_id: str | None = None,
    sort: str = "mostrecent",
    size: int = 20,
) -> dict[str, Any]:
    """Retrieve publication history and citation metrics for an author.

    Provide either author_name or author_id:
    - author_name: "Weinberg, Steven" (Last, First format)
    - author_id: "S.Weinberg.1" (InspireHEP BAI)

    Returns a list of papers plus aggregate metrics including
    total citations, h-index, and average citations per paper.

    Args:
        author_name: Author name in "Last, First" format.
        author_id: InspireHEP author identifier (BAI).
        sort: Sort order — "mostrecent" or "mostcited".
        size: Number of papers to return (1-100, default 20).
    """
    return _structured(
        await _get_author_papers(
            api_client,
            author_name=author_name,
            author_id=author_id,
            sort=sort,
            size=size,
        )
    )


@mcp.tool(title="Get Citations", annotations=_READ_ONLY)
async def get_citations(
    inspire_id: str,
    direction: str = "citing",
    size: int = 50,
) -> dict[str, Any]:
    """Retrieve citation graph data for a paper.

    Args:
        inspire_id: InspireHEP record ID (numeric).
        direction: "citing" (papers that cite this) or "cited_by" (papers this cites).
        size: Number of results to return (1–250, default 50).

    Returns citation list with metadata, total count, and a
    year-by-year citation timeline.
    """
    return _structured(
        await _get_citations(
            api_client, inspire_id=inspire_id, direction=direction, size=size
        )
    )


@mcp.tool(title="Search by Collaboration", annotations=_READ_ONLY)
async def search_by_collaboration(
    collaboration_name: str,
    sort: str = "mostrecent",
    size: int = 20,
    year: int | None = None,
) -> dict[str, Any]:
    """Find publications from a specific experimental collaboration.

    Handles common name variations (e.g. "lhcb" → "LHCb").

    Args:
        collaboration_name: Collaboration name (e.g. "ATLAS", "CMS", "LHCb", "Belle-II").
        sort: Sort order — "mostrecent" or "mostcited".
        size: Number of results to return (1–100, default 20).
        year: Optional year filter (e.g. 2024).

    Returns publication list, year distribution, total citations,
    and top-cited papers from the returned set.
    """
    return _structured(
        await _search_by_collaboration(
            api_client,
            collaboration_name=collaboration_name,
            sort=sort,
            size=size,
            year=year,
        )
    )


@mcp.tool(title="Get References", annotations=_READ_ONLY)
async def get_references(
    inspire_id: str,
    format: str = "bibtex",
) -> dict[str, Any]:
    """Generate a formatted reference list for a paper.

    Args:
        inspire_id: InspireHEP record ID (numeric).
        format: Output format — "bibtex", "json", "latex-us", or "latex-eu".

    Returns the reference list in the requested format along with
    total reference count and paper title.
    """
    return _structured(await _get_references(api_client, inspire_id=inspire_id, format=format))


@mcp.tool(title="Get BibTeX", annotations=_READ_ONLY)
async def get_bibtex(
    identifier: str,
) -> dict[str, Any]:
    """Retrieve the BibTeX citation entry for a paper.

    Accepts any common identifier format:
    - Inspire ID: "3456"
    - arXiv ID: "arxiv:2301.12345", "arxiv:hep-ph/0123456", or full URL
    - DOI: "10.1103/PhysRevLett.123.456789" or full URL

    Args:
        identifier: A DOI, arXiv ID, or InspireHEP record ID.

    Returns the BibTeX entry along with paper title, texkey, and
    the resolved Inspire record ID.
    """
    return _structured(await _get_bibtex(api_client, identifier=identifier))


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main() -> None:
    """Run the InspireHEP MCP server over stdio."""
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.info("Starting InspireHEP MCP server...")
    logger.info(
        "Config: cache_persistent=%s, cache_ttl=%s, rate_limit=%.1f req/s",
        settings.cache_persistent,
        settings.cache_ttl,
        settings.requests_per_second,
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
