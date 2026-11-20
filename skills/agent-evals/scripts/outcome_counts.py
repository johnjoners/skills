#!/usr/bin/env python3
"""Compute agent outcome counts from files on disk. Read-only; stdlib only.

  outcome_counts.py --root DIR --register FILE [--asof YYYY-MM-DD] [--agent NAME] [--tsv]

FILE holds a "## Register" table; the expression grammar is in references/outcomes.md.
--tsv prints ledger rows to stdout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import re
import sys

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
RANK = {"green": 0, "amber": 1, "red": 2}


# ---------- parsing outcomes.md ----------

def split_row(line: str) -> list[str]:
    """Split a markdown table row on unescaped pipes; unescape \\| inside cells."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    cells, cur, i = [], [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def read_table(text: str, heading: str) -> list[dict]:
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == heading)
    except StopIteration:
        sys.exit(f"outcome_counts: heading {heading!r} not found in outcomes.md")
    rows, header = [], None
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if not line.lstrip().startswith("|"):
            if header is not None and rows:
                break
            continue
        cells = split_row(line)
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def strip_code(cell: str) -> str:
    cell = cell.strip()
    if cell.startswith("`") and cell.endswith("`"):
        return cell[1:-1]
    return cell


# ---------- evidence readers ----------

class Vault:
    def __init__(self, root: str, asof: dt.date):
        self.root = root
        self.asof = asof

    def path(self, rel: str) -> str:
        return os.path.join(self.root, rel)

    def tsv(self, rel: str) -> tuple[list[str], list[list[str]]] | None:
        p = self.path(rel)
        if not os.path.isfile(p):
            return None
        header, rows = None, []
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip() or line.startswith("#"):
                    continue
                cells = line.split("\t")
                if header is None:
                    header = cells
                    continue
                rows.append(cells + [""] * (len(header) - len(cells)))
        return header or [], rows

    def files(self, pattern: str) -> list[str]:
        hits = glob.glob(self.path(pattern))
        return sorted(h for h in hits if os.path.isfile(h))


def to_date(s: str) -> dt.date | None:
    m = DATE_RE.search(s or "")
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def frontmatter_date(path: str, key: str) -> dt.date | None:
    try:
        with open(path, encoding="utf-8") as fh:
            head = fh.read(4000)
    except OSError:
        return None
    if not head.startswith("---"):
        return None
    end = head.find("\n---", 3)
    block = head[3:end if end > 0 else len(head)]
    m = re.search(rf"^{re.escape(key)}:\s*(\S+)", block, re.M)
    return to_date(m.group(1)) if m else None


def parse_conds(text: str) -> list[tuple]:
    conds = []
    for raw in [c.strip() for c in text.split(", ") if c.strip()]:
        m = re.match(r"^(\S+) (in|older) (\d+)d$", raw)
        if m:
            conds.append(("date", m.group(1), m.group(2), int(m.group(3))))
            continue
        m = re.match(r"^([\w-]+)(!~|~|=)(.*)$", raw)
        if not m:
            raise ValueError(f"bad condition: {raw!r}")
        conds.append(("col", m.group(1), m.group(2), m.group(3)))
    return conds


def date_ok(d: dt.date | None, op: str, n: int, asof: dt.date, ignore_windows: bool) -> bool:
    if ignore_windows:
        return d is not None
    if d is None:
        return False
    edge = asof - dt.timedelta(days=n)
    return (edge <= d <= asof) if op == "in" else (d < edge)


def match_value(op: str, want: str, have: str) -> bool:
    if op == "=":
        return have == want
    hit = re.search(want, have) is not None
    return hit if op == "~" else not hit


def tsv_matches(v: Vault, rel: str, conds: list[tuple], ignore_windows=False):
    """Return (rows, dates) for matching rows, or None if the TSV is missing."""
    t = v.tsv(rel)
    if t is None:
        return None
    header, rows = t
    idx = {h: i for i, h in enumerate(header)}
    date_col = idx.get("date", 0)
    out, dates = [], []
    for r in rows:
        ok, row_date = True, to_date(r[date_col])
        for c in conds:
            if c[0] == "date":
                col = c[1]
                d = row_date if col == "date" else to_date(r[idx[col]]) if col in idx else None
                if not date_ok(d, c[2], c[3], v.asof, ignore_windows):
                    ok = False
                    break
            else:
                col, op, want = c[1], c[2], c[3]
                if col not in idx or not match_value(op, want, r[idx[col]]):
                    ok = False
                    break
        if ok:
            out.append(r)
            if row_date:
                dates.append(row_date)
    return out, dates


