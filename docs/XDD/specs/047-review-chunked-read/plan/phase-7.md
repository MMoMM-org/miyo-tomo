---
title: "Phase 7: Privacy, deletion, measurement and documentation"
status: in_progress
version: "1.1"
phase: 7
---

# Phase 7: Privacy, deletion, measurement and documentation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-10; lines: 1217-1220]` — what `discard` removes, PRIVACY.md and setup.md content, the allowlist
- `[ref: SDD/Constraints; CON-3; lines: 100]` — no note text in stdout, stderr, cost records, `meta.json`, `manifest.json`, `condensed.json`
- `[ref: SDD/Quality Requirements/Security, Performance (guidance); lines: 1235, 1237]`
- `[ref: SDD/Directory Map/Documentation; lines: 461-483]`
- `[ref: SDD/Implementation Gotchas; lines: 1300-1301]` — the SDD map and WHY mirror tests
- `PRIVACY.md` "Where read content rests" (lines 140-168) and `tests/test_review_privacy_docs.py`

**Key Decisions**:
- PRIVACY.md names the new places where note content rests, that an interrupted run's material rests until the document is written, a drop, a start over or that period's next new read, the previous notes as a new source, the three models (haiku, sonnet, opus) and that each writes its own session transcript in the container home; `docs/setup.md` names the models too (F7-AC2, F7-AC3).
- `manifest.json` and `condensed.json` stay under the leak guard; content files are on the allowlist only while a stage lives (ADR-10).
- F8-AC1 is owned by `scripts/tomo-session-stats.py`; it is extended only where a required field is missing, as a recorded deviation (it is not in the SDD file table).

**Dependencies**: Phase 6. T7.1 ∥ T7.2 ∥ T7.3 ∥ T7.4 (files listed per task do not overlap).

---

## Tasks

Makes the privacy contract and the user documentation match the new flow, and gives the live walk its per-step measurement.

