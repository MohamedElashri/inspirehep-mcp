"""InspireHEP MCP Server - stdio and Streamable HTTP entry point."""

import argparse
import json
import logging
import math
from collections.abc import Sequence
from typing import Any

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .api_client import InspireHEPClient
from .config import settings
from .rate_limit import RateLimitMiddleware, RequestBodyLimitMiddleware
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


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health_check(_: Request) -> JSONResponse:
    """Return a lightweight health response without calling InspireHEP."""
    return JSONResponse(
        {"status": "ok", "service": "inspirehep-mcp", "version": __version__}
    )


# ------------------------------------------------------------------
# Tool registrations
# ------------------------------------------------------------------


@mcp.tool(title="Ping", annotations=_READ_ONLY)
async def ping() -> str:
    """Check that the InspireHEP MCP server is running."""
    return "InspireHEP MCP server is running."


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


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the InspireHEP MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=settings.transport,
        help="MCP transport (default: INSPIREHEP_TRANSPORT or stdio)",
    )
    parser.add_argument("--host", default=settings.host, help="HTTP bind address")
    parser.add_argument("--port", default=settings.port, type=int, help="HTTP port")
    parser.add_argument(
        "--path", default=settings.http_path, help="Streamable HTTP endpoint path"
    )
    parser.add_argument(
        "--stateless-http",
        action=argparse.BooleanOptionalAction,
        default=settings.http_stateless,
        help="Use independent stateless HTTP requests",
    )
    parser.add_argument(
        "--json-response",
        action=argparse.BooleanOptionalAction,
        default=settings.http_json_response,
        help="Return JSON instead of opening an SSE stream when possible",
    )
    parser.add_argument(
        "--rate-limit",
        default=settings.http_rate_limit,
        type=float,
        help="Per-client HTTP requests per minute; 0 disables the limit",
    )
    parser.add_argument(
        "--rate-limit-burst",
        default=settings.http_rate_limit_burst,
        type=int,
        help="Maximum per-client HTTP request burst",
    )
    parser.add_argument(
        "--max-body-size",
        default=settings.http_max_body_size,
        type=int,
        help="Maximum MCP request body in bytes; 0 disables the limit",
    )
    parser.add_argument(
        "--max-concurrency",
        default=settings.http_max_concurrency,
        type=int,
        help="Maximum concurrent HTTP connections or tasks",
    )
    parser.add_argument(
        "--timeout-keep-alive",
        default=settings.http_keep_alive_timeout,
        type=int,
        help="Idle HTTP keep-alive timeout in seconds",
    )
    parser.add_argument(
        "--trust-proxy-headers",
        action=argparse.BooleanOptionalAction,
        default=settings.trust_proxy_headers,
        help="Use X-Forwarded-For for rate-limit identity",
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if args.transport not in ("stdio", "streamable-http"):
        parser.error("--transport must be 'stdio' or 'streamable-http'")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not math.isfinite(args.rate_limit) or args.rate_limit < 0:
        parser.error("--rate-limit must be a finite, non-negative number")
    if args.rate_limit_burst < 1:
        parser.error("--rate-limit-burst must be at least 1")
    if args.max_body_size < 0:
        parser.error("--max-body-size must be non-negative")
    if args.max_concurrency < 1:
        parser.error("--max-concurrency must be at least 1")
    if args.timeout_keep_alive < 0:
        parser.error("--timeout-keep-alive must be non-negative")
    if not args.path.startswith("/"):
        parser.error("--path must start with '/'")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    """Run the server, retaining stdio as the backward-compatible default."""
    args = _parse_args(argv)
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.info("Starting InspireHEP MCP server using %s", args.transport)
    logger.info(
        "Config: cache_persistent=%s, cache_ttl=%s, rate_limit=%.1f req/s",
        settings.cache_persistent,
        settings.cache_ttl,
        settings.requests_per_second,
    )
    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return

    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=settings.dns_rebinding_protection,
        allowed_hosts=settings.allowed_hosts,
        allowed_origins=settings.allowed_origins,
    )
    logger.info("MCP endpoint: http://%s:%d%s", args.host, args.port, args.path)
    logger.info(
        "HTTP rate limit: %.1f requests/minute, burst=%d",
        args.rate_limit,
        args.rate_limit_burst,
    )
    http_app = mcp.streamable_http_app(
        host=args.host,
        streamable_http_path=args.path,
        stateless_http=args.stateless_http,
        json_response=args.json_response,
        transport_security=transport_security,
    )
    body_limited_app = RequestBodyLimitMiddleware(
        http_app,
        max_body_size=args.max_body_size,
        path=args.path,
    )
    app = RateLimitMiddleware(
        body_limited_app,
        requests_per_minute=args.rate_limit,
        burst=args.rate_limit_burst,
        path=args.path,
        trust_proxy_headers=args.trust_proxy_headers,
        max_clients=settings.http_rate_limit_max_clients,
    )
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=settings.log_level.lower(),
        proxy_headers=False,
        limit_concurrency=args.max_concurrency,
        timeout_keep_alive=args.timeout_keep_alive,
    )


if __name__ == "__main__":
    main()
