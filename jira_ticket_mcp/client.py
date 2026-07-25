from __future__ import annotations

import collections.abc
import types
from typing import Self

import httpx

from jira_ticket_mcp.config import Settings
from jira_ticket_mcp.errors import JiraAPIError
from jira_ticket_mcp.models import HttpMethod, JiraModel, Myself

_TIMEOUT_SECONDS = 30.0


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


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            auth=httpx.BasicAuth(username=email, password=api_token),
            timeout=httpx.Timeout(_TIMEOUT_SECONDS),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> JiraClient:
        return cls(
            base_url=settings.jira_base_url,
            email=settings.jira_email,
            api_token=settings.jira_api_token.get_secret_value(),
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
        params: collections.abc.Mapping[str, str] | None = None,
    ) -> httpx.Response:
        payload = (
            body.model_dump(by_alias=True, exclude_none=True)
            if body is not None
            else None
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

    async def aclose(self) -> None:
        await self._http.aclose()
