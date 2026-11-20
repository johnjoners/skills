"""Read-only MCP server over the johnjoners/skills catalogue.

Consumers point this server at the published GitHub repo; it fetches files
over the git trees and raw endpoints, caches them by content hash, and never
requires a clone. ``--skills-repo <path>`` reads a local checkout instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP
from yaml.scanner import ScannerError

GITHUB_REPO = "johnjoners/skills"
DEFAULT_REF = "main"
API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"

# Skill folders use lowercase names and hyphens only (see the repo's AGENTS.md).
SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
# File paths inside a skill folder; no hidden segments, no traversal.
SKILL_PATH_RE = re.compile(
    r"^(?:[A-Za-z0-9_][A-Za-z0-9 _-]*/)*[A-Za-z0-9_][A-Za-z0-9 _-]*\.[A-Za-z0-9]+$"
)

MAX_TEXT_BYTES = 512 * 1024
MAX_SEARCH_HITS = 200

MAX_YAML_EVENTS = 5000
MAX_YAML_DEPTH = 20


def safe_yaml_load(text: str) -> Any:
    """Parse YAML after a streaming pass rejects aliases and deep nesting."""
    depth = 0
    count = 0
    for ev in yaml.parse(text, Loader=yaml.SafeLoader):
        count += 1
        if count > MAX_YAML_EVENTS:
            raise ValueError("too many YAML events")
        if isinstance(ev, yaml.AliasEvent):
            raise ValueError("YAML aliases are not allowed")
        if isinstance(ev, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
            depth += 1
            if depth > MAX_YAML_DEPTH:
                raise ValueError("YAML nested too deep")
        elif isinstance(ev, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
            depth -= 1
    return yaml.safe_load(text)


def open_regular(root_fd: int, parts: list[str]) -> int:
    """Open a file under root_fd without following links.

    Rejects empty, dot and dot-prefixed segments. The leaf must be a regular
    file with exactly one hard link, checked with fstat on the open descriptor.
    """
    if not parts or any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        raise PermissionError("path segment not allowed")
    fd = os.dup(root_fd)
    try:
        for name in parts[:-1]:
            nxt = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    finally:
        os.close(fd)
    st = os.fstat(leaf)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        os.close(leaf)
        raise PermissionError("not a plain single-link file")
    return leaf


@dataclass
class SkillMeta:
    name: str
    description: str
    license: str
    compatibility: str
    files: list[str]


def _fold_descriptions(text: str) -> str:
    """Re-emit frontmatter with description values quoted on one line.

    Unquoted description values in the wild contain colons, which a plain
    YAML scalar cannot carry. Quoting the joined value keeps it loadable.
    """
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(description:\s*)(\S.*)$", line)
        if not m:
            out.append(line)
            i += 1
            continue
        parts = [m.group(2)]
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*:", nxt) or not nxt.strip():
                break
            parts.append(nxt.strip())
            j += 1
        value = " ".join(parts).replace("\\", "\\\\").replace('"', '\\"')
        out.append(f'{m.group(1)}"{value}"')
        i = j
    return "\n".join(out)


def parse_skill_md(text: str) -> tuple[dict[str, Any], str]:
    """Split SKILL.md into (frontmatter, body). Missing fields become ''."""
    fm: dict[str, Any] = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            raw = text[4:end]
            try:
                loaded = safe_yaml_load(raw)
            except (ScannerError, ValueError, yaml.YAMLError):
                loaded = safe_yaml_load(_fold_descriptions(raw))
            if isinstance(loaded, dict):
                fm = loaded
            body = text[end + 5 :]
    return fm, body.lstrip("\n")


class SkillsBackend:
    """Read skill records. Implemented by the remote and checkout backends."""

    def list_skill_names(self) -> list[str]:
        raise NotImplementedError

    def list_files(self, skill: str) -> list[str]:
        raise NotImplementedError

    def read_bytes(self, path: str) -> bytes:
        """path is repo-relative and already validated."""
        raise NotImplementedError

    def revision(self) -> str:
        raise NotImplementedError

    def skill_meta(self, skill: str) -> SkillMeta:
        text = self.read_bytes(f"skills/{skill}/SKILL.md").decode("utf-8", errors="replace")
        fm, _ = parse_skill_md(text)
        return SkillMeta(
            name=str(fm.get("name", skill)),
            description=str(fm.get("description", "")),
            license=str(fm.get("license", "")),
            compatibility=str(fm.get("compatibility", "")),
            files=self.list_files(skill),
        )


class GitHubBackend(SkillsBackend):
    """Reads the published repo over the git trees and raw endpoints."""

    def __init__(self, cache_dir: Path, ref: str) -> None:
        self.cache_dir = cache_dir
        self.ref = ref
        self._tree: list[dict[str, Any]] | None = None
        self._sha = ""
        token = os.environ.get("GITHUB_TOKEN", "")
        self._headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "skills-mcp",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def _get_json(self, url: str) -> Any:
        req = urllib.request.Request(url, headers=self._headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"github request failed with status {e.code}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"github request failed: {e.reason}") from e

    def _tree_entries(self) -> list[dict[str, Any]]:
        if self._tree is not None:
            return self._tree
        ref_info = self._get_json(f"{API}/repos/{GITHUB_REPO}/git/ref/heads/{self.ref}")
        self._sha = ref_info["object"]["sha"]
        tree = self._get_json(
            f"{API}/repos/{GITHUB_REPO}/git/trees/{self._sha}?recursive=1"
        )
        if tree.get("truncated"):
            raise RuntimeError("github tree response was truncated")
        self._tree = [e for e in tree["tree"] if e.get("type") == "blob"]
        return self._tree

    def revision(self) -> str:
        if not self._sha:
            self._tree_entries()
        return self._sha

    def list_skill_names(self) -> list[str]:
        names = {
            e["path"].split("/", 2)[1]
            for e in self._tree_entries()
            if e["path"].startswith("skills/")
            and e["path"].endswith("/SKILL.md")
            and e["path"].count("/") == 2
        }
        return sorted(n for n in names if SKILL_NAME_RE.match(n))

    def list_files(self, skill: str) -> list[str]:
        prefix = f"skills/{skill}/"
        return sorted(
            e["path"][len(prefix) :]
            for e in self._tree_entries()
            if e["path"].startswith(prefix) and SKILL_PATH_RE.match(e["path"][len(prefix) :])
        )

    def read_bytes(self, path: str) -> bytes:
        if any(seg.startswith(".") for seg in path.split("/")):
            raise PermissionError("path segment not allowed")
        sha = ""
        size = 0
        for e in self._tree_entries():
            if e["path"] == path:
                sha = e["sha"]
                size = int(e.get("size", 0))
                break
        if not sha:
            raise FileNotFoundError("no such file in the skills catalogue")
        if size > MAX_TEXT_BYTES:
            raise ValueError("file exceeds the read size limit")
        cached = self.cache_dir / sha
        if cached.exists():
            return cached.read_bytes()
        url = f"{RAW}/{GITHUB_REPO}/{self._sha}/{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "skills-mcp"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read(MAX_TEXT_BYTES + 1)
        except urllib.error.URLError as e:
            raise RuntimeError(f"github raw fetch failed: {e}") from e
        if len(data) > MAX_TEXT_BYTES:
            raise ValueError("file exceeds the read size limit")
        if hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest() != sha:
            raise RuntimeError("fetched content does not match the tree hash")
        tmp = self.cache_dir / f".{sha}.tmp"
        tmp.write_bytes(data)
        os.replace(tmp, cached)
        return data


class CheckoutBackend(SkillsBackend):
    """Reads a local checkout. Skills live under <root>/skills/."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.skills_dir = self.root / "skills"
        self.skills_fd = os.open(self.skills_dir, os.O_RDONLY | os.O_DIRECTORY)

    def revision(self) -> str:
        head = self.root / ".git" / "HEAD"
        try:
            text = head.read_text().strip()
        except OSError:
            return "unknown"
        if text.startswith("ref:"):
            ref_file = self.root / ".git" / text[4:].strip()
            try:
                return ref_file.read_text().strip()
            except OSError:
                return "unknown"
        return text

    def _read_confined(self, parts: list[str]) -> bytes:
        fd = open_regular(self.skills_fd, parts)
        try:
            st = os.fstat(fd)
            if st.st_size > MAX_TEXT_BYTES:
                raise ValueError("file exceeds the read size limit")
            out = b""
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                out += chunk
            return out
        finally:
            os.close(fd)

    def list_skill_names(self) -> list[str]:
        names = []
        for entry in os.scandir(self.skills_dir):
            if (
                entry.is_dir(follow_symlinks=False)
                and SKILL_NAME_RE.match(entry.name)
                and (self.skills_dir / entry.name / "SKILL.md").is_file()
            ):
                names.append(entry.name)
        return sorted(names)

    def list_files(self, skill: str) -> list[str]:
        out: list[str] = []
        base = self.skills_dir / skill
        if not base.is_dir():
            raise FileNotFoundError("no such skill in the catalogue")
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in filenames:
                if fn.startswith("."):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), base)
                rel = rel.replace(os.sep, "/")
                if SKILL_PATH_RE.match(rel):
                    out.append(rel)
        return sorted(out)

    def read_bytes(self, path: str) -> bytes:
        parts = path.split("/")
        if parts and parts[0] == "skills":
            parts = parts[1:]
        return self._read_confined(parts)


