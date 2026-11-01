"""Unit tests for bounded upstream work admission."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from inspirehep_mcp.api_client import InspireHEPClient
from inspirehep_mcp.errors import APIError


@pytest.mark.asyncio
async def test_upstream_capacity_fails_fast_and_recovers():
    client = InspireHEPClient(max_pending_requests=1)

    async with client._request_slot():
        with pytest.raises(APIError, match="Server busy") as exc_info:
            async with client._request_slot():
                pass
        assert exc_info.value.status_code == 503

    async with client._request_slot():
        assert client._pending_requests == 1

    assert client._pending_requests == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"requests_per_second": 0},
        {"max_pending_requests": 0},
    ],
)
def test_invalid_capacity_configuration(kwargs):
    with pytest.raises(ValueError):
        InspireHEPClient(**kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("requested,expected", [(100, 100), (250, 250), (500, 250)])
async def test_search_preserves_supported_citation_page_size(
    monkeypatch, requested, expected
):
    client = InspireHEPClient()
    get = AsyncMock(return_value={})
    monkeypatch.setattr(client, "get", get)
    await client.search_literature("higgs", size=requested, page=3)
    assert get.call_args.kwargs["params"]["size"] == expected
    assert get.call_args.kwargs["params"]["page"] == 3


@pytest.mark.asyncio
async def test_cancelled_upstream_request_releases_capacity():
    client = InspireHEPClient(max_pending_requests=1)
    started = asyncio.Event()

    async def work():
        async with client._request_slot():
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(work())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert client._pending_requests == 0
    async with client._request_slot():
        assert client._pending_requests == 1