- [ ] **T7.1 PRIVACY.md, setup, README, usage and backlog** `[activity: technical-writing]` `[parallel: true]`

  1. Prime: `PRIVACY.md` (140-168), `tests/test_review_privacy_docs.py`, `docs/setup.md` (~293), `README.md` (:25, :164 agents table, :174), `docs/usage.md`, `docs/XDD/backlog.md`, `tomo/config/vault-example.yaml` (review section) `[ref: SDD/ADR-10]` `[ref: SDD/Directory Map/Documentation; lines: 478-482]`
  2. Test: `test_review_privacy_docs.py` pins the new sentences — every stage file holding content is named, the deletion moments (write, Pass 1 abort, drop, new read), an interrupted run's rest time and that a Kado stop leaves nothing (F7-AC2), the previous notes as a read source, the three models by name, their own transcripts in the container home (F7-AC3); `docs/setup.md` names the three models; the old `read.json` sentences are gone.
  3. Implement: `PRIVACY.md`, `docs/setup.md`, `README.md` (every day read, previous reviews followed up, three agents in the agents table; references #270), `docs/usage.md` (what the carried marks mean — Could Have, short), `docs/XDD/backlog.md` (parked: a further condensing level, a setup marker for intentions, an age counter, non-note embeds), `tomo/config/vault-example.yaml` comment (previous notes use the existing folders and formats; version bump).
  4. Validate: `test_review_privacy_docs.py` green; ruff clean.
  5. Success: a user can see where review material rests, for how long, and which models see it `[ref: PRD/F7-AC2, F7-AC3]`

  - **Carry-over from T2.4 (2026-11-23):** `tests/test_046_t6_2_docs.py:11, 89-90` still pins `read-index.json` in PRIVACY.md's "where read content rests"; update that pin together with the PRIVACY.md rewrite.

- [ ] **T7.2 Leak guard and cleanup over the new steps** `[activity: testing]` `[parallel: true]`

  1. Prime: `tests/test_review_privacy.py` (leak guard, tmp allowlist ~212), `tests/test_review_e2e_cleanup.py`, `tests/review_privacy_fixture.py` (sentinel texts) `[ref: SDD/CON-3; ADR-10]` `[ref: SDD/Quality Requirements/Security; lines: 1237]`
  2. Test: the leak guard runs every review script incl. `review-digest.py` (`plan`, `check`, each refusal and stop) and `review-read.py --measure` and finds no sentinel text in stdout, stderr, `manifest.json`, `condensed.json`, `meta.json` or a cost record (F7-AC4); the allowlist lists `days/`, `growth/`, `children/`, `previous/`, `context*.json`, `weeks.json`, `digests/`, `carryover.json`, `proposals.json` and nothing else; `test_review_e2e_cleanup.py` shows 0 content files after write, after Pass 1 abort and after drop, for week, month and quarter (F7-AC1 end to end); an agent prompt built from `plan` holds no sentinel text.
  3. Implement: tests only (a production leak found here becomes a fix with its RED test first).
  4. Validate: tests green; ruff clean.
  5. Success: no note text reaches Tomo's records and no material outlives the document `[ref: PRD/F7-AC4; F7-AC1]`

- [x] **T7.3 Cost, time and peak size per step (`scripts/tomo-session-stats.py`)** `[activity: performance]` `[parallel: true]`

  1. Prime: `scripts/tomo-session-stats.py` (subagent stats, peak context, Sonnet default prices), `scripts/tomo-token-usage.py` (PRICE table: opus $15/$75, sonnet, haiku), `tests/test_tomo_session_stats.py` `[ref: SDD/Quality Requirements/Performance (guidance); lines: 1235]` `[ref: PRD/F8-AC1]`
  2. Test: on a synthetic transcript with a main session and one subagent per review agent: the report lists per step (main session, each subagent) cost at the per-model rates of `tomo-token-usage.py`, wall time (first to last timestamp) and peak context, with counts only and no message text; an unknown model falls back to the default price and says so.
  3. Implement: verify first; extend only the missing fields (per-model pricing per subagent, per-step time), recorded as a deviation in the SDD component table (`scripts/tomo-session-stats.py` MODIFY) with the owner told; version bump.
  4. Validate: `test_tomo_session_stats.py` green; ruff clean.
  5. Success: a live run shows where cost and time go, per step `[ref: PRD/F8-AC1]`

- [x] **T7.4 Directory Map and WHY mirror sweep** `[activity: technical-writing]` `[parallel: true]` `[model: routine]`

  1. Prime: `tests/test_review_sdd_map.py` (T1.1 extension), `tests/test_review_why_docs.py`, SDD Directory Map (429-505), `docs/tomo/scripts/**`, `docs/tomo/dot_claude/**` `[ref: SDD/Implementation Gotchas; lines: 1300-1301]`
  2. Test: every review file that exists is named in spec 045's, 046's or 047's map; no file the 047 map marks DELETE exists (`review_read_parts.py`, its test, its mirror); every review script, lib and agent has a `docs/tomo` mirror; every `review-digest.py` subcommand appears in the skill's WHY doc; the untruncated `rg` listing of `tomo/scripts/lib/review_*.py` and `tomo/scripts/review-*.py` matches the mirror list one to one.
  3. Implement: missing mirrors filled from the code's docstrings and the SDD; mirror cross-links updated (`review_period.md`, `review_doc.md`, `review_sections.md`, `review_day.md`, `review_children.md`, `review_doc_parse.md`); test updates only where a rule changed by design.
  4. Validate: both tests green; ruff clean.
  5. Success: the map and the WHY layer cover exactly the files that exist `[ref: SDD/Directory Map]`

  - **Carry-over from the T2.4 review (2026-11-23):** `docs/tomo/dot_claude/skills/periodic-review.md` (~553, ~597) still describes the removed "quarter part → read-invalid" mechanism; `docs/tomo/scripts/review-read.md` should say that a stored read discarded and then stopped by Kado leaves no stage and reports no `discarded` key, and that `--fresh` over an unreadable manifest reports `stage-invalid`.

  - **Carry-over from T4.3 (2026-11-23):** `tests/review_cli_contract.py` `REVIEW_SCRIPTS` (and its `SCRIPT_NAME` regex) is hand-listed and leaves out `review-digest.py`, so the CLI contract of the WHY docs and the skill does not cover it; add it (better: derive the list from `tomo/scripts/review-*.py`) and name its subcommands/options in `docs/tomo/dot_claude/skills/periodic-review.md`.

- [ ] **T7.5 Phase Validation** `[activity: validate]`

  - Full suite in ONE invocation — GREEN; ruff clean. Trace F7-AC1 … F7-AC5 and F8-AC1 to node ids. Read PRIVACY.md and setup.md once against ADR-10's list. No eval-gated file changed.
