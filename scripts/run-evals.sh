#!/bin/bash
# run-evals.sh — the plugin-eval gate for Tomo's runtime prose (spec 041, C1).
# Assembles a throwaway plugin copy of tomo/dot_claude/{agents,skills,commands}
# plus evals/ in $TMPDIR, runs `claude plugin eval` on it with fixed gate flags,
# and hands the result to scripts/lib/eval_verdict.py for a one-line verdict.
# It refuses (exit 3) before spending anything when the invocation or the suite
# is malformed, and it never writes into the repo: results go to the gitignored
# tomo-tmp/evals/<TS>/, and a repo change during the run voids the verdict.
# version: 0.1.1
set -e
set -o pipefail

# fd 3 is the real stdout: every verdict line goes there, so a redirect of fd 1 into a
# scratch file (tree snapshots) can never swallow it.
exec 3>&1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERDICT_PY="$SCRIPT_DIR/lib/eval_verdict.py"
MIN_CLAUDE_VERSION="2.1.269"

print_help() {
    cat <<'EOF'
Usage: run-evals.sh [OPTIONS]

Runs the eval suite under evals/ against Tomo's runtime prose with
`claude plugin eval`, and prints exactly one verdict line on stdout.

Options:
  --case <glob>         Run only the cases whose name matches <glob>. The
                        verdict is marked PARTIAL SUITE and does not satisfy
                        the merge rule.
  --rev <git-rev>       Take agents/skills/commands from <git-rev> instead of
                        the working tree (RED proof). evals/ always comes
                        from the working tree.
  --mutation <name>     Apply evals/_mutations/<name>.patch to the assembled
                        copy, never to the repo (RED proof). A patch that does
                        not apply is refused.
  --max-cost-usd <usd>  Hard cost ceiling for this invocation only (default 5;
                        also EVAL_MAX_COST_USD). Hitting it gives NOT GRADED.
  --runs <n>            Runs per case. Only together with --case, --mutation
                        or --rev; a full-suite gate run is always 3 runs.
  --keep-temp           Keep the plugin copy and the CLI's eval workspaces for
                        debugging (the CLI seals them mode 000; chmod 700 to
                        inspect).
  -h, --help            Show this help and exit.

Fixed flags passed to the CLI:
  --ablation none --threshold 1.0 --runs 3 -j 2 --no-publish --trust-plugin
  --scaffold --allow-tools Bash --model <"model" in tomo/dot_claude/settings.json>

Results: tomo-tmp/evals/<TS>/ (gitignored) holds aggregate-result.json,
report.html and verdict.txt (the verdict line).

Exit codes:
  0  GREEN       every grader passed in every run of every case
  1  RED         at least one grader failed; stderr names case/grader/run
  2  NOT GRADED  cost cap, API/rate-limit error, scaffold failure, harness
                 error, interrupt, or the repo changed during the run
  3  REFUSED     preflight failed before anything was spent (old claude,
                 no cases, missing leak guard, unknown --case/--mutation/--rev,
                 unreadable settings, bad options)

Sandbox: the eval harness cannot start inside Claude Code's Bash sandbox
(runs fail with EPERM -> NOT GRADED). Run this from a terminal, or from a
coding session with the sandbox disabled for this one command.

Environment:
  CLAUDE_BIN            claude binary (default ~/.local/bin/claude; named
                        explicitly so a shell alias or wrapper never runs).
                        Under pytest it must be set, or the run is refused.
  TOMO_EVALS_REPO_ROOT  repo to evaluate (default: the repo holding this script)
  EVAL_MAX_COST_USD     default for --max-cost-usd (5)
EOF
}

refuse() {
    DELIBERATE=true
    echo "REFUSED · $*" >&2
    exit 3
}

# ── CLI parsing ──────────────────────────────────────────

CASE_GLOB=""
REV=""
MUTATION=""
MAX_COST="${EVAL_MAX_COST_USD:-5}"
RUNS=""
KEEP_TEMP=false

need_value() {
    [ $# -ge 2 ] && [ -n "$2" ] || refuse "$1 needs a value"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --case)         need_value "$@"; CASE_GLOB="$2"; shift ;;
        --rev)          need_value "$@"; REV="$2"; shift ;;
        --mutation)     need_value "$@"; MUTATION="$2"; shift ;;
        --max-cost-usd) need_value "$@"; MAX_COST="$2"; shift ;;
        --runs)         need_value "$@"; RUNS="$2"; shift ;;
        --keep-temp)    KEEP_TEMP=true ;;
        -h|--help)      print_help; exit 0 ;;
        *)              print_help >&2; refuse "unknown option: $1" ;;
    esac
    shift
