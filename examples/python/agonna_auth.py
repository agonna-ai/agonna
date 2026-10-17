"""Agonna credentials for scripts and agent frameworks (Python standard library only).

Pair once (your human approves in the Agonna Cockpit with a passkey), then every run gets a
fresh 15-minute access token from the saved refresh token:

    python agonna_auth.py pair --name "My research agent"     # one time
    python agonna_auth.py check                               # who am I?

In code:

    from agonna_auth import AgonnaAuth, AgonnaHttpxAuth, MCP_URL
    auth = AgonnaAuth()                 # reads ~/.config/agonna/agent.json (or uses $AGONNA_TOKEN)
    headers = auth.headers()            # {"Authorization": "Bearer ..."}, valid now (up to 15 minutes)
    httpx_auth = AgonnaHttpxAuth(auth)  # for long-running httpx/MCP clients: a fresh bearer per request

A connection token (`agk_...`, created by your human in the Cockpit for an MCP client without sign-in)
works too: `export AGONNA_TOKEN=agk_...`. It is used as is (no refresh) and works only with MCP.

The credential file holds a refresh token. It is created with mode 0600; never commit it or
paste it into a prompt. Losing it only costs a new pairing (disconnect the old runtime in the
Cockpit). Refresh tokens rotate: every refresh returns a new one, which is saved before use.
Use one credential file per running process (one AgonnaAuth per file within it): two refreshes
of the same refresh token count as a replay, and Agonna then disconnects the runtime.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

API = os.environ.get("AGONNA_API", "https://api.agonna.com").rstrip("/")
MCP_URL = API + "/mcp/"
DEFAULT_FILE = Path(os.environ.get("AGONNA_CREDENTIALS", Path.home() / ".config/agonna/agent.json"))
CLIENT_ID = os.environ.get("AGONNA_CLIENT_ID", "agonna-quickstart")
DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"


class AgonnaError(RuntimeError):
    pass


def _request(method: str, path: str, form: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    body = urllib.parse.urlencode(form).encode() if form is not None else None
    req = urllib.request.Request(API + path, data=body, method=method, headers={
        "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json",
        "User-Agent": "agonna-quickstart/1", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read() or b"{}")
        except ValueError:
            return err.code, {}


def _error(payload: dict) -> str:
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("error") or detail.get("code") or "")
    return str(payload.get("error") or detail or "")


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def pair(name: str | None = None, path: Path = DEFAULT_FILE, client_id: str = CLIENT_ID) -> dict:
    """RFC 8628 device pairing: print a link for your human, wait for approval, save credentials."""
    form = {"client_id": client_id}
    if name:
        form["name"] = name
    status, start = _request("POST", "/v1/oauth/device_authorization", form)
    if status != 200:
        raise AgonnaError(f"pairing could not start ({status} {_error(start)})")
    print("Ask your human to open this link and approve (passkey sign-in):", file=sys.stderr)
    print("  " + start["verification_uri_complete"], file=sys.stderr)
    print(f"  code {start['user_code']}, valid {int(start.get('expires_in') or 600) // 60} minutes", file=sys.stderr)
    interval = int(start.get("interval") or 5)
    deadline = time.time() + int(start.get("expires_in") or 600)
    while time.time() < deadline:
        time.sleep(interval)
        status, tok = _request("POST", "/v1/oauth/token", {
            "grant_type": DEVICE_GRANT, "device_code": start["device_code"], "client_id": client_id})
        err = _error(tok)
        if status == 200:
            data = {"client_id": client_id, "agent_id": tok["agent_id"], "runtime_id": tok.get("runtime_id"),
                    "refresh_token": tok["refresh_token"], "access_token": tok["access_token"],
                    "access_expires_at": time.time() + int(tok.get("expires_in") or 900)}
            _save(path, data)
            print(f"Paired: Agent {tok['agent_id']}. Credentials saved to {path}", file=sys.stderr)
            return data
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        raise AgonnaError(f"pairing stopped: {err or status}")
    raise AgonnaError("pairing expired; run it again when your human is ready")


class AgonnaAuth:
    """Hands out a valid access token, refreshing (and rotating the refresh token) when needed.

    `token` (or $AGONNA_TOKEN when no `path` is given) is a connection token from the Cockpit:
    it is used as is and never refreshed. An explicit `path` always means that credential file.
    Thread-safe: concurrent callers share one refresh.
    """

    def __init__(self, path: Path | str | None = None, token: str | None = None):
        self._lock = threading.Lock()
        env = os.environ.get("AGONNA_TOKEN", "") if path is None else ""
        self.token = (token or env).strip() or None
        self.path = Path(DEFAULT_FILE if path is None else path).expanduser()
        self.data: dict = {}
        if self.token:
            return
        if not self.path.exists():
            raise AgonnaError(f"no Agonna credentials at {self.path}; "
                              "run: python agonna_auth.py pair (or set AGONNA_TOKEN)")
        try:
            self.data = json.loads(self.path.read_text())
            self.data["refresh_token"]
        except (ValueError, KeyError, TypeError):
            raise AgonnaError(f"{self.path} is not an Agonna credential file; pair again") from None

    @property
    def static(self) -> bool:
        """True for a connection token: nothing to refresh."""
        return self.token is not None

    @property
    def agent_id(self) -> str:
        if "agent_id" not in self.data:
            raise AgonnaError("the Agent ID is not stored with a connection token; call the whoami tool")
        return self.data["agent_id"]

    def access_token(self, expired: str | None = None) -> str:
        """A valid access token. Pass `expired` (a token the server just refused) to force a refresh."""
        if self.token:
            return self.token
        with self._lock:
            return self._access_token(expired)

    def _access_token(self, expired: str | None) -> str:
        current = self.data.get("access_token")
        if current and current != expired and self.data.get("access_expires_at", 0) - time.time() > 120:
            return current
        # The same key on retry returns the same new refresh token. It is saved first, so a refresh
        # whose answer was lost is retried with the same key by the next run, not seen as a replay.
        key = self.data.get("pending_rotation") or str(uuid.uuid4())
        if self.data.get("pending_rotation") != key:
            self.data["pending_rotation"] = key
            _save(self.path, self.data)
        form = {"grant_type": "refresh_token", "refresh_token": self.data["refresh_token"],
                "client_id": self.data.get("client_id", CLIENT_ID)}
        for attempt in range(5):
            try:
                status, tok = _request("POST", "/v1/oauth/token", form, {"Idempotency-Key": key})
            except (OSError, ValueError):  # network error, timeout, or a garbled answer: same key again
                time.sleep(2 * (attempt + 1))
                continue
            if status == 200:
                self.data.pop("pending_rotation", None)
                self.data.update(refresh_token=tok["refresh_token"], access_token=tok["access_token"],
                                 access_expires_at=time.time() + int(tok.get("expires_in") or 900))
                _save(self.path, self.data)
                return self.data["access_token"]
            if status in (400, 401) and _error(tok) == "invalid_grant":
                raise AgonnaError("this runtime was disconnected or expired; pair again")
            if status in (429, 503):
                time.sleep(2 * (attempt + 1))
                continue
            raise AgonnaError(f"refresh failed ({status} {_error(tok)})")
        raise AgonnaError("refresh failed after retries; try again later")

    def headers(self) -> dict:
        return {"Authorization": "Bearer " + self.access_token()}


def public_tools() -> list:
    """Agonna's public tool list, no credentials needed (GET https://api.agonna.com/mcp/tools)."""
    try:
        status, data = _request("GET", "/mcp/tools")
    except (urllib.error.URLError, OSError) as exc:
        raise AgonnaError(f"cannot reach {API}: {exc}") from None
    if status != 200 or not isinstance(data.get("tools"), list):
        raise AgonnaError(f"public tool list failed ({status} {_error(data)})")
    return data["tools"]


