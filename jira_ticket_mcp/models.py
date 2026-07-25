from __future__ import annotations

import enum
import typing

import pydantic
import pydantic.alias_generators

from jira_ticket_mcp.adf import AdfDocument


def _markdown_from_adf(value: pydantic.JsonValue) -> pydantic.JsonValue:
    if isinstance(value, dict):
        return AdfDocument(value).to_markdown()
    return value


# Text stored in Jira as ADF, exposed to callers as markdown.
Markdown = typing.Annotated[str, pydantic.BeforeValidator(_markdown_from_adf)]


class HttpMethod(enum.StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class IssueType(enum.StrEnum):
    EPIC = "Epic"
    STORY = "Story"
    TASK = "Task"
    BUG = "Bug"
    SUBTASK = "Sub-task"


class LinkType(enum.StrEnum):
    BLOCKS = "Blocks"
    CLONERS = "Cloners"
    DUPLICATE = "Duplicate"
    RELATES = "Relates"


class JiraModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        alias_generator=pydantic.alias_generators.to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class Myself(JiraModel):
    account_id: str
    display_name: str
    email_address: str | None = None
    active: bool


class UserRef(JiraModel):
    account_id: str
    display_name: str | None = None


class NamedRef(JiraModel):
    id: str | None = None
    name: str | None = None


class ParentRef(JiraModel):
    key: str


class IssueFields(JiraModel):
    summary: str | None = None
    description: Markdown | None = None
    labels: list[str] = pydantic.Field(default_factory=list)
    status: NamedRef | None = None
    assignee: UserRef | None = None
    priority: NamedRef | None = None
    parent: ParentRef | None = None
    issue_type: NamedRef | None = pydantic.Field(default=None, alias="issuetype")


class Issue(JiraModel):
    id: str
    key: str
    self_: str | None = pydantic.Field(default=None, alias="self")
    fields: IssueFields


class SearchPage(JiraModel):
    issues: list[Issue] = pydantic.Field(default_factory=list)
    next_page_token: str | None = None
    is_last: bool | None = None


class ToolName(enum.StrEnum):
    WHOAMI = "whoami"
    SEARCH_ISSUES = "search_issues"
    GET_ISSUE = "get_issue"
    LIST_TRANSITIONS = "list_transitions"
    CREATE_ISSUE = "create_issue"
    BATCH_CREATE_ISSUES = "batch_create_issues"
    EDIT_ISSUE = "edit_issue"
    REMOVE_ISSUE = "remove_issue"
    TRANSITION_ISSUE = "transition_issue"
    LINK_ISSUES = "link_issues"
    ADD_COMMENT = "add_comment"
    LIST_COMMENTS = "list_comments"
    REMOVE_COMMENT = "remove_comment"


class Transition(JiraModel):
    id: str
    name: str
    to: NamedRef | None = None


class TransitionList(JiraModel):
    transitions: list[Transition] = pydantic.Field(default_factory=list)


class Comment(JiraModel):
    id: str
    body: Markdown | None = None
    author: UserRef | None = None
    created: str | None = None


class CommentPage(JiraModel):
    comments: list[Comment] = pydantic.Field(default_factory=list)
    total: int | None = None


class IssueSummary(JiraModel):
    key: str
    summary: str | None = None
    status: str | None = None
    issue_type: str | None = None
    assignee: str | None = None
    priority: str | None = None

    @classmethod
    def from_issue(cls, issue: Issue) -> IssueSummary:
        fields = issue.fields
        return cls(
            key=issue.key,
            summary=fields.summary,
            status=fields.status.name if fields.status else None,
            issue_type=fields.issue_type.name if fields.issue_type else None,
            assignee=fields.assignee.display_name if fields.assignee else None,
            priority=fields.priority.name if fields.priority else None,
        )


class SearchResult(JiraModel):
    issues: list[IssueSummary] = pydantic.Field(default_factory=list)
    next_page_token: str | None = None
    is_last: bool | None = None


class BatchItemResult(JiraModel):
    index: int
    key: str | None = None
    error: str | None = None


class BatchCreateResult(JiraModel):
    created: list[BatchItemResult] = pydantic.Field(default_factory=list)
    failed: list[BatchItemResult] = pydantic.Field(default_factory=list)
