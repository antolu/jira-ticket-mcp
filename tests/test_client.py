from __future__ import annotations

import collections.abc
import json

import httpx
import respx

from jira_ticket_mcp.client import JiraClient

_MYSELF_PATH = "/rest/api/3/myself"


def _json_response(text: str) -> httpx.Response:
    return httpx.Response(200, text=text, headers={"content-type": "application/json"})


@respx.mock
async def test_get_myself_returns_parsed_model(
    jira_client: JiraClient,
    base_url: str,
    load_fixture: collections.abc.Callable[[str], str],
) -> None:
    fixture = load_fixture("myself_200.json")
    route = respx.get(f"{base_url}{_MYSELF_PATH}").mock(
        return_value=_json_response(fixture)
    )

    myself = await jira_client.get_myself()

    expected = json.loads(fixture)
    assert myself.account_id == expected["accountId"]
    assert myself.display_name == expected["displayName"]
    assert myself.email_address == expected["emailAddress"]
    assert myself.active is True
    assert not hasattr(myself, "timeZone")
    assert route.called


@respx.mock
async def test_get_myself_sends_basic_auth(
    jira_client: JiraClient,
    base_url: str,
    load_fixture: collections.abc.Callable[[str], str],
) -> None:
    route = respx.get(f"{base_url}{_MYSELF_PATH}").mock(
        return_value=_json_response(load_fixture("myself_200.json"))
    )

    await jira_client.get_myself()

    authorization = route.calls.last.request.headers["authorization"]
    assert authorization.startswith("Basic ")
