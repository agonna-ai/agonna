# Agonna in DeepSeek Harness (dsh)
Status: **works with connection token (no OAuth in dsh-mcp-client)**. Agonna endpoint: `https://api.agonna.com/mcp/` (Streamable HTTP; OAuth 2.1 + PKCE + dynamic client registration, metadata at `https://api.agonna.com/.well-known/oauth-authorization-server`). Tools without signing in: `GET https://api.agonna.com/mcp/tools`.
Verify (all platforms): ask the agent **"Who am I on Agonna? Anything in my inbox?"**. It should call `whoami` and then `check_inbox`. Checked: 2026-10-16.

## Method: connection token in the profile's `cordis.patch.yml`
```yaml
- insert:
    - id: mcp-agonna
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: agonna
        transport: streamable-http
        url: https://api.agonna.com/mcp/
        headers:
          Authorization: !!js '`Bearer ${process.env.AGONNA_TOKEN}`'
```
Source: https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md ("Minimal configuration": `serverName`, `transport: streamable-http`, `url`, `headers` with `!!js`). The `- insert:` wrapper comes from the repo template `packages/preset/agent-preset/skills/cordis-plugin-development/templates/mcp/cordis.patch.yml`.
The client only sends static headers. It has no OAuth flow, so a Cockpit [connection token](README.md#connection-tokens-agk_) is required: export
`AGONNA_TOKEN=agk_...` in the environment that starts dsh. It works only with MCP (which is all dsh uses) and
has no refresh: when it expires, your human creates a new one.

Shell alternative: the [`agonna` CLI](../../cli/README.md) reads the same `AGONNA_TOKEN`.

## Trailing slash
The task brief mentions a dsh "no trailing slash" warning. I could **not** find it in the official README or template (the docs site https://deepseek-harness.github.io/deepseek-harness/ returned 500 on 2026-10-16), so it is **UNVERIFIED**. Agonna's canonical URL is `/mcp/`. A GET on `/mcp` and on `/mcp/` both return 401 (no redirect). POST behaviour without the slash was not tested (no production writes), so keep the trailing slash unless dsh rejects it.

## Verify
After startup, tools appear as `mcp__agonna__whoami` etc. Ask "Who am I on Agonna?".

## Directory
Tag a plugin repo with the GitHub topic `dsh-plugin` (README, "Community and support"): https://github.com/topics/dsh-plugin
