# Outcome register

`outcome_counts.py` reads a markdown file with a `## Register` heading and one table, and evaluates each row's `evidence` cell against files under `--root`.

```
## Register

| id | agent | evidence | green | red |
|---|---|---|---|---|
| O-1 | writer | `rows state/posts.tsv where date in 30d` | >= 3 | = 0 |
| O-2 | writer | `age state/posts.tsv` | <= 14 | > 45 |
```

`green` and `red` are a comparison and an integer (`>= 3`, `= 0`, `<= 14`). A value that meets neither is amber. A missing file is red. Write `\|` for a literal `|` in a cell.

## Expressions

Paths are relative to `--root`. TSV files skip blank lines, `#` lines and the header row.

| Expression | Value |
|---|---|
| `rows <tsv> where <conds>` | data rows matching every condition |
| `days <tsv-or-glob> where <conds>` | distinct dates among matching rows or files |
| `age <tsv-or-glob> [where <conds>]` | days from the newest matching date to the run date |
| `files <glob> where <conds>` | matching files; a file's date is the first `YYYY-MM-DD` in its name, or its frontmatter value when the condition names that key |
| `value <glob> /regex/` | first capture group in the newest matching file, by filename date |
| `count <file> /regex/` | lines matching the regex |
| `stale-red <tsv> Nd` | check classes red on the newest run date whose red streak began N or more days earlier (needs columns `date`, `check_class`, `verdict`) |
| `fixed-red <tsv> Nd` | check classes that were red within N days and have since gone green (same columns) |

Join terms with ` + ` to sum them. Append ` when <expr> >= N` to score a row only once a gate
count reaches N; otherwise it reads `n/a`.

Conditions are comma-separated:

- `<column> in Nd` / `<column> older Nd`: that column's date is within, or older than, N days of the
  run date. `date` means the file's date or the TSV's `date` column.
- `<column>=value`, `<column>~regex`, `<column>!~regex`: TSV column equals, matches, or does not match.
- `content~regex`, `content!~regex`: file contents (for `files` and `days` on globs).
