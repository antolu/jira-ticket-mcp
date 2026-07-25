from __future__ import annotations

import collections.abc
import http

import mcp.server.fastmcp

from jira_ticket_mcp.client import JiraClient, build_fields
from jira_ticket_mcp.config import Settings, load_settings
from jira_ticket_mcp.errors import JiraAPIError
from jira_ticket_mcp.models import (
    BatchCreateResult,
    Comment,
    Issue,
    IssueSummary,
    IssueType,
    LinkType,
    Myself,
    SearchResult,
    ToolName,
    Transition,
)

_PARENT_HINT = (
    "Jira rejected the parent field. This server links epics through the parent "
    "field only, which works on team-managed projects; company-managed projects "
    "use an instance-specific Epic Link custom field instead."
)


class UnknownToolError(ValueError):
    pass


def resolve_tools(requested: str | None) -> frozenset[ToolName]:
    if requested is None:
        return frozenset(ToolName)
    names = [item.strip() for item in requested.split(",") if item.strip()]
    if not names:
        return frozenset(ToolName)
    selected: set[ToolName] = set()
    for name in names:
        try:
            selected.add(ToolName(name))
        except ValueError as exc:
            known = ", ".join(sorted(tool.value for tool in ToolName))
            msg = f"unknown tool {name!r}; available tools: {known}"
            raise UnknownToolError(msg) from exc
    return frozenset(selected)


def _reraise_parent_error(exc: JiraAPIError) -> JiraAPIError:
    haystack = " ".join([*exc.messages, *exc.errors]).lower()
    if exc.status == http.HTTPStatus.BAD_REQUEST and "parent" in haystack:
        return JiraAPIError(
            status=exc.status,
            messages=[*exc.messages, _PARENT_HINT],
            errors=exc.errors,
        )
    return exc


