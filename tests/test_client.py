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


@respx.mock
async def test_get_issue_parses_issue_and_ignores_custom_fields(
    jira_client: JiraClient,
    base_url: str,
    load_fixture: collections.abc.Callable[[str], str],
) -> None:
    fixture = load_fixture("issue_get_200.json")
    respx.get(f"{base_url}/rest/api/3/issue/OPS-42").mock(
        return_value=_json_response(fixture)
    )

    issue = await jira_client.get_issue("OPS-42")

    assert issue.key == "OPS-42"
    assert issue.self_ == json.loads(fixture)["self"]
    assert issue.fields.summary == "Rotate the staging API token"
    assert issue.fields.issue_type is not None
    assert issue.fields.issue_type.name == "Task"
    assert issue.fields.parent is not None
    assert issue.fields.parent.key == "OPS-1"
    assert issue.fields.labels == ["security", "staging"]
    assert not hasattr(issue.fields, "customfield_10014")


@respx.mock
async def test_get_issue_sends_requested_fields(
    jira_client: JiraClient,
    base_url: str,
    load_fixture: collections.abc.Callable[[str], str],
) -> None:
    route = respx.get(f"{base_url}/rest/api/3/issue/OPS-42").mock(
        return_value=_json_response(load_fixture("issue_get_200.json"))
    )

    await jira_client.get_issue("OPS-42", fields=["summary", "status"])

    assert route.calls.last.request.url.params["fields"] == "summary,status"


@respx.mock
async def test_search_jql_preserves_response_order(
    jira_client: JiraClient,
    base_url: str,
    load_fixture: collections.abc.Callable[[str], str],
) -> None:
    fixture = load_fixture("search_jql_200.json")
    respx.post(f"{base_url}/rest/api/3/search/jql").mock(
        return_value=_json_response(fixture)
    )

    page = await jira_client.search_jql("project = OPS")

    expected = [issue["key"] for issue in json.loads(fixture)["issues"]]
    assert [issue.key for issue in page.issues] == expected
    assert page.next_page_token == "CAEaBggBEgA"
    assert page.is_last is False


@respx.mock
async def test_search_jql_omits_unset_optional_keys(
    jira_client: JiraClient,
    base_url: str,
    load_fixture: collections.abc.Callable[[str], str],
) -> None:
    route = respx.post(f"{base_url}/rest/api/3/search/jql").mock(
        return_value=_json_response(load_fixture("search_jql_200.json"))
    )

    await jira_client.search_jql("project = OPS", max_results=10)

    body = json.loads(route.calls.last.request.content)
    assert body == {"jql": "project = OPS", "maxResults": 10}


@respx.mock
async def test_search_jql_sends_cursor_and_fields(
    jira_client: JiraClient,
    base_url: str,
    load_fixture: collections.abc.Callable[[str], str],
) -> None:
    route = respx.post(f"{base_url}/rest/api/3/search/jql").mock(
        return_value=_json_response(load_fixture("search_jql_200.json"))
    )

    await jira_client.search_jql(
        "project = OPS", next_page_token="CAEaBggBEgA", fields=["summary"]
    )

    body = json.loads(route.calls.last.request.content)
    assert body["nextPageToken"] == "CAEaBggBEgA"
    assert body["fields"] == ["summary"]


@respx.mock
async def test_search_jql_empty_page_yields_empty_list(
    jira_client: JiraClient,
    base_url: str,
    load_fixture: collections.abc.Callable[[str], str],
) -> None:
    respx.post(f"{base_url}/rest/api/3/search/jql").mock(
        return_value=_json_response(load_fixture("search_jql_empty_200.json"))
    )

    page = await jira_client.search_jql("project = NONE")

    assert page.issues == []
    assert page.is_last is True
    assert page.next_page_token is None
