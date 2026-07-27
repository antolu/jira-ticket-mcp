# jira-ticket-mcp

Minimal MCP server for managing Jira Cloud tickets.

The official Jira MCP server exposes a tool surface large enough to crowd out an
LLM's context. This one exposes a deliberately small, curated set of tools
covering the actions that actually get used.

## Configuration

The server reads three settings, from environment variables or from the
equivalent CLI arguments (CLI wins):

| Environment variable | CLI argument | Description |
|----------------------|--------------|-------------|
| `JIRA_BASE_URL` | `--jira-base-url` | Your Jira site, e.g. `https://example.atlassian.net` or `https://jira.example.com` |
| `JIRA_EMAIL` | `--jira-email` | The account email the API token belongs to (Cloud only) |
| `JIRA_API_TOKEN` | `--jira-api-token` | A Cloud API token, or a Data Center/Server personal access token |
| `JIRA_API_VERSION` | `--jira-api-version` | Force REST API `2` or `3`; autodetected from the host if unset |

## Running

```bash
uvx jira-ticket-mcp --jira-base-url https://example.atlassian.net \
                    --jira-email you@example.com \
                    --jira-api-token "$JIRA_API_TOKEN"
```

As an MCP server entry, e.g. for Claude Code:

```json
{
  "mcpServers": {
    "jira": {
      "command": "uvx",
      "args": ["jira-ticket-mcp"],
      "env": {
        "JIRA_BASE_URL": "https://example.atlassian.net",
        "JIRA_EMAIL": "you@example.com",
        "JIRA_API_TOKEN": "..."
      }
    }
  }
}
```

## Tools

| Tool | What it does |
|------|--------------|
| `whoami` | Return the authenticated account, including its `accountId` |
| `search_issues` | Search by JQL, returning a trimmed projection rather than full issues |
| `get_issue` | Fetch one issue in full detail |
| `list_transitions` | List the status transitions currently valid for an issue |
| `create_issue` | Create an issue; `parent_key` makes it a subtask or attaches it to an epic |
| `batch_create_issues` | Create many issues, returning a per-item result |
| `edit_issue` | Change any subset of summary, description, assignee, priority, type, parent, labels |
| `remove_issue` | Delete an issue |
| `transition_issue` | Move an issue to a new status |
| `link_issues` | Link two issues with a named link type |
| `add_comment` / `list_comments` / `remove_comment` | Manage comments |

Descriptions and comments are markdown in both directions; the server converts
to and from Atlassian Document Format at the boundary.

### Shrinking the surface further

Register only the tools you need with `--tools`:

```bash
uvx jira-ticket-mcp --tools search_issues,get_issue,edit_issue
```

Unlisted tools are never registered, so they cost the caller no context.

## Notes

- Jira Cloud (REST API v3, email + API token) and Data Center/Server (REST API v2,
  personal access token) are both supported. The API version is autodetected from
  the host (`*.atlassian.net` → v3, anything else → v2); override with
  `JIRA_API_VERSION`/`--jira-api-version` if autodetection picks the wrong one.
- Epics are linked through the `parent` field, which works on team-managed
  projects. Company-managed projects use an instance-specific Epic Link custom
  field; on those, setting a parent fails with an error saying so.
- `batch_create_issues` never raises on partial failure — Jira does not roll
  back, so it reports which items landed and which did not.

## Development

```bash
pip install -e ".[test,dev]"
pytest
pre-commit run --all-files
```

## License

MIT
