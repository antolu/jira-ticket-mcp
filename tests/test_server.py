from __future__ import annotations

import collections.abc
import json
import typing

import httpx
import mcp.server.fastmcp
import mcp.server.fastmcp.exceptions
import pydantic
import pytest
import respx

from jira_ticket_mcp.client import JiraClient
from jira_ticket_mcp.models import (
    BatchCreateResult,
    Comment,
    IssueSummary,
    SearchResult,
    ToolName,
)
from jira_ticket_mcp.server import UnknownToolError, build_server, resolve_tools

LoadFixture = collections.abc.Callable[[str], str]
FAILED_ITEM_INDEX = 2


class CommentListResult(pydantic.BaseModel):
    """FastMCP wraps a bare list return under a ``result`` key."""

    result: list[Comment]


ModelT = typing.TypeVar("ModelT", bound=pydantic.BaseModel)


async def _structured(
    server: mcp.server.fastmcp.FastMCP,
    name: str,
    arguments: dict[str, object],
    model: type[ModelT],
) -> ModelT:
    result = await server.call_tool(name, arguments)
    pair = typing.cast("tuple[object, dict[str, pydantic.JsonValue]]", result)
    return model.model_validate(pair[1])


def _json_response(text: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status, text=text, headers={"content-type": "application/json"}
    )


async def _tool_names(client: JiraClient, requested: str | None) -> list[str]:
    server = build_server(client, resolve_tools(requested))
    return [tool.name for tool in await server.list_tools()]


def test_resolve_tools_defaults_to_every_tool() -> None:
    assert resolve_tools(None) == frozenset(ToolName)
    assert resolve_tools("") == frozenset(ToolName)


def test_resolve_tools_rejects_unknown_name() -> None:
    with pytest.raises(UnknownToolError, match="delete_everything"):
        resolve_tools("get_issue,delete_everything")


async def test_allowlist_registers_only_named_tools(jira_client: JiraClient) -> None:
    names = await _tool_names(jira_client, "search_issues,get_issue,edit_issue")
    assert sorted(names) == ["edit_issue", "get_issue", "search_issues"]


async def test_default_registers_every_tool(jira_client: JiraClient) -> None:
    names = await _tool_names(jira_client, None)
    assert sorted(names) == sorted(tool.value for tool in ToolName)


@respx.mock
async def test_search_issues_returns_trimmed_projection(
    jira_client: JiraClient, base_url: str, load_fixture: LoadFixture
) -> None:
    respx.post(f"{base_url}/rest/api/3/search/jql").mock(
        return_value=_json_response(load_fixture("search_jql_200.json"))
    )
    server = build_server(jira_client, resolve_tools(None))

    payload = await _structured(
        server, "search_issues", {"jql": "project = OPS"}, SearchResult
    )

    assert [issue.key for issue in payload.issues] == ["OPS-3", "OPS-1", "OPS-2"]
    assert payload.issues[0].summary == "zeta task"
    assert payload.issues[0].issue_type == "Task"
    assert set(IssueSummary.model_fields) == {
        "key",
        "summary",
        "status",
        "issue_type",
        "assignee",
        "priority",
    }


@respx.mock
async def test_edit_issue_sends_only_supplied_fields(
    jira_client: JiraClient, base_url: str
) -> None:
    route = respx.put(f"{base_url}/rest/api/3/issue/OPS-42").mock(
        return_value=httpx.Response(204)
    )
    server = build_server(jira_client, resolve_tools(None))

    await server.call_tool("edit_issue", {"key": "OPS-42", "priority": "High"})

    body = json.loads(route.calls.last.request.content)
    assert body == {"fields": {"priority": {"name": "High"}}}


async def test_edit_issue_rejects_empty_change(jira_client: JiraClient) -> None:
    server = build_server(jira_client, resolve_tools(None))

    with pytest.raises(
        mcp.server.fastmcp.exceptions.ToolError, match="at least one field"
    ):
        await server.call_tool("edit_issue", {"key": "OPS-42"})


@respx.mock
async def test_create_issue_parent_rejection_names_project_style(
    jira_client: JiraClient, base_url: str
) -> None:
    respx.post(f"{base_url}/rest/api/3/issue").mock(
        return_value=_json_response(
            json.dumps({"errors": {"parent": "Field 'parent' cannot be set."}}), 400
        )
    )
    server = build_server(jira_client, resolve_tools(None))

    with pytest.raises(
        mcp.server.fastmcp.exceptions.ToolError, match="company-managed"
    ):
        await server.call_tool(
            "create_issue",
            {
                "project": "OPS",
                "issue_type": "Story",
                "summary": "s",
                "parent_key": "OPS-1",
            },
        )


