"""MCP tools for InspireHEP literature discovery and analysis."""

import json
import logging
from collections import Counter
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
# get_paper_figures
# ======================================================================

async def get_paper_figures(
    client: InspireHEPClient,
    inspire_id: str | None = None,
    arxiv_id: str | None = None,
    doi: str | None = None,
) -> str:
    """Retrieve figures for a specific paper.

    At least one identifier must be provided. The lookup order is:
    inspire_id > arxiv_id > doi.

    Args:
        client: The shared API client.
        inspire_id: InspireHEP record ID.
        arxiv_id: arXiv identifier (any format).
        doi: Digital Object Identifier (any format).

    Returns:
        JSON string with figures details for the LLM.
    """
    if not any([inspire_id, arxiv_id, doi]):
        return _format_error(
            ValueError("At least one identifier must be provided (inspire_id, arxiv_id, or doi)")
        )

    try:
        if inspire_id:
            nid = normalize_inspire_id(inspire_id)
            record = await client.get_literature_record(nid, fields="figures,titles")
        elif arxiv_id:
            nid = normalize_arxiv_id(arxiv_id)
            record = await client.get_literature_by_arxiv(nid, fields="figures,titles")
        else:
            assert doi is not None
            nid = normalize_doi(doi)
            record = await client.get_literature_by_doi(nid, fields="figures,titles")
    except NotFoundError:
        identifier = inspire_id or arxiv_id or doi
        return _format_error(NotFoundError("paper", str(identifier)))
    except (InvalidIdentifierError, InspireHEPError) as exc:
        return _format_error(exc)

    meta = record.get("metadata", {})
    titles = meta.get("titles", [])
    title = titles[0].get("title", "") if titles else ""
    inspire_url = f"https://inspirehep.net/literature/{record.get('id', '')}"
    
    raw_figures = meta.get("figures", [])
    figures = []
    
    for fig in raw_figures:
        figures.append({
            "caption": fig.get("caption", ""),
            "url": fig.get("url", ""),
            "description": fig.get("description", "")
        })

    result: dict[str, Any] = {
        "inspire_id": str(meta.get("control_number", record.get("id", ""))),
        "title": title,
        "inspire_url": inspire_url,
        "figures_count": len(figures),
        "figures": figures,
    }

    return json.dumps(result, indent=2)


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


# ======================================================================
# get_citations
# ======================================================================

async def get_citations(
    client: InspireHEPClient,
    inspire_id: str,
    direction: str = "citing",
    size: int = 50,
) -> str:
    """Retrieve citation graph data for a paper.

    Args:
        client: The shared API client.
        inspire_id: InspireHEP record ID.
        direction: "citing" (papers that cite this) or "cited_by" (papers this cites).
        size: Number of results (1-250).

    Returns:
        JSON string with citation list, total count, and year-by-year timeline.
    """
    valid_directions = {"citing", "cited_by"}
    if direction not in valid_directions:
        return _format_error(
            ValueError(f"Invalid direction '{direction}'. Must be one of: {', '.join(valid_directions)}")
        )

    try:
        nid = normalize_inspire_id(inspire_id)
    except InvalidIdentifierError as exc:
        return _format_error(exc)

    size = max(1, min(size, 250))

    try:
        if direction == "citing":
            # Papers that cite this paper
            raw = await client.search_literature(
                f"refersto:{nid}", sort="mostrecent", size=size
            )
        else:
            # Papers that this paper cites (its references)
            raw = await client.search_literature(
                f"citedby:recid:{nid}", sort="mostrecent", size=size
            )
    except InspireHEPError as exc:
        return _format_error(exc)

    hits = raw.get("hits", {})
    total = hits.get("total", 0)
    records = hits.get("hits", [])

    papers = [parse_paper_metadata(r) for r in records]

    # Build citation timeline (year → count)
    year_counts: Counter[str] = Counter()
    for p in papers:
        date = p.get("date", "")
        year = date[:4] if date and len(date) >= 4 else "unknown"
        year_counts[year] += 1
    timeline = dict(sorted(year_counts.items()))

    result: dict[str, Any] = {
        "inspire_id": nid,
        "direction": direction,
        "total_citations": total,
        "returned": len(papers),
        "timeline": timeline,
        "papers": papers,
    }
    return json.dumps(result, indent=2)


# ======================================================================
# search_by_collaboration
# ======================================================================

# Common collaboration name aliases
_COLLABORATION_ALIASES: dict[str, str] = {
    "lhcb": "LHCb",
    "atlas": "ATLAS",
    "cms": "CMS",
    "alice": "ALICE",
    "belle": "Belle",
    "belle ii": "Belle-II",
    "belle-ii": "Belle-II",
    "belle2": "Belle-II",
    "babar": "BaBar",
    "daya bay": "Daya Bay",
    "t2k": "T2K",
    "nova": "NOvA",
    "super-kamiokande": "Super-Kamiokande",
    "superkamiokande": "Super-Kamiokande",
    "super-k": "Super-Kamiokande",
    "planck": "Planck",
    "ligo": "LIGO Scientific",
    "virgo": "VIRGO",
    "xenon": "XENON",
    "darkside": "DarkSide",
    "fermi-lat": "Fermi-LAT",
    "ice cube": "IceCube",
    "icecube": "IceCube",
    "star": "STAR",
    "phenix": "PHENIX",
}


