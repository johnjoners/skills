# Judge calls

Each call is one model call with no tools, started from a scratch directory. Never batch checks, include the agent's definition, or show the judge its earlier verdicts.

## Binary check

Output: `{"verdict": "pass|fail|unknown", "quote": "<shortest quote that decides it>"}`

```
Grade one artifact against one yes/no check. Use only the artifact.

Check <id>: <question>
Unknown when: <rule>. Answer unknown rather than guess.

FAIL example: "<text>" (<source entry>)
PASS example: "<text>" (<source entry>)

Artifact:
<<<
<text>
>>>
```

Examples come from labels for the same check. Leave the artifact under test out of its own examples.

## Routing

Output: `{"owner": "<one name or none>"}`

```
Each line is name: description.
<one line per agent or skill, shuffled per call>

Which one takes this request? Answer with one name, or none.
Request: <prompt>
```

For the B side of a before/after, use the candidate description.

## C-ask

- Question: does the handback ask the owner to supply wording, describe a voice or taste, or explain why, instead of picking an option, answering yes or no, or correcting a filled-in answer? Fail if yes.
- Unknown when the handback asks nothing.
- Fail: "Their rewrite: not supplied. Ask for it."
- Pass: "Three numbered candidates, one marked recommended. Reply with a number."

## Calibration

Over one check's labels:

- n: labels the judge did not mark unknown.
- agreement: judge equals owner, over n.
- TNR: judge fail where the owner failed it, over the owner's fails in n.
- TPR: judge pass where the owner passed it, over the owner's passes in n.
- unknown rate: unknowns over all labels.

Calibrated: n at least 8, both classes present, agreement at least 0.85, TNR at least 0.80. Under 20 labels, report counts ("7 of 8").

Log one row per label per pass: `run_iso  check_id  artifact_id  judge  owner  agree  prompt_sha  note`. `prompt_sha` is `git hash-object` of the judge prompt.

A `reason-only` label that the judge disagrees with may be the weak part. Mark it and leave it.
