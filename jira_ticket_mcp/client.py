from __future__ import annotations

import collections.abc
import types
from typing import Self

import httpx
import pydantic

from jira_ticket_mcp.adf import AdfDocument
from jira_ticket_mcp.config import Settings
from jira_ticket_mcp.errors import JiraAPIError
from jira_ticket_mcp.models import (
    BatchCreateResult,
    BatchItemResult,
    Comment,
    CommentPage,
    HttpMethod,
    Issue,
    IssueType,
    JiraModel,
    LinkType,
    Myself,
    SearchPage,
    TransitionList,
)

_TIMEOUT_SECONDS = 30.0
_CLOUD_HOST = "atlassian.net"


def _detect_api_version(base_url: str, override: str | None) -> str:
    if override is not None:
        version = override.strip()
        if version not in {"2", "3"}:
            msg = f"jira_api_version must be '2' or '3', got {override!r}"
            raise ValueError(msg)
        return version
    host = httpx.URL(base_url).host
    is_cloud = host == _CLOUD_HOST or host.endswith(f".{_CLOUD_HOST}")
    return "3" if is_cloud else "2"


def _text_messages(response: httpx.Response) -> list[str]:
    try:
        text = response.text
    except UnicodeDecodeError:
        return []
    stripped = text.strip()
    return [stripped] if stripped else []


def _error_from_response(response: httpx.Response) -> JiraAPIError:
    status = response.status_code
    if not response.content:
        return JiraAPIError(status=status, messages=[], errors={})
    try:
        body = response.json()
    except ValueError:
        return JiraAPIError(status=status, messages=_text_messages(response), errors={})
    if not isinstance(body, dict):
        return JiraAPIError(status=status, messages=_text_messages(response), errors={})
    raw_messages = body.get("errorMessages", [])
    raw_errors = body.get("errors", {})
    messages = (
        [str(item) for item in raw_messages] if isinstance(raw_messages, list) else []
    )
    errors = (
        {str(key): str(value) for key, value in raw_errors.items()}
        if isinstance(raw_errors, dict)
        else {}
    )
    if not messages and not errors:
        messages = _text_messages(response)
    return JiraAPIError(status=status, messages=messages, errors=errors)


def _batch_result(body: pydantic.JsonValue, *, total: int) -> BatchCreateResult:
    created: list[BatchItemResult] = []
    failed: list[BatchItemResult] = []
    if not isinstance(body, dict):
        return BatchCreateResult(created=created, failed=failed)
    raw_issues = body.get("issues")
    if isinstance(raw_issues, list):
        created = [
            BatchItemResult(index=position, key=str(item["key"]))
            for position, item in enumerate(raw_issues)
            if isinstance(item, dict) and "key" in item
        ]
    raw_errors = body.get("errors")
    if isinstance(raw_errors, list):
        failed = [
            _batch_error(item, fallback=position)
            for position, item in enumerate(raw_errors)
        ]
    accounted = len(created) + len(failed)
    if accounted < total:
        failed.extend(
            BatchItemResult(
                index=position, error="Jira returned no result for this item"
            )
            for position in range(accounted, total)
        )
    return BatchCreateResult(created=created, failed=failed)


def _batch_error(item: pydantic.JsonValue, *, fallback: int) -> BatchItemResult:
    if not isinstance(item, dict):
        return BatchItemResult(index=fallback, error=str(item))
    raw_index = item.get("failedElementNumber")
    index = raw_index if isinstance(raw_index, int) else fallback
    status = item.get("status")
    detail = item.get("elementErrors")
    messages: list[str] = []
    if isinstance(detail, dict):
        raw_messages = detail.get("errorMessages")
        if isinstance(raw_messages, list):
            messages.extend(str(message) for message in raw_messages)
        raw_errors = detail.get("errors")
        if isinstance(raw_errors, dict):
            messages.extend(f"{key}: {value}" for key, value in raw_errors.items())
    text = "; ".join(messages) or "Jira rejected this item"
    if isinstance(status, int):
        text = f"{status}: {text}"
    return BatchItemResult(index=index, error=text)