def _normalize_collaboration(name: str) -> str:
    """Normalize collaboration name using known aliases."""
    return _COLLABORATION_ALIASES.get(name.lower().strip(), name.strip())


async def search_by_collaboration(
    client: InspireHEPClient,
    collaboration_name: str,
    sort: str = "mostrecent",
    size: int = 20,
    year: int | None = None,
) -> str:
    """Find publications from a specific experimental collaboration.

    Args:
        client: The shared API client.
        collaboration_name: Collaboration name (e.g. "ATLAS", "CMS", "LHCb").
        sort: One of "mostrecent", "mostcited".
        size: Number of results (1-100).
        year: Optional year filter.

    Returns:
        JSON string with collaboration publications, stats, and key papers.
    """
    valid_sorts = {"mostrecent", "mostcited"}
    if sort not in valid_sorts:
        return _format_error(
            ValueError(f"Invalid sort option '{sort}'. Must be one of: {', '.join(valid_sorts)}")
        )

    size = max(1, min(size, 100))
    collab = _normalize_collaboration(collaboration_name)

    # Build query
    query = f"collaboration:{collab}"
    if year is not None:
        query += f" and date {year}"

    try:
        raw = await client.search_literature(query, sort=sort, size=size)
    except InspireHEPError as exc:
        return _format_error(exc)

    hits = raw.get("hits", {})
    total = hits.get("total", 0)
    records = hits.get("hits", [])

    papers = [parse_paper_metadata(r) for r in records]

    # Identify top-cited papers from the returned set
    top_cited = sorted(papers, key=lambda p: p.get("citation_count", 0), reverse=True)[:5]

    # Publication year distribution from returned papers
    year_counts: Counter[str] = Counter()
    for p in papers:
        date = p.get("date", "")
        y = date[:4] if date and len(date) >= 4 else "unknown"
        year_counts[y] += 1

    result: dict[str, Any] = {
        "collaboration": collab,
        "query": query,
        "total_publications": total,
        "returned": len(papers),
        "sort": sort,
        "year_filter": year,
        "statistics": {
            "year_distribution": dict(sorted(year_counts.items())),
            "total_citations": sum(p.get("citation_count", 0) for p in papers),
        },
        "top_cited_papers": [
            {
                "title": p["title"],
                "inspire_id": p["inspire_id"],
                "citation_count": p["citation_count"],
                "date": p["date"],
            }
            for p in top_cited
        ],
        "papers": papers,
    }
    return json.dumps(result, indent=2)


# ======================================================================
# get_references
# ======================================================================

