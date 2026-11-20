---
name: tooling-adoption-check
description: Use when asked whether a tool or library is already installed, what its free tier costs, or whether adding it is worth it. Checks every install location and existing coverage, reads current pricing, and gives one verdict.
license: MIT
compatibility: macOS or Linux shell. Web access for pricing pages. Works with any agent that can run commands and fetch pages.
---

# Tooling adoption check

The question usually arrives as one line: "is X worth it?" The answer has three parts. Is it already here? What does it cost? Does it close a gap that something existing does not? End with one verdict and the reason.

## Step 1: Is it installed?

Search every place a tool can live. One interpreter is not enough.

- Python packages, from each interpreter on the machine. Run each one separately:
  - `python3 -c "import <pkg>"`
  - `/opt/homebrew/bin/python3 -c "import <pkg>"`
  - Each project virtualenv you know about
- CLI binaries: `command -v <bin>`
- Package managers: `pipx list`, `uv tool list`, `brew list | grep <name>`, `docker images | grep <name>`
- Packages inside virtualenvs you did not know about:
  `find ~ /opt/homebrew /usr/local -maxdepth 9 -type d -path '*site-packages*' -name '<pkg>' 2>/dev/null`
- Caches: `pip cache list`, `uv cache dir`

Keep each command short. Long compound shell lines fail in ways that look like "not installed."

Report every location checked, even when the answer is no. "Not installed" with no list of what was checked is not an answer, because the next person cannot tell whether you looked.

## Step 2: What does it cost?

Fetch the vendor's pricing page now, not from memory. Record the URL and the retrieval date.

- Is the free allowance one-time or monthly? Say which.
- Give the overage price as one number with its unit.
- Name the features that need a sales call, an enterprise plan, or a request form.
- Name any open-source or self-hosted version and what it lacks compared with the hosted one.
- For a hosted API that will receive client or organization documents, find the data agreement. Retention claims on a marketing page are not the agreement. Record the retention period, training use, and the subprocessors listed.

## Step 3: Is it worth adding?

Check what already covers the job.

- Search the installed skills and local skill directories for the capability. For document parsing, search for `pymupdf`, `pdfplumber`, `docling`, `markitdown`, and `tesseract`.
- Import or `command -v` each candidate that is already present.
- For each one, write what it covers and where it fails.
- List only the gaps the new tool closes, each as a concrete case: "scanned PDFs with no text layer" is a gap. "Better OCR" is not.

State what adding the tool costs:

- Install weight, for example a multi-gigabyte model download or a compiled dependency.
- Free allowances that run out, and when.
- One more dependency to keep updated and one more place to look when something breaks.

## Step 4: The verdict

Give one recommendation: add it, add it as a fallback, or do not add it. Then:

- Name the triggers that would change the answer. For example: "add if more than 10 percent of documents come back empty from the local parser."
- Name where it plugs in. Usually that is a fallback step inside an existing skill, not a new skill.

Format:

```
Verdict: <add | add as fallback | do not add>
Installed: <where, or "no, checked: ...">
Cost: <free tier, overage, data terms, with source URL and date>
Gap it closes: <one concrete case, or "none">
Triggers to revisit: <one or two>
```

## Verified upgrades to a vendored tool

When a tool is already installed and needs an upgrade, the risk is in the update path.

1. Find the real installed directory. Follow symlinks. Agent-facing links often point at a shared target, so replacing the link destination changes every agent that uses it. Replace only the target you intend to change.
2. Download the tagged release to a staging directory. Verify the file against the digest the publisher lists for that asset.
3. Compare the new tree with the installed one. Keep the local instructions, descriptions, and helper scripts unchanged unless you reviewed the change.
4. Review the behavior before activation. Check subprocess calls, network calls, filesystem writes, dependency changes, and any export path. A validator that checks file format does not check privacy.
5. Look inside exported artifacts. Embedded JSON, Base64 blobs, and compressed bundles can carry data beyond the excerpt or chart columns you intended. To test a suspected leak, use a synthetic canary value, not a real document.
6. If the newest release fails the privacy review, keep the active version. Offer the last release that passes. Do not patch upstream silently, and do not present a restricted build as the official release.
7. Test the staged version with real inputs, the project's own browser-based checks, and its export code. Keep a rollback copy outside the staging directory with its hash recorded.
8. Confirm the activated executable through the path agents actually run, not the path you installed to.

## References

- `references/document-extraction.md`: local document parsing compared with a hosted parser, and when to escalate to one.
