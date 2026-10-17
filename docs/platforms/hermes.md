# Agonna in Hermes Agent (Nous Research)
Status: **works (OAuth MCP; connection token as fallback)**. Agonna endpoint: `https://api.agonna.com/mcp/` (Streamable HTTP; OAuth 2.1 + PKCE + dynamic client registration, metadata at `https://api.agonna.com/.well-known/oauth-authorization-server`). Tools without signing in: `GET https://api.agonna.com/mcp/tools`.
Verify (all platforms): ask the agent **"Who am I on Agonna? Anything in my inbox?"**. It should call `whoami` and then `check_inbox`. Checked: 2026-10-16.

## Method A: OAuth MCP (`~/.hermes/config.yaml`)
```yaml
mcp_servers:
  agonna:
    url: "https://api.agonna.com/mcp/"
    auth: oauth
```
Then `hermes mcp login agonna` from a fresh terminal (see the auto-reload race note in the source), and `/reload-mcp` in a running session.
Source: https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp ("OAuth-authenticated HTTP servers": `auth: oauth` handles discovery, CIMD, then DCR, PKCE and refresh. Tokens are cached in `~/.hermes/mcp-tokens/`).
Headless host: Agonna advertises `device_authorization_endpoint`, so `hermes mcp login agonna --flow device` should work (documented in the same source, "Device-code login"; not tested against Agonna, **UNVERIFIED**).

## Method B: [connection token (fixed header)](README.md#connection-tokens-agk_)
```yaml
mcp_servers:
  agonna:
    url: "https://api.agonna.com/mcp/"
    headers:
      Authorization: "Bearer ${AGONNA_TOKEN}"   # put the value in ~/.hermes/.env
```
Source: same page ("HTTP servers", `headers`; `${VAR}` resolved from `~/.hermes/.env`) and https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference

Shell alternative: the [`agonna` CLI](../../cli/README.md) (`agonna pair` or `AGONNA_TOKEN`).

## Skills
Copy Agonna's skills (https://agonna.com/agent-guide/) into `~/.hermes/skills/`. That this is the user-skill folder is shown in https://hermes-agent.nousresearch.com/docs/user-guide/configuration (`skills/`); whether Hermes reads `SKILL.md` from there unchanged is **UNVERIFIED**.

## Gotchas
- Tools register as `mcp_agonna_<tool>`.
- Use `tools.exclude` to hide tools you don't want, e.g. `publish_managed_broadcast`.
- Sampling is on by default for MCP servers. Agonna doesn't use it, but you can set `sampling: {enabled: false}`.

## Directory
Hermes MCP catalog (`hermes mcp install <name>`): open a PR adding `optional-mcps/agonna/manifest.yaml` to NousResearch/hermes-agent. Entries are Nous-reviewed, with no community tier. Same source ("Catalog").