done

# ── Preflight (nothing spent; any failure exits 3) ───────

if [ -n "${PYTEST_CURRENT_TEST:-}" ] && [ -z "${CLAUDE_BIN:-}" ]; then
    refuse "CLAUDE_BIN is not set under pytest — a test must never reach the real claude binary"
fi
CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude}"

[ -n "$REV" ] && [ -n "$MUTATION" ] && refuse "--rev and --mutation are mutually exclusive"
if [ -n "$RUNS" ]; then
    [ -n "$CASE_GLOB" ] || [ -n "$MUTATION" ] || [ -n "$REV" ] \
        || refuse "--runs needs --case, --mutation or --rev; a full-suite gate run is always 3 runs"
    echo "$RUNS" | grep -Eq '^[1-9][0-9]*$' \
        || refuse "--runs must be a positive integer without leading zeros, got '$RUNS'"
fi
echo "$MAX_COST" | grep -Eq '^[0-9]+(\.[0-9]+)?$' \
    || refuse "--max-cost-usd / EVAL_MAX_COST_USD must be a number, got '$MAX_COST'"

[ -n "${TMPDIR:-}" ] || refuse "TMPDIR is not set (temporary files never go to /tmp)"
TMP_BASE="${TMPDIR%/}"
[ -d "$TMP_BASE" ] || refuse "TMPDIR does not exist: $TMP_BASE"

ROOT="${TOMO_EVALS_REPO_ROOT:-$SCRIPT_DIR/..}"
ROOT="$(cd "$ROOT" 2>/dev/null && pwd)" || refuse "repo root not found: ${TOMO_EVALS_REPO_ROOT:-$SCRIPT_DIR/..}"
git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || refuse "not a git work tree: $ROOT"
DOT_CLAUDE="$ROOT/tomo/dot_claude"
EVALS="$ROOT/evals"

MODEL="$(python3 -c '
import json, re, sys
try:
    m = json.load(open(sys.argv[1])).get("model")
except Exception:
    sys.exit(1)
if not isinstance(m, str) or not re.fullmatch(r"[A-Za-z0-9._:\[\]-]+", m):
    sys.exit(1)
print(m)
' "$DOT_CLAUDE/settings.json" 2>/dev/null)" \
    || refuse "no readable \"model\" in tomo/dot_claude/settings.json"

for d in agents skills commands; do
    [ -d "$DOT_CLAUDE/$d" ] || refuse "missing tomo/dot_claude/$d"
done

