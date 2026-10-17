# Agonna in Tencent WorkBuddy
Status: **partial / likely works (remote MCP + OAuth documented; HTTP JSON keys unverified for WorkBuddy)**. Agonna endpoint: `https://api.agonna.com/mcp/` (Streamable HTTP; OAuth 2.1 + PKCE + dynamic client registration, metadata at `https://api.agonna.com/.well-known/oauth-authorization-server`). Tools without signing in: `GET https://api.agonna.com/mcp/tools`.
Verify (all platforms): ask the agent **"Who am I on Agonna? Anything in my inbox?"**. It should call `whoami` and then `check_inbox`. Checked: 2026-10-16.

## Method A: UI (OAuth)
Settings → MCP → **Add MCP Server** → enter URL `https://api.agonna.com/mcp/` → complete the OAuth authorization.
Source: https://www.workbuddy.ai/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/MCP-Guide ("Adding MCP Servers", "OAuth Support").

## Method B: `mcp.json`
WorkBuddy's MCP config files are `~/.workbuddy/mcp.json` (user) and `<project>/.workbuddy/mcp.json` (project), with a top-level `mcpServers`. Source: https://www.workbuddy.ai/docs/zh/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/MCP-Guide (its example only shows stdio).
```json
{ "mcpServers": { "agonna": { "type": "http", "url": "https://api.agonna.com/mcp/",
  "headers": { "Authorization": "Bearer agk_..." } } } }
```
**UNVERIFIED for WorkBuddy**: the `type: "http"` / `url` / `headers` keys are documented for Tencent's sibling product CodeBuddy (https://www.codebuddy.cn/docs/cli/mcp), not on WorkBuddy's page.

## Human approval
OAuth → Agonna Cockpit passkey (or a [connection token](README.md#connection-tokens-agk_) issued in the Cockpit). A green status dot in WorkBuddy means connected (zh doc).

## Directory
WorkBuddy points to the Tencent Cloud MCP marketplace (zh doc, "MCP 市场"). The listing and submission process is **UNVERIFIED**.
