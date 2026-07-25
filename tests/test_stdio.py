"""End-to-end checks that spawn the server and speak MCP over real stdio.

Everything else exercises ``build_server`` in-process. These tests cover what
that cannot: the console entry point, CLI argument parsing, and the stdio
transport a client actually connects through. No Jira call is made, so no
credentials are needed.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import mcp
import mcp.client.stdio
import pytest

from jira_ticket_mcp.models import ToolName

_LAUNCH = (
    "import sys; sys.argv = ['jira-ticket-mcp', *sys.argv[1:]]; "
    "from jira_ticket_mcp.server import main; main()"
)

_CREDENTIALS = {
    "JIRA_BASE_URL": "https://example.atlassian.net",
    "JIRA_EMAIL": "smoke@example.com",
    "JIRA_API_TOKEN": "smoke-token",
}

_STARTUP_TIMEOUT_SECONDS = 60.0


async def _list_tool_names(*args: str) -> list[str]:
    params = mcp.StdioServerParameters(
        command=sys.executable,
        args=["-c", _LAUNCH, *args],
        env={**os.environ, **_CREDENTIALS},
    )
    async with asyncio.timeout(_STARTUP_TIMEOUT_SECONDS):
        async with mcp.client.stdio.stdio_client(params) as (read, write):
            async with mcp.ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                return sorted(tool.name for tool in listing.tools)


async def test_stdio_server_registers_every_tool() -> None:
    assert await _list_tool_names() == sorted(tool.value for tool in ToolName)


async def test_stdio_server_honours_the_tools_allowlist() -> None:
    names = await _list_tool_names("--tools", "search_issues,get_issue")

    assert names == ["get_issue", "search_issues"]


async def test_stdio_server_exposes_required_arguments() -> None:
    params = mcp.StdioServerParameters(
        command=sys.executable,
        args=["-c", _LAUNCH],
        env={**os.environ, **_CREDENTIALS},
    )
    async with asyncio.timeout(_STARTUP_TIMEOUT_SECONDS):
        async with mcp.client.stdio.stdio_client(params) as (read, write):
            async with mcp.ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()

    tools = {tool.name: tool for tool in listing.tools}
    assert tools["get_issue"].inputSchema["required"] == ["key"]
    assert tools["edit_issue"].inputSchema["required"] == ["key"]
    assert "summary" not in tools["edit_issue"].inputSchema["required"]
    assert tools["whoami"].inputSchema.get("required", []) == []


def test_server_refuses_to_start_without_configuration() -> None:
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in _CREDENTIALS and not name.startswith("JIRA_")
    }

    completed = subprocess.run(
        [sys.executable, "-c", _LAUNCH],
        env=environment,
        capture_output=True,
        text=True,
        timeout=_STARTUP_TIMEOUT_SECONDS,
        check=False,
    )

    assert completed.returncode != 0
    assert "jira_base_url" in completed.stderr
    assert "jira_api_token" in completed.stderr


def test_unknown_tool_name_is_rejected_at_startup() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", _LAUNCH, "--tools", "get_issue,delete_everything"],
        env={**os.environ, **_CREDENTIALS},
        capture_output=True,
        text=True,
        timeout=_STARTUP_TIMEOUT_SECONDS,
        check=False,
    )

    assert completed.returncode != 0
    assert "delete_everything" in completed.stderr


@pytest.mark.parametrize("flag", ["--jira-base-url", "--jira-email"])
def test_missing_flag_value_is_rejected(flag: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", _LAUNCH, flag],
        env={**os.environ, **_CREDENTIALS},
        capture_output=True,
        text=True,
        timeout=_STARTUP_TIMEOUT_SECONDS,
        check=False,
    )

    assert completed.returncode != 0