def file_matches(v: Vault, pattern: str, conds: list[tuple], ignore_windows=False):
    out, dates = [], []
    for p in v.files(pattern):
        d_name = to_date(os.path.basename(p))
        ok, d_used = True, d_name
        for c in conds:
            if c[0] == "date":
                d = d_name if c[1] == "date" else frontmatter_date(p, c[1])
                d_used = d
                if not date_ok(d, c[2], c[3], v.asof, ignore_windows):
                    ok = False
                    break
            elif c[1] == "content":
                with open(p, encoding="utf-8", errors="replace") as fh:
                    if not match_value(c[2], c[3], fh.read()):
                        ok = False
                        break
            else:
                raise ValueError(f"file condition on {c[1]!r} not supported")
        if ok:
            out.append(p)
            if d_used:
                dates.append(d_used)
    return out, dates


# ---------- expressions ----------

def split_where(rest: str) -> tuple[str, list[tuple]]:
    if " where " in rest:
        target, conds = rest.split(" where ", 1)
        return target.strip(), parse_conds(conds)
    return rest.strip(), []


def eval_term(v: Vault, term: str, ignore_windows=False):
    """Return dict(value=int|None, dates=set, note=str)."""
    term = term.strip()
    kind, _, rest = term.partition(" ")
    if kind in ("rows", "days", "age", "files"):
        target, conds = split_where(rest)
        is_tsv = target.endswith(".tsv")
        res = tsv_matches(v, target, conds, ignore_windows) if is_tsv else \
            file_matches(v, target, conds, ignore_windows)
        if res is None:
            return {"value": None, "dates": set(), "note": f"missing {target}"}
        items, dates = res
        newest = max(dates) if dates else None
        note = (f"{len(items)} matched, newest {newest}" if newest
                else f"{len(items)} matched" if items else "none on disk")
        if kind == "age":
            return {"value": (v.asof - newest).days if newest else None, "dates": set(dates),
                    "note": note}
        if kind == "days":
            return {"value": len(set(dates)), "dates": set(dates), "note": note}
        return {"value": len(items), "dates": set(dates), "note": note}
    if kind == "value":
        m = re.match(r"^(\S+) /(.*)/$", rest)
        pattern, rx = m.group(1), m.group(2)
        files = [(to_date(os.path.basename(p)), p) for p in v.files(pattern)]
        files = [f for f in files if f[0] and f[0] <= v.asof]
        if not files:
            return {"value": None, "dates": set(), "note": f"no file for {pattern}"}
        d, p = max(files)
        with open(p, encoding="utf-8", errors="replace") as fh:
            mm = re.search(rx, fh.read())
        val = int(mm.group(1)) if mm else None
        return {"value": val, "dates": {d}, "note": f"{os.path.relpath(p, v.root)}"}
    if kind == "count":
        m = re.match(r"^(\S+) /(.*)/$", rest)
        p, rx = v.path(m.group(1)), m.group(2)
        if not os.path.isfile(p):
            return {"value": None, "dates": set(), "note": f"missing {m.group(1)}"}
        with open(p, encoding="utf-8", errors="replace") as fh:
            n = sum(1 for line in fh if re.search(rx, line))
        return {"value": n, "dates": set(), "note": f"{n} matching lines"}
    if kind in ("stale-red", "fixed-red"):
        rel, n = rest.split()
        n = int(n.rstrip("d"))
        t = v.tsv(rel)
        if t is None:
            return {"value": None, "dates": set(), "note": f"missing {rel}"}
        header, rows = t
        idx = {h: i for i, h in enumerate(header)}
        by_class: dict[str, list[tuple[dt.date, str]]] = {}
        for r in rows:
            d = to_date(r[idx["date"]])
            if d and d <= v.asof:
                by_class.setdefault(r[idx["check_class"]], []).append((d, r[idx["verdict"]]))
        if not by_class:
            return {"value": 0, "dates": set(), "note": "no rows"}
        newest = max(d for runs in by_class.values() for d, _ in runs)
        hits = []
        for cls, runs in by_class.items():
            runs.sort()
            if kind == "stale-red":
                if not (runs[-1][0] == newest and runs[-1][1] == "red"):
                    continue
                start = runs[-1][0]
                for d, verdict in reversed(runs):
                    if verdict != "red":
                        break
                    start = d
                if (newest - start).days >= n:
                    hits.append(f"{cls} since {start}")
            else:
                edge = v.asof - dt.timedelta(days=n)
                reds = [d for d, verdict in runs if verdict == "red" and d >= edge]
                if reds and any(verdict == "green" and d > min(reds) for d, verdict in runs):
                    hits.append(cls)
        return {"value": len(hits), "dates": set(), "note": "; ".join(hits) or "none"}
    raise ValueError(f"unknown expression kind {kind!r} in {term!r}")


