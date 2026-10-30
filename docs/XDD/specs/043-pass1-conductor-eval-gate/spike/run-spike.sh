#!/bin/bash
# Spike 043: assemble a throwaway "tomo" plugin from the working tree, swap in
# the inbox-analyst stub, add two probe cases, and run them once each with
# `claude plugin eval` (--keep-temp, so the traces can be read afterwards).
# Run from a terminal, NOT from Claude Code's sandbox (EPERM). Cost cap $1.
# Output: tomo-tmp/spike043/ (gitignored).
set -e
SPIKE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(git -C "$SPIKE" rev-parse --show-toplevel)"
OUT="$REPO/tomo-tmp/spike043"
P="$OUT/plugin"
rm -rf "$OUT"
mkdir -p "$P/.claude-plugin" "$P/evals"
printf '{"name": "tomo"}\n' > "$P/.claude-plugin/plugin.json"
for d in agents skills commands; do cp -R "$REPO/tomo/dot_claude/$d" "$P/$d"; done
cp "$SPIKE/inbox-analyst.stub.md" "$P/agents/inbox-analyst.md"

cp -R "$SPIKE/pass1-suggest-probe" "$P/evals/pass1-suggest-probe"
cp -R "$REPO/evals/_lib" "$P/evals/_lib"
cp -R "$REPO/evals/upload-failure-reported" "$P/evals/report-only-probe"
sed -i '' -e 's/^name: .*/name: report-only-probe/' -e 's/^runs: .*/runs: 1/' "$P/evals/report-only-probe/case.yaml"
cp "$SPIKE"/report-only-probe/graders/*.md "$P/evals/report-only-probe/graders/"
chmod +x "$P"/evals/*/scaffold.sh

MODEL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["model"])' "$REPO/tomo/dot_claude/settings.json")"
cd "$OUT"
claude plugin eval "$P" \
  --ablation none --threshold 1.0 --runs 1 -j 2 \
  --no-publish --trust-plugin --scaffold --allow-tools Bash \
  --model "$MODEL" --max-cost-usd 1 --keep-temp \
  --output-dir "$OUT/results" --json "$OUT/results/aggregate-result.json" \
  --report "$OUT/results/report.html"
