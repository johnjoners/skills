# AGENTS.md

Each top-level folder is one skill in the Agent Skills format. `README.md` lists them.

## Skill layout

```
<name>/
  SKILL.md       frontmatter: name, description, license, compatibility
  scripts/       executables the skill runs
  templates/     files the skill copies and edits
  references/    long material loaded only when needed
```

- `name` matches the folder: lowercase, hyphens, 64 characters max.
- `description` says what the skill does and when to use it, in under 1024 characters. Agents
  choose skills from this line alone.
- Keep `SKILL.md` under 500 lines; move detail into `references/`.
- Paths inside a skill are relative to the skill folder.

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
