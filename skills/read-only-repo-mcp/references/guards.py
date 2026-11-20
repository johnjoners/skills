"""Reference guards for a read-only repository server.

Stdlib plus PyYAML. Copy the pieces you need. Run this file directly to
execute the self-test:

    uv run --no-project --python 3.11 --with pyyaml python guards.py

Functions:
    open_regular(root_fd, parts)      confined open, regular single-link file only
    safe_yaml_load(text)              alias and nesting checks before construction
    utf8_page(path, offset, limit)    byte-offset UTF-8 paging at char boundaries
"""

from __future__ import annotations

import codecs
import os
import stat
import tempfile

import yaml

MAX_YAML_EVENTS = 5000
MAX_YAML_DEPTH = 20


def open_regular(root_fd: int, parts: list[str]) -> int:
    """Open a file under root_fd without following links.

    Rejects empty, '.', '..', and dot-prefixed segments. Every directory is
    opened with O_NOFOLLOW | O_DIRECTORY relative to the previous one. The
    leaf must be a regular file with exactly one hard link, checked with
    fstat on the open descriptor, so the check and the read see one object.
    Returns the open descriptor; the caller closes it.
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


def safe_yaml_load(text: str, max_events: int = MAX_YAML_EVENTS,
                   max_depth: int = MAX_YAML_DEPTH):
    """Parse YAML only after a streaming pass rejects aliases and deep nesting.

    The event pass runs before yaml.safe_load builds any object, so merge-alias
    expansion never starts. Post-load checks cannot stop that expansion.
    """
    depth = 0
    count = 0
    for ev in yaml.parse(text, Loader=yaml.SafeLoader):
        count += 1
        if count > max_events:
            raise ValueError("too many YAML events")
        if isinstance(ev, yaml.AliasEvent):
            raise ValueError("YAML aliases are not allowed")
        if isinstance(ev, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
            depth += 1
            if depth > max_depth:
                raise ValueError("YAML nested too deep")
        elif isinstance(ev, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
            depth -= 1
    return yaml.safe_load(text)


def utf8_page(path: str, offset: int, limit: int) -> tuple[str, int]:
    """Return (text, next_offset) for one page of a UTF-8 file.

    Starts at a byte offset, skips continuation bytes so a page never begins
    mid-character, and holds back any trailing partial character for the next
    page. next_offset counts only the bytes actually returned.
    """
    if limit < 4:
        raise ValueError("limit must be at least 4 bytes")
    with open(path, "rb") as f:
        f.seek(offset)
        raw = f.read(limit + 4)
    start = 0
    while start < min(3, len(raw)) and 0x80 <= raw[start] <= 0xBF:
        start += 1
    chunk = raw[start:start + limit]
    dec = codecs.getincrementaldecoder("utf-8")()
    # Hold back an incomplete trailing character; it belongs to the next page.
    text = dec.decode(chunk, final=False)
    consumed = len(text.encode("utf-8"))
    return text, offset + start + consumed


def _self_test() -> None:
    root = tempfile.mkdtemp(prefix="guards-test-")
    os.makedirs(os.path.join(root, "a", "b"))
    body = "héllo 世界 🙂 " * 40
    path = os.path.join(root, "a", "b", "f.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    os.symlink(path, os.path.join(root, "link.md"))
    with open(os.path.join(root, "two.md"), "w") as f:
        f.write("x")
    os.link(os.path.join(root, "two.md"), os.path.join(root, "hard.md"))
    with open(os.path.join(root, ".env"), "w") as f:
        f.write("SECRET=1")

    rfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fd = open_regular(rfd, ["a", "b", "f.md"])
        os.close(fd)
        for parts in (["link.md"], ["hard.md"], ["a"], ["a", "..", "two.md"], [".env"]):
            try:
                open_regular(rfd, parts)
                raise AssertionError(f"not denied: {parts}")
            except (PermissionError, OSError):
                pass
    finally:
        os.close(rfd)

    assert safe_yaml_load("a: 1\nb: [2, 3]") == {"a": 1, "b": [2, 3]}
    for bad in ("a: &x [1]\nb: *x",
                "a: " + "[" * 30 + "]" * 30,
                "k: &a [1,2]\nl: &b [*a,*a]\nm: [*b,*b]"):
        try:
            safe_yaml_load(bad)
            raise AssertionError("YAML input not rejected")
        except ValueError:
            pass

    off, parts = 0, []
    size = os.path.getsize(path)
    while off < size:
        text, nxt = utf8_page(path, off, 7)
        assert nxt > off, "no progress"
        parts.append(text)
        off = nxt
    assert "".join(parts) == body, "pages do not rebuild the file"
    print(f"self-test ok: {len(parts)} pages, guards behave as expected")


if __name__ == "__main__":
    _self_test()