@respx.mock
async def test_batch_create_reports_per_item_without_raising(
    jira_client: JiraClient, base_url: str, load_fixture: LoadFixture
) -> None:
    respx.post(f"{base_url}/rest/api/3/issue/bulk").mock(
        return_value=_json_response(load_fixture("issue_bulk_partial_200.json"))
    )
    server = build_server(jira_client, resolve_tools(None))

    payload = await _structured(
        server,
        "batch_create_issues",
        {
            "project": "OPS",
            "issues": [{"summary": "one"}, {"summary": "two"}, {"summary": "three"}],
        },
        BatchCreateResult,
    )

    assert [item.key for item in payload.created] == ["OPS-101", "OPS-102"]
    assert len(payload.failed) == 1
    assert payload.failed[0].index == FAILED_ITEM_INDEX
    assert "summary" in str(payload.failed[0].error)


@respx.mock
async def test_add_comment_converts_markdown_to_adf(
    jira_client: JiraClient, base_url: str
) -> None:
    route = respx.post(f"{base_url}/rest/api/3/issue/OPS-42/comment").mock(
        return_value=_json_response(json.dumps({"id": "10500"}), 201)
    )
    server = build_server(jira_client, resolve_tools(None))

    await server.call_tool(
        "add_comment", {"key": "OPS-42", "markdown": "**deploy** blocked"}
    )

    body = json.loads(route.calls.last.request.content)
    assert body["body"]["type"] == "doc"


@respx.mock
async def test_transition_issue_posts_transition_id(
    jira_client: JiraClient, base_url: str
) -> None:
    route = respx.post(f"{base_url}/rest/api/3/issue/OPS-42/transitions").mock(
        return_value=httpx.Response(204)
    )
    server = build_server(jira_client, resolve_tools(None))

    await server.call_tool("transition_issue", {"key": "OPS-42", "transition_id": "31"})

    assert json.loads(route.calls.last.request.content) == {"transition": {"id": "31"}}


@respx.mock
async def test_link_issues_sends_named_link_type(
    jira_client: JiraClient, base_url: str
) -> None:
    route = respx.post(f"{base_url}/rest/api/3/issueLink").mock(
        return_value=httpx.Response(201)
    )
    server = build_server(jira_client, resolve_tools(None))

    await server.call_tool(
        "link_issues",
        {"inward_key": "OPS-1", "outward_key": "OPS-2", "link_type": "Blocks"},
    )

    body = json.loads(route.calls.last.request.content)
    assert body["type"] == {"name": "Blocks"}
    assert body["inwardIssue"] == {"key": "OPS-1"}


@respx.mock
async def test_remove_issue_deletes(jira_client: JiraClient, base_url: str) -> None:
    route = respx.delete(f"{base_url}/rest/api/3/issue/OPS-42").mock(
        return_value=httpx.Response(204)
    )
    server = build_server(jira_client, resolve_tools(None))

    await server.call_tool("remove_issue", {"key": "OPS-42"})

    assert route.called


@respx.mock
async def test_list_comments_returns_markdown_bodies(
    jira_client: JiraClient, base_url: str, load_fixture: LoadFixture
) -> None:
    respx.get(f"{base_url}/rest/api/3/issue/OPS-42/comment").mock(
        return_value=_json_response(load_fixture("comments_200.json"))
    )
    server = build_server(jira_client, resolve_tools(None))

    payload = await _structured(
        server, "list_comments", {"key": "OPS-42"}, CommentListResult
    )

    assert [comment.id for comment in payload.result] == ["10500", "10501"]
    assert payload.result[0].body == "Rotated on staging, waiting on prod."
    assert payload.result[1].body is not None
    assert "**release window**" in payload.result[1].body
    assert payload.result[0].author is not None
    assert payload.result[0].author.display_name == "Mia Okafor"


@respx.mock
async def test_get_issue_returns_description_as_markdown(
    jira_client: JiraClient, base_url: str, load_fixture: LoadFixture
) -> None:
    respx.get(f"{base_url}/rest/api/3/issue/OPS-42").mock(
        return_value=_json_response(load_fixture("issue_get_200.json"))
    )
    server = build_server(jira_client, resolve_tools(None))

    result = await server.call_tool("get_issue", {"key": "OPS-42"})
    pair = typing.cast("tuple[object, dict[str, pydantic.JsonValue]]", result)
    fields = pair[1]["fields"]

    assert isinstance(fields, dict)
    assert fields["description"] == "The staging token expires on Friday."
