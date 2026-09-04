"""Unit tests for bounded upstream work admission."""

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
