"""Utility functions for ID normalization and response parsing."""

import re

from .errors import InvalidIdentifierError

# arXiv ID patterns
# New style: YYMM.NNNNN (with optional vN version suffix)
_ARXIV_NEW_RE = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")
# Old style: archive/YYMMNNN (with optional vN version suffix)
_ARXIV_OLD_RE = re.compile(r"^([a-z-]+/\d{7})(v\d+)?$")
# Full arXiv URL
_ARXIV_URL_RE = re.compile(r"arxiv\.org/abs/(.+?)(?:v\d+)?$")

# DOI pattern
_DOI_RE = re.compile(r"^10\.\d{4,9}/[^\s]+$")
# DOI URL
_DOI_URL_RE = re.compile(r"doi\.org/(10\.\d{4,9}/[^\s]+)$")

# Inspire ID: purely numeric
_INSPIRE_ID_RE = re.compile(r"^\d+$")


def normalize_arxiv_id(raw: str) -> str:
    """Normalize an arXiv identifier to its canonical form (without version).

    Accepts: '2301.12345', '2301.12345v2', 'hep-ph/0123456',
             'https://arxiv.org/abs/2301.12345'

    Returns the bare ID, e.g. '2301.12345' or 'hep-ph/0123456'.
    Raises InvalidIdentifierError if the format is unrecognised.
    """
    raw = raw.strip()

    # Try URL first
    url_match = _ARXIV_URL_RE.search(raw)
    if url_match:
        raw = url_match.group(1)

    # Strip version suffix for matching
    if _ARXIV_NEW_RE.match(raw):
        return _ARXIV_NEW_RE.match(raw).group(1)  # type: ignore[union-attr]
    if _ARXIV_OLD_RE.match(raw):
        return _ARXIV_OLD_RE.match(raw).group(1)  # type: ignore[union-attr]

    raise InvalidIdentifierError("arXiv", raw)


def normalize_doi(raw: str) -> str:
    """Normalize a DOI to its canonical form (without URL prefix).

    Accepts: '10.1103/PhysRevLett.123.456789',
             'https://doi.org/10.1103/PhysRevLett.123.456789'

    Returns the bare DOI string.
    Raises InvalidIdentifierError if the format is unrecognised.
    """
    raw = raw.strip()

    # Try URL first
    url_match = _DOI_URL_RE.search(raw)
    if url_match:
        raw = url_match.group(1)

    if _DOI_RE.match(raw):
        return raw

    raise InvalidIdentifierError("DOI", raw)


def normalize_inspire_id(raw: str) -> str:
    """Normalize an InspireHEP record ID (purely numeric).

    Raises InvalidIdentifierError if not numeric.
    """
    raw = raw.strip()
    if _INSPIRE_ID_RE.match(raw):
        return raw
    raise InvalidIdentifierError("Inspire", raw)


def detect_identifier_type(raw: str) -> tuple[str, str]:
    """Detect the type of a literature identifier and return (type, normalized_value).

    Returns one of: ('inspire', id), ('arxiv', id), ('doi', id).
    Raises InvalidIdentifierError if the format cannot be determined.
    """
    raw = raw.strip()

    # DOI always starts with 10. or contains doi.org
    if raw.startswith("10.") or "doi.org/" in raw:
        return ("doi", normalize_doi(raw))

    # arXiv URL
    if "arxiv.org" in raw:
        return ("arxiv", normalize_arxiv_id(raw))

    # Old-style arXiv (contains /)
    if "/" in raw and _ARXIV_OLD_RE.match(raw.split("v")[0] if "v" in raw else raw):
        return ("arxiv", normalize_arxiv_id(raw))

    # New-style arXiv (YYMM.NNNNN)
    if "." in raw and _ARXIV_NEW_RE.match(raw.split("v")[0] if "v" in raw else raw):
        return ("arxiv", normalize_arxiv_id(raw))

    # Pure numeric → Inspire ID
    if _INSPIRE_ID_RE.match(raw):
        return ("inspire", raw)

    raise InvalidIdentifierError("unknown", raw)


def parse_paper_metadata(record: dict) -> dict:
    """Extract a standardised paper metadata dict from an InspireHEP API record.

    The input `record` is a single element from the API's `hits.hits` array,
    i.e. it has top-level keys like 'id', 'metadata', 'links', etc.
    """
    meta = record.get("metadata", {})

    # Authors – keep first 10 + total count
    raw_authors = meta.get("authors", [])
    authors = [
        {
            "full_name": a.get("full_name", ""),
            "affiliations": [
                aff.get("value", "") for aff in a.get("affiliations", [])
            ],
        }
        for a in raw_authors[:10]
    ]

    # arXiv eprint
    arxiv_eprints = meta.get("arxiv_eprints", [])
    arxiv_id = arxiv_eprints[0].get("value", "") if arxiv_eprints else None
    arxiv_categories = arxiv_eprints[0].get("categories", []) if arxiv_eprints else []

    # DOIs
    dois = meta.get("dois", [])
    doi = dois[0].get("value", "") if dois else None

    # Publication info
    pub_info = meta.get("publication_info", [])
    publication = None
    if pub_info:
        p = pub_info[0]
        publication = {
            "journal_title": p.get("journal_title", ""),
            "journal_volume": p.get("journal_volume", ""),
            "page_start": p.get("page_start", ""),
            "year": p.get("year"),
        }

    # Collaborations
    collaborations = [c.get("value", "") for c in meta.get("collaborations", [])]

    # Citation count
    citation_count = meta.get("citation_count", 0)

    # Abstracts
    abstracts = meta.get("abstracts", [])
    abstract = abstracts[0].get("value", "") if abstracts else ""

    # Earliest date
    earliest_date = meta.get("earliest_date", meta.get("legacy_creation_date", ""))

    return {
        "inspire_id": str(record.get("id", "")),
        "title": meta.get("titles", [{}])[0].get("title", "") if meta.get("titles") else "",
        "authors": authors,
        "total_authors": len(raw_authors),
        "abstract": abstract,
        "arxiv_id": arxiv_id,
        "arxiv_categories": arxiv_categories,
        "doi": doi,
        "publication": publication,
        "collaborations": collaborations,
        "citation_count": citation_count,
        "date": earliest_date,
        "inspire_url": f"https://inspirehep.net/literature/{record.get('id', '')}",
    }
