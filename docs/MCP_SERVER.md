# Clearwake as an MCP server in front of PayPal

Point Claude Desktop, Claude Code, ChatGPT or Cursor at Clearwake's MCP server instead of PayPal's. The agent gets the same 28 PayPal tools, with the same names and schemas as `@paypal/mcp` 1.8.1 started with `--tools=all` (`docs/paypal_mcp_tools.json`). The money tools are wrapped by `guard()`: limits from the signed policy, one request id per money move, PayPal's record read before any retry, and a signed, hash chained receipt per call. Read tools pass through untouched.

Label: the tests and the install check below run on the local provider (`clearwake/mcp_local_upstream.py`), which answers with PayPal's tool names and result shapes. The sandbox backend starts PayPal's own MCP server as the child and was not run in this build. This is Clearwake's own code, not a PayPal product.

## Use it

Claude Code, one line:

```
pip install git+https://github.com/Sriharsan/clearwake-paypal
claude mcp add paypal-guarded -- python -m clearwake.mcp_server
```

Claude Desktop, `claude_desktop_config.json`:

```
{
  "mcpServers": {
    "paypal-guarded": {
      "command": "python",
      "args": ["-m", "clearwake.mcp_server"]
    }
  }
}
```

`examples/mcp_server_config.json` holds both. The page https://clearwake-mu.vercel.app/developers (section Guard PayPal's Agent Toolkit) and https://clearwake-mu.vercel.app/break show the same snippets.

## Backends

| Backend | What it does | Needs |
|---|---|---|
| `local` (default) | `clearwake.mcp_local_upstream` answers with PayPal's tool names and result shapes. Nothing leaves the machine. | nothing |
| `paypal` | Starts `npx -y @paypal/mcp --tools=all` as the child. Refused unless `CLEARWAKE_SANDBOX_ACK=I_CONFIRM_SANDBOX_ONLY`, `PAYPAL_ENVIRONMENT=SANDBOX` and a sandbox `PAYPAL_ACCESS_TOKEN` are set. | Node.js, a sandbox token |

Options: `--policy` (default: the signed policy shipped inside the package, the same file as `policy/merchant.yaml`), `--data-dir` (ledger, approvals, receipts; default `.clearwake-mcp`), `--timeout`, `--strict`, `--state` and `--fault drop_answer:N` for the local provider.

## What the guard does

The same behaviour as `docs/MCP_GUARD.md`, which describes the proxy this server is built on: `accept_dispute_claim` and `create_refund` take their amount from PayPal's record and the policy, above the limit they are held for a person with an MCP error result and nothing sent, a lost response marks the move UNKNOWN and the next call reads PayPal's record before sending anything, and every call writes a receipt that `python -m clearwake.mcp_guard verify --data-dir .clearwake-mcp` checks offline. A stopped call returns `{"clearwake_guard": {"state", "detail", "sent", "request_id"}}`.

## Tests

`tests/test_mcp_server.py`, over stdio on the local provider, no network:

1. The tool list is the 28 tools of PayPal's server (names and descriptions from `docs/paypal_mcp_tools.json`); the copy shipped in the package equals the docs file.
2. A guarded refund of USD 40.00 on a capture, above the USD 5.00 limit, is refused: state `held for a person`, `sent` false, no refund applied at the provider, a refusal receipt, and the receipts verify.
3. A lost response: a refund of USD 1.50 is applied, the answer is dropped, the state is UNKNOWN; the agent calls again and the guard reads PayPal's record, answers VERIFIED with `sent` false, and still one refund exists.
4. A read tool (`get_dispute`) passes through with no receipt.
5. It starts from a folder with no repository files.
6. The `paypal` backend is refused without the sandbox acknowledgement, without `PAYPAL_ENVIRONMENT=SANDBOX` and without a token.

## Install check in a clean virtualenv

Run on 12 November 2026, Windows, Python 3.13, a new virtualenv in an empty temporary folder, then run from that folder (not the repository):

```
python -m venv v
./v/Scripts/python -m pip install "D:/my startup/clearwake"          # local path, before the push
./v/Scripts/python -m pip list | grep -i clearwake                   # clearwake 0.1.0
./v/Scripts/python -m clearwake.mcp_server --data-dir data --state state.json
  initialize, then tools/list   ->  tools/list -> 28 tools
  create_refund 40.00           ->  {"clearwake_guard": {"state": "held for a person", "detail": "Policy refused: above limit (limit 5.00 USD). Held for a person; nothing was sent to PayPal.", "sent": false, ...}}
  stderr                        ->  Clearwake MCP guard running on stdio. Policy 396af6170103, receipts ...\data\mcp-receipts.ndjson
```

The wheel bundles `verdock_core` and `relayloom` and ships the policy and the tool list inside the package, so the install needs no submodule folders and no other package.

The same check with the GitHub address, `pip install git+https://github.com/Sriharsan/clearwake-paypal`, in a second clean virtualenv: it installed in 30 seconds, fetched the pinned submodules, `import clearwake, verdock_core, relayloom` worked from `site-packages`, and `python -m clearwake.mcp_guard --help` ran. That run used the repository as pushed before this server was added, so it did not contain `clearwake.mcp_server`. Re-run it after the push: `./v/Scripts/python -m pip install git+https://github.com/Sriharsan/clearwake-paypal` and then the `tools/list` line above.

## Not verified

- The `paypal` backend (PayPal's own MCP server as the child, on the sandbox) was not started in this build.
- The record reads follow PayPal's published response shapes and were run on the local provider only.
- The other limits are listed in `docs/MCP_GUARD.md`.

Files: `clearwake/mcp_server.py`, `clearwake/mcp_guard.py`, `clearwake/mcp_local_upstream.py`, `clearwake/packaged/paypal_mcp_tools.json`, `tests/test_mcp_server.py`, `examples/mcp_server_config.json`.
