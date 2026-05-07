# XDD 014 — MOC-creation skill (`/moc-propose`, `/moc-create`)

**Status:** PRD draft — 2026-05-07
**Current phase:** requirements.md (PRD)
**Backlog origin:** F-43 (Must)
**Roadmap position:** Track #1 in `docs/XDD/roadmap-obsidian-power.md`.
**Launch gate:** Satisfied 2026-05-07 (commit `053bc4e`).

## Problem in one paragraph

Tomo can propose MOCs only as a side-effect of `/inbox` runs (via F-34
accumulation, F-35 placeholder triggers, or per-item analyst
classification). There is no way for the user to *deliberately* organise
a topic-area: "I want a Boardgames MOC NOW for the 5 unclassified
notes I already have, regardless of inbox state." The pre-existing
primitives (`create_moc` action in the schema, `t_moc_tomo` template,
tier-3 new-MOC-proposal spec) are wired only into the inbox-analyst
emission path. Hand-crafting MOCs in Obsidian leads to convention drift
that downstream features (garden-audit F-44, weekly review F-45) will
have to handle.

## Solution in one paragraph

Two new commands. `/moc-propose <topic>` queries Kado for notes
relating to the topic, optionally seeds from F-34's accumulation
index, and writes a proposal artefact in suggestions-doc shape with
proposed MOC name, parent, sections, and child-note placement —
profile-aware (miyo Dewey vs LYT free thematic). After the user
approves the proposal in the doc, `/moc-create` parses the approved
artefact, emits `instructions.json` with one `create_moc` action
plus `add_relationship` actions for bidirectional links on each
child, and Hashi materialises the result. Reuses existing schema
actions; reuses the suggestions-doc UI; reuses the Hashi executor.
No new MCP surface. New: a `moc-architect` agent (sonnet, classification
work) and `moc-propose.py` / `moc-render.py` scripts (deterministic
work). Reference-skill prereq: `obsidian-markdown` lazy-loaded.

## Files

- [requirements.md](requirements.md) — product requirements (PRD), draft
- solution.md — technical design (SDD), pending
- plan/phase-N.md — implementation plan, pending

## Tracking

- Backlog entry: `docs/XDD/backlog.md` → F-43
- Roadmap: track #1 in `docs/XDD/roadmap-obsidian-power.md`
- Launch gate satisfied: 2026-05-07 (commit `053bc4e`)
- Branch when implementation starts: `feat/f-43-moc-creation-skill`
- Reference-skill prereq: import `obsidian-markdown` (aitmpl.com,
  reference-only, Kado-MCP-compatible per `decisions.md` 2026-05-06)
- Related specs: F-13 (`/scan-mocs`, will be superseded);
  F-34 (XDD 013, accumulation detection — complementary inbox-side
  trigger); F-35 (placeholder MOC trigger, shipped 2026-05-07);
  F-44 (garden-audit, depends on this primitive);
  F-45 (weekly review, soft prereq);
  F-46 (tag-audit, lower-priority follow-up)

## Open questions before SDD

See requirements.md §8 (OQ1–OQ8). Tentative leans noted; stakeholder
input required before SDD locks the surface.
