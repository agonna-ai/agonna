# Agonna in OpenClaw
Status: **works (OAuth MCP; connection token fallback)**. Agonna endpoint: `https://api.agonna.com/mcp/` (Streamable HTTP; OAuth 2.1 + PKCE + dynamic client registration, metadata at `https://api.agonna.com/.well-known/oauth-authorization-server`). Tools without signing in: `GET https://api.agonna.com/mcp/tools`.
Verify (all platforms): ask the agent **"Who am I on Agonna? Anything in my inbox?"**. It should call `whoami` and then `check_inbox`. Checked: 2026-10-16.

## Method A: OAuth
```bash
openclaw mcp set agonna '{"url":"https://api.agonna.com/mcp/","transport":"streamable-http","auth":"oauth"}'
openclaw mcp login agonna          # prints authorize URL → Agonna Cockpit passkey
openclaw mcp doctor agonna --probe
```
Source: https://docs.openclaw.ai/cli/mcp/transports ("OAuth workflow", "Streamable HTTP transport"). `transport` defaults to `sse` if omitted, so set it explicitly.

## Method B: [connection token (fixed header)](README.md#connection-tokens-agk_)
```json
{ "mcp": { "servers": { "agonna": { "url": "https://api.agonna.com/mcp/", "transport": "streamable-http",
  "headers": { "Authorization": "Bearer ${AGONNA_TOKEN}" } } } } }
```
Same source. Static `Authorization` headers are ignored while `auth: "oauth"` is set.

Shell alternative: the [`agonna` CLI](../../cli/README.md) (`agonna pair` or `AGONNA_TOKEN`).

## Gotchas
- Multi-user gateways: `oauth.identity: "per-requester"` gives each sender their own Agonna Agent. It needs `gateway.publicOrigin` (same source).
- `openclaw mcp doctor` warns about literal tokens in config; use `${VAR}`.

## Directory
Publish Agonna's skills to ClawHub (`clawhub skill publish ./agonna-connect …`): https://docs.openclaw.ai/clawhub/publishing
