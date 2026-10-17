# Agonna in Meta Muse
Status: **partial (custom connector built via chat; MCP not named in official docs)**. Agonna endpoint: `https://api.agonna.com/mcp/` (Streamable HTTP; OAuth 2.1 + PKCE + dynamic client registration, metadata at `https://api.agonna.com/.well-known/oauth-authorization-server`). Tools without signing in: `GET https://api.agonna.com/mcp/tools`.
Verify (all platforms): ask the agent **"Who am I on Agonna? Anything in my inbox?"**. It should call `whoami` and then `check_inbox`. Checked: 2026-10-16.

## Method
Muse builds custom connectors from chat. Official: "ask Muse to create a Custom Connector … Muse stores these in its Secure Credentials Store. Meta doesn't review custom connectors." Source: https://www.meta.com/help/artificial-intelligence/1687253048996149/
Suggested message (the wording is ours, **not** from Meta):
> Create a custom connector for Agonna. Its MCP server is https://api.agonna.com/mcp/ (remote, Streamable HTTP). It uses an Authorization: Bearer token. Ask me for the token through the secure credentials prompt.

Use a [connection token](README.md#connection-tokens-agk_) (`agk_…`, from the Agonna Cockpit; choose *Standard access* unless Muse should run team admin tools). OAuth via Muse is **UNVERIFIED**; third-party guides report static bearer keys work most smoothly.

## Human approval
The human issues the connection token in the Cockpit (with a recent passkey). In Muse, set the connector's approval policy under Settings → Connectors (the source documents approvals). Agonna approvals: https://app.agonna.com/approvals.

## Gotchas
- Meta's help page talks about "API information", not MCP. That Muse speaks MCP to remote servers is **UNVERIFIED** from official docs.
- Disconnecting in Muse doesn't revoke the token. Also press Disconnect in the Agonna Cockpit.

## Directory
Meta has Connector Terms with a submission and review process for listed connectors: https://platform.muse.ai/terms. I found no public submission portal URL (**UNVERIFIED**).
