"""Clearwake as an MCP server in front of PayPal, end to end over stdio on the local provider (no network, no model, no PayPal call)."""
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from clearwake import mcp_server
from verdock_core.receipts import ReceiptLog, load_seed, verify_log

ROOT = Path(__file__).resolve().parent.parent
TOOLS = json.loads((ROOT / "docs" / "paypal_mcp_tools.json").read_text(encoding="utf-8"))
PACKAGED = json.loads((ROOT / "clearwake" / "packaged" / "paypal_mcp_tools.json").read_text(encoding="utf-8"))


class Server:
    """A client of `python -m clearwake.mcp_server`: newline delimited JSON-RPC over its stdin and stdout."""

    def __init__(self, test, *flags, fault="", cwd=ROOT):
        self.dir = Path(tempfile.mkdtemp(prefix="mcp-server-test-"))
        test.addCleanup(shutil.rmtree, self.dir, True)
        self.state = self.dir / "state.json"
        cmd = [sys.executable, "-m", "clearwake.mcp_server", "--data-dir", str(self.dir / "g"), "--state", str(self.state), "--timeout", "1.0", *flags]
        if fault:
            cmd += ["--fault", fault]
        self.proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
                                     env={**__import__("os").environ, "PYTHONPATH": str(ROOT)})
        test.addCleanup(self.close)
        self.lines, self.n = queue.Queue(), 0
        threading.Thread(target=lambda: [self.lines.put(line) for line in iter(self.proc.stdout.readline, b"")], daemon=True).start()
        self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}})
        self.proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')

    def rpc(self, method, params=None, wait=30):
        self.n += 1
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}).encode("utf-8") + b"\n")
        while True:
            msg = json.loads(self.lines.get(timeout=wait))
            if msg.get("id") == self.n:
                return msg

    def call(self, name, arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})["result"]
        return result.get("isError", False), json.loads(result["content"][0]["text"])

    def refunds(self):
        return json.loads(self.state.read_text(encoding="utf-8"))["refunds"]

    def receipts(self):
        path = self.dir / "g" / "mcp-receipts.ndjson"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


class McpServerTests(unittest.TestCase):
    def test_the_tool_list_is_the_28_tools_of_the_paypal_toolkit_server(self):
        s = Server(self)
        tools = s.rpc("tools/list")["result"]["tools"]
        want = sorted(t["name"] for t in TOOLS["tools"] if t["in_mcp_tools_all"])
        self.assertEqual(sorted(t["name"] for t in tools), want)
        self.assertEqual(len(tools), 28)
        for name in ("create_refund", "accept_dispute_claim", "get_dispute", "list_disputes", "create_order"):
            self.assertIn(name, [t["name"] for t in tools])
        by = {t["name"]: t for t in tools}
        self.assertEqual(by["create_refund"]["description"], next(t["description"] for t in TOOLS["tools"] if t["name"] == "create_refund"))

    def test_the_packaged_tool_list_is_the_same_file_as_the_docs_one(self):
        self.assertEqual(PACKAGED, TOOLS)

    def test_a_guarded_refund_over_the_limit_is_refused_and_the_provider_is_never_called(self):
        s = Server(self)
        error, body = s.call("create_refund", {"capture_id": "CAPTURE0000000004", "amount": {"currency_code": "USD", "value": "40.00"}})
        self.assertTrue(error)
        self.assertEqual(body["clearwake_guard"]["state"], "held for a person")
        self.assertFalse(body["clearwake_guard"]["sent"])
        self.assertEqual(s.refunds(), [])
        refused = [r for r in s.receipts() if r["action_id"] == "clearwake.policy.refused"]
        self.assertTrue(refused and refused[0]["params"]["amount_minor"] == 4000)
        self.assertTrue(verify_log(str(s.dir / "g" / "mcp-receipts.ndjson"),
                                   ReceiptLog(str(s.dir / "g" / "mcp-receipts.ndjson"), load_seed(str(s.dir / "g" / "mcp-receipts.seed"))).public_key)["ok"])

    def test_a_lost_response_is_read_back_and_not_retried(self):
        s = Server(self, fault="drop_answer:1")
        args = {"capture_id": "CAPTURE0000000004", "amount": {"currency_code": "USD", "value": "1.50"}}
        error, body = s.call("create_refund", args)
        self.assertEqual((error, body["clearwake_guard"]["state"]), (True, "UNKNOWN"))
        self.assertEqual(len(s.refunds()), 1)             # PayPal applied it, the answer never came
        error, body = s.call("create_refund", {**args, "note_to_payer": "Sorry"})
        self.assertFalse(error)
        self.assertEqual((body["clearwake_guard"]["state"], body["clearwake_guard"]["sent"]), ("VERIFIED", False))
        self.assertEqual(len(s.refunds()), 1)             # read back, not sent again

    def test_read_tools_pass_through_with_no_receipt(self):
        s = Server(self)
        error, record = s.call("get_dispute", {"dispute_id": "PP-D-1002"})
        self.assertFalse(error)
        self.assertNotIn("clearwake_guard", record)
        self.assertEqual(s.receipts(), [])

    def test_it_runs_from_a_folder_with_no_repository_files(self):
        """Started from a folder that holds none of the repository files. The clean virtualenv install in docs/MCP_SERVER.md proves the packaged policy and tool list."""
        empty = Path(tempfile.mkdtemp(prefix="mcp-server-empty-"))
        self.addCleanup(shutil.rmtree, empty, True)
        s = Server(self, cwd=empty)
        self.assertEqual(len(s.rpc("tools/list")["result"]["tools"]), 28)
        error, body = s.call("create_refund", {"capture_id": "CAPTURE0000000004", "amount": {"currency_code": "USD", "value": "40.00"}})
        self.assertEqual((error, body["clearwake_guard"]["state"]), (True, "held for a person"))

    def test_the_paypal_backend_is_refused_without_the_sandbox_acknowledgement(self):
        command, error = mcp_server.build_command("paypal", env={})
        self.assertIsNone(command)
        self.assertIn("CLEARWAKE_SANDBOX_ACK", error)
        command, error = mcp_server.build_command("paypal", env={"CLEARWAKE_SANDBOX_ACK": "I_CONFIRM_SANDBOX_ONLY", "PAYPAL_ENVIRONMENT": "LIVE", "PAYPAL_ACCESS_TOKEN": "x"})
        self.assertIsNone(command)
        self.assertIn("SANDBOX", error)
        command, error = mcp_server.build_command("paypal", env={"CLEARWAKE_SANDBOX_ACK": "I_CONFIRM_SANDBOX_ONLY", "PAYPAL_ENVIRONMENT": "SANDBOX"})
        self.assertIsNone(command)
        self.assertIn("PAYPAL_ACCESS_TOKEN", error)


if __name__ == "__main__":
    unittest.main()
