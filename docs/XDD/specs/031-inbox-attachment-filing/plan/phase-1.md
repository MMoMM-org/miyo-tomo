---
title: "Phase 1: Detection and resolution core"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Detection and resolution core

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples; "Embed extraction — why a new matcher is needed"]`
- `[ref: SDD/Implementation Examples; "Resolution — traced walkthrough"]` — the five-file inbox table with all four outcomes
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-2]`
- `[ref: PRD/Feature 1]`, `[ref: PRD/Feature 2]`, `[ref: PRD/Detailed Feature Specifications; business rules 1-4, 10]`
- Source to read: `tomo/scripts/lib/render_actions.py:59-100` (`_KNOWN_FILE_EXTENSIONS`, `_ensure_md_extension`), `tomo/scripts/topic-extract.py:308-325` (`_strip_link_target`)

**Key Decisions**:
- **ADR-1** — resolution is a basename lookup against a per-run index of the inbox subtree. Ambiguity is an outcome, not an error to paper over.
- **ADR-2** — this is a pure library. No Kado import, no agent involvement. The caller supplies the file list.

**Dependencies**: none. This phase is self-contained and blocks Phase 5.

---

## Tasks

Establishes the detection and resolution capability as a pure, fully unit-testable library. Nothing in this phase touches the pipeline.

- [ ] **T1.1 Embed extraction** `[activity: domain-modeling]`

  1. **Prime**: Read the extraction example `[ref: SDD/Implementation Examples]` and the classifier at `tomo/scripts/lib/render_actions.py:59-66`. Note that the frozenset contains `md` — the test is two-step, not a membership check.
  2. **Test** (RED):
     - `![[karte.jpg]]` → `["karte.jpg"]` `[ref: PRD/AC-F1.1]`
     - `[[karte.jpg]]` (plain link, no bang) → `[]` `[ref: PRD/AC-F1.3]`
     - `![[Some Note]]` (no extension) → `[]` `[ref: PRD/AC-F1.2]`
     - `![[Note.md]]` → `[]` — the two-step classifier; a membership check would wrongly return it
     - `![[Board.canvas]]` and `![[Data.base]]` → `[]`
     - `![[karte.jpg|Karte]]` (alias) → `["karte.jpg"]`
     - `![[karte.jpg#section]]` (anchor) → `["karte.jpg"]`
     - `![[Images/karte.jpg]]` (path-qualified) → `["Images/karte.jpg"]` — path **preserved**, unlike `_strip_link_target`
     - same embed twice → one entry, document order `[ref: PRD/AC-F1.4]`
     - empty body / no embeds → `[]` `[ref: PRD/AC-F1.5]`
  3. **Implement**: Create `tomo/scripts/lib/attachment_index.py` with `extract_attachment_embeds(body) -> list[str]`, `_is_attachment_target`, `_strip_alias_and_anchor`. The regex captures the leading bang: `r"(!)?\[\[([^\[\]]+)\]\]"`.
  4. **Validate**: `./venv/bin/python -m pytest tests/test_attachment_index.py -q`; `ruff` clean.
  5. **Success**:
     - [ ] Plain links are never returned `[ref: PRD/AC-F1.3]`
     - [ ] Note extensions are never returned, including `.md` which IS in the frozenset `[ref: SDD/Implementation Examples]`
     - [ ] A path-qualified target keeps its path `[ref: PRD/AC-F2.2]`

- [ ] **T1.2 Inbox file index** `[activity: domain-modeling]`

  1. **Prime**: Read the traced walkthrough's index table `[ref: SDD/Implementation Examples]`. The index maps basename → list of paths, so collisions are representable rather than lost.
  2. **Test** (RED):
     - a flat listDir result indexes each file under its basename
     - two files sharing a basename in different folders produce one key with two paths
     - folder entries (`type: "folder"`) are excluded
     - an empty or missing result yields an empty index (fail-open, `[ref: SDD/Cross-Cutting Concepts; "Fail open, never guess"]`)
     - `.md` files are indexed too — the index describes the inbox, filtering is the resolver's job
  3. **Implement**: `build_inbox_index(list_dir_result) -> dict[str, list[str]]` in the same module.
  4. **Validate**: unit tests pass; `ruff` clean.
  5. **Success**:
     - [ ] Collisions are preserved as multiple paths, never collapsed `[ref: PRD/Business rule 4]`
     - [ ] An empty index is a valid state, not an exception `[ref: PRD/Business rule 10]`

- [ ] **T1.3 Embed resolution** `[activity: domain-modeling]`

  1. **Prime**: Read the traced walkthrough in full `[ref: SDD/Implementation Examples]`. Four outcomes, four rows.
  2. **Test** (RED) — reproduce the SDD's five-file inbox verbatim as the fixture:
     - `![[prag-karte.jpg]]` → resolved to `100 Inbox/Images/prag-karte.jpg` — **the sibling assumption would fail here** `[ref: PRD/AC-F2.1]`
     - `![[karte.jpg]]` with two index hits → `ambiguous`, no path `[ref: PRD/AC-F2.4]`
     - `![[Images/karte.jpg]]` → resolved verbatim after index-membership check `[ref: PRD/AC-F2.2]`
     - target absent from the index → `unresolved`, no path `[ref: PRD/AC-F2.3]`
     - a path-qualified target NOT in the index → `unresolved`, never fabricated
     - empty index → every target `unresolved`
     - case-differing basename → `unresolved`, never a wrong file
  3. **Implement**: `resolve_attachments(embed_targets, index) -> list[AttachmentRef]` returning `{embed_target, resolved_path, status}` with status in `resolved | unresolved | ambiguous`.
  4. **Validate**: unit tests pass; `ruff` clean.
  5. **Success**:
     - [ ] No returned path is absent from the index — fabrication is impossible by construction `[ref: PRD/Quality: no fabrication]`
     - [ ] Ambiguity yields no action and is distinguishable from absence `[ref: PRD/Business rule 4]`
     - [ ] Resolution is O(1) per embed `[ref: SDD/Quality Requirements; Cost]`

- [ ] **T1.4 WHY-layer documentation** `[activity: documentation]` `[parallel: true]`

  1. **Prime**: Read the repo rule on `docs/tomo/<mirrored-path>.md` in `CLAUDE.md`.
  2. **Test**: n/a — documentation deliverable.
  3. **Implement**: Create `docs/tomo/scripts/lib/attachment_index.md` recording: why a tenth wikilink regex was necessary (the nine existing ones do not capture the bang); why the classifier is two-step (`md` is in the frozenset); why path-qualified targets keep their path (unlike `_strip_link_target`); why ambiguity is an outcome rather than a best-guess.
  4. **Validate**: every rationale in the runtime file's comments has a counterpart here.
  5. **Success**: `[ref: CLAUDE.md; WHY-persistence layer rule]`

- [ ] **T1.5 Phase Validation** `[activity: validate]`

  - Run all Phase 1 tests. Confirm the traced walkthrough's four outcomes are each covered by a named test. `ruff` clean. No Kado import anywhere in `attachment_index.py` — grep to prove it.