async def get_references(
    client: InspireHEPClient,
    inspire_id: str,
    format: str = "bibtex",
    style: str | None = None,
) -> str:
    """Generate a formatted reference list for a paper.

    Args:
        client: The shared API client.
        inspire_id: InspireHEP record ID.
        format: Output format — "bibtex", "json", or "latex-us" / "latex-eu".
        style: Citation style hint (currently unused, reserved for future).

    Returns:
        JSON string containing the formatted references and metadata.
    """
    valid_formats = {"bibtex", "json", "latex-us", "latex-eu"}
    if format not in valid_formats:
        return _format_error(
            ValueError(f"Invalid format '{format}'. Must be one of: {', '.join(sorted(valid_formats))}")
        )

    try:
        nid = normalize_inspire_id(inspire_id)
    except InvalidIdentifierError as exc:
        return _format_error(exc)

    # First, get the paper's references as JSON to know what we're formatting
    try:
        record = await client.get_literature_record(nid, fields="references,titles")
    except NotFoundError:
        return _format_error(NotFoundError("paper", nid))
    except InspireHEPError as exc:
        return _format_error(exc)

    meta = record.get("metadata", {})
    refs = meta.get("references", [])
    title = ""
    titles = meta.get("titles", [])
    if titles:
        title = titles[0].get("title", "")

    if not refs:
        result: dict[str, Any] = {
            "inspire_id": nid,
            "paper_title": title,
            "total_references": 0,
            "format": format,
            "references": "",
            "note": "This paper has no references in InspireHEP.",
        }
        return json.dumps(result, indent=2)

    # Extract reference record IDs
    ref_recids: list[str] = []
    for ref in refs:
        rec_ref = ref.get("record", {}).get("$ref", "")
        if rec_ref:
            # Extract recid from URL like https://inspirehep.net/api/literature/84483
            parts = rec_ref.rstrip("/").split("/")
            if parts:
                ref_recids.append(parts[-1])

    if format == "json":
        # Return structured JSON reference data
        ref_data: list[dict[str, Any]] = []
        for ref in refs:
            entry: dict[str, Any] = {}
            refinfo = ref.get("reference", {})
            rec_ref = ref.get("record", {}).get("$ref", "")

            # Extract recid
            if rec_ref:
                parts = rec_ref.rstrip("/").split("/")
                entry["inspire_id"] = parts[-1] if parts else None
                entry["inspire_url"] = f"https://inspirehep.net/literature/{parts[-1]}"

            # Publication info from reference
            pub = refinfo.get("publication_info", {})
            if pub:
                entry["journal_title"] = pub.get("journal_title", "")
                entry["journal_volume"] = pub.get("journal_volume", "")
                entry["page_start"] = pub.get("page_start", "")
                entry["year"] = pub.get("year")

            # Authors
            authors = refinfo.get("authors", [])
            if authors:
                entry["authors"] = [a.get("full_name", "") for a in authors[:5]]

            # Title
            ref_title = refinfo.get("title", {})
            if isinstance(ref_title, dict):
                entry["title"] = ref_title.get("title", "")
            elif isinstance(ref_title, str):
                entry["title"] = ref_title

            # arXiv
            arxiv = refinfo.get("arxiv_eprint", "")
            if arxiv:
                entry["arxiv_id"] = arxiv

            # DOI
            dois = refinfo.get("dois", [])
            if dois:
                entry["doi"] = dois[0]

            if entry:
                ref_data.append(entry)

        result = {
            "inspire_id": nid,
            "paper_title": title,
            "total_references": len(refs),
            "format": "json",
            "references": ref_data,
        }
        return json.dumps(result, indent=2)

    # For bibtex / latex formats, fetch from the API for each referenced paper
    # Use the API's built-in formatting by fetching BibTeX for the paper's references
    # Strategy: fetch BibTeX for each referenced record (batch via search query)
    if ref_recids:
        # Build a query to get all references at once, then fetch formatted output
        recid_query = " or ".join(f"recid:{rid}" for rid in ref_recids[:250])
        try:
            formatted_text = await client.get_text(
                "/literature",
                params={"q": recid_query, "size": min(len(ref_recids), 250), "format": format},
            )
        except InspireHEPError as exc:
            return _format_error(exc)
    else:
        formatted_text = "% No resolvable references found."

    result = {
        "inspire_id": nid,
        "paper_title": title,
        "total_references": len(refs),
        "resolvable_references": len(ref_recids),
        "format": format,
        "references": formatted_text,
    }
    return json.dumps(result, indent=2)


# ======================================================================
# get_bibtex
# ======================================================================

async def get_bibtex(
    client: InspireHEPClient,
    identifier: str,
) -> str:
    """Retrieve the BibTeX citation entry for a paper.

    Accepts any common identifier format:
    - Inspire ID: "3456"
    - arXiv ID: "2301.12345", "hep-ph/0123456", or full URL
    - DOI: "10.1103/PhysRevLett.123.456789" or full URL

    Args:
        client: The shared API client.
        identifier: A DOI, arXiv ID, or InspireHEP record ID.

    Returns:
        JSON string containing the BibTeX entry and paper metadata.
    """
    # Detect identifier type and normalise
    try:
        id_type, normalised = detect_identifier_type(identifier)
    except InvalidIdentifierError as exc:
        return _format_error(exc)

    # Resolve to an Inspire record so we can get the recid
    try:
        if id_type == "inspire":
            record = await client.get_literature_record(normalised, fields="titles,texkeys")
        elif id_type == "arxiv":
            record = await client.get_literature_by_arxiv(normalised, fields="titles,texkeys")
        elif id_type == "doi":
            record = await client.get_literature_by_doi(normalised, fields="titles,texkeys")
        else:
            return _format_error(ValueError(f"Unsupported identifier type: {id_type}"))
    except NotFoundError:
        return _format_error(NotFoundError("paper", identifier))
    except InspireHEPError as exc:
        return _format_error(exc)

    meta = record.get("metadata", {})
    # For arXiv/DOI lookups record["id"] may be the arXiv ID or DOI,
    # so prefer control_number which is always the numeric Inspire recid.
    recid = str(meta.get("control_number", record.get("id", "")))
    title = ""
    titles = meta.get("titles", [])
    if titles:
        title = titles[0].get("title", "")
    texkeys = meta.get("texkeys", [])
    texkey = texkeys[0] if texkeys else None

    if not recid:
        return _format_error(ValueError("Could not determine Inspire record ID for this paper."))

    # Fetch BibTeX formatted text
    try:
        bibtex_text = await client.get_text(
            f"/literature/{recid}",
            params={"format": "bibtex"},
        )
    except InspireHEPError as exc:
        return _format_error(exc)

    result: dict[str, Any] = {
        "inspire_id": recid,
        "identifier": identifier,
        "identifier_type": id_type,
        "paper_title": title,
        "texkey": texkey,
        "bibtex": bibtex_text.strip(),
    }
    return json.dumps(result, indent=2)
