from __future__ import annotations

import pydantic
import pydantic_settings

_REQUIRED_SCHEME = "https://"


class Settings(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(
        cli_prog_name="jira-ticket-mcp",
        cli_kebab_case=True,
        cli_parse_args=True,
    )

    jira_base_url: str = pydantic.Field(description="Jira base URL")
    jira_email: str | None = pydantic.Field(
        default=None,
        description="Jira account email (required for Jira Cloud / API v3 basic auth)",
    )
    jira_api_token: pydantic.SecretStr = pydantic.Field(
        description="Jira API token (Cloud) or personal access token (Data Center)"
    )
    jira_api_version: str | None = pydantic.Field(
        default=None,
        description="Force Jira REST API version ('2' or '3'); autodetected from host",
    )
    tools: str | None = pydantic.Field(
        default=None,
        description="Comma-separated allowlist of tools to register (default: all)",
    )

    @pydantic.field_validator("jira_base_url", "jira_email", mode="before")
    @classmethod
    def _reject_blank(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError(_BLANK_MESSAGE)
            return stripped
        return value

    @pydantic.field_validator("jira_base_url")
    @classmethod
    def _require_https(cls, value: str) -> str:
        if not value.startswith(_REQUIRED_SCHEME):
            raise ValueError(_SCHEME_MESSAGE)
        return value.rstrip("/")


_BLANK_MESSAGE = "must not be empty or whitespace"
_SCHEME_MESSAGE = f"must use the {_REQUIRED_SCHEME} scheme"


def load_settings() -> Settings:
    return Settings()
