"""Integration tests for MCP tools against the live InspireHEP API.

These tests make real HTTP requests. Run with:
    uv run pytest tests/test_tools_integration.py -v

They are slower and depend on network availability.
"""

import json

import pytest
import pytest_asyncio

from inspirehep_mcp.api_client import InspireHEPClient
from inspirehep_mcp.tools import (
    get_author_papers,
    get_citations,
    get_paper_details,
    get_references,
    search_by_collaboration,
    search_papers,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    c = InspireHEPClient()
    yield c
    await c.close()


# ======================================================================
# search_papers
# ======================================================================


class TestSearchPapers:
    async def test_basic_search(self, client):
        result = json.loads(await search_papers(client, query="higgs boson", size=3))
        assert result["total_results"] > 0
        assert result["returned"] == 3
        assert result["query"] == "higgs boson"
        assert len(result["papers"]) == 3

    async def test_paper_fields_present(self, client):
        result = json.loads(await search_papers(client, query="dark matter", size=1))
        paper = result["papers"][0]
        assert "inspire_id" in paper
        assert "title" in paper
        assert "authors" in paper
        assert "inspire_url" in paper

    async def test_sort_mostcited(self, client):
        result = json.loads(
            await search_papers(client, query="supersymmetry", sort="mostcited", size=2)
        )
        assert result["sort"] == "mostcited"
        assert result["returned"] == 2

    async def test_invalid_sort(self, client):
        result = json.loads(await search_papers(client, query="test", sort="invalid"))
        assert "error" in result

    async def test_size_clamped(self, client):
        result = json.loads(await search_papers(client, query="neutrino", size=200))
        assert result["returned"] <= 100


# ======================================================================
# get_paper_details
# ======================================================================


class TestGetPaperDetails:
    async def test_by_inspire_id(self, client):
        result = json.loads(await get_paper_details(client, inspire_id="3456"))
        assert result["inspire_id"] == "3456"
        assert "title" in result
        assert "urls" in result

    async def test_by_arxiv_id(self, client):
        result = json.loads(await get_paper_details(client, arxiv_id="1207.7214"))
        assert result["arxiv_id"] == "1207.7214"
        assert result["citation_count"] > 0

    async def test_by_doi(self, client):
        result = json.loads(
            await get_paper_details(client, doi="10.1016/0370-2693(73)90494-2")
        )
        assert result["doi"] == "10.1016/0370-2693(73)90494-2"

    async def test_no_identifier(self, client):
        result = json.loads(await get_paper_details(client))
        assert "error" in result

    async def test_not_found(self, client):
        result = json.loads(await get_paper_details(client, inspire_id="99999999999"))
        assert "error" in result

    async def test_invalid_arxiv(self, client):
        result = json.loads(await get_paper_details(client, arxiv_id="not-valid"))
        assert "error" in result

    async def test_detail_fields(self, client):
        result = json.loads(await get_paper_details(client, inspire_id="3456"))
        assert "references_count" in result
        assert "document_type" in result
        assert "urls" in result
        assert isinstance(result["urls"], dict)


# ======================================================================
# get_author_papers
# ======================================================================


class TestGetAuthorPapers:
    async def test_by_name(self, client):
        result = json.loads(
            await get_author_papers(client, author_name="Weinberg, Steven", size=3)
        )
        assert result["total_papers"] > 0
        assert result["returned"] == 3
        assert "author" in result
        assert result["author"]["bai"] is not None

    async def test_by_bai(self, client):
        result = json.loads(
            await get_author_papers(client, author_id="Steven.Weinberg.1", size=2)
        )
        assert result["total_papers"] > 0

    async def test_metrics(self, client):
        result = json.loads(
            await get_author_papers(
                client, author_name="Weinberg, Steven", sort="mostcited", size=5
            )
        )
        metrics = result["metrics"]
        assert "total_citations" in metrics
        assert "h_index" in metrics
        assert "average_citations" in metrics
        assert metrics["total_citations"] > 0

    async def test_no_author(self, client):
        result = json.loads(await get_author_papers(client))
        assert "error" in result

    async def test_invalid_sort(self, client):
        result = json.loads(
            await get_author_papers(client, author_name="Test", sort="invalid")
        )
        assert "error" in result


# ======================================================================
# get_citations
# ======================================================================


class TestGetCitations:
    async def test_citing(self, client):
        result = json.loads(
            await get_citations(client, inspire_id="3456", direction="citing", size=3)
        )
        assert result["direction"] == "citing"
        assert result["total_citations"] > 0
        assert result["returned"] == 3
        assert "timeline" in result

    async def test_cited_by(self, client):
        result = json.loads(
            await get_citations(client, inspire_id="3456", direction="cited_by", size=3)
        )
        assert result["direction"] == "cited_by"
        assert result["total_citations"] > 0

    async def test_invalid_direction(self, client):
        result = json.loads(
            await get_citations(client, inspire_id="3456", direction="bad")
        )
        assert "error" in result

    async def test_invalid_id(self, client):
        result = json.loads(
            await get_citations(client, inspire_id="not-numeric")
        )
        assert "error" in result

    async def test_timeline_has_years(self, client):
        result = json.loads(
            await get_citations(client, inspire_id="3456", direction="citing", size=10)
        )
        assert isinstance(result["timeline"], dict)


# ======================================================================
# search_by_collaboration
# ======================================================================


class TestSearchByCollaboration:
    async def test_basic(self, client):
        result = json.loads(
            await search_by_collaboration(client, collaboration_name="ATLAS", size=3)
        )
        assert result["collaboration"] == "ATLAS"
        assert result["total_publications"] > 0
        assert result["returned"] == 3

    async def test_alias_normalization(self, client):
        result = json.loads(
            await search_by_collaboration(client, collaboration_name="lhcb", size=1)
        )
        assert result["collaboration"] == "LHCb"

    async def test_year_filter(self, client):
        result = json.loads(
            await search_by_collaboration(
                client, collaboration_name="CMS", year=2024, size=2
            )
        )
        assert result["year_filter"] == 2024
        assert result["total_publications"] > 0

    async def test_top_cited(self, client):
        result = json.loads(
            await search_by_collaboration(
                client, collaboration_name="ATLAS", sort="mostcited", size=5
            )
        )
        assert len(result["top_cited_papers"]) > 0
        assert result["top_cited_papers"][0]["citation_count"] > 0

    async def test_invalid_sort(self, client):
        result = json.loads(
            await search_by_collaboration(client, collaboration_name="CMS", sort="bad")
        )
        assert "error" in result


# ======================================================================
# get_references
# ======================================================================


class TestGetReferences:
    async def test_bibtex(self, client):
        result = json.loads(
            await get_references(client, inspire_id="3456", format="bibtex")
        )
        assert result["total_references"] > 0
        assert result["format"] == "bibtex"
        assert "@" in result["references"]  # BibTeX entries start with @

    async def test_json_format(self, client):
        result = json.loads(
            await get_references(client, inspire_id="3456", format="json")
        )
        assert result["format"] == "json"
        assert isinstance(result["references"], list)
        assert len(result["references"]) > 0

    async def test_latex_us(self, client):
        result = json.loads(
            await get_references(client, inspire_id="3456", format="latex-us")
        )
        assert result["format"] == "latex-us"
        assert "\\bibitem" in result["references"]

    async def test_invalid_format(self, client):
        result = json.loads(
            await get_references(client, inspire_id="3456", format="bad")
        )
        assert "error" in result

    async def test_not_found(self, client):
        result = json.loads(
            await get_references(client, inspire_id="99999999999")
        )
        assert "error" in result

    async def test_invalid_id(self, client):
        result = json.loads(
            await get_references(client, inspire_id="abc")
        )
        assert "error" in result
