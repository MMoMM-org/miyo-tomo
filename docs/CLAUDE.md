# docs/ — Documentation Rules

## When to update what
- New learning → run /memory-add (not manual file edits)
- Significant architectural decision → record in `docs/XDD/reference/` (tier-1/tier-2/tier-3) or ADR
- New major feature → update README + relevant docs/ + `docs/XDD/specs/<NNN>-<slug>/`
- Post-MVP features and doc debt → `docs/XDD/backlog.md`

## XDD Structure
- `docs/XDD/specs/` — implementation specs (PRD → SDD → plan/phase-N.md)
- `docs/XDD/reference/` — architecture reference (tier-1 high-level, tier-2 mid, tier-3 detailed)
- `docs/XDD/backlog.md` — open items
- `docs/XDD/README.md` — consolidated doc index

## Critical Documentation Pattern
Always add significant new docs to the Critical Documentation section in `docs/ai/memory/memory.md`.
