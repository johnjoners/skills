#!/usr/bin/env python3
"""First-pass scan for prompt-injection signals in saved external content.

Usage: python3 scan.py <file> [<file> ...]
Exit status: 0 when nothing matched, 1 when anything matched, 2 on usage error.
Standard library only.
"""

import re
import sys

CHECKS = [
    ("zero-width or bidi control", re.compile(
        "[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")),
    ("long base64-like run", re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")),
    ("instruction override", re.compile(
        r"ignore (all |the )?(previous|prior|above) (instructions|messages)"
        r"|disregard (the )?above|new instructions|you are now|pretend (you are|to be)"
        r"", re.I)),
    ("fake role tag", re.compile(r"<\s*system\s*>|<\|im_start\|>|\[INST\]", re.I)),
    ("tool-call syntax in prose", re.compile(r"<function_calls>|\"tool_use\"\s*:")),
    ("exfiltration request", re.compile(
        r"(send|forward|print|reveal|output) (the |your )?(api key|secret|password|memory|system prompt|conversation)",
        re.I)),
    ("query-string data carrier", re.compile(r"[?&](d|data|payload|q)=[A-Za-z0-9%+/=]{40,}")),
    ("shell or fetch suggestion", re.compile(r"\b(curl|wget)\s+https?://|\brm -rf\b|\bsudo\b")),
    ("git destructive suggestion", re.compile(r"git push\s+(-f|--force)|git reset --hard")),
    ("urgency or authority claim", re.compile(
        r"this is urgent|your (manager|boss|admin) (says|requires|asked)|security (policy|requires) (you|that)",
        re.I)),
]


def scan(path):
    hits = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            for label, pattern in CHECKS:
                for m in pattern.finditer(line):
                    snippet = line.strip()
                    if len(snippet) > 160:
                        snippet = snippet[:157] + "..."
                    hits.append((lineno, label, m.group(0)[:60], snippet))
    return hits


def main(argv):
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    total = 0
    for path in argv:
        try:
            hits = scan(path)
        except OSError as e:
            print(f"{path}: cannot read ({e.strerror})")
            return 2
        print(f"{path}: {len(hits)} hit(s)")
        for lineno, label, matched, snippet in hits:
            print(f"  line {lineno}: {label}: {matched!r}")
            print(f"    {snippet}")
        total += len(hits)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
