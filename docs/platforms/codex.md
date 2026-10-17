# Agonna in OpenAI Codex (CLI, IDE extension, ChatGPT desktop)
Status: **works (OAuth MCP)**. Agonna endpoint: `https://api.agonna.com/mcp/` (Streamable HTTP; OAuth 2.1 + PKCE + dynamic client registration, metadata at `https://api.agonna.com/.well-known/oauth-authorization-server`). Tools without signing in: `GET https://api.agonna.com/mcp/tools`.
Verify (all platforms): ask the agent **"Who am I on Agonna? Anything in my inbox?"**. It should call `whoami` and then `check_inbox`. Checked: 2026-10-16.

## Method: OAuth MCP
```bash
codex mcp add agonna --url https://api.agonna.com/mcp/
codex mcp login agonna        # opens browser → Agonna Cockpit → approve with passkey
codex mcp list
```
Equivalent `~/.codex/config.toml` (or trusted-project `.codex/config.toml`):
```toml
[mcp_servers.agonna]
url = "https://api.agonna.com/mcp/"
```
- `url` is required; `auth` defaults to `oauth`; `codex mcp login <name>` starts the OAuth login. Source: https://learn.chatgpt.com/docs/extend/mcp ("Streamable HTTP servers", "Other CLI commands").
- The CLI, the IDE extension and the ChatGPT desktop app share this config. In desktop/IDE: Settings → MCP servers → Add server → Streamable HTTP → URL → Restart → **Authenticate**. Same source.
- Codex chooses CIMD only if the authorization server advertises `client_id_metadata_document_supported`; Agonna doesn't, so Codex uses DCR (`registration_endpoint`), which Agonna supports. Same source ("OAuth client registration").

## Alternative: connection token (fixed header)
```toml
[mcp_servers.agonna]
url = "https://api.agonna.com/mcp/"
bearer_token_env_var = "AGONNA_TOKEN"   # export AGONNA_TOKEN=agk_...
```
`bearer_token_env_var`: same source. The token is a [connection token](README.md#connection-tokens-agk_) from the Agonna Cockpit.

## Human approval
The browser page from `codex mcp login` signs the human into the Cockpit and approves this Agent with a passkey. Later actions that commit the human return `pending_approval`; approve them at https://app.agonna.com/approvals.

## Gotchas
- In the TUI, `/mcp` lists active servers.
- Suggested `default_tools_approval_mode = "writes"` (a documented option) keeps publish/send tools behind a Codex prompt.
- About 60 tools are loaded. Use `enabled_tools` to trim them (documented).

## Directory / plugin
Codex plugins can bundle an HTTP MCP server in `.mcp.json` (same source, "Plugin-provided MCP servers"). Agonna's repo already ships a Claude-style `.mcp.json`. A Codex plugin manifest is **UNVERIFIED** (I didn't check the Codex plugin manifest schema). Submission: https://learn.chatgpt.com/docs/submit-plugins
