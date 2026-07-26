from __future__ import annotations

import collections.abc
import json

import httpx
import respx

from jira_ticket_mcp.client import JiraClient

LoadFixture = collections.abc.Callable[[str], str]


def _json_response(text: str) -> httpx.Response:
    return httpx.Response(200, text=text, headers={"content-type": "application/json"})


def test_encode_rich_text_returns_wiki_string(jira_client_v2: JiraClient) -> None:
    assert jira_client_v2.encode_rich_text("**bold**") == "*bold*"


@respx.mock
async def test_uses_v2_paths_and_bearer_auth(
    jira_client_v2: JiraClient,
    dc_base_url: str,
    load_fixture: LoadFixture,
) -> None:
    route = respx.get(f"{dc_base_url}/rest/api/2/myself").mock(
        return_value=_json_response(load_fixture("myself_200.json"))
    )

    await jira_client_v2.get_myself()

    assert route.called
    assert route.calls.last.request.headers["authorization"] == "Bearer pat-token"


@respx.mock
async def test_get_issue_converts_wiki_description_to_markdown(
    jira_client_v2: JiraClient,
    dc_base_url: str,
    load_fixture: LoadFixture,
) -> None:
    respx.get(f"{dc_base_url}/rest/api/2/issue/DC-7").mock(
        return_value=_json_response(load_fixture("issue_get_v2_200.json"))
    )

    issue = await jira_client_v2.get_issue("DC-7")

    assert issue.fields.description is not None
    assert "## Heading" in issue.fields.description
    assert "**strong**" in issue.fields.description


@respx.mock
async def test_add_comment_sends_wiki_string_body(
    jira_client_v2: JiraClient,
    dc_base_url: str,
) -> None:
    route = respx.post(f"{dc_base_url}/rest/api/2/issue/DC-7/comment").mock(
        return_value=_json_response('{"id": "10"}')
    )

    await jira_client_v2.add_comment("DC-7", "**bold**")

    body = json.loads(route.calls.last.request.content)
    assert body["body"] == "*bold*"


@respx.mock
async def test_search_uses_offset_pagination(
    jira_client_v2: JiraClient,
    dc_base_url: str,
    load_fixture: LoadFixture,
) -> None:
    route = respx.post(f"{dc_base_url}/rest/api/2/search").mock(
        return_value=_json_response(load_fixture("search_v2_200.json"))
    )

    page = await jira_client_v2.search_jql("project = OPS", next_page_token="0")

    sent = json.loads(route.calls.last.request.content)
    assert sent["startAt"] == 0
    assert "nextPageToken" not in sent
    assert [issue.key for issue in page.issues] == ["OPS-1", "OPS-2"]
    assert page.next_page_token == "2"
    assert page.is_last is False


@respx.mock
async def test_search_marks_last_page(
    jira_client_v2: JiraClient,
    dc_base_url: str,
) -> None:
    body = {
        "startAt": 4,
        "maxResults": 50,
        "total": 5,
        "issues": [{"id": "9", "key": "OPS-9", "fields": {}}],
    }
    respx.post(f"{dc_base_url}/rest/api/2/search").mock(
        return_value=_json_response(json.dumps(body))
    )

    page = await jira_client_v2.search_jql("project = OPS", next_page_token="4")

    assert page.is_last is True
    assert page.next_page_token is None
