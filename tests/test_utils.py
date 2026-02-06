"""Unit tests for ID normalization and response parsing utilities."""

import pytest

from inspirehep_mcp.errors import InvalidIdentifierError
from inspirehep_mcp.utils import (
    detect_identifier_type,
    normalize_arxiv_id,
    normalize_doi,
    normalize_inspire_id,
    parse_paper_metadata,
)


# ======================================================================
# normalize_arxiv_id
# ======================================================================


class TestNormalizeArxivId:
    def test_new_style(self):
        assert normalize_arxiv_id("2301.12345") == "2301.12345"

    def test_new_style_5digit(self):
        assert normalize_arxiv_id("2301.12345") == "2301.12345"

    def test_new_style_with_version(self):
        assert normalize_arxiv_id("2301.12345v2") == "2301.12345"

    def test_old_style(self):
        assert normalize_arxiv_id("hep-ph/0123456") == "hep-ph/0123456"

    def test_old_style_with_version(self):
        assert normalize_arxiv_id("hep-ph/0123456v1") == "hep-ph/0123456"

    def test_url_new_style(self):
        assert normalize_arxiv_id("https://arxiv.org/abs/2301.12345") == "2301.12345"

    def test_url_old_style(self):
        assert normalize_arxiv_id("https://arxiv.org/abs/hep-ph/0123456") == "hep-ph/0123456"

    def test_url_with_version(self):
        assert normalize_arxiv_id("https://arxiv.org/abs/2301.12345v3") == "2301.12345"

    def test_whitespace_stripped(self):
        assert normalize_arxiv_id("  2301.12345  ") == "2301.12345"

    def test_invalid_raises(self):
        with pytest.raises(InvalidIdentifierError) as exc_info:
            normalize_arxiv_id("not-an-arxiv-id")
        assert exc_info.value.id_type == "arXiv"

    def test_empty_raises(self):
        with pytest.raises(InvalidIdentifierError):
            normalize_arxiv_id("")

    def test_other_archive_old_style(self):
        assert normalize_arxiv_id("astro-ph/0123456") == "astro-ph/0123456"


# ======================================================================
# normalize_doi
# ======================================================================


class TestNormalizeDoi:
    def test_bare_doi(self):
        assert normalize_doi("10.1103/PhysRevLett.123.456789") == "10.1103/PhysRevLett.123.456789"

    def test_doi_url(self):
        assert normalize_doi("https://doi.org/10.1103/PhysRevLett.123.456789") == "10.1103/PhysRevLett.123.456789"

    def test_whitespace_stripped(self):
        assert normalize_doi("  10.1103/PhysRevLett.123.456789  ") == "10.1103/PhysRevLett.123.456789"

    def test_invalid_raises(self):
        with pytest.raises(InvalidIdentifierError) as exc_info:
            normalize_doi("not-a-doi")
        assert exc_info.value.id_type == "DOI"

    def test_empty_raises(self):
        with pytest.raises(InvalidIdentifierError):
            normalize_doi("")

    def test_doi_with_special_chars(self):
        doi = "10.1007/JHEP01(2024)123"
        assert normalize_doi(doi) == doi


# ======================================================================
# normalize_inspire_id
# ======================================================================


class TestNormalizeInspireId:
    def test_numeric(self):
        assert normalize_inspire_id("3456") == "3456"

    def test_large_id(self):
        assert normalize_inspire_id("1234567") == "1234567"

    def test_whitespace_stripped(self):
        assert normalize_inspire_id("  3456  ") == "3456"

    def test_non_numeric_raises(self):
        with pytest.raises(InvalidIdentifierError) as exc_info:
            normalize_inspire_id("abc")
        assert exc_info.value.id_type == "Inspire"

    def test_mixed_raises(self):
        with pytest.raises(InvalidIdentifierError):
            normalize_inspire_id("123abc")

    def test_empty_raises(self):
        with pytest.raises(InvalidIdentifierError):
            normalize_inspire_id("")


# ======================================================================
# detect_identifier_type
# ======================================================================


