"""Unit tests for public tool input and output bounds."""

import json

import pytest

from inspirehep_mcp.config import settings
from inspirehep_mcp.tools import (
    get_bibtex,
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

    async def search_literature(self, *args, **kwargs):
        self.called = True
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
