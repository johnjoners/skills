# skills

Agent skills in the open [Agent Skills](https://agentskills.io) format: a folder with a
`SKILL.md` (YAML frontmatter plus instructions) and any scripts or templates it uses. Any
agent that reads `SKILL.md` folders can load them.

| Skill | Does |
| --- | --- |
| [motion](motion/) | Animated explainers and charts built as editable HTML, rendered to MP4, ProRes or GIF |
| [browser-session-takeover](browser-session-takeover/) | Drive the user's already-signed-in browser instead of a fresh profile that hits login walls |
| [cloud-vm-cost-research](cloud-vm-cost-research/) | Compare cloud VM costs, nonprofit credits and data-protection terms from primary sources |
| [official-parcel-gis-evidence](official-parcel-gis-evidence/) | Verify parcels and address records against official GIS sources, keeping each query as evidence |
| [peer-review](peer-review/) | Pre-commit peer review of a diff: correctness, error handling, concurrency, deletion debt |
| [prompt-injection-check](prompt-injection-check/) | Gate external content for injected instructions before it drives a tool call |
| [read-only-repo-mcp](read-only-repo-mcp/) | Build a read-only MCP server over a repository checkout, with path and parsing safeguards |
| [secure-review](secure-review/) | SOC2-lite security review for code on auth, secret, crypto, input and privacy surfaces |
| [tooling-adoption-check](tooling-adoption-check/) | Check whether a tool is installed, what its free tier costs, and whether it is worth adding |
| [skill-sanitizer](skill-sanitizer/) | Prepares a private skill for public use by generalizing local assumptions and delivering a separate cleaned copy |

## Install

Copy or symlink a skill folder into the directory your agent loads skills from:

```sh
git clone https://github.com/johnjoners/skills
ln -s "$PWD/skills/<skill>" <agent-skills-dir>/<skill>
```

Agents without skill loading can be pointed at a `SKILL.md` directly.

## Requirements

Each skill lists its own setup in its `SKILL.md`, with any Python packages in a
`requirements.txt` beside it.

## License

[MIT](LICENSE). Skills call outside programs without bundling them; those programs keep
their own licenses.
