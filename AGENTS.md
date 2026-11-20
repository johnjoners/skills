# AGENTS.md

Each folder under `skills/` is one skill in the Agent Skills format. `README.md` lists
them. `mcp/` holds a read-only MCP server over the catalogue; it is the only runtime
code in the repo.

## Skill layout

```
skills/<name>/
  SKILL.md       frontmatter: name, description, license, compatibility
  scripts/       executables the skill runs
  templates/     files the skill copies and edits
  references/    long material loaded only when needed
  requirements.txt Python packages the scripts need, if any
```

- `name` matches the folder: lowercase, hyphens, 64 characters max.
- `description` says what the skill does and when to use it, in under 1024 characters. Agents
  choose skills from this line alone.
- Keep `SKILL.md` under 500 lines; move detail into `references/`.
- Paths inside a skill are relative to the skill folder.
- Dependencies live with the skill that needs them, never at the repo root. System programs
  (ffmpeg, a browser) go in `compatibility`.

## Rules

- No model, vendor, agent or harness names in instructions. A skill has to work under any
  agent that can read files and run commands.
- No paths outside the repo, no personal data, no credentials.
- Scripts take inputs as arguments, write only where told, and exit non-zero on failure.
- Third-party code keeps its license file beside it.
- Add a skill to the README table in the same change.
- Before committing, run the skill's example end to end and look at the output. Scratch
  renders, probes and one-off check scripts stay out of the repo.
- CI comes in when the repo has enough skills to need it, as one workflow that runs every
  skill's example.

## MCP server

- One package, `skills_mcp`, one module, `server.py`. Read-only; every tool keeps the
  read-only, non-destructive, idempotent, closed-world annotations.
- Two backends behind one interface: `GitHubBackend` (HTTP fetch, content-hash cache)
  and `CheckoutBackend` (local path, confined opens). Reads stay under `skills/`.
- Hidden paths, traversal, symlinks and hard-linked files are refused at open time.
- Dependencies are project-managed with `uv` and pinned in `mcp/uv.lock`. Nothing
  installs globally.
- Scratch clients, probes and renders stay outside the repo.
