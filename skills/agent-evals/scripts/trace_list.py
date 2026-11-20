#!/usr/bin/env python3
"""List agent transcripts (*.jsonl) under --root, oldest first, read-only.

  trace_list.py --root DIR [--agent REGEX] [--days N] [--at-risk N] [--cleanup N]

--agent keeps files whose first 200 KB match the regex. --days keeps files younger than N days,
--at-risk keeps files older than N. Prints age, days to expiry, size and the first user message.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys


def message_text(d: dict) -> str:
    msg = d.get("message", d)
    content = msg.get("content", "") if isinstance(msg, dict) else ""
    if isinstance(content, list):
        content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content if isinstance(content, str) else ""


def first_prompt(path: str) -> tuple[str, str]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            role = d.get("role") or d.get("type") or (d.get("message") or {}).get("role")
            if role != "user":
                continue
            text = message_text(d)
            if text.strip():
                return str(d.get("timestamp", "")), " ".join(text.split())
    return "", ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", required=True, help="directory searched recursively for *.jsonl")
    ap.add_argument("--agent", help="regex the transcript head must match")
    ap.add_argument("--days", type=int, help="only transcripts younger than N days")
    ap.add_argument("--at-risk", type=int, help="only transcripts older than N days")
    ap.add_argument("--cleanup", type=int, default=30, help="retention in days (default 30)")
    args = ap.parse_args()
    if not os.path.isdir(os.path.expanduser(args.root)):
        print(f"trace_list: not a directory: {args.root}", file=sys.stderr)
        return 1
    pattern = re.compile(args.agent.encode()) if args.agent else None
    now = dt.datetime.now().timestamp()
    rows = []
    for base, _, names in os.walk(os.path.expanduser(args.root)):
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(base, name)
            if pattern:
                with open(path, "rb") as fh:
                    if not pattern.search(fh.read(200_000)):
                        continue
            age = (now - os.path.getmtime(path)) / 86400
            if args.days is not None and age > args.days:
                continue
            if args.at_risk is not None and age < args.at_risk:
                continue
            ts, prompt = first_prompt(path)
            rows.append((age, ts[:10], os.path.getsize(path), path, prompt))
    for age, ts, size, path, prompt in sorted(rows, reverse=True):
        print(f"{ts or '-':<10} age {age:5.1f}d  expires in {args.cleanup - age:5.1f}d  "
              f"{size // 1024:>6} KB  {prompt[:90]}")
        print(f"           {path}")
    print(f"\n{len(rows)} transcripts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
