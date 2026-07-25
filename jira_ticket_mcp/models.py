from __future__ import annotations

import enum

import pydantic
import pydantic.alias_generators

from jira_ticket_mcp.adf import AdfDocument


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
    description: AdfDocument | None = None
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
