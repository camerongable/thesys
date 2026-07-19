#!/usr/bin/env python3
"""Line-delimited stdio bridge for Thesys MCP JSON-RPC over HTTP.

The bridge keeps auth and policy in the API. It only forwards JSON-RPC messages
from stdin to the project-scoped MCP endpoint and writes JSON-RPC responses to
stdout, which is the shape local developer agents expect from stdio MCP tools.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Thesys MCP stdio bridge.")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--dev-role", default=None)
    args = parser.parse_args()

    endpoint = f"{args.api_base.rstrip('/')}/api/mcp/rpc"
    if args.project_id:
        endpoint = f"{args.api_base.rstrip('/')}/api/mcp/projects/{args.project_id}/rpc"

    for line in sys.stdin:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            response = _post_json(endpoint, stripped, args.dev_role)
        except Exception as exc:  # noqa: BLE001 - stdio bridge must return JSON-RPC errors.
            request_id = _request_id(stripped)
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": "Thesys MCP stdio bridge request failed.",
                    "data": {"error": str(exc)},
                },
            }
        sys.stdout.write(json.dumps(response, sort_keys=True) + "\n")
        sys.stdout.flush()
    return 0


def _post_json(endpoint: str, body: str, dev_role: str | None) -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if dev_role:
        headers["X-Dev-User-Role"] = dev_role
    request = urllib.request.Request(
        endpoint,
        data=body.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def _request_id(raw: str) -> str | int | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload.get("id") if isinstance(payload, dict) else None


if __name__ == "__main__":
    raise SystemExit(main())
