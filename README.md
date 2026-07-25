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
| `JIRA_BASE_URL` | `--jira-base-url` | Your Jira Cloud site, e.g. `https://example.atlassian.net` |
| `JIRA_EMAIL` | `--jira-email` | The account email the API token belongs to |
| `JIRA_API_TOKEN` | `--jira-api-token` | An API token from https://id.atlassian.com/manage-profile/security/api-tokens |

## Status

Early development. The tool surface and `uvx` invocation are documented once
they exist.

## License

MIT
