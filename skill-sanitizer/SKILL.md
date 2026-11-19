---
name: skill-sanitizer
description: Prepare a private skill for public release as a separate copy.
license: MIT
compatibility: Works with any agent that can read and write files.
---

# Skill sanitizer

Input: a skill folder. Output: a separate cleaned copy. Do not edit the source.

1. Read `SKILL.md` and every file it uses.
2. Separate reusable procedure from details tied to the source author's people, accounts, machines, organization or setup.
3. In the copy, turn incidental local details into inputs or neutral examples. Remove credentials and unrelated private material. Keep service names and details the skill needs to work.
4. Check the copy's examples, scripts and references. Run an example from a clean directory when practical.
5. Deliver the copy with a short summary of changes and any judgment calls.

Keep behavior and useful detail. Do not make a service-specific skill generic. Do not invent configuration or remove a capability just because it is local; make its required settings inputs the consumer can provide.