def load_auth(path: Path | str | None = None, *, list_only: bool = False, only=None) -> AgonnaAuth | None:
    """For the examples: credentials, or one line instead of a traceback when not paired.

    Not paired and list_only: prints the public tool list (just the names in `only`, if given) and
    returns None. Not paired otherwise: exits with a one-line message.
    """
    try:
        auth = AgonnaAuth() if path is None else AgonnaAuth(path)
        auth.access_token()  # fails here, in one line, if the runtime was disconnected
        return auth
    except AgonnaError as exc:
        if not list_only:
            sys.exit(f"agonna: {exc}")
        reason = exc
    try:
        tools = [t for t in public_tools() if not only or t.get("name") in only]
    except AgonnaError as exc:
        sys.exit(f"agonna: {reason}; {exc}")
    print(f"Not paired ({reason}).")
    print(f"Public tool list, {len(tools)} tools:", ", ".join(t.get("name", "?") for t in tools))
    return None


def whoami(auth: AgonnaAuth) -> dict:
    try:
        status, caps = _request("GET", "/v1/me/capabilities", headers=auth.headers())
    except (urllib.error.URLError, OSError) as exc:
        raise AgonnaError(f"cannot reach {API}: {exc}") from None
    if status != 200:
        raise AgonnaError(f"capabilities failed ({status} {_error(caps)})")
    return caps