[ -f "$EVALS/_lib/no-leak.md" ] || refuse "missing evals/_lib/no-leak.md (canonical leak guard)"
CASES=""
for dir in "$EVALS"/*/; do
    [ -d "$dir" ] || continue
    name="$(basename "$dir")"
    case "$name" in _*|results) continue ;; esac
    [ -f "$dir/case.yaml" ] || [ -f "$dir/prompt.md" ] || continue
    CASES="$CASES $name"
done
CASES="${CASES# }"
[ -n "$CASES" ] || refuse "evals/ holds no case (a case is evals/<name>/ with case.yaml or prompt.md)"
for name in $CASES; do
    cmp -s "$EVALS/_lib/no-leak.md" "$EVALS/$name/graders/9-no-leak.md" \
        || refuse "case $name lacks graders/9-no-leak.md byte-identical to evals/_lib/no-leak.md"
done

if [ -n "$CASE_GLOB" ]; then
    matched=false
    for name in $CASES; do
        # shellcheck disable=SC2254  # the glob is the point
        case "$name" in $CASE_GLOB) matched=true ;; esac
    done
    $matched || refuse "--case '$CASE_GLOB' matches no case; cases: $CASES"
fi

PATCH_FILE=""
if [ -n "$MUTATION" ]; then
    case "$MUTATION" in *[!A-Za-z0-9._-]*|.*) refuse "invalid mutation name: $MUTATION" ;; esac
    PATCH_FILE="$EVALS/_mutations/$MUTATION.patch"
    [ -f "$PATCH_FILE" ] || refuse "no such mutation: evals/_mutations/$MUTATION.patch"
fi

if [ -n "$REV" ]; then
    git -C "$ROOT" rev-parse --verify --quiet "$REV^{commit}" >/dev/null \
        || refuse "--rev '$REV' is not a commit"
fi

git -C "$ROOT" check-ignore --quiet tomo-tmp/evals/probe \
    || refuse "tomo-tmp/ is not gitignored in $ROOT — results would dirty the tree"

[ -x "$CLAUDE_BIN" ] || refuse "claude binary not executable: $CLAUDE_BIN"
CLAUDE_VERSION="$("$CLAUDE_BIN" --version 2>/dev/null | awk 'NR==1{print $1}')" || CLAUDE_VERSION=""
echo "$CLAUDE_VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' \
    || refuse "cannot read the claude version from $CLAUDE_BIN --version"
awk -v a="$CLAUDE_VERSION" -v b="$MIN_CLAUDE_VERSION" 'BEGIN {
    split(a, x, "."); split(b, y, ".")
    for (i = 1; i <= 3; i++) { if (x[i] + 0 > y[i] + 0) exit 0; if (x[i] + 0 < y[i] + 0) exit 1 }
    exit 0 }' || refuse "claude $CLAUDE_VERSION is older than $MIN_CLAUDE_VERSION (claude plugin eval)"

# ── Work dir, cleanup, unexpected-failure mapping ─────────

WORK=""
PHASE=preflight   # preflight → an unexpected failure is REFUSED (3); run → NOT GRADED (2)
DELIBERATE=false
# shellcheck disable=SC2329  # invoked by the EXIT trap
cleanup() {
    rc=$?
    if [ -n "$WORK" ] && [ "$KEEP_TEMP" = false ]; then
        case "$WORK" in
            "$TMP_BASE"/tomo-evals.??????)
                chmod -R u+rwx "$WORK" 2>/dev/null || true
                rm -rf "$WORK" ;;
            *) echo "run-evals: refusing to remove unexpected path: $WORK" >&2 ;;
        esac
    elif [ -n "$WORK" ]; then
        echo "run-evals: kept plugin copy at $WORK" >&2
    fi
    if [ "$rc" -ne 0 ] && [ "$DELIBERATE" = false ]; then
        # set -e tripped somewhere: never let a stray exit code read as RED (1).
        if [ "$PHASE" = preflight ]; then
            echo "REFUSED · runner error (exit $rc) before anything was spent" >&2
            exit 3
        fi
        echo "NOT GRADED · runner error (exit $rc)" >&3
        exit 2
    fi
}
trap cleanup EXIT
trap 'DELIBERATE=true; echo "NOT GRADED · interrupted" >&3; exit 2' INT TERM

WORK="$(mktemp -d "$TMP_BASE/tomo-evals.XXXXXX")"

# ── Tree snapshot (F1-AC2) ───────────────────────────────

# git status plus one line per non-ignored file (tracked or untracked):
# "<blob hash> <path>" (or link:/absent). Comparing the before/after files names
# every path that changed during the run. Gitignored paths (tomo-tmp/) are not covered.
tree_state() {
    git -C "$ROOT" -c core.quotePath=false status --porcelain --untracked-files=all | sed 's/^/status /'
    (
        cd "$ROOT"
        git -c core.quotePath=false ls-files --cached --others --exclude-standard | sort -u > "$WORK/tree.files"
        : > "$WORK/tree.regular"
        while IFS= read -r f; do
            [ -n "$f" ] || continue
            if [ -L "$f" ]; then printf 'link:%s %s\n' "$(readlink "$f")" "$f"
            elif [ -f "$f" ]; then printf '%s\n' "$f" >> "$WORK/tree.regular"
            else printf 'absent %s\n' "$f"
            fi
        done < "$WORK/tree.files"
        if [ -s "$WORK/tree.regular" ]; then
            git hash-object --no-filters --stdin-paths < "$WORK/tree.regular" > "$WORK/tree.hashes"
            paste -d ' ' "$WORK/tree.hashes" "$WORK/tree.regular"
        fi
    )
}

tree_state > "$WORK/tree.before"
if grep -q '^status ' "$WORK/tree.before"; then TREE=dirty; else TREE=clean; fi

# ── Assemble the plugin copy (ADR-1) ─────────────────────

PLUGIN="$WORK/tomo"
mkdir -p "$PLUGIN/.claude-plugin" "$WORK/src"
printf '{"name": "tomo"}\n' > "$PLUGIN/.claude-plugin/plugin.json"

if [ -n "$REV" ]; then
    git -C "$ROOT" archive "$REV" tomo/dot_claude/agents tomo/dot_claude/skills tomo/dot_claude/commands \
        | tar -x -C "$WORK/src" || refuse "git archive of $REV failed"
    for d in agents skills commands; do mv "$WORK/src/tomo/dot_claude/$d" "$PLUGIN/$d"; done
else
    for d in agents skills commands; do cp -R "$DOT_CLAUDE/$d" "$PLUGIN/$d"; done
fi

mkdir "$PLUGIN/evals"
for entry in "$EVALS"/* "$EVALS"/.[!.]*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    [ "$(basename "$entry")" = results ] && continue
    cp -R "$entry" "$PLUGIN/evals/"
done

if [ -n "$PATCH_FILE" ]; then
    (cd "$PLUGIN" && patch -p1 --forward --silent -i "$PATCH_FILE" </dev/null >/dev/null 2>&1) \
        || refuse "mutation $MUTATION does not apply to the assembled copy — refresh the patch"
fi

# ── Run ──────────────────────────────────────────────────

TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
mkdir -p "$ROOT/tomo-tmp/evals"
OUT="$ROOT/tomo-tmp/evals/$TS"
n=0
until mkdir "$OUT" 2>/dev/null; do
    n=$((n + 1)); OUT="$ROOT/tomo-tmp/evals/$TS-$n"
    [ "$n" -lt 100 ] || refuse "cannot create a results dir under tomo-tmp/evals/"
done

set -- plugin eval "$PLUGIN" \
    --ablation none --threshold 1.0 --runs "${RUNS:-3}" -j 2 \
    --no-publish --trust-plugin --scaffold --allow-tools Bash \
    --model "$MODEL" --max-cost-usd "$MAX_COST" \
    --output-dir "$OUT" --json "$OUT/aggregate-result.json" --report "$OUT/report.html"
[ -n "$CASE_GLOB" ] && set -- "$@" --case "$CASE_GLOB"
$KEEP_TEMP && set -- "$@" --keep-temp

PHASE=run
CLI_RC=0
(cd "$WORK" && "$CLAUDE_BIN" "$@") >&2 || CLI_RC=$?

tree_state > "$WORK/tree.after"

not_graded() {
    DELIBERATE=true
    line="NOT GRADED · $* · claude $CLAUDE_VERSION · tree $TREE · $OUT"
    echo "$line" >&3
    echo "$line" > "$OUT/verdict.txt"
    exit 2
}

if ! cmp -s "$WORK/tree.before" "$WORK/tree.after"; then
    changed="$({ diff "$WORK/tree.before" "$WORK/tree.after" || true; } | sed -n -e '/^[<>] status /d' -e 's/^[<>] [^ ]* //p' | sort -u | tr '\n' ' ')"
    not_graded "tree changed during run: ${changed% }"
fi

case "$CLI_RC" in
    0|1|2) ;;
    130|143) not_graded "interrupted (claude exit $CLI_RC)" ;;
    *) not_graded "claude exited $CLI_RC" ;;
esac

set -- "$OUT/aggregate-result.json" --tree "$TREE"
[ -n "$CASE_GLOB" ] && set -- "$@" --partial-suite
[ -n "$MUTATION" ] && set -- "$@" --mutation "$MUTATION"
[ -n "$REV" ] && set -- "$@" --rev "$REV"

VERDICT_RC=0
VERDICT_LINE="$(python3 "$VERDICT_PY" "$@")" || VERDICT_RC=$?

if [ "$VERDICT_RC" -eq 0 ] && [ "$CLI_RC" -ne 0 ]; then
    not_graded "claude exited $CLI_RC but the result reads GREEN"
fi
case "$VERDICT_RC" in
    0|1|2) [ -n "$VERDICT_LINE" ] || not_graded "verdict script failed (exit $VERDICT_RC, empty verdict)" ;;
    *) not_graded "verdict script failed (exit $VERDICT_RC)" ;;
esac
echo "$VERDICT_LINE" >&3
DELIBERATE=true
exit "$VERDICT_RC"
