# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- GSD:project-start source:PROJECT.md -->

## Project

**jira-ticket-mcp**

A minimal MCP server for managing Jira Cloud tickets, published to PyPI and runnable via `uvx`. It exists because the official Jira MCP server is a context explosion — this one exposes a deliberately small, curated set of tools covering the actions that actually get used, with per-tool gating (`--tools`) so callers can shrink the surface further; unregistered tools cost the caller no context.

### Constraints

- **Tech stack**: Python 3.11+; official `mcp` SDK (FastMCP) derives tool schemas from type hints and pydantic models
- **Tech stack**: `httpx` async client; `respx` mocks the transport in tests (no real Jira instance is ever contacted)
- **Typing**: mypy with no `typing.Any`; pydantic models for all requests/responses
- **Compatibility**: Jira Cloud (REST API v3, email + API token) and Data Center/Server (REST API v2, personal access token) are both supported; `client.py`'s `_detect_api_version()` picks v3/v2 from the host, overridable via `jira_api_version`
- **Distribution**: runs under `uvx`, published to PyPI from GitHub Actions; version is derived from git tags via setuptools-scm — never hand-edit `jira_ticket_mcp/_version.py`
- **Licensing**: MIT

<!-- GSD:project-end -->

## Commands

```bash
pip install -e ".[test,dev]"

pytest                                          # full suite
pytest -vv --maxfail=1 --durations=10           # matches CI exactly
pytest --lf                                     # last failures only, for debugging
pytest tests/test_client.py::test_name          # single test
pytest --cov=jira_ticket_mcp                    # coverage

pre-commit run --all-files                      # ruff-check, ruff-format, mypy — must pass before commit
```

Run ruff/mypy via `pre-commit`, not standalone — versions are pinned there (and separately in `pyproject.toml`'s `dev` extra) and must match CI.

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Request flow: `server.py` (MCP tool definitions) → `client.py` (`JiraClient`, one HTTP call per tool) → Jira REST API. `models.py` holds all pydantic request/response shapes; there's no separate service/repository layer.

- **`server.py`** — `build_server()` wires each `ToolName` to a `JiraClient` call via `FastMCP.add_tool`, gated by the `enabled` set so unregistered tools are never sent to the caller. `resolve_tools()` parses the `--tools`/`tools` allowlist. Tool docstrings are the descriptions MCP callers see — keep them accurate when changing behavior. `_reraise_parent_error()` intercepts Jira's opaque "parent field" rejection and appends a hint about the Epic Link caveat (see below).
- **`client.py`** — `JiraClient` wraps a single `httpx.AsyncClient`. `_detect_api_version()` picks v3 (Cloud, basic auth with email+token) vs v2 (Data Center, bearer token) from the host unless `jira_api_version` overrides it; endpoint methods that differ between versions branch internally (e.g. `search_jql` vs `_search_v2`) so callers never need to know which version is in play. All requests funnel through one `_request()` chokepoint that converts non-2xx responses into `JiraAPIError`. `build_fields()` is the single place that assembles a Jira `fields` payload from optional args, shared by `create_issue`, `batch_create_issues`, and `edit_issue`.
- **`models.py`** — pydantic models with `alias_generator=to_camel` to match Jira's camelCase JSON. `Markdown` is an `Annotated[str, BeforeValidator]` type that transparently converts ADF (v3) or wiki markup (v2) to markdown when a model is built — callers of `Issue`/`Comment` always see markdown regardless of API version. `IssueSummary.from_issue()` is the trimmed projection `search_issues` returns instead of full `Issue` objects.
- **`adf.py` / `wiki.py`** — the two rich-text codecs, selected by `JiraClient.encode_rich_text()` based on API version (the only place that decision is made when writing). `adf.py` uses `marklas` (markdown→ADF) and `pyadf` (ADF→markdown), replacing media/attachment nodes with a `[attachment: label]` placeholder since attachments can't round-trip through markdown. `wiki.py` hand-rolls markdown→wiki-markup over a `mistune` AST (no library does this direction) and uses `jira2markdown` for the reverse.
- **`config.py`** — `Settings` (pydantic-settings) reads `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN`/`JIRA_API_VERSION`/`TOOLS` from env or CLI (`cli_parse_args=True`); CLI wins over env.
- **`errors.py`** — `JiraAPIError` normalizes Jira's inconsistent error bodies (`errorMessages` list, `errors` dict, or plain text) into one shape with a readable `str()`.

**Batch semantics**: `batch_create_issues` never raises on partial failure — Jira's bulk endpoint doesn't roll back, so `_batch_result()`/`_batch_error()` in `client.py` reconcile the `issues`/`errors` arrays (padding with synthetic failures if Jira's counts don't add up) into a per-item `BatchCreateResult`.

**Adding a new tool**: add a `ToolName` member in `models.py`, register it in `build_server()` with `@register(...)`, add the matching `JiraClient` method if new HTTP behavior is needed, and update the tools table in `README.md`.

**Non-obvious gotchas** (documented in the README because they don't follow from the API surface): epics attach through the `parent` field, which only works on team-managed projects — company-managed projects need an instance-specific Epic Link custom field, and setting `parent` there fails with an error explaining this. `edit_issue`'s `description` fully replaces the field, so attachments embedded in the old description are lost when it's rewritten.

<!-- GSD:architecture-end -->

## Testing

`respx` mocks the `httpx` transport — see `tests/conftest.py` for the `jira_client`/`jira_client_v2` fixtures and `tests/fixtures/*.json` for canned Jira responses. Functional tests only (`def test_x()`, never `class TestX`).

> **Note:** `.planning/codebase/*.md` (ARCHITECTURE.md, STACK.md, STRUCTURE.md, TESTING.md, CONVENTIONS.md) describe an unrelated hypothetical search-engine/Elasticsearch project and do not reflect this codebase — they predate a prior `/gsd-map-codebase` run gone wrong. Don't trust them; regenerate before relying on GSD tooling that reads them.

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
