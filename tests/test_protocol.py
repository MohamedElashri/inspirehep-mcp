"""Exercise the public MCP contract through modern and legacy client connections."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx2 as httpx
import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from inspirehep_mcp import __version__, server
from inspirehep_mcp.config import settings
from inspirehep_mcp.errors import APIError
from inspirehep_mcp.rate_limit import RateLimitMiddleware, RequestBodyLimitMiddleware


@pytest.fixture(
    params=[
        ("memory", "auto"),
        ("memory", "legacy"),
        ("http", "auto"),
        ("http", "legacy"),
    ]
)
def connection(request, monkeypatch):
    @asynccontextmanager
    async def connect():
        upstream = AsyncMock()
        upstream.search_literature.return_value = {
            "hits": {
                "total": 5,
                "hits": [
                    {
                        "id": str(index),
                        "metadata": {
                            "titles": [{"title": f"Paper {index}"}],
                            "abstracts": [{"value": "A long abstract. " * 50}],
                            "citation_count": index,
                        },
                    }
                    for index in (1, 2)
                ],
            }
        }
        monkeypatch.setattr(server, "api_client", upstream)
        transport, mode = request.param
        if transport == "memory":
            async with Client(server.mcp, mode=mode) as client:
                yield client, upstream
        else:
            http_app = server.mcp.streamable_http_app(
                stateless_http=True, json_response=True
            )
            app = RateLimitMiddleware(RequestBodyLimitMiddleware(http_app))
            async with (
                http_app.router.lifespan_context(http_app),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://localhost:8000",
                ) as http_client,
                Client(
                    streamable_http_client(
                        "http://localhost:8000/mcp", http_client=http_client
                    ),
                    mode=mode,
                    read_timeout_seconds=10,
                ) as client,
            ):
                yield client, upstream
        upstream.close.assert_awaited_once()

    return connect


@pytest.mark.asyncio
async def test_discovery_and_stable_tool_catalogue(connection):
    async with connection() as (client, _):
        assert client.server_info.name == "InspireHEP"
        assert client.server_info.version == __version__
        first = await client.session.list_tools()
        second = await client.session.list_tools()
        assert first.tools == second.tools
        assert len(first.tools) == 9
        if client.protocol_version == "2026-07-28":
            assert first.ttl_ms == 300_000
            assert first.cache_scope == "public"
            assert first.result_type == "complete"
        for tool in first.tools:
            assert tool.title and tool.description
            assert tool.annotations.read_only_hint is True
            assert tool.annotations.destructive_hint is False
            assert tool.annotations.idempotent_hint is True
            assert tool.annotations.open_world_hint is (tool.name != "ping")
            assert tool.input_schema["type"] == "object"
            if tool.name != "ping":
                assert tool.output_schema["type"] == "object"
        search = next(tool for tool in first.tools if tool.name == "search_papers")
        props = search.input_schema["properties"]
        assert props["sort"]["enum"] == ["bestmatch", "mostrecent", "mostcited"]
        assert props["size"]["minimum"] == 1
        assert props["size"]["maximum"] == 100
        assert props["page"]["minimum"] == 1
        assert props["query"]["maxLength"] == settings.max_input_length


@pytest.mark.asyncio
async def test_structured_results_and_text_fallback(connection):
    async with connection() as (client, upstream):
        result = await client.call_tool(
            "search_papers",
            {
                "query": "higgs",
                "size": 2,
                "page": 2,
                "compact": True,
            },
        )
        assert result.is_error is False
        payload = result.structured_content
        assert json.loads(result.content[0].text) == payload
        assert payload["page"] == 2
        assert payload["next_page"] == 3
        assert payload["has_more"] is True
        assert (
            payload["papers"][0]["inspire_url"] == "https://inspirehep.net/literature/1"
        )
        assert "abstract" not in payload["papers"][0]
        upstream.search_literature.assert_awaited_once_with(
            "higgs", sort="bestmatch", size=2, page=2
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,arguments",
    [
        ("search_papers", {"query": "higgs", "sort": "wrong"}),
        ("search_papers", {"query": "higgs", "size": 101}),
        ("search_papers", {"query": "higgs", "page": 0}),
        ("search_papers", {"query": "x" * (settings.max_input_length + 1)}),
        ("get_citations", {"inspire_id": "1", "direction": "wrong"}),
        ("get_references", {"inspire_id": "1", "format": "wrong"}),
        ("get_paper_details", {}),
        ("get_bibtex", {"identifier": "not an identifier"}),
    ],
)
async def test_bad_arguments_are_mcp_tool_errors(connection, name, arguments):
    async with connection() as (client, upstream):
        result = await client.call_tool(name, arguments)
        assert result.is_error is True
        assert result.content[0].text
        assert result.structured_content is None
        upstream.search_literature.assert_not_awaited()
        upstream.get_literature_record.assert_not_awaited()


@pytest.mark.asyncio
async def test_upstream_error_is_actionable_and_connection_recovers(connection):
    async with connection() as (client, upstream):
        upstream.search_literature.side_effect = APIError(
            "Server busy", status_code=503
        )
        result = await client.call_tool("search_papers", {"query": "higgs"})
        assert result.is_error is True
        assert "503" in result.content[0].text
        assert "Suggestion:" in result.content[0].text
        assert (await client.call_tool("ping", {})).is_error is False


@pytest.mark.asyncio
async def test_oversized_result_is_mcp_error(connection, monkeypatch):
    async with connection() as (client, _):
        monkeypatch.setattr(settings, "max_response_bytes", 100)
        result = await client.call_tool("search_papers", {"query": "higgs"})
        assert result.is_error is True
        assert "safety limit" in result.content[0].text


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_real_stdio_subprocess(mode):
    import sys

    async with Client(
        StdioServerParameters(
            command=sys.executable, args=["-m", "inspirehep_mcp.server"]
        ),
        mode=mode,
        read_timeout_seconds=10,
    ) as client:
        assert client.server_info.version == __version__
        assert len((await client.list_tools()).tools) == 9
        assert (await client.call_tool("ping", {})).is_error is False
