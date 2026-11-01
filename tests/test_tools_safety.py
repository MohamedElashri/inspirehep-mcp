"""Unit tests for public tool input and output bounds."""

import json

import pytest

from inspirehep_mcp.config import settings
from inspirehep_mcp.tools import (
    get_author_papers,
    get_bibtex,
    get_citations,
    get_paper_figures,
    get_references,
    search_by_collaboration,
    search_papers,
)


class FakeClient:
    def __init__(self, record=None, search_result=None):
        self.record = record or {}
        self.search_result = search_result or {"hits": {"total": 0, "hits": []}}
        self.called = False
        self.text_params = None
        self.search_kwargs = None

    async def search_literature(self, *args, **kwargs):
        self.called = True
        self.search_kwargs = kwargs
        return self.search_result

    async def get_literature_record(self, *args, **kwargs):
        self.called = True
        return self.record

    async def get_text(self, *args, **kwargs):
        self.called = True
        self.text_params = kwargs.get("params")
        return "formatted"


@pytest.mark.asyncio
async def test_long_search_input_is_rejected_before_upstream(monkeypatch):
    monkeypatch.setattr(settings, "max_input_length", 4)
    client = FakeClient()

    result = json.loads(await search_papers(client, query="12345"))

    assert "at most 4 characters" in result["error"]
    assert client.called is False


@pytest.mark.asyncio
async def test_long_identifier_is_rejected_before_upstream(monkeypatch):
    monkeypatch.setattr(settings, "max_identifier_length", 4)
    client = FakeClient()

    result = json.loads(await get_bibtex(client, identifier="12345"))

    assert "at most 4 characters" in result["error"]
    assert client.called is False


@pytest.mark.asyncio
async def test_reference_results_are_capped(monkeypatch):
    monkeypatch.setattr(settings, "max_references", 2)
    refs = [
        {
            "record": {"$ref": f"https://inspirehep.net/api/literature/{index}"},
            "reference": {"title": {"title": f"Paper {index}"}},
        }
        for index in range(3)
    ]
    client = FakeClient(record={"metadata": {"references": refs, "titles": []}})

    result = json.loads(await get_references(client, inspire_id="1", format="json"))

    assert result["total_references"] == 3
    assert result["returned_references"] == 2
    assert result["truncated"] is True
    assert len(result["references"]) == 2


@pytest.mark.asyncio
async def test_formatted_reference_results_respect_upstream_cap(monkeypatch):
    monkeypatch.setattr(settings, "max_references", 300)
    refs = [
        {"record": {"$ref": f"https://inspirehep.net/api/literature/{index}"}}
        for index in range(251)
    ]
    client = FakeClient(record={"metadata": {"references": refs, "titles": []}})

    result = json.loads(await get_references(client, inspire_id="1", format="bibtex"))

    assert result["returned_references"] == 250
    assert result["truncated"] is True
    assert client.text_params["size"] == 250
    assert client.text_params["q"].count("recid:") == 250


@pytest.mark.asyncio
async def test_figure_results_are_capped(monkeypatch):
    monkeypatch.setattr(settings, "max_figures", 1)
    figures = [{"caption": str(index)} for index in range(2)]
    client = FakeClient(
        record={"id": "1", "metadata": {"figures": figures, "titles": []}}
    )

    result = json.loads(await get_paper_figures(client, inspire_id="1"))

    assert result["figures_count"] == 2
    assert result["returned_figures"] == 1
    assert result["truncated"] is True


@pytest.mark.asyncio
async def test_serialized_response_size_is_capped(monkeypatch):
    monkeypatch.setattr(settings, "max_response_bytes", 100)
    client = FakeClient(
        search_result={
            "hits": {
                "total": 1,
                "hits": [
                    {
                        "id": "1",
                        "metadata": {
                            "titles": [{"title": "x" * 500}],
                            "authors": [],
                        },
                    }
                ],
            }
        }
    )

    result = json.loads(await search_papers(client, query="safe"))

    assert result == {
        "error": "Response exceeds the configured server safety limit.",
        "max_response_bytes": 100,
    }


@pytest.mark.asyncio
async def test_collaboration_year_is_bounded():
    client = FakeClient()

    result = json.loads(
        await search_by_collaboration(client, collaboration_name="ATLAS", year=9999)
    )

    assert "supported range" in result["error"]
    assert client.called is False


_PAGED_TOOLS = [
    (search_papers, {"query": "higgs"}),
    (get_author_papers, {"author_id": "S.Weinberg.1"}),
    (get_citations, {"inspire_id": "1"}),
    (search_by_collaboration, {"collaboration_name": "LHCb"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,kwargs", _PAGED_TOOLS)
@pytest.mark.parametrize("page", [0, -1, True, 1.5])
async def test_invalid_page_never_calls_upstream(tool, kwargs, page):
    client = FakeClient()
    result = json.loads(await tool(client, **kwargs, page=page))
    assert "page must be a positive integer" in result["error"]
    assert client.called is False


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,kwargs", _PAGED_TOOLS)
@pytest.mark.parametrize(
    "total,page,count,next_page",
    [
        (5, 1, 2, 2),
        (5, 2, 2, 3),
        (5, 3, 1, None),
        (5, 4, 0, None),
    ],
)
async def test_pagination_and_compact_provenance(
    tool, kwargs, total, page, count, next_page
):
    client = FakeClient(
        search_result={
            "hits": {
                "total": total,
                "hits": [
                    {
                        "id": str(index),
                        "metadata": {
                            "titles": [{"title": "Higgs"}],
                            "abstracts": [{"value": "abstract"}],
                        },
                    }
                    for index in range(count)
                ],
            }
        }
    )
    full = json.loads(await tool(client, **kwargs, size=2, page=page))
    compact = json.loads(await tool(client, **kwargs, size=2, page=page, compact=True))
    assert client.search_kwargs["page"] == page
    assert client.search_kwargs["size"] == 2
    assert compact["next_page"] == next_page
    assert compact["has_more"] is (next_page is not None)
    assert compact["returned"] == count
    for full_paper, summary in zip(full["papers"], compact["papers"], strict=True):
        assert "abstract" in full_paper
        assert "abstract" not in summary
        assert "authors" not in summary
        assert summary["inspire_url"] == full_paper["inspire_url"]
        assert summary["inspire_id"] == full_paper["inspire_id"]


@pytest.mark.asyncio
async def test_formatted_references_without_resolvable_records():
    client = FakeClient(
        record={
            "metadata": {
                "references": [{"reference": {"title": {"title": "Unlinked paper"}}}],
            }
        }
    )
    result = json.loads(await get_references(client, inspire_id="1"))
    assert result["total_references"] == 1
    assert result["returned_references"] == 0
    assert result["resolvable_references"] == 0
    assert "No resolvable references" in result["references"]
    assert client.text_params is None
