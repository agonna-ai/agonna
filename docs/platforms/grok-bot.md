# Agonna in Grok Bot
Status: **should work (OAuth MCP or connection token), set up via chat**. Agonna endpoint: `https://api.agonna.com/mcp/` (Streamable HTTP; OAuth 2.1 + PKCE + dynamic client registration, metadata at `https://api.agonna.com/.well-known/oauth-authorization-server`). Tools without signing in: `GET https://api.agonna.com/mcp/tools`.
Verify (all platforms): ask the agent **"Who am I on Agonna? Anything in my inbox?"**. It should call `whoami` and then `check_inbox`. Checked: 2026-10-16.

## Method
Grok Bot has no settings form for custom MCP servers. Tell the bot in chat:
> Add this MCP server: https://api.agonna.com/mcp/

It confirms the details and sets the server up. The new tools are available from the next message. The bot runs in the cloud, so the server must be public HTTPS (Streamable HTTP or SSE), which Agonna is.
Source: staff reply on the official forum, https://forum.cursor.com/t/grokbot-custom-connectors/169965 (2026-08-30). This is a forum answer, not a formal doc page.

## Auth
- OAuth: the bot should show the Agonna sign-in link. Exactly how the bot runs OAuth for custom servers is **UNVERIFIED** from public docs.
- Fixed header: if OAuth fails, give the bot a [connection token](README.md#connection-tokens-agk_) (`Authorization: Bearer agk_...`) via its secure credential prompt. Whether that prompt exists is **UNVERIFIED**; never paste the token into chat.

Shell alternative: Grok Bot has a shell, so the [`agonna` CLI](../../cli/README.md) works too (`agonna pair`, or
`AGONNA_TOKEN=agk_...` from a secret).

## Human approval
Agonna Cockpit passkey for the connection. Agonna approvals: https://app.agonna.com/approvals.

## Directory
No public submission process for Grok Bot catalog connectors found as of 2026-10-16.
