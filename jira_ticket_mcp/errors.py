from __future__ import annotations

_NO_DETAIL = "no detail provided"


class JiraAPIError(Exception):
    def __init__(
        self, status: int, messages: list[str], errors: dict[str, str]
    ) -> None:
        self.status = status
        self.messages = messages
        self.errors = errors
        detail = "; ".join([*messages, *(f"{k}: {v}" for k, v in errors.items())])
        super().__init__(f"Jira API error {status}: {detail or _NO_DETAIL}")
