"""InspireHEP MCP Server - main entry point."""

import logging

from mcp.server.fastmcp import FastMCP

from .api_client import InspireHEPClient
from .tools import get_author_papers as _get_author_papers
from .tools import get_paper_details as _get_paper_details
from .tools import search_papers as _search_papers

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "InspireHEP",
    instructions="MCP server for searching and retrieving high-energy physics literature from InspireHEP",
)

# Shared API client instance
api_client = InspireHEPClient()


# ------------------------------------------------------------------
# Tool registrations
# ------------------------------------------------------------------


@mcp.tool()
async def ping() -> str:
    """Check that the InspireHEP MCP server is running."""
    return "InspireHEP MCP server is running."


@mcp.tool()
async def search_papers(
    query: str,
    sort: str = "bestmatch",
    size: int = 10,
) -> str:
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
    return await _search_papers(api_client, query, sort=sort, size=size)


@mcp.tool()
async def get_paper_details(
    inspire_id: str | None = None,
    arxiv_id: str | None = None,
    doi: str | None = None,
) -> str:
    """Retrieve detailed metadata for a specific paper.

    Provide at least one identifier. Accepts multiple formats:
    - inspire_id: "3456"
    - arxiv_id: "2301.12345", "hep-ph/0123456", or full URL
    - doi: "10.1103/PhysRevLett.123.456789" or full URL

    Returns title, authors, abstract, citations, references count,
    publication info, keywords, URLs, and more.
    """
    return await _get_paper_details(
        api_client, inspire_id=inspire_id, arxiv_id=arxiv_id, doi=doi
    )


@mcp.tool()
async def get_author_papers(
    author_name: str | None = None,
    author_id: str | None = None,
    sort: str = "mostrecent",
    size: int = 20,
) -> str:
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
    return await _get_author_papers(
        api_client, author_name=author_name, author_id=author_id, sort=sort, size=size
    )


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main() -> None:
    """Run the InspireHEP MCP server."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting InspireHEP MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
