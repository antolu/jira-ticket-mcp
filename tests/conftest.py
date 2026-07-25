from __future__ import annotations

import collections.abc
import pathlib

import pytest

from jira_ticket_mcp.client import JiraClient

BASE_URL = "https://example.atlassian.net"

_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def load_fixture() -> collections.abc.Callable[[str], str]:
    def _load(name: str) -> str:
        return (_FIXTURE_DIR / name).read_text(encoding="utf-8")

    return _load


@pytest.fixture
async def jira_client() -> collections.abc.AsyncIterator[JiraClient]:
    client = JiraClient(
        base_url=BASE_URL, email="mia@example.com", api_token="dummy-token"
    )
    try:
        yield client
    finally:
        await client.aclose()
