---
name: peer-review
description: Peer review of uncommitted or specified changes before a commit or pull request. Use when asked to review changes or check a diff, or when a pre-commit or pre-PR hook asks for one. Skip doc-only or config-only changes under about 20 lines, trivial renames, and formatting-only changes.
license: MIT
compatibility: Works with any agent that can run git commands and read files.
---

# peer-review

Review a change the way a careful reviewer on the team would, before the pull request exists. Find what would otherwise come back as a review comment. Stay on the diff.

## Step 1: Choose the target

In this order:

1. Paths or commits the user named. Use them.
2. Staged and unstaged changes: `git diff` plus `git diff --staged`.
3. A clean tree with a review request: `git show HEAD`.

Get the scope:

```bash
git status --short
git diff --stat
git diff --staged --stat
```

If the change is documentation-only, configuration-only, or under about 20 lines of trivial edits, say so, run one sanity check (the tests, a linter, or a parse of the changed file), and stop.

## Step 2: Read the intent

Read the commit message, the PR description, or the user's request. Write down the intended behavior in one sentence. Every finding is measured against that sentence. A change that does what it says and does it safely needs no more review than that.

## Step 3: Review axes

Work through these in order. When an axis has nothing to flag, move on. Do not pad.

1. **Correctness.** Does the code do the intended thing? Check empty input, `None`, zero-length collections, off-by-one bounds, Unicode and byte-versus-character lengths, timezone handling, and integer overflow where it matters.
2. **Security.** If the diff touches auth, secrets, crypto, personal data, SQL, a subprocess, or a path built from input, hand the diff to the secure-review skill. Do not run a shallow security pass here.
3. **Error handling.** Are errors swallowed with a bare `except` or an empty catch? Is a non-idempotent operation retried? Do error paths have tests? Does a failure leave the system in a half-written state?
4. **Concurrency.** Shared state without a lock. File writes without an atomic rename. Async code that awaits inside a lock. Two writers to one resource.
5. **Naming and structure.** Would a reader with no context understand each identifier? Does a new abstraction serve more than one caller? Does the code reach into a neighbor's internals?
6. **Deletion.** When behavior moves or is replaced, is the old code removed? Look for commented-out blocks, unused helpers, unused imports, and flags that are always set one way.
7. **Size.** Is the change larger than the problem? Count the files touched that the intent does not need. Speculative configuration and extension points that have one user are findings.
8. **Tests.** Does each behavior change have a test that fails without the change? Did the test change weaken an assertion to make it pass? Are new tests testing behavior or only the implementation?

## Step 4: Write the findings

For each finding:

```
[BLOCK|NIT|FYI] path/to/file:LINE
  Concern: <one sentence on what goes wrong>
  Fix: <the change, one line or a short snippet>
```

- BLOCK: fix before shipping. Use it only for a real defect, a security issue, data loss, or a broken test.
- NIT: a reviewer might push back on it, but it does not block the change.
- FYI: worth knowing, for example a nearby problem outside this diff. Put these in a follow-up, not in this change.

## Step 5: Verdict

End with exactly one line:

- `SHIP: nothing to flag beyond nits`
- `HOLD: <N> blockers`
- `NEEDS-HUMAN: <reason>` when the change needs a judgment this review cannot make, such as a new algorithm, a cryptographic design, or a performance requirement with no measurement.

## Rules

- Do not invent findings. If the diff is clean, the verdict is `SHIP` and the report says what was checked.
- Stay on the diff. Unrelated problems go in a follow-up note.
- Do not re-read a file that is already in context unless the diff changed it since.
- Cite line numbers from the current file, not the diff hunk header.
