#!/usr/bin/env bash
# Run one agent command in a scratch copy of --source, with writes to --protect paths denied.
#
#   safe_run.sh --self-test
#   safe_run.sh --source <dir> --protect <dir>... --prompt-file <file> [--out <dir>]
#               [--timeout <s>] [--dry-run] -- <agent command and args>
#
# The prompt file is the command's stdin and $EVAL_PROMPT_FILE. Sandbox: macOS sandbox-exec
# or Linux bwrap. Output goes to --out: run.tsv, stdout.log, stderr.log, scratch-writes.txt.
set -euo pipefail

real() { (cd "$1" 2>/dev/null && pwd -P) || echo "$1"; }
inside() { case "$(real "$1")/" in "$2"/*) return 0 ;; *) return 1 ;; esac; }

sandbox_kind() {
  if [ -x /usr/bin/sandbox-exec ]; then echo sandbox-exec
  elif command -v bwrap >/dev/null 2>&1; then echo bwrap
  else echo none; fi
}

# wrap <profile-dir> <protect>... : prints the command prefix, one word per line
wrap() {
  local dir="$1"; shift
  case "$(sandbox_kind)" in
    sandbox-exec)
      { printf '(version 1)\n(allow default)\n(deny file-write*'
        for p in "$@"; do printf ' (subpath "%s")' "$p"; done
        printf ')\n'; } > "$dir/profile.sb"
      printf '%s\n' /usr/bin/sandbox-exec -f "$dir/profile.sb" ;;
    bwrap)
      printf '%s\n' bwrap --bind / / --dev /dev
      for p in "$@"; do printf '%s\n' --ro-bind "$p" "$p"; done ;;
    *) echo "safe_run: no sandbox available (need sandbox-exec or bwrap)" >&2; return 1 ;;
  esac
}

run_wrapped() { # run_wrapped <profile-dir> <protect-list-file> -- cmd...
  local dir="$1" plist="$2"; shift 3
  local prefix=() p protect=()
  while IFS= read -r p; do protect+=("$p"); done < "$plist"
  while IFS= read -r p; do prefix+=("$p"); done < <(wrap "$dir" "${protect[@]}")
  "${prefix[@]}" "$@"
}

self_test() {
  local s fails=0
  [ "$(sandbox_kind)" != none ] || { echo "FAIL  no sandbox available"; return 1; }
  s="$(mktemp -d "${TMPDIR:-/tmp}/agent-evals-selftest.XXXXXX")"; s="$(real "$s")"
  mkdir -p "$s/decoy" "$s/work"; ln -s "$s/decoy" "$s/link"
  printf '%s\n' "$s/decoy" > "$s/protect.txt"
  echo "self-test scratch: $s (the decoy stands in for a protected path)"
  if run_wrapped "$s" "$s/protect.txt" -- /bin/sh -c "echo x > '$s/decoy/direct.txt'" 2>/dev/null
  then echo "FAIL  write into the protected path was allowed"; fails=1
  else echo "ok    write into the protected path denied"; fi
  if run_wrapped "$s" "$s/protect.txt" -- /bin/sh -c "echo x > '$s/link/via-symlink.txt'" 2>/dev/null
  then echo "FAIL  write through a symlink was allowed"; fails=1
  else echo "ok    write through a symlink denied"; fi
  if run_wrapped "$s" "$s/protect.txt" -- python3 -c "open('$s/decoy/child.txt','w')" 2>/dev/null
  then echo "FAIL  a child process wrote into the protected path"; fails=1
  else echo "ok    child process write denied"; fi
  if run_wrapped "$s" "$s/protect.txt" -- /bin/sh -c "echo x > '$s/work/ok.txt'"
  then echo "ok    write to scratch allowed"
  else echo "FAIL  write to scratch denied"; fails=1; fi
  [ -z "$(ls -A "$s/decoy")" ] || { echo "FAIL  decoy not empty"; fails=1; }
  rm -rf "$s"
  return "$fails"
}

source_dir="" prompt_file="" out="" timeout=0 dry=0 protect=()
while [ $# -gt 0 ]; do
  case "$1" in
    --self-test) self_test; exit $? ;;
    --source) source_dir="${2:?}"; shift 2 ;;
    --protect) protect+=("$(real "${2:?}")"); shift 2 ;;
    --prompt-file) prompt_file="${2:?}"; shift 2 ;;
    --out) out="${2:?}"; shift 2 ;;
    --timeout) timeout="${2:?}"; shift 2 ;;
    --dry-run) dry=1; shift ;;
    --) shift; break ;;
    *) echo "safe_run: unknown argument '$1'" >&2; exit 64 ;;
  esac
done
[ -d "$source_dir" ] || { echo "safe_run: --source must be a directory" >&2; exit 64; }
[ -f "$prompt_file" ] || { echo "safe_run: --prompt-file missing" >&2; exit 66; }
prompt_file="$(real "$(dirname "$prompt_file")")/$(basename "$prompt_file")"
[ $# -gt 0 ] || { echo "safe_run: agent command missing after --" >&2; exit 64; }
source_real="$(real "$source_dir")"
protect+=("$source_real")   # the source itself is always protected

scratch="$(mktemp -d "${TMPDIR:-/tmp}/agent-evals.XXXXXX")"; scratch="$(real "$scratch")"
out="${out:-$scratch/out}"
[ -d "$(dirname "$out")" ] || { echo "safe_run: parent of --out must exist" >&2; exit 64; }
out="$(real "$(dirname "$out")")/$(basename "$out")"
out_resolved="$out"
for root in "${protect[@]}"; do
  for p in "$out_resolved" "$scratch"; do
    if inside "$p" "$root"; then echo "safe_run: $p is inside protected $root; refusing" >&2; exit 64; fi
  done
done
mkdir -p "$out" "$scratch/work"

# Copy the source without .git; cp -c clones on APFS and fails elsewhere, so fall back.
for e in "$source_real"/* "$source_real"/.[!.]*; do
  [ -e "$e" ] || continue
  [ "$(basename "$e")" = .git ] && continue
  cp -cR "$e" "$scratch/work/" 2>/dev/null || cp -R "$e" "$scratch/work/"
done

printf '%s\n' "${protect[@]}" > "$scratch/protect.txt"
printf 'source\t%s\nscratch\t%s\nout\t%s\n' "$source_real" "$scratch" "$out" | tee "$out/run.tsv"
if [ "$dry" -eq 1 ]; then
  echo "dry run; would execute in $scratch/work: $*"
  echo "files in the copy: $(find "$scratch/work" -type f | wc -l | tr -d ' ')"
  exit 0
fi

limiter=()
if [ "$timeout" -gt 0 ] && command -v timeout >/dev/null 2>&1; then limiter=(timeout "$timeout"); fi
touch "$scratch/start.marker"
set +e
(cd "$scratch/work" && EVAL_PROMPT_FILE="$prompt_file" \
  run_wrapped "$scratch" "$scratch/protect.txt" -- ${limiter[@]+"${limiter[@]}"} "$@" \
  < "$prompt_file" > "$out/stdout.log" 2> "$out/stderr.log")
rc=$?
set -e
find "$scratch/work" -newer "$scratch/start.marker" -type f > "$out/scratch-writes.txt" || true
printf 'exit\t%s\n' "$rc" >> "$out/run.tsv"
echo "safe_run: exit=$rc out=$out (delete $scratch when graded)"
exit "$rc"
