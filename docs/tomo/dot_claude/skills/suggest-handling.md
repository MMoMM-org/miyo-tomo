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
