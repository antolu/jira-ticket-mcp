from __future__ import annotations

import sys

import pydantic
import pytest

from jira_ticket_mcp.client import JiraClient
from jira_ticket_mcp.config import Settings


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_API_VERSION"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "argv", ["jira-ticket-mcp"])


def _settings(url: str, *, version: str | None = None) -> Settings:
    return Settings(
        jira_base_url=url,
        jira_api_token=pydantic.SecretStr("secret"),
        jira_api_version=version,
    )


def test_v3_client_requires_email() -> None:
    with pytest.raises(ValueError, match="email"):
        JiraClient(base_url="https://x.atlassian.net", api_token="t", api_version="3")


async def test_v2_client_needs_no_email() -> None:
    client = JiraClient(
        base_url="https://dc.example.com", api_token="t", api_version="2"
    )
    await client.aclose()


def test_cloud_host_detected_as_v3() -> None:
    with pytest.raises(ValueError, match="email"):
        JiraClient.from_settings(_settings("https://team.atlassian.net"))


async def test_datacenter_host_detected_as_v2() -> None:
    client = JiraClient.from_settings(_settings("https://jira.corp.example.com"))
    await client.aclose()


async def test_lookalike_host_is_not_treated_as_cloud() -> None:
    client = JiraClient.from_settings(_settings("https://evilatlassian.net"))
    await client.aclose()


async def test_override_forces_v2_on_cloud_host() -> None:
    client = JiraClient.from_settings(
        _settings("https://team.atlassian.net", version="2")
    )
    await client.aclose()


def test_invalid_override_is_rejected() -> None:
    with pytest.raises(ValueError, match="'2' or '3'"):
        JiraClient.from_settings(_settings("https://team.atlassian.net", version="9"))
