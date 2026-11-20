---
name: read-only-repo-mcp
description: Use when building a read-only MCP server over a repository checkout. Covers path confinement, bounded reads, YAML and UTF-8 guards, and testing with a real MCP client.
license: MIT
compatibility: Python 3.11 or later. PyYAML for the guard module. The official mcp Python SDK when the server uses it, and uv for the lockfile and a throwaway client.
---

# Read-only repository MCP

A server that lets an agent read a repo's records and nothing else. The hard parts are path confinement, bounded output, and parsing untrusted YAML and UTF-8 without a crash or a memory blowup. Build those first, then the tools.

## Before writing code

1. Read the repo's own editing and privacy rules. They decide which records are public.
2. Define the record allowlist as a list of paths or globs. Anything not on it is invisible to the server, including its existence.
3. Exclude by default: hidden paths (`.env`, `.git`), private directories, code and runtime files, and anything that is not a record.
4. Decide the fixed resource set now. The server exposes those resources and no arbitrary filesystem template.

## Dependencies

- Use `uv` with a lockfile. Install nothing globally.
- Use the official `mcp` SDK unless there is a reason not to. A stdlib-only server (hand-rolled JSON-RPC) is fine, but then the SDK stays out of the repo and the test must use a real client (see Verification).
- Pin the SDK range: `mcp>=1,<2`.

## Filesystem confinement

The reference implementation is `references/guards.py`, function `open_regular`. Use it as written or copy the logic.

- Pin the checkout root with `os.open(root, O_RDONLY | O_DIRECTORY)`. Keep that descriptor for the life of the server.
- Walk each requested directory with `os.open(name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW, dir_fd=fd)`.
- Open the leaf with `O_RDONLY | O_NOFOLLOW | O_NONBLOCK`. A FIFO or device blocks a plain open forever, so `O_NONBLOCK` is required.
- Run `os.fstat` on the open descriptor. Require `S_ISREG` and `st_nlink == 1`. A hard link to a file outside the allowlist has `st_nlink > 1`.
- Check the open descriptor, not the path. A path check followed by an open leaves a window in which the path can be swapped for a symlink.
- Turn OS errors into short messages. Never return an absolute local path in an error.

## Bounds

Every response has a limit, and every truncated response says so.

| Limit | Suggested starting value |
|---|---|
| Directory depth | 6 |
| Records per listing | 200 |
| Text page size | 32 KiB |
| Binary read size | 2 MiB |
| Total search I/O per call | 16 MiB |

- Count failed UTF-8 decodes against the search I/O budget. They read bytes too.
- Return `truncated: true` and a `next_offset` when a page ends early.
- For pagination, `utf8_page` in `guards.py` takes a byte offset, skips continuation bytes at the start, and holds back an incomplete trailing character for the next page. Return the offset computed from the bytes actually sent, not the requested length.

## YAML

- Reject aliases before construction. A post-load check cannot stop exponential merge-alias expansion, because SafeLoader expands the aliases while it builds the object. `safe_yaml_load` in `guards.py` runs a streaming event pass first and raises on `AliasEvent`, on more than 5000 events, or on nesting deeper than 20.
- After loading, check node count, types, required keys, allowed status values, evidence references, and date normalization. Normalize ISO dates to strings so the JSON output is stable.
- Test with tiny repeated merge-alias inputs in a subprocess under a timeout. A passing test on a normal file proves nothing about the attack.

## Images and PDFs

- Return images with FastMCP's `Image(data=..., format="jpeg")` or `"png"`. Check the file extension against the magic bytes (`FF D8 FF` for JPEG, `89 50 4E 47` for PNG) before reading the body.
- Check the size before reading. Refuse anything over the binary limit.
- For PDFs, do not decode binary. List the file and point clients at its retained text extraction.

## Tool annotations

- Mark every tool `readOnlyHint=True`, `destructiveHint=False`, `idempotentHint=True`, `openWorldHint=False`.
- Annotate dictionary returns as `dict[str, Any]`. A bare `dict` return annotation can leave `CallToolResult.structuredContent` unset.

## Verification

Run these in order. Each must pass before the next.

1. Unit guards: `uv run --no-project --python 3.11 --with pyyaml python references/guards.py` (prints `self-test ok`).
2. Real client: start the server with `uv run --project <repo> --locked python <server>`, then connect with the SDK's `stdio_client` and `ClientSession`. A raw JSON-RPC pipe does not test a real client. Run the client from a directory outside the repo with `uv run --no-project --python 3.11 --with 'mcp>=1,<2' <outside-repo>/client.py </dev/null`.
3. The client should cover: initialization, the tool list and annotations, one structured result, a literal search, a large real image (check its MIME type and byte count), a denied path (`.env`, a symlink, a hard link), and each fixed resource.
4. Run the client twice: once with the default checkout root, once with an explicit root from a different working directory.
5. Take lookup names from the committed snapshot, such as each record's `name` field. A lookup that matches only an alias fails, and the failure looks like a server bug.
6. Point test temp storage at a directory owned by the test run, outside the repo.

Build in vertical slices: one failing behavior, the smallest fix, a passing suite, then the next behavior.

## Release

A server consumers install from a git URL needs a fixed ref, not a floating branch.

1. Tag the verified commit with an annotated tag named for the server and its version
   (`mcp-v0.1.0` style when the server shares a repo with other content). Push the tag.
2. Cut a GitHub release on the tag with the one-line install command pointing at the tag:
   `uvx --from "git+https://<host>/<owner>/<repo>@<tag>[#subdirectory=<dir>]" <server>`.
3. Run the release's own install command from scratch and call one tool through a real
   client. A release that does not install is not a release.
4. Update the install snippet in the README to the tag in the same change.

## Delivery

- Keep smoke-test scripts outside the repo.
- Stage finished code only, after the full suite and a real-checkout smoke run pass.
- Do not commit, publish, add client configuration, or add a write or control tool without explicit authorization.

## References

- `references/guards.py`: confinement, YAML, and UTF-8 guards with a self-test. Last run: 120 UTF-8 pages rebuilt the source exactly, the denied paths were rejected, and three YAML inputs were rejected before parsing.