def eval_expr(v: Vault, expr: str, ignore_windows=False):
    when = None
    if " when " in expr:
        expr, when = expr.split(" when ", 1)
    terms = [t for t in re.split(r" \+ ", expr) if t.strip()]
    first_kind = terms[0].strip().split(" ", 1)[0]
    results = [eval_term(v, t, ignore_windows) for t in terms]
    if any(r["value"] is None for r in results) and first_kind != "age":
        missing = [r["note"] for r in results if r["value"] is None]
        return {"value": None, "dates": set(), "note": "; ".join(missing)}
    if first_kind == "days":
        dates = set().union(*[r["dates"] for r in results])
        value = len(dates)
    elif first_kind == "age":
        value = results[0]["value"]
    else:
        value = sum(r["value"] for r in results)
    out = {"value": value, "dates": set().union(*[r["dates"] for r in results]),
           "note": "; ".join(r["note"] for r in results)}
    if when and not ignore_windows:
        m = re.match(r"^(.*) >= (\d+)$", when.strip())
        gate = eval_expr(v, m.group(1))
        if gate["value"] is None or gate["value"] < int(m.group(2)):
            out["na"] = True
            out["note"] = f"not scored: {m.group(1)} < {m.group(2)}"
    return out


def meets(value, rule: str) -> bool:
    m = re.match(r"^(<=|>=|=|<|>)\s*(-?\d+)$", rule.strip())
    if not m or value is None:
        return False
    op, n = m.group(1), int(m.group(2))
    return {"<=": value <= n, ">=": value >= n, "=": value == n, "<": value < n,
            ">": value > n}[op]


def verdict_for(res: dict, green: str, red: str) -> str:
    if res.get("na"):
        return "n/a"
    if res["value"] is None:
        return "red"
    if meets(res["value"], green):
        return "green"
    if meets(res["value"], red):
        return "red"
    return "amber"


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="directory the evidence paths are relative to")
    ap.add_argument("--register", required=True, help="markdown file holding the Register table")
    ap.add_argument("--asof", default=dt.date.today().isoformat())
    ap.add_argument("--agent", default=None, help="only this agent")
    ap.add_argument("--tsv", action="store_true", help="print ledger rows (tab separated)")
    args = ap.parse_args()

    asof = dt.date.fromisoformat(args.asof)
    v = Vault(os.path.expanduser(args.root), asof)
    try:
        with open(os.path.expanduser(args.register), encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        sys.exit(f"outcome_counts: {e}")
    register = read_table(text, "## Register")

    results = []
    for r in register:
        if args.agent and r["agent"] != args.agent:
            continue
        res = eval_expr(v, strip_code(r["evidence"]))
        res["verdict"] = verdict_for(res, r["green"], r["red"])
        results.append((r, res))

    run_iso = dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    if args.tsv:
        for r, res in results:
            val = "-" if res["value"] is None else str(res["value"])
            print("\t".join([run_iso, r["agent"], "outcome", r["id"], val,
                             f"green {r['green']} red {r['red']}", res["verdict"], "-",
                             f"outcomes-{asof}", res["note"].replace("\t", " ")]))
        return 0

    print(f"Outcome counts as of {asof} (root {v.root})\n")
    print(f"{'id':<9} {'agent':<18} {'value':>6}  {'verdict':<9} evidence")
    worst: dict[str, list[str]] = {}
    for r, res in results:
        val = "-" if res["value"] is None else str(res["value"])
        print(f"{r['id']:<9} {r['agent']:<18} {val:>6}  {res['verdict']:<9} {res['note']}")
        worst.setdefault(r["agent"], []).append(res["verdict"])
    print("\nOutcome verdict per agent (worst scored count; n/a never sets it):")
    for agent, verdicts in worst.items():
        scored = [x for x in verdicts if x in RANK]
        print(f"  {agent:<18} {max(scored, key=RANK.get) if scored else 'n/a'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
