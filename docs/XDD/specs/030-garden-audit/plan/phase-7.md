---
title: "Phase 7: Target Suggestions (second-pass opt-in) for dead_link + broken_up"
status: implemented (live pick-validation deferred to release)
version: "1.0"
phase: 7
---

# Phase 7: Target Suggestions (second-pass opt-in)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

garden-audit lets the user *type* a `Replace with:` (dead_link) / `Repoint to:` (broken_up) target
but never *suggests* one. This phase adds on-demand candidate suggestions, computed only for findings
the user explicitly opts in — so it scales to the hundreds of findings a real scan produces without
bloating the report or the scan cost.

**Specification References**:
- `[ref: PRD/Feature 3 — approve-and-apply]` (this extends the fixable-finding UX)
- `[ref: lib/orphan_link.py]` — existing topic-overlap MOC scorer (reused for broken_up repoint)
- `[ref: SDD/ADR-5 — check→action]`, `[ref: SDD/ADR-1 — Approved gate]`

**Key Decisions** (confirmed by user 2026-07-20):
- **D1 — Suggest is a SEPARATE per-finding opt-in, decoupled from Apply.** Each fixable
  `dead_link` / `broken_up` finding renders an extra `- [ ] Suggest targets` box, independent of
  `- [x] Apply`. Apply = "I'll fix this (I'll type the target)"; Suggest = "compute candidates for me".
  Ticking Apply does NOT trigger suggestion computation.
- **D2 — candidates computed ONLY on a second `--suggest` invocation, only for Suggest-ticked
  findings.** A real scan produces hundreds of findings; fuzzy-matching every dead target against the
  whole vault on every scan violates the perf constitution and bloats the report. Pass-1 Suggest opt-in
  costs nothing (a rendered checkbox); the `/garden-audit --suggest` re-invocation (mirrors
  `--configure`) reads the report + wire, computes candidates for opted-in findings, and rewrites those
  blocks in place with a pick list.
- **D3 — candidate sources:** `dead_link` → `difflib` (stdlib, no new dep) stem fuzzy-match of the dead
  target against all cache note stems, top-3 above cutoff. `broken_up` → `orphan_link` topic-overlap
  (the note as pseudo-orphan) MERGED with stem-similarity of the broken target against MOC stems (a
  mistyped MOC), top-3.
- **D4 — pick via sub-checkboxes**, mirroring how `moc-proposal` renders MOC selection. The parser reads
  a ticked suggestion sub-checkbox as the Replace/Repoint value; a value the user typed directly into
  the field OVERRIDES a ticked suggestion.

**Dependencies**: Phases 1-5 (the working apply path + the render/parser two-artifact split + the
`Replace with:` / `Repoint to:` fields this feeds). Independent of Phase 6.

**Must Not Touch**: the suggestions `build_actions` hot path; the Pass-1 scan cost (Suggest opt-in adds
only a static checkbox — no per-finding computation in Pass 1).

---

## Tasks

- [x] **T7.1 Candidate computation** `[activity: backend]` `[ref: lib/orphan_link.py]`

  1. Prime: read `lib/orphan_link.py` (`_score_against_mocs`, `LINK_THRESHOLD`, `TOP_N`) and the cache
     entry shape (path/stem/kind/topics).
  2. Test: `dead_link` — a dead target `"Ohne Tipfehler"` against stems including `"OhneTippfehler"`
     returns it as the top candidate with a score; below-cutoff noise is excluded; empty on no match.
     `broken_up` — a note whose broken up-target is a near-miss MOC stem returns that MOC; a note with
     strong topic overlap to a differently-named MOC also returns it; merged + deduped + top-3.
  3. Implement: new `tomo/scripts/lib/target_suggest.py` — `suggest_dead_link_targets(dead_target,
     stems, *, cutoff, top_n)` via `difflib.get_close_matches` / `SequenceMatcher`;
     `suggest_repoint_mocs(note_entry, moc_entries, broken_target, *, top_n)` reusing
     `orphan_link._score_against_mocs` + a stem-similarity pass, merged by score DESC.
  4. Validate: unit tests green; deterministic ordering (stable ties).
  - Success: both functions return `[{target, score}]` sorted DESC, capped, threshold-gated.

