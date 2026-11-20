# Trace review

Find where the runtime stores transcripts, how a file names its agent, and the retention period. `scripts/trace_list.py --root <dir> [--agent <regex>]` lists them with age and days to expiry.

## Each week

1. `trace_list.py --days 7` for the sample. `--at-risk <retention minus 7>` for transcripts about to expire.
2. Copy each at-risk transcript's first user message into the agent's golden set with path, date and outcome. Redact tokens, keys, `Bearer` strings and one-time codes.
3. Sample every run if the agent has 10 or fewer. Otherwise take the 10 newest plus every run that ended in an error, a block, the turn cap or a permission denial.
4. Read each end to end: the task, each tool call and target, each error, the handback.
5. Write one line per failure with file and line. Write `clean` for a clean run.
6. Group lines into codes in the agent's `failures.md`. A code is `F-<short>-<n>` with a name, a one-sentence definition and its first trace. When you merge or rename a code, note which lines moved.
7. Count per code per week.
8. Turn the worst trace into a golden task. A code seen in 3 or more traces becomes a check candidate once owner verdicts exist to label it.
9. Grade the ask (SKILL.md, Step 8).

## Common failure shapes

- Drafted from the wrong source.
- A rejected shape reissued with new nouns.
- The running definition argues what the design note replaced.
- Described unrun work instead of reporting it blocked.
- Referenced a path that no longer exists.
- Claimed a file that is not on disk.
- Handed the drafting back to the owner.

## Archive

Copy transcripts older than two-thirds of the retention period, with their metadata files, to a directory outside the runtime's cleanup path.
