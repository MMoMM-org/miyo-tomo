---
from: tomo
to: kouzou
date: 2026-04-23
topic: stdout/stderr discipline — generalizable agent-prompt hardening for JSON-producing scripts
status: pending
priority: normal
requires_action: true
---

# Stdout/stderr discipline for JSON-producing scripts — generalizable agent-prompt pattern

A live failure in a Tomo Pass-2 run today surfaced a pattern worth promoting
into Kouzou's agent-authoring standards (or wherever shared Claude-Code
conventions live). Fix is prompt-level, not tool-level — applies to any
agent that drives a Python script whose stdout is JSON/YAML captured to
a file.

## What Changed

Tomo's `instruction-builder.md` and `inbox-orchestrator.md` now carry a
STRICT section forbidding `2>&1` on commands whose stdout is redirected
to a data file. Representative block (from `instruction-builder.md` v2.3.1):

> **NEVER append `2>&1` to any command whose stdout is captured to a file.**
> Tomo's Python scripts (parser, reducer, render, diff) routinely print
> status + warning lines to stderr by design. With `2>&1`, those lines
> land in the output file BEFORE the JSON blob, corrupting it. The script
> itself still exits 0 (it worked from its own perspective), so the
> failure surfaces opaquely on the next step's `json.load`.
>
> Correct form: `python3 script.py > out.json` — stderr flows to the
> Bash-tool output, which the session already sees.
>
> If stderr genuinely must be silenced (rare): `2>/dev/null`, never `2>&1`.

Full discussion in Tomo memory: `feedback_never_redirect_stderr_into_json.md`.

## Why

The failure mode is silent + confusing:
1. Agent LLM appends `2>&1` "for visibility" — reasonable intuition.
2. Script writes warnings to stderr (e.g. "force_atomic: 1 log entry
   has Force Atomic Note but no atomic proposal — resolve subflow will
   be triggered").
3. Warnings land at the top of the captured file, before the JSON body.
4. Script exits 0 — agent sees success, moves on.
5. Next step calls `json.load` → `Expecting value: line 1 column 1 (char 0)`.
6. The agent or user sees a JSON error with no hint that stdout was
   polluted upstream. Root cause takes minutes to find.

This is not a Tomo-specific issue — any MiYo agent that does
`python3 some-script.py > data.json` in a Bash tool call is a candidate.
The fix is always the same: don't add `2>&1`; let stderr flow to the
tool output.

## Impact on Kouzou

Suggestion: add this pattern to the Kouzou agent-authoring standards
under whichever section covers "script dispatch conventions" (likely
`~/Kouzou/standards/` or the Claude-Docker global-config equivalent).
Short enough to live as a single bullet under a "Bash tool hygiene"
heading:

> When capturing a script's stdout to a data file (`> file.json`,
> `> file.yaml`, `> file.md`), never append `2>&1`. Stderr carries
> status + warnings and would corrupt the captured data while the
> script still exits 0 — producing opaque `json.load` failures on the
> next step. Let stderr flow to the Bash-tool output unredirected. Use
> `2>/dev/null` only when stderr must be silenced.

A cross-reference to the memory file (or the underlying Tomo commit
`c72ba0d`) lets readers audit the original failure if they want the
detailed context.

## Action Required

- Decide where this belongs in Kouzou's standards (agent authoring,
  script dispatch, or a more general "Bash tool hygiene" section).
- Add the pattern (or link to this handoff) so other MiYo repos'
  agents inherit the guard.
- Close as `done` when incorporated; Tomo will archive.

## References

- Tomo commit: `c72ba0d fix(agents): forbid 2>&1 on stdout-captured script calls`
- Tomo memory: `feedback_never_redirect_stderr_into_json.md`
- Trigger incident: Tomo Pass-2 live run 2026-04-23, XDD-012 `suggestion-parser.py`
  invocation — parser output of `force_atomic: resolve subflow will be triggered`
  warning corrupted `parsed-suggestions.json` when the Bash call used `2>&1`.