def build_server(backend: SkillsBackend) -> FastMCP:
    mcp = FastMCP(
        "skills-mcp",
        instructions=(
            "Read-only access to the johnjoners/skills catalogue of agent skills. "
            "Use list_skills to see what exists, get_skill for one skill's "
            "frontmatter and file list, get_skill_file for SKILL.md bodies and "
            "bundled scripts, templates and references, and search_skills to "
            "find skills by keyword."
        ),
    )

    read_only = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }

    @mcp.tool(annotations=read_only)
    def list_skills() -> dict[str, Any]:
        """List every skill in the catalogue with its one-line description."""
        out = []
        for name in backend.list_skill_names():
            meta = backend.skill_meta(name)
            out.append({"name": meta.name, "description": meta.description})
        return {"revision": backend.revision(), "skills": out}

    @mcp.tool(annotations=read_only)
    def get_skill(name: str) -> dict[str, Any]:
        """Get one skill: frontmatter fields plus the files it bundles.

        name is the folder name from list_skills (lowercase, hyphens).
        """
        if not SKILL_NAME_RE.match(name):
            raise ValueError("invalid skill name")
        try:
            meta = backend.skill_meta(name)
        except FileNotFoundError:
            raise ValueError("unknown skill; call list_skills for the catalogue")
        return {
            "name": meta.name,
            "description": meta.description,
            "license": meta.license,
            "compatibility": meta.compatibility,
            "files": meta.files,
        }

    @mcp.tool(annotations=read_only)
    def get_skill_file(name: str, path: str, offset: int = 0) -> dict[str, Any]:
        """Read one text file bundled with a skill.

        path comes from get_skill's files list (for example "SKILL.md" or
        "scripts/scan.py"). offset is a byte offset for paging long files;
        the response carries next_offset until the file is fully returned.
        """
        if not SKILL_NAME_RE.match(name):
            raise ValueError("invalid skill name")
        if not SKILL_PATH_RE.match(path) or path.startswith("/"):
            raise ValueError("invalid file path")
        try:
            data = backend.read_bytes(f"skills/{name}/{path}")
        except FileNotFoundError:
            raise ValueError("unknown file; call get_skill for the file list")
        text = data.decode("utf-8")
        raw = text.encode("utf-8")
        page = raw[offset : offset + MAX_TEXT_BYTES // 4]
        # Never split a multi-byte character at the page end. A lead byte
        # (0xC0-0xFF) whose continuation runs past the slice decodes short.
        while page and (page[-1] & 0xC0) == 0x80:
            page = page[:-1]
        try:
            page_text = page.decode("utf-8")
        except UnicodeDecodeError:
            page = page[:-1]
            page_text = page.decode("utf-8")
        next_offset = offset + len(page)
        return {
            "name": name,
            "path": path,
            "offset": offset,
            "content": page_text,
            "next_offset": next_offset if next_offset < len(raw) else None,
        }

    @mcp.tool(annotations=read_only)
    def search_skills(query: str) -> dict[str, Any]:
        """Literal, case-insensitive search across every file in the catalogue.

        Returns up to 200 matches with the skill, file path, line number and
        the matching line.
        """
        if not query:
            raise ValueError("query must not be empty")
        needle = query.lower()
        hits: list[dict[str, Any]] = []
        truncated = False
        for name in backend.list_skill_names():
            for path in backend.list_files(name):
                try:
                    data = backend.read_bytes(f"skills/{name}/{path}")
                except (OSError, ValueError, RuntimeError):
                    continue
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    # Binary or invalid bytes still cost I/O; skip the content.
                    continue
                for lineno, line in enumerate(text.splitlines(), start=1):
                    if needle in line.lower():
                        hits.append(
                            {
                                "skill": name,
                                "path": path,
                                "line": lineno,
                                "text": line.strip()[:300],
                            }
                        )
                        if len(hits) >= MAX_SEARCH_HITS:
                            truncated = True
                            break
                if truncated:
                    break
            if truncated:
                break
        return {"query": query, "truncated": truncated, "matches": hits}

    @mcp.resource("skills://catalogue")
    def catalogue() -> str:
        """JSON snapshot of the whole catalogue: names and descriptions."""
        return json.dumps(list_skills(), indent=2)

    return mcp


def default_cache_dir() -> Path:
    return Path(
        os.environ.get(
            "SKILLS_MCP_CACHE",
            Path.home() / ".cache" / "skills-mcp",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only MCP server over the johnjoners/skills catalogue."
    )
    parser.add_argument(
        "--skills-repo",
        type=Path,
        default=None,
        help="Local checkout of johnjoners/skills to read instead of GitHub.",
    )
    parser.add_argument(
        "--ref",
        default=os.environ.get("SKILLS_MCP_REF", DEFAULT_REF),
        help="Git branch to read when fetching from GitHub (default: main).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=default_cache_dir(),
        help="Content-hash cache for fetched files (default: ~/.cache/skills-mcp).",
    )
    args = parser.parse_args()

    if args.skills_repo is not None:
        backend: SkillsBackend = CheckoutBackend(args.skills_repo)
    else:
        args.cache_dir.mkdir(parents=True, exist_ok=True)
        backend = GitHubBackend(args.cache_dir, args.ref)

    mcp = build_server(backend)
    mcp.run()


if __name__ == "__main__":
    main()
