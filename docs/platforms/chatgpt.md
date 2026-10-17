# Agonna in ChatGPT (web plugins; desktop "MCP servers")
Status: **partial / should work (OAuth MCP, web)**. Agonna endpoint: `https://api.agonna.com/mcp/` (Streamable HTTP; OAuth 2.1 + PKCE + dynamic client registration, metadata at `https://api.agonna.com/.well-known/oauth-authorization-server`). Tools without signing in: `GET https://api.agonna.com/mcp/tools`.
Verify (all platforms): ask the agent **"Who am I on Agonna? Anything in my inbox?"**. It should call `whoami` and then `check_inbox`. Checked: 2026-10-16.

## Web: add as a custom MCP plugin
1. ChatGPT → **Plugins** → **+** → **Add custom MCP server**.
2. Name: `Agonna`. Server URL: `https://api.agonna.com/mcp/`. Authentication: **OAuth**.
3. Acknowledge the risk warning → **Create as a plugin** → install it, then select it in a chat.
Source: https://developers.openai.com/api/docs/guides/custom-mcp-server ("How to use"). Supported transports: SSE and streaming HTTP. OAuth supports CIMD or DCR (same page).
Workspace (Business/Enterprise): an admin may need to allow custom MCP / developer mode. Source: https://help.openai.com/en/articles/12584461 (403 to curl; content seen via search on 2026-10-16. **Recheck in a browser**).

## Desktop app
Settings → MCP servers → Add server → Streamable HTTP → `https://api.agonna.com/mcp/` → Restart → Authenticate. The desktop app shares Codex's config; see `codex.md`. Source: https://learn.chatgpt.com/docs/extend/mcp ("Configure in the ChatGPT desktop app").

## Human approval
ChatGPT opens the Agonna Cockpit OAuth page, and the human approves with a passkey. Agonna approvals: https://app.agonna.com/approvals.

## Gotchas
- OpenAI warns that if the authorization server doesn't advertise `offline_access` (or an equivalent) in `scopes_supported`, ChatGPT may lose access when the token expires (help article above). Agonna advertises only `["agent"]` (checked live 2026-10-16). Agonna does issue refresh tokens, but whether ChatGPT refreshes them is **UNVERIFIED**. Action for Agonna: consider advertising `offline_access`.
- ChatGPT only reaches public HTTPS servers. Agonna's is public, so no tunnel is needed.
- I didn't verify which ChatGPT plans can add custom MCP plugins (**UNVERIFIED**).

## Directory
Submit via the OpenAI Platform plugin portal ("With MCP": production HTTPS, domain verification, tool scan, reviewer test credentials): https://developers.openai.com/plugins/deploy/submission and https://learn.chatgpt.com/docs/submit-plugins
