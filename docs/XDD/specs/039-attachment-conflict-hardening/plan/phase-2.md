---
title: "Phase 2: Refusal rules"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Refusal rules

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/F2]` — folder refusal, F2-AC1..AC3, F2-AC9
- `[ref: PRD/F5]` — #185, F5-AC1..AC4; F5-AC7 (`unsafe_sequence`)
- `[ref: SDD/ADR-5]` — `check_typed_folder`, its closed reason set
- `[ref: SDD/ADR-6]` — `breaks_link`
- `[ref: SDD/Interface Specifications K4]`
- `[ref: research.md/R1 §4, R2 §5 (measured folder table)]`

**Key Decisions**:
- Pure functions on strings, no I/O, no run state — the same rule for both read paths (038 ADR-5).
- **Refuse, never repair.** No `.strip()`, no normalisation on the returned value.
- Sentences live in the new `lib/refusal_sentences.py` (K16), not in `render_actions.py` (2877 lines). Each new module starts with a `# version:` header and a why-docstring, and gets its `docs/tomo/scripts/lib/*.md` WHY file in the same task.
- `FORBIDDEN_CHARS` and `sanitize_stem` are not touched; the link-breaking set is local to `typed_name_check.py`, so a derived title such as `C# Notizen` sanitises exactly as it does today.
- `breaks_link` applies to folders too: a folder becomes part of a qualified embed.

**Dependencies**: Phase 1 (T1.5 must be in, or the new reason renders as "blank").

---

## Tasks

Delivers every refusal the plan will need, fully tested, before any surface can produce a typed folder.

- [x] **T2.1 `breaks_link` and `unsafe_sequence` for typed names (#185)** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `typed_name_check.py` (0.1.3) `:30-80`; `obsidian_filename.py:32`; backlog `:2500-2572` `[ref: SDD/ADR-6]`
  2. Test: `" a.png"`, `"a.png "`, `"\ta.png"` → `breaks_link`; each of `#`, `^`, `[`, `]` anywhere → `breaks_link`; `"   "` still `blank`; `a/b.png` still `separator_present` (order of checks: blank → separator → edge whitespace (`breaks_link`) → `unsafe_sequence` → forbidden → `# ^ [ ]` (`breaks_link`) — `unsafe_sequence` precedes forbidden because `<` and `\x00` are forbidden characters; corrected at the Phase 2 drift check); `{{`, `<%`, `\x01` anywhere → `unsafe_sequence`, and a Pass 2 run fed such a typed name produces every other item and exits 0 — shown RED first against today's code, where it aborts with exit 2 (F5-AC7); `REFUSAL_REASONS` is exactly five (rename and re-pin `test_038_t3_1_*:235-247` `…closed_set_of_three`); the 038 padding-pinning test flips from accept to refuse; `sanitize_stem("C# Notizen")` unchanged; the sentence for `breaks_link` says the name would break the link and never "Obsidian does not allow"
  3. Implement: `typed_name_check.py` new local sets + checks; `lib/refusal_sentences.py` (K16) with the sentences, `_typed_name_refusal_reason` delegating to it
  4. Validate: T1.6's join test still green unchanged; ruff clean; docs `docs/tomo/scripts/lib/typed_name_check.md` "exactly three" → five
  5. Success: `[ref: PRD/F5-AC1]` `[ref: PRD/F5-AC2]` `[ref: PRD/F5-AC3]` `[ref: PRD/F5-AC4]` `[ref: PRD/F5-AC7]`

- [x] **T2.2 `check_typed_folder`** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: research.md R2 §5 (the measured `_asset_dest_join` / `_check_path_shape` table); `render_actions.py:182-203` `[ref: SDD/ADR-5]`
  2. Test: table-driven, one row per reason and at least one accepting row each side — `""`/`"  "` `blank`; `../x`, `a/../b`, `/abs`, `~/x`, `./a`, `a/./b`, `a\b`, `C:/x` `escapes_vault` (a `.` segment is a relative-path element, pinned here); `a//b` `empty_segment`; `" a"`, `"a /b"` `edge_whitespace`; `"a/"` `trailing_separator`; `a:b`, `a*b` `forbidden_character`; `a#b`, `C# Projekte`, `a[b` `breaks_link` (owner ruling 2026-10-12); `a/{{x}}`, `a<%b`, `a\x01b` `unsafe_sequence`; the inbox folder itself, a descendant, and a case-variant of it `inside_inbox`; accepted: `Atlas/290 Assets/296 Maps`, `Ä/ü ß`, a sibling whose name merely starts with the inbox name (`100 Inbox Archive` when the inbox is `100 Inbox`)
  3. Implement: `check_typed_folder(folder, *, inbox_path)` and `FOLDER_REFUSAL_REASONS`; one sentence per reason in `lib/refusal_sentences.py` (K16, used by T5.1)
  4. Validate: property — for every input `_check_path_shape` (`render_actions.py:182-203`, incl. `{{`/`<%` and `_CONTROL_CHARS_RE` at `:111`) rejects as a folder, `check_typed_folder` refuses too; ruff clean
  5. Success: `[ref: PRD/F2-AC1]` `[ref: PRD/F2-AC2]` `[ref: PRD/F2-AC3]` `[ref: PRD/F2-AC9]`; sentences for `[ref: PRD/F2-AC5]`

- [x] **T2.3 Phase 2 validation** `[activity: validate]`

  - Full suite green; ruff clean; no production call site uses `check_typed_folder` yet (grep) — it is wired in Phase 4; Pass 2 output byte-identical on the 038 baseline except for a typed name the 038 tests deliberately feed with padding or `# ^ [ ]`.