def build_server(
    client: JiraClient, enabled: collections.abc.Container[ToolName]
) -> mcp.server.fastmcp.FastMCP:
    server = mcp.server.fastmcp.FastMCP("jira-ticket-mcp")

    def register(
        name: ToolName,
    ) -> collections.abc.Callable[
        [collections.abc.Callable[..., object]], collections.abc.Callable[..., object]
    ]:
        def decorator(
            func: collections.abc.Callable[..., object],
        ) -> collections.abc.Callable[..., object]:
            if name in enabled:
                server.add_tool(func, name=name.value)
            return func

        return decorator

    @register(ToolName.WHOAMI)
    async def whoami() -> Myself:
        """Return the authenticated Jira account, including its accountId."""
        return await client.get_myself()

    @register(ToolName.SEARCH_ISSUES)
    async def search_issues(
        jql: str, max_results: int = 50, next_page_token: str | None = None
    ) -> SearchResult:
        """Search issues by JQL, returning a trimmed projection of each issue."""
        page = await client.search_jql(
            jql, max_results=max_results, next_page_token=next_page_token
        )
        return SearchResult(
            issues=[IssueSummary.from_issue(issue) for issue in page.issues],
            next_page_token=page.next_page_token,
            is_last=page.is_last,
        )

    @register(ToolName.GET_ISSUE)
    async def get_issue(key: str) -> Issue:
        """Fetch one issue in full detail by key."""
        return await client.get_issue(key)

    @register(ToolName.LIST_TRANSITIONS)
    async def list_transitions(key: str) -> list[Transition]:
        """List the status transitions currently valid for an issue."""
        return (await client.get_transitions(key)).transitions

    @register(ToolName.CREATE_ISSUE)
    async def create_issue(  # ruff: ignore[too-many-arguments]
        project: str,
        issue_type: IssueType | str,
        summary: str,
        *,
        description: str | None = None,
        assignee_account_id: str | None = None,
        priority: str | None = None,
        parent_key: str | None = None,
        labels: list[str] | None = None,
    ) -> Issue:
        """Create an issue. Set parent_key to make a subtask or attach to an epic."""
        fields = build_fields(
            project=project,
            issue_type=issue_type,
            summary=summary,
            description=description,
            assignee_account_id=assignee_account_id,
            priority=priority,
            parent_key=parent_key,
            labels=labels,
        )
        try:
            return await client.create_issue(fields)
        except JiraAPIError as exc:
            raise _reraise_parent_error(exc) from exc

    @register(ToolName.BATCH_CREATE_ISSUES)
    async def batch_create_issues(
        project: str, issues: list[dict[str, str]]
    ) -> BatchCreateResult:
        """Create many issues in one call.

        Each entry accepts summary, issue_type, description, parent_key, priority,
        and assignee_account_id. Returns a per-item result and does not raise when
        only some items fail.
        """
        field_sets = [
            build_fields(
                project=project,
                issue_type=item.get("issue_type", IssueType.TASK),
                summary=item.get("summary"),
                description=item.get("description"),
                assignee_account_id=item.get("assignee_account_id"),
                priority=item.get("priority"),
                parent_key=item.get("parent_key"),
            )
            for item in issues
        ]
        return await client.bulk_create_issues(field_sets)

    @register(ToolName.EDIT_ISSUE)
    async def edit_issue(  # ruff: ignore[too-many-arguments]
        key: str,
        *,
        summary: str | None = None,
        description: str | None = None,
        assignee_account_id: str | None = None,
        priority: str | None = None,
        issue_type: IssueType | str | None = None,
        parent_key: str | None = None,
        labels: list[str] | None = None,
    ) -> str:
        """Edit any subset of an issue's fields, including its type and parent."""
        fields = build_fields(
            issue_type=issue_type,
            summary=summary,
            description=description,
            assignee_account_id=assignee_account_id,
            priority=priority,
            parent_key=parent_key,
            labels=labels,
        )
        if not fields:
            msg = "edit_issue requires at least one field to change"
            raise ValueError(msg)
        try:
            await client.edit_issue(key, fields)
        except JiraAPIError as exc:
            raise _reraise_parent_error(exc) from exc
        return f"Updated {key}: {', '.join(sorted(fields))}"

    @register(ToolName.REMOVE_ISSUE)
    async def remove_issue(key: str) -> str:
        """Delete an issue permanently."""
        await client.delete_issue(key)
        return f"Deleted {key}"

    @register(ToolName.TRANSITION_ISSUE)
    async def transition_issue(key: str, transition_id: str) -> str:
        """Move an issue to a new status. Use list_transitions for valid ids."""
        await client.transition_issue(key, transition_id)
        return f"Transitioned {key}"

    @register(ToolName.LINK_ISSUES)
    async def link_issues(
        inward_key: str, outward_key: str, link_type: LinkType | str
    ) -> str:
        """Link two issues, e.g. link_type Blocks means inward blocks outward."""
        await client.link_issues(inward_key, outward_key, link_type)
        return f"Linked {inward_key} {link_type} {outward_key}"

    @register(ToolName.ADD_COMMENT)
    async def add_comment(key: str, markdown: str) -> Comment:
        """Add a comment to an issue, written as markdown."""
        return await client.add_comment(key, markdown)

    @register(ToolName.LIST_COMMENTS)
    async def list_comments(key: str) -> list[Comment]:
        """List an issue's comments."""
        return (await client.get_comments(key)).comments

    @register(ToolName.REMOVE_COMMENT)
    async def remove_comment(key: str, comment_id: str) -> str:
        """Delete a comment from an issue."""
        await client.delete_comment(key, comment_id)
        return f"Deleted comment {comment_id} from {key}"

    return server


def run(settings: Settings | None = None) -> None:
    resolved = settings if settings is not None else load_settings()
    enabled = resolve_tools(resolved.tools)
    client = JiraClient.from_settings(resolved)
    build_server(client, enabled).run()


def main() -> None:
    run()
