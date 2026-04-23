---
from: tomo
to: kokoro
date: 2026-04-23
topic: XDD 012 + schema/layout updates — ADR candidates and stale arch-doc flags
status: pending
priority: normal
requires_action: true
---

# XDD 012 + schema/layout updates shipped — ADR candidates + arch-doc refresh

Four Tomo changes landed on `main` between 2026-04-21 and 2026-04-23 that
affect how the system is described in Kokoro's authoritative architecture
docs. Kokoro can decide which deserve ADRs and which are just doc-sync.

## What Changed

### 1. XDD 012 — Force Atomic Note Synthesis (shipped 2026-04-23)

New Pass-2 pattern introduced: when the user ticks `Force Atomic Note` on
a log entry whose inbox item had no analyst-proposed atomic section in
Pass 1, Pass 2 **halts** before rendering, dispatches `inbox-analyst`
with a new `force_atomic=true` input that bypasses Step 7's worthiness
gate, and writes a **companion** `<date>_suggestions-fan.md` to the
vault inbox. The user reviews + approves atomic proposals in the
companion doc; on the next `/inbox` run, `suggestion-parser.py --fan-resolve-file`
merges both docs by stem and renders instructions normally.

**Architectural novelty**: this is the first Tomo pipeline with a
cross-run, halt-and-produce-follow-up state. Proposal-first is preserved
(no silent synthesis) and the existing Approve-checkbox UI is reused
(no new controls). Cost envelope: ~$0.30 per FAN resolution vs. ~$33
for re-running full Pass 1.

Source: `docs/XDD/specs/012-force-atomic-synthesis/` (PRD + SDD + plan +
README).

### 2. `daily_log.date_sources` — config-driven date priority (shipped 2026-04-23)

`shared-ctx.schema.json` gained a new required field inside `daily_log`:
`date_sources: ["content", "frontmatter", "filename"]` (default order,
user-configurable via `tomo-daily-log-wizard`). Replaces the previously
hardcoded `filename > frontmatter > content` order in `inbox-analyst.md`
Step 8. Live trigger: user's note mentioned `30.03.` in content but
frontmatter had today's date → old order filed it wrong.

Also expanded auto-derived `date_formats` in `shared-ctx-builder.py` to
cover common German/European natural-language forms (`DD.MM.YYYY`,
`DD.MM.`, `D.M.YYYY`, `DD/MM/YYYY` etc.) so content-parsing actually
finds them.

Schema evolution — `schema_version` stays `"1"`, but the `daily_log`
object's `required` array extended.

### 3. Layout refactor (shipped 2026-04-22, merged 2026-04-23)

Repo split tightened:
- `scripts/` — user-facing scripts (install, update, backup, restore,
  token-usage). Called by the user from shell.
- `tomo/scripts/` — runtime scripts synced into the instance by
  `update-tomo.sh`. Called from agents via `python3 scripts/...` inside
  the container (where the instance's `scripts/` is `tomo/scripts/`).
- `tests/` — all test suites, `.py` + `.sh` + fixtures. Previously mixed
  into `scripts/`.

Driver: `test-phase1.sh` had been silently wiping the user's
`tomo-instance/` on any accidental run because it used the default
install path (the real one). Refactor fixed the cascade.

### 4. Seigyo → Tomo Hashi naming (in progress, Tomo side done 2026-04-23)

Per the 2026-04-20 decision, Tomo's tier-3 `instruction-set-apply.md`
and `instruction-set-cleanup.md` now name the Obsidian plugin as
**Tomo Hashi (友橋)** with a historical "(formerly Seigyo)" pointer.
`docs/instructions-json.md` is now the paired-contract doc for both
`.json` + `.md` companion artefacts (Tomo Hashi consumer-facing).

## Why

- XDD 012 closes the last known FAN-UX gap — users can now force atomic
  creation on sub-worthiness items without re-running full Pass 1.
- `date_sources` fixes a hidden-split bug where the wizard let users
  configure time-of-day priority but not day-of-day priority (see
  feedback_audit_sibling_concerns_on_config_driven.md for the lesson
  — worth an ADR pattern if Kokoro tracks anti-patterns).
- Layout refactor is defensive: prevents real-instance wipe via test
  run (test-phase1.sh rm -rf trap).
- Naming sweep is cleanup toward F-01 delivery (post-MVP execution plugin).

## Impact on Kokoro

Likely stale Kokoro arch docs (I don't have write access to verify — please audit):

- **`04-miyo-tomo.md` (or equivalent Tomo architecture doc):**
  - Scripts layout section: `scripts/` no longer holds runtime scripts.
  - Pass-2 flow section: Add Step 2.5 FAN Resolve Subflow branch.
  - Daily-log section: Add `date_sources` key alongside `time_extraction`.
  - Naming: "Seigyo" references should become "Tomo Hashi" (or keep
    historical pointers as Tomo's tier-3 did — up to you).

- **ADR log — three candidate entries:**
  - ADR: Force Atomic Note synthesis via companion resolve doc (XDD 012
    pattern — halt-and-produce-follow-up; first of its kind in Tomo).
  - ADR: Config-driven date-source priority replacing hardcoded order,
    with the wider principle "when making a key config-driven, audit
    sibling concerns of the same decision".
  - ADR (or ADR-update): scripts/ split user-facing vs runtime — may
    warrant its own entry if Kokoro tracks layout decisions.

## Action Required

- Audit the flagged Kokoro arch docs against the Tomo `main` state as
  of commit `301708f`.
- Decide ADR scope for the three candidates. If you write them, copy
  the driving evidence from Tomo's XDD-012 spec + shared-ctx.schema.json
  diff + layout-refactor commits so the ADRs are self-contained.
- No reply handoff needed — close this as `done` when your audit is
  complete; Tomo will archive.

## References

- XDD 012 spec: `docs/XDD/specs/012-force-atomic-synthesis/` (Tomo main)
- Schema diff: `tomo/schemas/shared-ctx.schema.json` — `daily_log.date_sources`
  added as required field
- Layout refactor commit: `c7446b5 refactor(layout): scripts/ holds only user scripts; runtime → tomo/scripts/; tests → tests/`
- Merge commit: `301708f merge: feat/inbox-tagging-fixes — inbox workflow hardening, voice, XDD 012`
- Related Tomo memory:
  - `feedback_audit_sibling_concerns_on_config_driven.md` — the lesson behind
    the date_sources migration
  - `feedback_never_redirect_stderr_into_json.md` — agent-prompt hardening
    pattern (also handed off to Kouzou separately)
  - `project_tomo_hashi_plugin.md` — 2026-04-20 naming decision
