#!/usr/bin/env python3
"""Run a live MCP JSON-RPC contract check against a Thesys API project."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Thesys MCP JSON-RPC compatibility.")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    endpoint = f"{args.api_base.rstrip('/')}/api/mcp/projects/{args.project_id}/rpc"
    metrics = [
        _initialize_metric(endpoint),
        _tools_list_metric(endpoint),
        _read_tool_metric(endpoint),
        _proposal_tool_metric(endpoint),
    ]
    passed = sum(1 for metric in metrics if metric["passed"])
    report = {"passed": passed == len(metrics), "score": passed, "total": len(metrics), "metrics": metrics}
    if args.json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("MCP Contract Eval")
        print(f"Result: {passed}/{len(metrics)} checks passed")
        for metric in metrics:
            status = "PASS" if metric["passed"] else "FAIL"
            print(f"- [{status}] {metric['label']}: {metric['observed']} (expected {metric['expected']})")
    return 0 if report["passed"] else 1


def _initialize_metric(endpoint: str) -> dict[str, Any]:
    response = _rpc(endpoint, "initialize", {"protocolVersion": "2025-11-25"}, "init")
    result = response.get("result") or {}
    return _metric(
        "initialize",
        "Initialize lifecycle",
        result.get("protocolVersion") == "2025-11-25" and "tools" in result.get("capabilities", {}),
        result.get("protocolVersion"),
        "protocol 2025-11-25 with tools capability",
    )


def _tools_list_metric(endpoint: str) -> dict[str, Any]:
    response = _rpc(endpoint, "tools/list", {"includeProposals": False}, "list")
    tools = (response.get("result") or {}).get("tools") or []
    names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
    return _metric(
        "tools_list",
        "Tools list",
        {"get_project_summary", "list_project_memory"}.issubset(names),
        len(names),
        "read tools exposed through tools/list",
    )


def _read_tool_metric(endpoint: str) -> dict[str, Any]:
    response = _rpc(
        endpoint,
        "tools/call",
        {
            "name": "get_project_summary",
            "arguments": {},
            "_meta": {"client_id": "mcp-contract-eval"},
        },
        "read",
    )
    structured = (response.get("result") or {}).get("structuredContent") or {}
    return _metric(
        "read_tool",
        "Read tool call",
        structured.get("tool_name") == "get_project_summary"
        and structured.get("approval_required") is False,
        structured.get("status"),
        "executed read tool with no approval",
    )


def _proposal_tool_metric(endpoint: str) -> dict[str, Any]:
    response = _rpc(
        endpoint,
        "tools/call",
        {
            "name": "propose_memory_update",
            "arguments": {"summary": "MCP contract eval proposes an auditable memory update."},
            "_meta": {"client_id": "mcp-contract-eval"},
        },
        "proposal",
    )
    structured = (response.get("result") or {}).get("structuredContent") or {}
    return _metric(
        "proposal_tool",
        "Proposal tool call",
        structured.get("tool_name") == "propose_memory_update"
        and structured.get("approval_required") is True
        and bool(structured.get("approval_request_id")),
        structured.get("status"),
        "approval-gated proposal response",
    )


def _rpc(endpoint: str, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    payload = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
    request = urllib.request.Request(
        endpoint,
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def _metric(key: str, label: str, passed: bool, observed: Any, expected: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "passed": passed,
        "observed": observed,
        "expected": expected,
    }


if __name__ == "__main__":
    sys.exit(main())