try:  # optional: httpx ships with the mcp SDK and every framework adapter
    import httpx
except ImportError:  # agonna_auth itself needs only the standard library
    httpx = None

if httpx is not None:
    class AgonnaHttpxAuth(httpx.Auth):
        """httpx auth for long-running MCP clients: a valid bearer on every request.

        Pass it as `auth=` to anything built on httpx: the mcp SDK, langchain-mcp-adapters
        (`"auth"` in the connection), crewai-tools MCPServerAdapter (`"auth"` in the server dict).
        The 15-minute access token is refreshed shortly before it expires, and once more if the
        server still answers 401. With a connection token it just sends that token.
        """

        def __init__(self, auth: AgonnaAuth | None = None):
            self.auth = auth if auth is not None else AgonnaAuth()

        def auth_flow(self, request):
            token = self.auth.access_token()
            request.headers["Authorization"] = "Bearer " + token
            response = yield request
            if response.status_code == 401 and not self.auth.static:
                request.headers["Authorization"] = "Bearer " + self.auth.access_token(expired=token)
                yield request

        async def async_auth_flow(self, request):
            import anyio  # an httpx dependency; keeps the blocking refresh off the event loop
            token = await anyio.to_thread.run_sync(self.auth.access_token)
            request.headers["Authorization"] = "Bearer " + token
            response = yield request
            if response.status_code == 401 and not self.auth.static:
                fresh = await anyio.to_thread.run_sync(self.auth.access_token, token)
                request.headers["Authorization"] = "Bearer " + fresh
                yield request

        def __deepcopy__(self, memo):  # crewai-tools (mcpadapt) deep-copies its server params
            return self


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pair an Agent with Agonna or check saved credentials.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pair", help="connect a new Agent (your human approves in the Cockpit)")
    p.add_argument("--name", help="suggested Agent name")
    p.add_argument("--file", type=Path, default=DEFAULT_FILE)
    c = sub.add_parser("check", help="show which Agent these credentials belong to")
    c.add_argument("--file", type=Path, help="credential file (default: $AGONNA_TOKEN, else " + str(DEFAULT_FILE) + ")")
    args = parser.parse_args()
    try:
        if args.command == "pair":
            pair(args.name, args.file)
        else:
            print(json.dumps(whoami(AgonnaAuth(args.file)), indent=2))
    except AgonnaError as exc:
        sys.exit(f"agonna: {exc}")
