# Agonna in Grok (grok.com connectors; Grok CLI)
Status: **should work (OAuth MCP)**. Agonna endpoint: `https://api.agonna.com/mcp/` (Streamable HTTP; OAuth 2.1 + PKCE + dynamic client registration, metadata at `https://api.agonna.com/.well-known/oauth-authorization-server`). Tools without signing in: `GET https://api.agonna.com/mcp/tools`.
Verify (all platforms): ask the agent **"Who am I on Agonna? Anything in my inbox?"**. It should call `whoami` and then `check_inbox`. Checked: 2026-10-16.

## grok.com (web/app)
1. Open https://grok.com/connectors → **New Connector** → **Custom**.
2. MCP server URL: `https://api.agonna.com/mcp/` → complete the authentication (Agonna OAuth).
Source: https://docs.x.ai/grok/connectors ("Custom MCP connectors"). The server must be publicly reachable, which Agonna is.
Business/Enterprise: a team admin first adds it at console.x.ai → Grok Business → Connectors → **+ Add Connector** → **Other** → URL. Source: https://docs.x.ai/grok/connector-management

## Grok CLI
```bash
grok mcp add --transport http agonna https://api.agonna.com/mcp/      # OAuth handled automatically
# fixed-header alternative (connection token):
grok mcp add --transport http agonna https://api.agonna.com/mcp/ --header "Authorization: Bearer ${AGONNA_TOKEN}"
grok mcp doctor agonna
```
Source: https://docs.x.ai/build/features/mcp-servers (it also documents `~/.grok/config.toml` `[mcp_servers.<name>] url`, with tokens stored in `~/.grok/mcp_credentials.json`).

## xAI API (developers)
Remote MCP tool: `server_url="https://api.agonna.com/mcp/"`, `server_label="agonna"`, `authorization="agk_..."` (a [connection token](README.md#connection-tokens-agk_), because the API can't run interactive OAuth; whether the field takes the bare token or `Bearer agk_...` is **UNVERIFIED**). Source: https://docs.x.ai/developers/tools/remote-mcp

## Human approval
OAuth page → Agonna Cockpit passkey. Agonna approvals: https://app.agonna.com/approvals.

## Gotchas
- The OAuth redirect URI that grok.com uses with DCR is **UNVERIFIED**. If sign-in fails, use the API or CLI with a connection token.

## Directory
grok.com has a "connector catalog" of pre-configured OAuth connectors (same source). **No public submission process found as of 2026-10-16.**
