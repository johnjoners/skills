# skills

Agent skills in the open [Agent Skills](https://agentskills.io) format: a folder with a
`SKILL.md` (YAML frontmatter plus instructions) and any scripts or templates it uses. Any
agent that reads `SKILL.md` folders can load them.

| Skill | Does |
| --- | --- |
| [agent-evals](skills/agent-evals/) | Grade an agent on results and quality: golden sets, a judge calibrated to the owner's verdicts, before/after scores in a write-protected harness |
| [browser-session-takeover](skills/browser-session-takeover/) | Drive the user's already-signed-in browser instead of a fresh profile that hits login walls |
| [cloud-vm-cost-research](skills/cloud-vm-cost-research/) | Compare cloud VM costs, nonprofit credits and data-protection terms from primary sources |
| [motion](skills/motion/) | Animated explainers and charts built as editable HTML, rendered to MP4, ProRes or GIF |
| [official-parcel-gis-evidence](skills/official-parcel-gis-evidence/) | Verify parcels and address records against official GIS sources, keeping each query as evidence |
| [peer-review](skills/peer-review/) | Pre-commit peer review of a diff: correctness, error handling, concurrency, deletion debt |
| [prompt-injection-check](skills/prompt-injection-check/) | Gate external content for injected instructions before it drives a tool call |
| [read-only-repo-mcp](skills/read-only-repo-mcp/) | Build a read-only MCP server over a repository checkout, with path and parsing safeguards |
| [secure-review](skills/secure-review/) | SOC2-lite security review for code on auth, secret, crypto, input and privacy surfaces |
| [skill-sanitizer](skills/skill-sanitizer/) | Prepares a private skill for public use by generalizing local assumptions and delivering a separate cleaned copy |
| [tooling-adoption-check](skills/tooling-adoption-check/) | Check whether a tool is installed, what its free tier costs, and whether it is worth adding |

## Install

Copy or symlink a skill folder into the directory your agent loads skills from:

```sh
git clone https://github.com/johnjoners/skills
ln -s "$PWD/skills/skills/<skill>" <agent-skills-dir>/<skill>
```

Agents without skill loading can be pointed at a `SKILL.md` directly.

## MCP server

An agent can also read this catalogue over MCP without cloning it. `mcp/` holds a
read-only server that lists, reads and searches the skills over HTTP:

```sh
uvx johnjoners-skills==0.1.1
```

Client config:

```json
{
  "mcpServers": {
    "skills": {
      "command": "uvx",
      "args": ["johnjoners-skills==0.1.1"]
    }
  }
}
```

Fetches cache by content hash under `~/.cache/skills-mcp`. Set `GITHUB_TOKEN` to raise
the API rate limit. `--skills-repo <path>` reads a local checkout instead.

## Requirements

Each skill lists its own setup in its `SKILL.md`, with any Python packages in a
`requirements.txt` beside it. The MCP server needs Python 3.11 or later and
[uv](https://docs.astral.sh/uv/) on PATH; the rest is pinned in `mcp/uv.lock`.

## License

[MIT](LICENSE). Skills call outside programs without bundling them; those programs keep
their own licenses.
