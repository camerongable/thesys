#!/usr/bin/env python3
"""Write the Garak REST-generator configuration without persisting credentials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a Garak REST target configuration.")
    parser.add_argument("--target-uri", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorization", default="")
    args = parser.parse_args()
    if not args.target_uri.startswith("https://"):
        raise ValueError("Garak target URI must use HTTPS.")
    headers = {"Authorization": args.authorization} if args.authorization else {}
    config = {
        "rest": {
            "RestGenerator": {
                "uri": args.target_uri,
                "method": "post",
                "headers": headers,
                "req_template_json_object": {"prompt": "$INPUT"},
                "response_json": True,
                "response_json_field": "text",
                "request_timeout": 60,
            }
        }
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
