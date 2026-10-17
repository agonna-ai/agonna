"""Tests for agonna.py: standard library only, no network (HTTP is mocked).

    python -m unittest -v test_agonna.py      # from the cli/ directory
"""
import contextlib
import io
import json
import os
import stat
import tempfile
import threading
import time
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest import mock

import agonna


class FakeResponse:
    def __init__(self, status=200, body=b"", ctype="application/json"):
        self.status, self._body = status, body
        self.headers = Message()
        self.headers["Content-Type"] = ctype

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code, body=b"", headers=None):
    msg = Message()
    for k, v in (headers or {}).items():
        msg[k] = v
    return urllib.error.HTTPError("https://x", code, "err", msg, io.BytesIO(body))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patches = [
            mock.patch.object(agonna, "CONFIG_DIR", Path(self.tmp.name)),
            mock.patch.dict(os.environ, {}, clear=False),
            mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used in a test")),
            mock.patch.object(agonna.time, "sleep"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("AGONNA_TOKEN", None)

    def write_profile(self, **extra):
        data = {"client_id": "agonna-cli", "agent_id": "a1", "refresh_token": "rt-0",
                "access_token": "at-old", "access_expires_at": 0}
        data.update(extra)
        agonna.save(agonna.profile_path("agent"), data)
        return data

    def read_profile(self):
        return json.loads(agonna.profile_path("agent").read_text())


class ParseKvTest(Base):
    def test_key_values_are_json_when_possible(self):
        self.assertEqual(agonna.parse_kv(["a=1", "b=true", "c=hello", "d=[1,2]", "e="]),
                         {"a": 1, "b": True, "c": "hello", "d": [1, 2], "e": ""})

    def test_one_json_object(self):
        self.assertEqual(agonna.parse_kv(['{"x": {"y": 2}}']), {"x": {"y": 2}})

    def test_empty(self):
        self.assertEqual(agonna.parse_kv([]), {})

    def test_bad_pair_is_usage_error(self):
        with self.assertRaises(agonna.Fail) as cm:
            agonna.parse_kv(["novalue"])
        self.assertEqual(cm.exception.code, 2)

    def test_bad_json_object_is_usage_error_not_traceback(self):
        with self.assertRaises(agonna.Fail) as cm:
            agonna.parse_kv(["{bad json"])
        self.assertEqual(cm.exception.code, 2)


class ErrorTextTest(unittest.TestCase):
    def test_shapes(self):
        self.assertEqual(agonna.error_text({"error": "invalid_grant"}), "invalid_grant")
        self.assertEqual(agonna.error_text({"detail": {"error": "x"}}), "x")
        self.assertEqual(agonna.error_text({"detail": "plain"}), "plain")
        self.assertEqual(agonna.error_text({}), "")
        self.assertEqual(agonna.error_text(["not", "a", "dict"]), "['not', 'a', 'dict']")
        self.assertEqual(agonna.error_text(None), "")


class HttpTest(Base):
    def test_sets_own_user_agent_and_parses_json(self):
        seen = {}

        def urlopen(req, timeout):
            seen.update(req.headers)
            return FakeResponse(200, b'{"ok": 1}')

        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            self.assertEqual(agonna.http("GET", "https://x/"), (200, {"ok": 1}))
        self.assertTrue(seen["User-agent"].startswith("agonna-cli/"))  # Python-urllib/* gets 403 at the edge

    def test_retries_429_with_retry_after(self):
        answers = [http_error(429, b"{}", {"Retry-After": "7"}), FakeResponse(200, b'{"ok": 2}')]
        with mock.patch("urllib.request.urlopen", side_effect=answers):
            self.assertEqual(agonna.http("GET", "https://x/"), (200, {"ok": 2}))
        agonna.time.sleep.assert_called_with(7)

    def test_gives_back_status_after_repeated_429(self):
        with mock.patch("urllib.request.urlopen", side_effect=[http_error(429, b'{"error": "slow"}') for _ in range(4)]):
            self.assertEqual(agonna.http("GET", "https://x/"), (429, {"error": "slow"}))

    def test_non_json_error_body(self):
        with mock.patch("urllib.request.urlopen", side_effect=[http_error(502, b"<html>bad gateway</html>")]):
            status, out = agonna.http("GET", "https://x/")
        self.assertEqual((status, out), (502, {"detail": "<html>bad gateway</html>"}))

    def test_non_json_success_body_is_fail_not_traceback(self):
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(200, b"<html>captive portal</html>")):
            with self.assertRaises(agonna.Fail):
                agonna.http("GET", "https://x/")

    def test_connection_reset_is_retried_then_fail(self):
        with mock.patch("urllib.request.urlopen", side_effect=ConnectionResetError("reset")) as m:
            with self.assertRaises(agonna.Fail) as cm:
                agonna.http("GET", "https://x/")
        self.assertEqual(m.call_count, 4)
        self.assertIn("cannot reach", str(cm.exception))

    def test_url_error_then_success(self):
        answers = [urllib.error.URLError("dns"), FakeResponse(200, b"{}")]
        with mock.patch("urllib.request.urlopen", side_effect=answers):
            self.assertEqual(agonna.http("GET", "https://x/"), (200, {}))

    def test_event_stream_body(self):
        body = (b'event: message\ndata: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
                b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"x":1}}\n\n')
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(200, body, "text/event-stream")):
            self.assertEqual(agonna.http("POST", "https://x/", body={})[1]["result"], {"x": 1})


