# skills

Agent skills in the open [Agent Skills](https://agentskills.io) format: a folder with a
`SKILL.md` (YAML frontmatter plus instructions) and any scripts or templates it uses. Any
agent that reads `SKILL.md` folders can load them.

| Skill | Does |
| --- | --- |
| [motion](motion/) | Animated explainers and charts built as editable HTML, rendered to MP4, ProRes or GIF |
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
