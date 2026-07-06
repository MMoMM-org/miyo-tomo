# WHY: suggest-handling

> Rationale for decisions in `tomo/dot_claude/skills/suggest-handling/SKILL.md`.

## Clear inbox-state.jsonl + items/ at the top of Common setup

WHY: `tomo-tmp/inbox-state.jsonl` is append-only and is never truncated
between runs (`state-update.py` opens it in mode `'a'`). The aggregation
stages (`suggestions-reducer.py`, `mark-captured.py`) now scope their work-list
to the current `run_id` (#116), which is the real fix for stale-run
re-ingestion. Wiping the working state at the start of the suggest sub-flow is
belt-and-suspenders: even if the `run_id` filter ever regresses, a fresh run
cannot inherit a prior run's `done` stems and re-emit fabricated proposals for
source notes that no longer exist.

WHY the reset lives here and not in `reset-tomo-tmp.sh --pass1`: the `--pass1`
mode also clears `tomo-tmp/routing-plan.json`, which this skill reads in step 1
(before Common setup). Running `--pass1` here would delete the routing plan the
skill just consumed. The reset is therefore narrowed to exactly the two
prior-run artefacts that leak — `inbox-state.jsonl` and `items/` — and runs
after the routing plan has been read.

## Emit `_suggestions.json` alongside `_suggestions.md` (ADR-026)

WHY: Kokoro ADR-026 charters a Hashi Suggestions Editor that needs a
machine-readable sibling of the suggestions doc. Step 5 passes
`--json-output tomo-tmp/suggestions-wire.json` to `suggestions-render.py`, and
step 6 publishes it to the vault at the SAME `<YYYY-MM-DD_HHMM>` stem as the
`.md`. The markdown stays the baseline round-trip surface — Tomo never assumes
Hashi is installed.

WHY `kado-write-file.py` and not a raw `kado-write` note: the sibling is a JSON
file, and Kado's `operation=note` requires markdown (rejects non-`.md`). The
`file` op (base64) is the only correct write path; `kado-write-file.py` wraps
`kado_client.write_file` so the write is deterministic instead of asking the
model to base64-encode.

WHY the wire is a COMPLETE mirror of the review surface (not editable deltas):
Marcus's rule is "if Hashi edited the JSON, use ONLY the JSON; otherwise ONLY the
markdown — never a mix." Under that rule the changed JSON is the sole authority,
so anything the markdown lets the user decide must be carried in the JSON or it
would be silently dropped when a single field is edited. The wire therefore
mirrors: every note's full option set (title, template, location, tags,
decision, keep_source, delete_source, force_atomic, suppressed/worthiness,
candidate MOCs + anchors + source), proposed MOCs (with `M##` ids for
merge/rename as a graph op), daily-note updates, and tag-handler approvals. The
notes/proposed-MOCs are projected from the structured `item` the reducer now
persists; the daily + tag-handler sections are mirrored by parsing our OWN
freshly-rendered markdown with the parser's own section parsers (so the wire is
byte-faithful to the parse output — no second, divergent implementation).

WHY the change signal is a SHA-256 `emit_digest` over the editable payload:
tool-agnostic — Hashi need do nothing to preserve it (any semantic edit moves the
digest; a canonical re-serialization means reformatting alone does not). See
`docs/tomo/dot_claude/agents/synthesis-conductor.md` for the JSON-only Pass-2
read-back side.
