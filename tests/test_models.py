from __future__ import annotations

import collections.abc
import json

import pytest

from jira_ticket_mcp.models import (
    HttpMethod,
    Issue,
    IssueFields,
    IssueType,
    LinkType,
    SearchPage,
)

LoadFixture = collections.abc.Callable[[str], str]


def test_issue_fields_ignores_undeclared_keys(load_fixture: LoadFixture) -> None:
    payload = json.loads(load_fixture("issue_get_200.json"))["fields"]

    fields = IssueFields.model_validate(payload)

    assert fields.summary == "Rotate the staging API token"
    assert fields.description is not None
    assert not hasattr(fields, "customfield_10014")
    assert not hasattr(fields, "customfield_10020")
    assert not hasattr(fields, "watches")


def test_issue_exposes_self_from_reserved_key(load_fixture: LoadFixture) -> None:
    payload = json.loads(load_fixture("issue_get_200.json"))

    issue = Issue.model_validate(payload)

    assert issue.self_ == payload["self"]


def test_issue_fields_reads_lowercase_issuetype_key(load_fixture: LoadFixture) -> None:
    payload = json.loads(load_fixture("issue_get_200.json"))["fields"]

    fields = IssueFields.model_validate(payload)

    assert fields.issue_type is not None
    assert fields.issue_type.name == "Task"


def test_search_page_defaults_issues_to_empty_list() -> None:
    page = SearchPage.model_validate({"issues": []})

    assert page.issues == []


def test_search_page_preserves_order(load_fixture: LoadFixture) -> None:
    payload = json.loads(load_fixture("search_jql_200.json"))

    page = SearchPage.model_validate(payload)

    assert [issue.key for issue in page.issues] == [
        issue["key"] for issue in payload["issues"]
    ]


def test_issue_type_is_case_sensitive() -> None:
    assert IssueType("Task") is IssueType.TASK
    with pytest.raises(ValueError, match="task"):
        IssueType("task")
    with pytest.raises(ValueError, match="is not a valid IssueType"):
        IssueType("")


def test_issue_type_compares_as_string() -> None:
    assert IssueType.TASK == "Task"
    assert IssueType.TASK != "task"
    assert IssueType.SUBTASK == "Sub-task"


def test_http_method_members_are_strings() -> None:
    assert HttpMethod.GET == "GET"
    assert all(isinstance(member, str) for member in HttpMethod)


def test_link_type_members_are_strings() -> None:
    assert LinkType.BLOCKS == "Blocks"
    assert all(isinstance(member, str) for member in LinkType)
