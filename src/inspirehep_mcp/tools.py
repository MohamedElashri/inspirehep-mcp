"""Tier 1 MCP tools for InspireHEP literature discovery."""

import json
import logging
from typing import Any

from .api_client import InspireHEPClient
from .errors import APIError, InspireHEPError, InvalidIdentifierError, NotFoundError
from .utils import (
    detect_identifier_type,
    normalize_arxiv_id,
    normalize_doi,
    normalize_inspire_id,
    parse_paper_metadata,
)

logger = logging.getLogger(__name__)


def _format_error(err: Exception) -> str:
    """Format an exception into a user-friendly error string."""
    return json.dumps({"error": str(err)})


# ======================================================================
# search_papers
# ======================================================================

async def search_papers(
    client: InspireHEPClient,
    query: str,
    sort: str = "bestmatch",
    size: int = 10,
) -> str:
    """Search InspireHEP for papers matching a query.

    Supports field-specific queries like ``author:ellis``, ``title:higgs``,
    ``collaboration:ATLAS``, or free-text searches.

    Args:
        client: The shared API client.
        query: Search query string.
        sort: One of "bestmatch", "mostrecent", "mostcited".
        size: Number of results to return (1-100).

    Returns:
        JSON string with results for the LLM.
    """
    # Validate sort
    valid_sorts = {"bestmatch", "mostrecent", "mostcited"}
    if sort not in valid_sorts:
        return _format_error(
            ValueError(f"Invalid sort option '{sort}'. Must be one of: {', '.join(valid_sorts)}")
        )

    # Clamp size
    size = max(1, min(size, 100))

    try:
        raw = await client.search_literature(query, sort=sort, size=size)
    except InspireHEPError as exc:
        return _format_error(exc)

    hits = raw.get("hits", {})
    total = hits.get("total", 0)
    records = hits.get("hits", [])

    papers = [parse_paper_metadata(r) for r in records]

    result: dict[str, Any] = {
        "total_results": total,
        "returned": len(papers),
        "query": query,
        "sort": sort,
        "papers": papers,
    }
    return json.dumps(result, indent=2)


# ======================================================================
# get_paper_details
# ======================================================================

_DETAIL_FIELDS = ",".join(
    [
        "titles",
        "authors.full_name",
        "authors.affiliations",
        "authors.ids",
        "abstracts",
        "arxiv_eprints",
        "dois",
        "publication_info",
        "collaborations",
        "citation_count",
        "citation_count_without_self_citations",
        "earliest_date",
        "legacy_creation_date",
        "references",
        "documents",
        "urls",
        "keywords",
        "inspire_categories",
        "texkeys",
        "report_numbers",
        "document_type",
        "number_of_pages",
    ]
)


def _build_detail_response(record: dict) -> dict[str, Any]:
    """Build a rich detail dict from a full API record."""
    base = parse_paper_metadata(record)
    meta = record.get("metadata", {})

    # Expand author list for detail view (up to 50)
    raw_authors = meta.get("authors", [])
    base["authors"] = [
        {
            "full_name": a.get("full_name", ""),
            "affiliations": [
                aff.get("value", "") for aff in a.get("affiliations", [])
            ],
            "inspire_ids": [
                i.get("value", "")
                for i in a.get("ids", [])
                if i.get("schema") == "INSPIRE BAI"
            ],
        }
        for a in raw_authors[:50]
    ]
    base["total_authors"] = len(raw_authors)

    # References summary
    refs = meta.get("references", [])
    base["references_count"] = len(refs)

    # Citation counts
    base["citation_count_without_self_citations"] = meta.get(
        "citation_count_without_self_citations", 0
    )

    # Document type
    base["document_type"] = meta.get("document_type", [])

    # Keywords
    keywords = meta.get("keywords", [])
    base["keywords"] = [k.get("value", "") for k in keywords if k.get("value")]

    # Inspire categories
    categories = meta.get("inspire_categories", [])
    base["inspire_categories"] = [c.get("term", "") for c in categories]

    # TeXkeys
    texkeys = meta.get("texkeys", [])
    base["texkey"] = texkeys[0] if texkeys else None

    # Report numbers
    report_numbers = meta.get("report_numbers", [])
    base["report_numbers"] = [r.get("value", "") for r in report_numbers]

    # Number of pages
    base["number_of_pages"] = meta.get("number_of_pages")

    # URLs
    urls: dict[str, str | None] = {}
    arxiv_id = base.get("arxiv_id")
    if arxiv_id:
        urls["arxiv_abs"] = f"https://arxiv.org/abs/{arxiv_id}"
        urls["arxiv_pdf"] = f"https://arxiv.org/pdf/{arxiv_id}"
    doi = base.get("doi")
    if doi:
        urls["doi"] = f"https://doi.org/{doi}"
    docs = meta.get("documents", [])
    if docs:
        urls["fulltext"] = docs[0].get("url")
    urls["inspire"] = base["inspire_url"]

    # Links from API (bibtex, latex, etc.)
    links = record.get("links", {})
    if links.get("bibtex"):
        urls["bibtex"] = links["bibtex"]

    base["urls"] = urls

    return base