class AccessTokenTest(Base):
    def test_connection_token_from_env_is_used_as_is(self):
        os.environ["AGONNA_TOKEN"] = " agk_abc \n"
        with mock.patch.object(agonna, "http", side_effect=AssertionError("no HTTP")):
            self.assertEqual(agonna.access_token("agent"), "agk_abc")

    def test_not_paired(self):
        with self.assertRaises(agonna.Fail) as cm:
            agonna.access_token("agent")
        self.assertEqual(cm.exception.code, 4)

    def test_corrupt_profile_is_fail_not_traceback(self):
        agonna.profile_path("agent").write_text("{not json")
        with self.assertRaises(agonna.Fail) as cm:
            agonna.access_token("agent")
        self.assertEqual(cm.exception.code, 4)

    def test_fresh_token_needs_no_refresh(self):
        self.write_profile(access_token="at-ok", access_expires_at=time.time() + 600)
        with mock.patch.object(agonna, "http", side_effect=AssertionError("no HTTP")):
            self.assertEqual(agonna.access_token("agent"), "at-ok")

    def test_refresh_rotates_and_saves_0600(self):
        self.write_profile()
        with mock.patch.object(agonna, "http", return_value=(200, {
                "access_token": "at-1", "refresh_token": "rt-1", "expires_in": 900})) as h:
            self.assertEqual(agonna.access_token("agent"), "at-1")
        form, headers = h.call_args.kwargs["form"], h.call_args.kwargs["headers"]
        self.assertEqual((form["grant_type"], form["refresh_token"]), ("refresh_token", "rt-0"))
        self.assertTrue(headers["Idempotency-Key"])
        saved = self.read_profile()
        self.assertEqual((saved["refresh_token"], saved["access_token"]), ("rt-1", "at-1"))
        self.assertNotIn("pending_rotation", saved)
        self.assertEqual(stat.S_IMODE(agonna.profile_path("agent").stat().st_mode), 0o600)

    def test_lost_answer_reuses_the_same_key_next_run(self):
        self.write_profile()
        with mock.patch.object(agonna, "http", side_effect=agonna.Fail("cannot reach")) as h:
            with self.assertRaises(agonna.Fail):
                agonna.access_token("agent")
        first_key = h.call_args.kwargs["headers"]["Idempotency-Key"]
        self.assertEqual(self.read_profile()["pending_rotation"], first_key)
        with mock.patch.object(agonna, "http", return_value=(200, {
                "access_token": "at-1", "refresh_token": "rt-1"})) as h:
            agonna.access_token("agent")
        self.assertEqual(h.call_args.kwargs["headers"]["Idempotency-Key"], first_key)

    def test_invalid_grant_means_pair_again(self):
        self.write_profile()
        with mock.patch.object(agonna, "http", return_value=(401, {"error": "invalid_grant"})):
            with self.assertRaises(agonna.Fail) as cm:
                agonna.access_token("agent")
        self.assertEqual(cm.exception.code, 4)
        self.assertIn("pair", str(cm.exception))

    @unittest.skipIf(agonna.fcntl is None, "no fcntl on this platform")
    def test_concurrent_refreshes_happen_once(self):
        """Two refreshes of one refresh token = replay = Agonna disconnects the runtime."""
        self.write_profile()
        calls = []

        def slow_refresh(*a, **kw):
            calls.append(kw["form"]["refresh_token"])
            threading.Event().wait(0.2)  # hold the lock a moment
            return 200, {"access_token": f"at-{len(calls)}", "refresh_token": f"rt-{len(calls)}"}

        out = []
        with mock.patch.object(agonna, "http", side_effect=slow_refresh):
            threads = [threading.Thread(target=lambda: out.append(agonna.access_token("agent"))) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(calls, ["rt-0"])
        self.assertEqual(out, ["at-1"] * 4)


class CallTest(Base):
    def setUp(self):
        super().setUp()
        os.environ["AGONNA_TOKEN"] = "agk_test"

    def rpc(self, result=None, status=200, raw=None):
        return mock.patch.object(agonna, "http", return_value=(
            status, raw if raw is not None else {"jsonrpc": "2.0", "id": 1, "result": result}))

    def test_request_shape(self):
        with self.rpc({"structuredContent": {"result": [1, 2]}}) as h:
            self.assertEqual(agonna.call("agent", "search", {"query": "q"}), [1, 2])
        args, kw = h.call_args
        self.assertEqual(args, ("POST", agonna.MCP_URL))
        self.assertEqual(kw["body"]["method"], "tools/call")
        self.assertEqual(kw["body"]["params"], {"name": "search", "arguments": {"query": "q"}})
        self.assertEqual(kw["headers"]["Authorization"], "Bearer agk_test")

    def test_text_content_fallback(self):
        with self.rpc({"content": [{"type": "text", "text": '{"a": 1}'}]}):
            self.assertEqual(agonna.call("agent", "whoami", {}), {"a": 1})
        with self.rpc({"content": [{"type": "text", "text": "plain words"}]}):
            self.assertEqual(agonna.call("agent", "whoami", {}), "plain words")

    def test_tool_error(self):
        with self.rpc({"isError": True, "content": [{"type": "text", "text": "boom"}]}):
            with self.assertRaises(agonna.Fail) as cm:
                agonna.call("agent", "whoami", {})
        self.assertEqual(cm.exception.code, 5)

    def test_jsonrpc_error_dict_or_string(self):
        with self.rpc(raw={"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "nope"}}):
            with self.assertRaisesRegex(agonna.Fail, "nope"):
                agonna.call("agent", "whoami", {})
        with self.rpc(raw={"error": "flat"}):
            with self.assertRaisesRegex(agonna.Fail, "flat"):
                agonna.call("agent", "whoami", {})

    def test_status_codes(self):
        for status, code in ((423, 3), (401, 4), (403, 4), (500, 5)):
            with self.rpc(status=status, raw={"detail": "x"}):
                with self.assertRaises(agonna.Fail) as cm:
                    agonna.call("agent", "whoami", {})
            self.assertEqual(cm.exception.code, code, status)

    def test_pending_approval_exits_3_and_prints_it(self):
        pending = {"status": "pending_approval", "approval_id": "ap1", "tell_your_human": "approve at ..."}
        out = io.StringIO()
        with self.rpc({"structuredContent": pending}), contextlib.redirect_stdout(out):
            with self.assertRaises(agonna.Fail) as cm:
                agonna.call("agent", "publish_managed_listing", {})
        self.assertEqual(cm.exception.code, 3)
        self.assertEqual(json.loads(out.getvalue())["approval_id"], "ap1")


class MainTest(Base):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = agonna.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_tools_is_public_and_tolerant(self):
        tools = {"tools": [{"name": "whoami", "description": "Who am I"}, {"name": "x"}]}
        with mock.patch.object(agonna, "http", return_value=(200, tools)) as h:
            code, out, _ = self.run_main("tools")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [{"name": "whoami", "description": "Who am I"},
                                           {"name": "x", "description": ""}])
        self.assertNotIn("headers", h.call_args.kwargs)  # no credentials needed

    def test_tools_error_is_not_an_empty_success(self):
        with mock.patch.object(agonna, "http", return_value=(403, {"detail": "blocked"})):
            code, out, err = self.run_main("tools")
        self.assertEqual((code, out), (5, ""))
        self.assertIn("403", err)

    def test_not_paired_exit_4_one_line(self):
        code, out, err = self.run_main("whoami")
        self.assertEqual((code, out), (4, ""))
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_commands_map_to_tools(self):
        os.environ["AGONNA_TOKEN"] = "agk_test"
        cases = [
            (["inbox"], "check_inbox", {"status": "unread", "limit": 20}),
            (["inbox", "--all", "--limit", "5"], "check_inbox", {"status": "all", "limit": 5}),
            (["read", "c1", "--after", "3"], "read_conversation", {"conversation_id": "c1", "after": 3}),
            (["search", "rust", "--type", "need", "--tag", "a", "--tag", "b"], "search",
             {"query": "rust", "listing_type": "need", "tags": ["a", "b"]}),
            (["approval", "ap1"], "read_approval", {"approval_id": "ap1"}),
            (["call", "whoami"], "whoami", {}),
            (["call", "check_inbox", "limit=3"], "check_inbox", {"limit": 3}),
        ]
        for argv, tool, args in cases:
            with mock.patch.object(agonna, "call", return_value={"ok": True}) as c:
                code, out, _ = self.run_main(*argv)
            self.assertEqual(code, 0, argv)
            self.assertEqual(c.call_args.args[1:], (tool, args), argv)

    def test_writes_carry_a_request_id(self):
        os.environ["AGONNA_TOKEN"] = "agk_test"
        for argv, tool in ((["send", "@bob", "hi", "--intent", "chat"], "send_message"),
                           (["contact", "L1", "hello"], "contact_publication"),
                           (["ask", "Book it?", "--option", "Yes", "--option", "No"], "ask_my_human")):
            with mock.patch.object(agonna, "call", return_value={}) as c:
                self.run_main(*argv)
            name, args = c.call_args.args[1:]
            self.assertEqual(name, tool)
            self.assertTrue(args["request_id"])
        self.assertEqual(args["options"], ["Yes", "No"])

    def test_publish_uses_my_agent_id_and_clamps_ttl(self):
        os.environ["AGONNA_TOKEN"] = "agk_test"
        seen = []

        def fake_call(profile, tool, args):
            seen.append((tool, args))
            return {"agent_id": "me"} if tool == "whoami" else {"listing": {"id": "L1"}}

        with mock.patch.object(agonna, "call", side_effect=fake_call):
            code, _, err = self.run_main("publish", "need", "Title", "--capability", "learning.x",
                                         "--hours", "100000", "--request-id", "r1")
        self.assertEqual(code, 0)
        tool, args = seen[-1]
        self.assertEqual((tool, args["request_id"]), ("publish_managed_listing", "r1"))
        self.assertEqual(args["payload"]["agent_id"], "me")
        self.assertEqual(args["payload"]["ttl_seconds"], 2592000)
        self.assertIn("--request-id r1", err)

    def test_bad_call_json_exit_2(self):
        os.environ["AGONNA_TOKEN"] = "agk_test"
        code, _, err = self.run_main("call", "whoami", "{oops")
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err)

    def test_token_prints_connection_token(self):
        os.environ["AGONNA_TOKEN"] = "agk_test"
        self.assertEqual(self.run_main("token")[:2], (0, "agk_test\n"))


class PairTest(Base):
    def test_pair_polls_until_approved_and_saves(self):
        answers = [
            (200, {"device_code": "dc", "user_code": "ABCD", "verification_uri_complete": "https://app/x",
                   "interval": 1, "expires_in": 600}),
            (400, {"error": "authorization_pending"}),
            (400, {"error": "slow_down"}),
            (200, {"agent_id": "a9", "runtime_id": "r9", "access_token": "at", "refresh_token": "rt",
                   "expires_in": 900}),
        ]
        with mock.patch.object(agonna, "http", side_effect=answers), contextlib.redirect_stderr(io.StringIO()):
            out = agonna.pair("agent", "My agent")
        self.assertEqual(out["agent_id"], "a9")
        self.assertEqual(self.read_profile()["refresh_token"], "rt")

    def test_pair_denied(self):
        answers = [(200, {"device_code": "dc", "user_code": "U", "verification_uri_complete": "u",
                          "interval": 1, "expires_in": 600}), (400, {"error": "access_denied"})]
        with mock.patch.object(agonna, "http", side_effect=answers), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(agonna.Fail) as cm:
                agonna.pair("agent", None)
        self.assertEqual(cm.exception.code, 4)


class TrialTest(Base):
    def test_trial_saves_token_and_is_used_as_bearer(self):
        reg = (201, {"id": "t1", "agent_token": "tt", "trial": {"expires_at": "2026-10-23T00:00:00+00:00"}})
        with mock.patch.object(agonna, "http", side_effect=[reg]) as h, contextlib.redirect_stderr(io.StringIO()):
            out = agonna.trial("agent", "Trial bot", "")
        self.assertEqual(out["agent_id"], "t1")
        self.assertEqual(h.call_args.args[:2], ("POST", agonna.API + "/v1/agents"))
        self.assertEqual(agonna.access_token("agent"), "tt")
        mode = stat.S_IMODE(os.stat(agonna.profile_path("agent")).st_mode)
        self.assertEqual(mode, 0o600)

    def test_trial_never_overwrites_a_profile(self):
        self.write_profile()
        with self.assertRaises(agonna.Fail) as cm:
            agonna.trial("agent", "x", "")
        self.assertEqual(cm.exception.code, 2)

    def test_pair_keeps_the_trial_identity(self):
        agonna.save(agonna.profile_path("agent"), {"agent_id": "t1", "trial_token": "tt"})
        answers = [(200, {"device_code": "dc", "user_code": "U", "verification_uri_complete": "u",
                          "interval": 1, "expires_in": 600}),
                   (200, {"agent_id": "t1", "runtime_id": "r", "access_token": "at", "refresh_token": "rt",
                          "expires_in": 900})]
        with mock.patch.object(agonna, "http", side_effect=answers) as h, contextlib.redirect_stderr(io.StringIO()):
            out = agonna.pair("agent", None)
        self.assertEqual(h.call_args_list[0].kwargs["headers"], {"Authorization": "Bearer tt"})
        self.assertEqual(out["agent_id"], "t1")
        data = self.read_profile()
        self.assertEqual(data["refresh_token"], "rt")
        self.assertNotIn("trial_token", data)
        self.assertEqual(agonna.access_token("agent"), "at")

    def test_claim_required_says_pair(self):
        agonna.save(agonna.profile_path("agent"), {"agent_id": "t1", "trial_token": "tt"})
        with mock.patch.object(agonna, "http", return_value=(403, {"detail": {"code": "claim_required"}})):
            with self.assertRaises(agonna.Fail) as cm:
                agonna.call("agent", "send_message", {})
        self.assertIn("agonna pair", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
