"""Clearwake as an MCP server in front of PayPal (stdio).

    python -m clearwake.mcp_server                       # the local provider: safe to try, no account, no network
    python -m clearwake.mcp_server --backend paypal      # PayPal's own MCP server as the child, sandbox only

Point Claude Desktop, Claude Code, ChatGPT or Cursor at this server instead of PayPal's. The agent sees the same 28 PayPal tools with the
same names and schemas (docs/paypal_mcp_tools.json), and every money tool is wrapped by guard(): the limits come from the signed policy,
one request id per money move, PayPal's record is read before any retry, and every call writes a signed, hash chained receipt that
verifies offline. Read tools pass through untouched.

It is the guard proxy of clearwake/mcp_guard.py with the PayPal side chosen for you:

  local   clearwake/mcp_local_upstream.py answers with PayPal's tool names and result shapes. Nothing leaves the machine. Default.
  paypal  starts `npx -y @paypal/mcp --tools=all` as the child. Refused unless CLEARWAKE_SANDBOX_ACK=I_CONFIRM_SANDBOX_ONLY and
          PAYPAL_ENVIRONMENT=SANDBOX are set, and PAYPAL_ACCESS_TOKEN is in the environment. Clearwake never runs against production.

Clearwake's own code, not a PayPal product.
"""
import argparse
import os
import shutil
import sys

from .mcp_guard import Proxy

ACK = "I_CONFIRM_SANDBOX_ONLY"


def build_command(backend, state=None, fault="", env=None):
    """The child process the guard talks to. Returns (command, error). error is a sentence when the backend must be refused."""
    env = os.environ if env is None else env
    if backend == "local":
        command = [sys.executable, "-m", "clearwake.mcp_local_upstream", "--tools=all"]
        if state:
            command += ["--state", state]
        if fault:
            command += ["--fault", fault]
        return command, ""
    if env.get("CLEARWAKE_SANDBOX_ACK") != ACK:
        return None, f"The paypal backend needs CLEARWAKE_SANDBOX_ACK={ACK} in the environment. Clearwake runs on the PayPal sandbox only."
    if str(env.get("PAYPAL_ENVIRONMENT", "")).upper() != "SANDBOX":
        return None, "The paypal backend needs PAYPAL_ENVIRONMENT=SANDBOX. Clearwake refuses to run against anything else."
    if not env.get("PAYPAL_ACCESS_TOKEN"):
        return None, "The paypal backend needs a sandbox PAYPAL_ACCESS_TOKEN in the environment."
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        return None, "The paypal backend needs Node.js (npx) to start @paypal/mcp."
    return [npx, "-y", "@paypal/mcp", "--tools=all"], ""


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m clearwake.mcp_server", description="Clearwake as an MCP server in front of PayPal (stdio).")
    p.add_argument("--backend", choices=("local", "paypal"), default="local", help="local provider (default) or PayPal's MCP server on the sandbox")
    p.add_argument("--policy", default=None, help="signed policy file (default: the policy shipped with Clearwake)")
    p.add_argument("--data-dir", default=".clearwake-mcp", help="ledger, approvals and signed receipts")
    p.add_argument("--timeout", type=float, default=None, help="seconds to wait for PayPal on one call (default 60, 3 for the local provider)")
    p.add_argument("--strict", action="store_true", help="hold money tools the policy has no operation for")
    p.add_argument("--state", default=None, help="state file of the local provider")
    p.add_argument("--fault", default="", help="local provider only: drop_answer:N loses the answer of the next N money moves")
    args = p.parse_args(argv)
    command, error = build_command(args.backend, args.state, args.fault)
    if error:
        print(error, file=sys.stderr)
        return 2
    timeout = args.timeout if args.timeout is not None else (3.0 if args.backend == "local" else 60.0)
    Proxy(command, policy=args.policy, data_dir=args.data_dir, timeout=timeout, strict=args.strict).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
