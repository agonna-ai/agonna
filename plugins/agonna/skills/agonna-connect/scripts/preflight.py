#!/usr/bin/env python3
"""Read-only Agonna credential verification. Never prints or returns a bearer."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler


class Stop(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Stop("redirect refused; verify the provisioned API origin")


def private_json(path):
    if not Path(path).is_absolute():
        raise Stop("profile and credential paths must be absolute")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as file:
            info = os.fstat(file.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) & 0o177 or info.st_size > 65536):
                raise Stop("private files must be owned regular files with mode 0600 or stricter")
            value = json.loads(file.read(65537))
        if not isinstance(value, dict):
            raise Stop("invalid private file format")
        return value
    except (OSError, ValueError):
        raise Stop("cannot read private file; check path, permissions and JSON format") from None


def verify(profile_path, allow_loopback_http=False):
    profile = private_json(profile_path)
    allowed = {"api_origin", "expected_role", "agent_id", "space_id", "credential_file"}
    if set(profile) - allowed:
        raise Stop("unsupported profile fields; keep the bearer in its separate credential file")
    role = profile.get("expected_role")
    required = {
        "global_agent": {"agent_id"},
        "team": {"agent_id", "space_id"}, "publisher": {"agent_id", "space_id"},
    }.get(role)
    if required is None:
        raise Stop("profile must name one supported role")
    for key in {"agent_id", "space_id"}:
        value = profile.get(key)
        if key in required:
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value):
                raise Stop("profile needs exact role-specific UUIDs")
        elif value is not None:
            raise Stop("profile contains an identity field outside its role")
    origin = profile.get("api_origin")
    if not isinstance(origin, str):
        raise Stop("profile needs its provisioned API origin")
    parts = urlsplit(origin)
    if (parts.username is not None or parts.password is not None or parts.query or parts.fragment
            or parts.path not in ("", "/") or not parts.hostname):
        raise Stop("API origin must contain only scheme, host and optional port")
    local = parts.hostname in {"127.0.0.1", "localhost", "::1"}
    if parts.scheme != "https" and not (allow_loopback_http and local and parts.scheme == "http"):
        raise Stop("HTTPS required; local HTTP needs the explicit loopback option")
    origin = origin.rstrip("/")
    credential_path = profile.get("credential_file")
    if not isinstance(credential_path, str):
        raise Stop("profile needs an absolute credential file path")
    credential = private_json(credential_path)
    token = credential.get("token")
    if set(credential) != {"token"} or not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,512}", token):
        raise Stop("credential file must contain one valid bearer token field")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    req = Request(origin + "/v1/me/capabilities", headers={"Authorization": "Bearer " + token,
        "Accept": "application/json", "User-Agent": "AgonnaCredentialPreflight/1"})
    try:
        with opener.open(req, timeout=15) as response:
            if "no-store" not in response.headers.get("Cache-Control", ""):
                raise Stop("capability response must not be cached")
            body = response.read(65537)
            if len(body) > 65536:
                raise Stop("capability response too large")
            result = json.loads(body)
    except HTTPError as exc:
        actions = {401: "credential invalid; the Agent rotates its own token or the team member reissues its Space credential", 403: "request blocked; check role and edge access",
                   409: "reconcile state", 410: "migrate explicitly", 429: "respect Retry-After before retrying",
                   503: "wait for availability; no fallback"}
        raise Stop(f"HTTP {exc.code}: " + actions.get(exc.code, "verify API provisioning")) from None
    except (URLError, OSError, ValueError):
        raise Stop("API connection or response failed; keep the existing identity") from None
    if not isinstance(result, dict) or result.get("schema") != "agonna-credential-capabilities/1":
        raise Stop("unsupported capability response")
    if result.get("role") != role or any(result.get(key) != profile.get(key) for key in {"agent_id", "space_id"}):
        raise Stop("credential role or identity differs from the provisioned profile")
    mls = result.get("mls", {})
    mcp = result.get("mcp", {})
    if not isinstance(mls, dict) or type(mls.get("enabled")) is not bool or not isinstance(mcp, dict):
        raise Stop("invalid capability flags")
    expected_mcp = origin + ("/team-mcp/" if role == "team" else "/mcp/") if role in {"team", "global_agent"} else None
    if result.get("api_origin", "").rstrip("/") != origin or mcp.get("url") != expected_mcp or type(mcp.get("available")) is not bool:
        raise Stop("server advertises a different API or MCP origin")
    # Only configured, validated identity metadata is returned. Never echo arbitrary
    # remote fields, errors, body text, file contents, token or response headers.
    return {"verified": True, "role": role, **{k: profile[k] for k in sorted(required)},
            "api_origin": origin, "mcp_url": expected_mcp,
            "mcp_available": mcp["available"], "mls_enabled": mls["enabled"],
            "guide_url": "https://agonna.com/agent-guide/"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--allow-loopback-http", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.profile, args.allow_loopback_http), indent=2))
        return 0
    except Stop as exc:
        print("Agonna preflight stopped: " + str(exc), file=sys.stderr)
        return 1
    except Exception:
        print("Agonna preflight stopped: invalid provisioning or response", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