class JiraClient:
    def __init__(
        self,
        base_url: str,
        *,
        api_token: str,
        email: str | None = None,
        api_version: str = "3",
    ) -> None:
        self._api_version = api_version
        auth: httpx.Auth | None = None
        headers: dict[str, str] = {}
        if api_version == "3":
            if not email:
                msg = "Jira Cloud (API v3) requires an email for basic auth"
                raise ValueError(msg)
            auth = httpx.BasicAuth(username=email, password=api_token)
        else:
            headers["Authorization"] = f"Bearer {api_token}"
        self._http = httpx.AsyncClient(
            base_url=base_url,
            auth=auth,
            headers=headers,
            timeout=httpx.Timeout(_TIMEOUT_SECONDS),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> JiraClient:
        return cls(
            base_url=settings.jira_base_url,
            email=settings.jira_email,
            api_token=settings.jira_api_token.get_secret_value(),
            api_version=_detect_api_version(
                settings.jira_base_url, settings.jira_api_version
            ),
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _request(
        self,
        method: HttpMethod,
        path: str,
        *,
        body: JiraModel | None = None,
        json_body: dict[str, pydantic.JsonValue] | None = None,
        params: collections.abc.Mapping[str, str] | None = None,
    ) -> httpx.Response:
        payload = (
            body.model_dump(by_alias=True, exclude_none=True)
            if body is not None
            else json_body
        )
        response = await self._http.request(method, path, json=payload, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise _error_from_response(exc.response) from exc
        return response

    async def get_myself(self) -> Myself:
        response = await self._request(HttpMethod.GET, "/rest/api/3/myself")
        return Myself.model_validate(response.json())

    async def get_issue(self, key: str, *, fields: list[str] | None = None) -> Issue:
        params = {"fields": ",".join(fields)} if fields else None
        response = await self._request(
            HttpMethod.GET, f"/rest/api/3/issue/{key}", params=params
        )
        return Issue.model_validate(response.json())

    async def search_jql(
        self,
        jql: str,
        *,
        max_results: int = 50,
        next_page_token: str | None = None,
        fields: list[str] | None = None,
    ) -> SearchPage:
        payload: dict[str, pydantic.JsonValue] = {
            "jql": jql,
            "maxResults": max_results,
        }
        if next_page_token is not None:
            payload["nextPageToken"] = next_page_token
        if fields is not None:
            payload["fields"] = list(fields)
        response = await self._request(
            HttpMethod.POST, "/rest/api/3/search/jql", json_body=payload
        )
        return SearchPage.model_validate(response.json())

    async def create_issue(self, fields: dict[str, pydantic.JsonValue]) -> Issue:
        response = await self._request(
            HttpMethod.POST, "/rest/api/3/issue", json_body={"fields": fields}
        )
        return Issue.model_validate(response.json())

    async def bulk_create_issues(
        self, field_sets: list[dict[str, pydantic.JsonValue]]
    ) -> BatchCreateResult:
        payload: dict[str, pydantic.JsonValue] = {
            "issueUpdates": [{"fields": fields} for fields in field_sets]
        }
        response = await self._request(
            HttpMethod.POST, "/rest/api/3/issue/bulk", json_body=payload
        )
        return _batch_result(response.json(), total=len(field_sets))

    async def edit_issue(self, key: str, fields: dict[str, pydantic.JsonValue]) -> None:
        await self._request(
            HttpMethod.PUT, f"/rest/api/3/issue/{key}", json_body={"fields": fields}
        )

    async def delete_issue(self, key: str) -> None:
        await self._request(HttpMethod.DELETE, f"/rest/api/3/issue/{key}")

    async def get_transitions(self, key: str) -> TransitionList:
        response = await self._request(
            HttpMethod.GET, f"/rest/api/3/issue/{key}/transitions"
        )
        return TransitionList.model_validate(response.json())

    async def transition_issue(self, key: str, transition_id: str) -> None:
        await self._request(
            HttpMethod.POST,
            f"/rest/api/3/issue/{key}/transitions",
            json_body={"transition": {"id": transition_id}},
        )

    async def link_issues(
        self, inward_key: str, outward_key: str, link_type: LinkType | str
    ) -> None:
        payload: dict[str, pydantic.JsonValue] = {
            "type": {"name": str(link_type)},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        await self._request(HttpMethod.POST, "/rest/api/3/issueLink", json_body=payload)

    async def add_comment(self, key: str, markdown: str) -> Comment:
        body = AdfDocument.from_markdown(markdown).model_dump()
        response = await self._request(
            HttpMethod.POST,
            f"/rest/api/3/issue/{key}/comment",
            json_body={"body": body},
        )
        return Comment.model_validate(response.json())

    async def get_comments(self, key: str) -> CommentPage:
        response = await self._request(
            HttpMethod.GET, f"/rest/api/3/issue/{key}/comment"
        )
        return CommentPage.model_validate(response.json())

    async def delete_comment(self, key: str, comment_id: str) -> None:
        await self._request(
            HttpMethod.DELETE, f"/rest/api/3/issue/{key}/comment/{comment_id}"
        )

    async def aclose(self) -> None:
        await self._http.aclose()


def build_fields(  # ruff: ignore[too-many-arguments]
    *,
    project: str | None = None,
    issue_type: IssueType | str | None = None,
    summary: str | None = None,
    description: str | None = None,
    assignee_account_id: str | None = None,
    priority: str | None = None,
    parent_key: str | None = None,
    labels: list[str] | None = None,
) -> dict[str, pydantic.JsonValue]:
    fields: dict[str, pydantic.JsonValue] = {}
    if project is not None:
        fields["project"] = {"key": project}
    if issue_type is not None:
        fields["issuetype"] = {"name": str(issue_type)}
    if summary is not None:
        fields["summary"] = summary
    if description is not None:
        fields["description"] = AdfDocument.from_markdown(description).model_dump()
    if assignee_account_id is not None:
        fields["assignee"] = {"accountId": assignee_account_id}
    if priority is not None:
        fields["priority"] = {"name": priority}
    if parent_key is not None:
        fields["parent"] = {"key": parent_key}
    if labels is not None:
        fields["labels"] = list(labels)
    return fields
