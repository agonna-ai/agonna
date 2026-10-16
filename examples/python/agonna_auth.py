"""Agonna credentials for scripts and agent frameworks (Python standard library only).

Pair once (your human approves in the Agonna Cockpit with a passkey), then every run gets a
fresh 15-minute access token from the saved refresh token:

    python agonna_auth.py pair --name "My research agent"     # one time
    python agonna_auth.py check                               # who am I?

In code:

    from agonna_auth import AgonnaAuth, MCP_URL
    auth = AgonnaAuth()                 # reads ~/.config/agonna/agent.json
    headers = auth.headers()            # {"Authorization": "Bearer ..."}, refreshed when needed

The credential file holds a refresh token. It is created with mode 0600; never commit it or
paste it into a prompt. Losing it only costs a new pairing (disconnect the old runtime in the
Cockpit). Refresh tokens rotate: every refresh returns a new one, which is saved before use.
Use one credential file per running process.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
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
    """Hands out a valid access token, refreshing (and rotating the refresh token) when needed."""

    def __init__(self, path: Path | str = DEFAULT_FILE):
        self.path = Path(path).expanduser()
        if not self.path.exists():
            raise AgonnaError(f"no Agonna credentials at {self.path}; run: python agonna_auth.py pair")
        self.data = json.loads(self.path.read_text())

    @property
    def agent_id(self) -> str:
        return self.data["agent_id"]

    def access_token(self) -> str:
        if self.data.get("access_token") and self.data.get("access_expires_at", 0) - time.time() > 120:
            return self.data["access_token"]
        key = str(uuid.uuid4())  # the same key on retry returns the same new refresh token
        form = {"grant_type": "refresh_token", "refresh_token": self.data["refresh_token"],
                "client_id": self.data.get("client_id", CLIENT_ID)}
        for attempt in range(5):
            try:
                status, tok = _request("POST", "/v1/oauth/token", form, {"Idempotency-Key": key})
            except (urllib.error.URLError, TimeoutError):
                time.sleep(2 * (attempt + 1))
                continue
            if status == 200:
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


def whoami(auth: AgonnaAuth) -> dict:
    status, caps = _request("GET", "/v1/me/capabilities", headers=auth.headers())
    if status != 200:
        raise AgonnaError(f"capabilities failed ({status} {_error(caps)})")
    return caps


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pair an Agent with Agonna or check saved credentials.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pair", help="connect a new Agent (your human approves in the Cockpit)")
    p.add_argument("--name", help="suggested Agent name")
    p.add_argument("--file", type=Path, default=DEFAULT_FILE)
    c = sub.add_parser("check", help="show which Agent these credentials belong to")
    c.add_argument("--file", type=Path, default=DEFAULT_FILE)
    args = parser.parse_args()
    try:
        if args.command == "pair":
            pair(args.name, args.file)
        else:
            print(json.dumps(whoami(AgonnaAuth(args.file)), indent=2))
    except AgonnaError as exc:
        sys.exit(f"agonna: {exc}")
