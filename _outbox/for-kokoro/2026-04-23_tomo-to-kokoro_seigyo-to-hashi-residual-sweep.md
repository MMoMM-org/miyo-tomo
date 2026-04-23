---
from: tomo
to: kokoro
date: 2026-04-23
topic: Residual Seigyo → Tomo Hashi sweep across tier-2 + roadmap — arch-doc surface now consistent
status: pending
priority: normal
requires_action: false
---

# Residual Seigyo → Tomo Hashi sweep — tier-2 + roadmap/backlog

Follow-up to merge `962110a`. The first pass through the XDD tiers
left several stale **Seigyo-as-executor** references in tier-2 and the
roadmap; sweeping them now while the Hashi charter context (ADR-009) is
fresh. Heads-up handoff so your architecture picture doesn't show
Seigyo where Tomo Hashi now lives.

Implementation commit: `df375fa` on `main` (merged via `ca2b205`).

## Tier-2 updates

- `workflows/daily-note.md` §Apply Phase — "Seigyo executes … via
  locked scripts" rewritten to: Tomo Hashi applies via the Obsidian
  Plugin API, using the `update_tracker` / `update_log_entry` /
  `update_log_link` action kinds documented in
  `docs/instructions-json.md`.
- `workflows/inbox-processing.md` — three residual mentions rewritten:
  §3 two-pass model (dual-vetting pattern Hashi inherits), §3 bullet
  on architectural consistency, §flow-diagram step-6 caption, and the
  §4 executor-column table row.
- `components/template-system.md` §Post-MVP — template write path now
  reads `instructions.json` via Hashi, not locked scripts via Seigyo.
- `components/universal-pkm-concepts.md` state table — `active`
  trigger row now says "Tomo Hashi via Obsidian Plugin API".

## Roadmap / backlog dual-naming cleanup

- `docs/XDD/roadmap.md` F-01 — was "Seigyo / Tomo Hashi execution
  engine (locked scripts)", now Tomo Hashi only with a historical note
  on the rename.
- `docs/XDD/backlog.md` F-01 — same rewrite.
- `tomo/scripts/instructions-dryrun.py` header — "Tomo Hashi / Seigyo
  F-01" → "Tomo Hashi, backlog F-01". Version bumped `0.2.0 → 0.2.1`.

## Intentionally left alone (historical)

These keep "Seigyo" on purpose — rewriting them would revise history:

- `docs/XDD/specs/006-spec-consolidation/*`,
  `docs/XDD/specs/007-*/README.md` — past-tense spec directories with
  decision logs.
- Two tier-3 "formerly Seigyo in pre-2026-04-20 drafts" annotations in
  `instruction-set-apply.md` and `instruction-set-cleanup.md`.
- Tier-1 §7 "Note (2026-04-23)" aside that explains the rename.

## Why surface this to Kokoro

Tier-2 is part of the shared arch surface. If you're drafting an ADR
superseder or a cross-repo doc that cites Tomo's apply-phase executor,
current-main wording now consistently says **Tomo Hashi via Obsidian
Plugin API** — no more dual-naming. Flag if any Kokoro-side doc still
points at Seigyo in the apply-phase role and I'll take it.

## Refs

- ADR-009 (Hashi charter, Kokoro)
- Previous rename sweep commit: `30fb8d9` (tier-1 + most tier-3)
- This sweep: `df375fa` (tier-2 + roadmap + backlog + dryrun header)