async def get_paper_details(
    client: InspireHEPClient,
    inspire_id: str | None = None,
    arxiv_id: str | None = None,
    doi: str | None = None,
) -> str:
    """Retrieve detailed metadata for a specific paper.

    At least one identifier must be provided. The lookup order is:
    inspire_id > arxiv_id > doi.

    Args:
        client: The shared API client.
        inspire_id: InspireHEP record ID.
        arxiv_id: arXiv identifier (any format).
        doi: Digital Object Identifier (any format).

    Returns:
        JSON string with full paper details for the LLM.
    """
    if not any([inspire_id, arxiv_id, doi]):
        return _format_error(
            ValueError("At least one identifier must be provided (inspire_id, arxiv_id, or doi)")
        )

    try:
        if inspire_id:
            nid = normalize_inspire_id(inspire_id)
            record = await client.get_literature_record(nid, fields=_DETAIL_FIELDS)
        elif arxiv_id:
            nid = normalize_arxiv_id(arxiv_id)
            record = await client.get_literature_by_arxiv(nid, fields=_DETAIL_FIELDS)
        else:
            assert doi is not None
            nid = normalize_doi(doi)
            record = await client.get_literature_by_doi(nid, fields=_DETAIL_FIELDS)
    except NotFoundError:
        identifier = inspire_id or arxiv_id or doi
        return _format_error(NotFoundError("paper", str(identifier)))
    except (InvalidIdentifierError, InspireHEPError) as exc:
        return _format_error(exc)

    detail = _build_detail_response(record)
    return json.dumps(detail, indent=2)


# ======================================================================
# get_author_papers
# ======================================================================

def _compute_h_index(citation_counts: list[int]) -> int:
    """Compute the h-index from a list of citation counts."""
    sorted_counts = sorted(citation_counts, reverse=True)
    h = 0
    for i, c in enumerate(sorted_counts):
        if c >= i + 1:
            h = i + 1
        else:
            break
    return h


async def _resolve_author_bai(client: InspireHEPClient, author_name: str) -> tuple[str, dict[str, Any]]:
    """Resolve an author name to a BAI via the authors API.

    Returns (bai_string, author_info_dict).
    Falls back to the raw name if no match is found.
    """
    try:
        result = await client.search_authors(author_name, size=1)
        hits = result.get("hits", {}).get("hits", [])
        if hits:
            meta = hits[0].get("metadata", {})
            name_info = meta.get("name", {})
            # Extract BAI
            ids = meta.get("ids", [])
            bai_entries = [i for i in ids if i.get("schema") == "INSPIRE BAI"]
            if bai_entries:
                bai = bai_entries[0]["value"]
                author_info = {
                    "name": name_info.get("value", author_name),
                    "preferred_name": name_info.get("preferred_name", ""),
                    "bai": bai,
                    "inspire_author_id": str(hits[0].get("id", "")),
                }
                return bai, author_info
    except InspireHEPError:
        pass  # Fall back to raw name

    return author_name, {"name": author_name, "bai": None, "inspire_author_id": None}


async def get_author_papers(
    client: InspireHEPClient,
    author_name: str | None = None,
    author_id: str | None = None,
    sort: str = "mostrecent",
    size: int = 20,
) -> str:
    """Retrieve publication history and metrics for an author.

    Provide either ``author_name`` (e.g. "Weinberg, Steven") or
    ``author_id`` (InspireHEP BAI like "Steven.Weinberg.1").

    When ``author_name`` is given, the tool first resolves it to a BAI
    via the authors API for accurate disambiguation.

    Args:
        client: The shared API client.
        author_name: Author name in "Last, First" format.
        author_id: InspireHEP author identifier (BAI).
        sort: One of "mostrecent", "mostcited".
        size: Number of papers to return (1-100).

    Returns:
        JSON string with publication list and aggregate metrics.
    """
    if not any([author_name, author_id]):
        return _format_error(
            ValueError("Either author_name or author_id must be provided")
        )

    valid_sorts = {"mostrecent", "mostcited"}
    if sort not in valid_sorts:
        return _format_error(
            ValueError(f"Invalid sort option '{sort}'. Must be one of: {', '.join(valid_sorts)}")
        )

    size = max(1, min(size, 100))

    # Resolve author to BAI for accurate results
    author_info: dict[str, Any] = {}
    if author_id:
        query = f"a {author_id}"
        author_info = {"bai": author_id}
    else:
        assert author_name is not None
        bai, author_info = await _resolve_author_bai(client, author_name)
        query = f"a {bai}"

    try:
        raw = await client.search_literature(query, sort=sort, size=size)
    except InspireHEPError as exc:
        return _format_error(exc)

    hits = raw.get("hits", {})
    total = hits.get("total", 0)
    records = hits.get("hits", [])

    papers = [parse_paper_metadata(r) for r in records]

    # Aggregate metrics from returned papers
    citation_counts = [p.get("citation_count", 0) for p in papers]
    total_citations = sum(citation_counts)
    h_index = _compute_h_index(citation_counts)

    result: dict[str, Any] = {
        "author": author_info,
        "total_papers": total,
        "returned": len(papers),
        "sort": sort,
        "metrics": {
            "total_citations": total_citations,
            "h_index": h_index,
            "h_index_note": (
                f"Computed from the {len(papers)} returned papers"
                if len(papers) < total
                else "Computed from all papers"
            ),
            "average_citations": round(total_citations / len(papers), 1) if papers else 0,
        },
        "papers": papers,
    }
    return json.dumps(result, indent=2)