class TestDetectIdentifierType:
    def test_doi_bare(self):
        assert detect_identifier_type("10.1103/PhysRevLett.123.456789") == (
            "doi",
            "10.1103/PhysRevLett.123.456789",
        )

    def test_doi_url(self):
        t, v = detect_identifier_type("https://doi.org/10.1103/PhysRevLett.123.456789")
        assert t == "doi"
        assert v == "10.1103/PhysRevLett.123.456789"

    def test_arxiv_new(self):
        assert detect_identifier_type("2301.12345") == ("arxiv", "2301.12345")

    def test_arxiv_old(self):
        assert detect_identifier_type("hep-ph/0123456") == ("arxiv", "hep-ph/0123456")

    def test_arxiv_url(self):
        t, v = detect_identifier_type("https://arxiv.org/abs/2301.12345")
        assert t == "arxiv"
        assert v == "2301.12345"

    def test_inspire_id(self):
        assert detect_identifier_type("3456") == ("inspire", "3456")

    def test_unknown_raises(self):
        with pytest.raises(InvalidIdentifierError) as exc_info:
            detect_identifier_type("random-string")
        assert exc_info.value.id_type == "unknown"


# ======================================================================
# parse_paper_metadata
# ======================================================================


class TestParsePaperMetadata:
    def test_minimal_record(self):
        record = {"id": 123, "metadata": {}}
        result = parse_paper_metadata(record)
        assert result["inspire_id"] == "123"
        assert result["title"] == ""
        assert result["authors"] == []
        assert result["total_authors"] == 0
        assert result["abstract"] == ""
        assert result["arxiv_id"] is None
        assert result["doi"] is None
        assert result["publication"] is None
        assert result["citation_count"] == 0
        assert result["inspire_url"] == "https://inspirehep.net/literature/123"

    def test_full_record(self):
        record = {
            "id": 456,
            "metadata": {
                "titles": [{"title": "Test Paper"}],
                "authors": [
                    {"full_name": "Author One", "affiliations": [{"value": "MIT"}]},
                    {"full_name": "Author Two", "affiliations": []},
                ],
                "abstracts": [{"value": "This is an abstract."}],
                "arxiv_eprints": [{"value": "2301.12345", "categories": ["hep-ph"]}],
                "dois": [{"value": "10.1103/test"}],
                "publication_info": [
                    {
                        "journal_title": "Phys.Rev.D",
                        "journal_volume": "100",
                        "page_start": "123",
                        "year": 2024,
                    }
                ],
                "collaborations": [{"value": "ATLAS"}],
                "citation_count": 42,
                "earliest_date": "2024-01-15",
            },
        }
        result = parse_paper_metadata(record)
        assert result["inspire_id"] == "456"
        assert result["title"] == "Test Paper"
        assert len(result["authors"]) == 2
        assert result["authors"][0]["full_name"] == "Author One"
        assert result["authors"][0]["affiliations"] == ["MIT"]
        assert result["abstract"] == "This is an abstract."
        assert result["arxiv_id"] == "2301.12345"
        assert result["arxiv_categories"] == ["hep-ph"]
        assert result["doi"] == "10.1103/test"
        assert result["publication"]["journal_title"] == "Phys.Rev.D"
        assert result["publication"]["year"] == 2024
        assert result["collaborations"] == ["ATLAS"]
        assert result["citation_count"] == 42
        assert result["date"] == "2024-01-15"

    def test_authors_capped_at_10(self):
        authors = [{"full_name": f"Author {i}"} for i in range(20)]
        record = {"id": 1, "metadata": {"authors": authors}}
        result = parse_paper_metadata(record)
        assert len(result["authors"]) == 10
        assert result["total_authors"] == 20

    def test_empty_record(self):
        result = parse_paper_metadata({})
        assert result["inspire_id"] == ""
        assert result["title"] == ""

    def test_legacy_date_fallback(self):
        record = {"id": 1, "metadata": {"legacy_creation_date": "2020-01-01"}}
        result = parse_paper_metadata(record)
        assert result["date"] == "2020-01-01"
