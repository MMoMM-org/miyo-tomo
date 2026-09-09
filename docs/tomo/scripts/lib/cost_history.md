# WHY: lib/cost_history.py

> Rationale for decisions in `tomo/scripts/lib/cost_history.py`.
> The append-only record of what each `/inbox` run cost in Kado round trips.
> Only non-obvious decisions are recorded here.

## WHY a History at All (spec 034 F9, T6.1)

ADR-3's claim is that recursive discovery made triage *cheaper* — the base cost
fell from three Kado calls to two. F9 asks for the actual figure to be recorded
so the claim stays checkable after the spec closes, and so a later reader can
tell a pipeline regression (the base cost moved) from a busy run (more items,
more destination folders).

A history whose source is a constant records the intent, not the behaviour.
`_count_kado_calls` used to return `2 + 7 + …`, and the Phase-3 gate proved the
consequence rather than arguing it: with a second base listing reintroduced by
hand, the fake client recorded **3** base calls while the estimator still
printed `kado_calls=9`. Every figure in an entry is therefore read off the
client's own round-trip counter (`kado_client.observed_call_count`), never
declared. See `docs/tomo/scripts/inbox-triage.md` for the checkpoint mechanics.

## WHY One Shared Helper for Two Processes

The entry is appended from two processes — `inbox-triage.py` for the three
actions that terminate there, `suggestions-reducer.py` for the two that reach
it. Copying the assembly is how the two drift apart, and the item's own success
criterion is *"a history accumulates without anyone remembering to record it"*.
`build_entry` and `record_run` are the one place the record's shape is decided.

Shaped on `lib/squelch_persist.py`: a `lib/` module with a public append
function, stdlib-only. Both callers reach `lib/` identically (`SCRIPT_DIR` +
`sys.path.insert`), so there is no import split to design around.

## WHY the Folder Fields Are Absent, Not Zero

`folder_listing_calls` and `distinct_destination_folders` measure the reducer's
destination-folder listings (T5.2). On `idle`, `synthesize` and `transcribe`
the reducer never runs, so there is no measurement to report — and a zero would
assert one that nobody took, which is exactly the reading a later cost
comparison would get wrong. `build_entry` omits both when they are None.

They are separate from `base_kado_calls` for the same reason: a single number
mixing a fixed pipeline cost with a content-scaling one tells a reader nothing
about either. Precedent — the I38 daily-note existence probe has always been a
per-item, content-scaling Kado cost and has never been counted as a base call.

## WHY the Entry Cannot Be Written by inbox-triage.py for Every Action

Triage writes `routing-plan.json`, and only *then* does the skill invoke
`suggestions-reducer.py`. The folder counts do not exist when triage finishes.
So for `suggest` and `fan-resolve` the entry is appended by the **reducer**,
which reads triage's own metrics back out of the routing plan. The three
actions that terminate inside triage still spend base and byFrontmatter calls,
and a history that omits them cannot show what idling costs — so triage records
those itself, guarded by `DOWNSTREAM_COST_ENTRY_ACTIONS`.

## WHY Not a Script Invoked From a SKILL.md Step

The first cut put the two reducer paths in `record-run-cost.py`, called from a
step in each skill's markdown. That step is executed by an LLM, and **no test
can see a markdown instruction** — the entry for the two highest-traffic
actions would have depended on the runtime remembering a line, which is
precisely what "without anyone remembering" rules out. The reducer already runs
on both paths as a Python process and already holds the folder counts, so the
step was removed and the script retired (`RETIRED_SCRIPTS` in
`scripts/update-tomo.sh` clears it from any instance that received it).

Surfaced by the implementer's own unverifiable-assumption report rather than by
a failing test — because there was no test that could fail.

## WHY `action` Is on the Entry

The SDD's original field list did not name it. Without it every entry with
absent folder fields is indistinguishable from an entry whose downstream step
was skipped, and an idle run's two base calls read as a suspiciously cheap
Pass 1. The SDD was amended to carry it.

## WHY an Unwritable History Never Fails the Run

`[ref: SDD/Error Handling]` — measurement must never fail a run. `append_entry`
catches `OSError` (an occupied or read-only `state/`), warns to stderr and
returns False. The alternative trades a working triage for a bookkeeping
detail.

## WHY `state/`, cwd-Relative

`mark-captured.py`'s `state/moc-squelch.json` default is the precedent: a small
persistent registry in the instance state directory, addressed cwd-relative
because the instance runtime runs from the instance root. It also satisfies the
requirement that clearing `tomo-tmp/` leaves earlier entries intact — the
history is deliberately not a working-directory artefact.

The cwd-relative default is a trap for host tests, which run from the repo
root: an entry point driven without redirecting the path appends into the repo
working tree. `tests/conftest.py` carries an autouse guard that fails the
offending test by name rather than leaving the directory for `git status` to
find.