- [x] **T7.2 Suggest opt-in render + `--suggest` enrichment** `[activity: backend]`
      `[ref: garden-audit-render.py]`

  1. Prime: read the current per-finding render + the `--configure` re-invocation pattern.
  2. Test: Pass-1 render emits `- [ ] Suggest targets` for every fixable `dead_link`/`broken_up`
     (NOT for advisory, NOT for unparented/orphan which already carry candidates). `--suggest` mode:
     given a report with a Suggest-ticked finding + its wire, the finding's block is rewritten with a
     `Pick one:` sub-checkbox list from T7.1; un-ticked Suggest findings are untouched; the Approved
     gate + other findings are preserved byte-for-byte.
  3. Implement: render the opt-in box; add a `--suggest` code path that loads report + wire + cache,
     computes candidates for Suggest-ticked findings, and re-renders those blocks with pick
     sub-checkboxes (`- [ ] [[Candidate]] (0.92)`).
  4. Validate: round-trips with T7.3.
  - Success: Pass-1 cost unchanged (static box only); enrichment touches only opted-in findings.

- [x] **T7.3 Parser: read Suggest opt-in + ticked pick** `[activity: backend]`
      `[ref: garden-audit-parser.py]`

  1. Prime: read `parse_decision_map` + the Repoint/Replace field parse.
  2. Test: a finding with a ticked `- [x] [[Candidate]]` sub-checkbox and an EMPTY `Replace with:` →
     confirmed_item uses the ticked candidate; a finding with BOTH a typed field value AND a ticked
     candidate → the typed value wins; no tick + empty field → removal (unchanged). `--suggest` detects
     Suggest-ticked findings for T7.2.
  3. Implement: extend the decision map to read the Suggest opt-in and the ticked pick sub-checkbox;
     precedence: typed field > ticked pick > empty(removal).
  4. Validate: round-trip render→parse for both check types.
  - Success: pick selection flows into the same `garden_action` discrimination as a typed value.

- [x] **T7.4 CLI + agent wiring** `[activity: integration]` `[ref: garden-auditor.md]`

  1. Prime: read the `--configure` wizard wiring in `garden-auditor.md` + `garden-audit.py` argparse.
  2. Test: `/garden-audit --suggest` (or the agent's `suggest` mode) reads the in-vault report + wire,
     runs T7.2 enrichment, and re-uploads the report via `kado-write-file`. No new external surface.
  3. Implement: `--suggest` mode in `garden-audit.py`/the agent; the command doc + `garden-auditor.md`
     branch; STRICT block if runtime deviation observed.
  4. Validate: the mode is `/name`-invocable; documented in `tomo-help`.
  - Success: user flow = Pass-1 report → tick Suggest → `/garden-audit --suggest` → pick → tick
    Apply + Approved → `/inbox`.

- [x] **T7.5 Requirements delta + docs** `[activity: docs]` (live validation: deferred — no live
      Kado in this build environment; run on the test vault before release)

  1. [x] Updated `requirements.md` (Feature 3 — Suggest opt-in + candidate sources + pick precedence;
     Could-Have preamble notes Phase 7 shipped) and `solution.md` (D1-D4 decision block).
  2. [x] `docs/tomo/` mirrors: `lib/target_suggest.md`, `garden-audit-suggest.md`, `kado-read-file.md`;
     Suggest/pick branches added to `garden-audit-render.md` + `garden-audit-parser.md`.
  3. [ ] Live-validate on the test vault: a real mistyped dead link surfaces its correct target as the
     top pick. **Deferred** — requires a live Kado + populated cache; run at release.
  - Success: spec reflects the shipped feature (done); live pick validation pending at release.

---

## Phase 7 extension — live-report refinements (user feedback, 2026-07-21)

Three refinements from a live garden-audit report, extending Phase 7:

- [x] **Integrity "in:" headers.** `broken_up`/`dead_link` headers read `<label> in: [[note]]` (the
  note is the container); structure/advisory keep `<label>: [[note]]`. `_render_finding` branches on
  `tier == "integrity"`.
- [x] **Structure Suggest + "File under:" field.** unparented/orphan render the `- [ ] Suggest targets`
  opt-in and an editable `- **File under:** [[]]` field. New `target_suggest.suggest_file_under_mocs`
  computes topic-overlap MOC candidates surfacing top-N even BELOW the scan's `LINK_THRESHOLD`. Parser
  `RE_FILEUNDER_FIELD` → `parse_decision_map.file_under`; `file_note` target precedence typed File-under
  > ticked pick > scan candidate > skip, threaded into link_to_moc + add_relationship.
- [x] **"No suggestions found" note.** A Suggest-ticked finding with zero candidates gets an explicit
  note instead of an unchanged block (the F08 case), for every check type; idempotent.

Edited: `lib/target_suggest.py` (0.3.0), `garden-audit-render.py` (0.8.0), `garden-audit-parser.py`
(0.5.0) + tests + docs/tomo mirrors + requirements.md/solution.md.
