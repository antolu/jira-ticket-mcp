from __future__ import annotations

import sys

import pydantic
import pytest

from jira_ticket_mcp.config import Settings, load_settings

_ENV_VARS = (
    "JIRA_BASE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "JIRA_API_VERSION",
    "TOOLS",
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "argv", ["jira-ticket-mcp"])


def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_BASE_URL", "https://env.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "env@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "env-token")


def test_reads_every_setting_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch)

    settings = load_settings()

    assert settings.jira_base_url == "https://env.atlassian.net"
    assert settings.jira_email == "env@example.com"
    assert settings.jira_api_token.get_secret_value() == "env-token"
    assert settings.tools is None


def test_cli_argument_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch)
    monkeypatch.setattr(
        sys, "argv", ["jira-ticket-mcp", "--jira-base-url", "https://cli.atlassian.net"]
    )

    settings = load_settings()

    assert settings.jira_base_url == "https://cli.atlassian.net"
    assert settings.jira_email == "env@example.com"


def test_cli_supplies_settings_absent_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "jira-ticket-mcp",
            "--jira-base-url",
            "https://cli.atlassian.net",
            "--jira-email",
            "cli@example.com",
            "--jira-api-token",
            "cli-token",
            "--tools",
            "get_issue,search_issues",
        ],
    )

    settings = load_settings()

    assert settings.jira_email == "cli@example.com"
    assert settings.jira_api_token.get_secret_value() == "cli-token"
    assert settings.tools == "get_issue,search_issues"


def test_missing_configuration_names_every_absent_setting() -> None:
    with pytest.raises(pydantic.ValidationError) as excinfo:
        load_settings()

    message = str(excinfo.value)
    assert "jira_base_url" in message
    assert "jira_api_token" in message


def test_email_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_BASE_URL", "https://dc.example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "pat")

    settings = load_settings()

    assert settings.jira_email is None


def test_accepts_api_version_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch)
    monkeypatch.setenv("JIRA_API_VERSION", "2")

    assert load_settings().jira_api_version == "2"


def test_missing_configuration_names_only_the_absent_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JIRA_BASE_URL", "https://env.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "env@example.com")

    with pytest.raises(pydantic.ValidationError) as excinfo:
        load_settings()

    missing = [error["loc"] for error in excinfo.value.errors()]
    assert missing == [("jira_api_token",)]


def test_token_is_not_exposed_by_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch)

    settings = load_settings()

    assert "env-token" not in repr(settings)
    assert "env-token" not in str(settings.jira_api_token)


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_required_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    _set_env(monkeypatch)
    monkeypatch.setenv("JIRA_EMAIL", value)

    with pytest.raises(pydantic.ValidationError, match="must not be empty"):
        load_settings()


def test_base_url_requires_https(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch)
    monkeypatch.setenv("JIRA_BASE_URL", "http://env.atlassian.net")

    with pytest.raises(pydantic.ValidationError, match="https://"):
        load_settings()


def test_base_url_is_stripped_of_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch)
    monkeypatch.setenv("JIRA_BASE_URL", "https://env.atlassian.net/")

    assert load_settings().jira_base_url == "https://env.atlassian.net"


def test_settings_accept_direct_construction() -> None:
    settings = Settings(
        jira_base_url="https://direct.atlassian.net",
        jira_email="direct@example.com",
        jira_api_token=pydantic.SecretStr("direct-token"),
    )

    assert settings.jira_base_url == "https://direct.atlassian.net"
