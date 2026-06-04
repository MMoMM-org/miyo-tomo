---
from: tomo
to: kokoro
date: 2026-05-27
topic: "XDD 018 Agent Architecture Cleanup — key decisions for Kokoro architecture docs"
status: done
status_note: ADR-018 amended: source_* → sources[] array, 6-state triage documented. decisions.md memory updated.
priority: normal
requires_action: true
---

# XDD 018 — Agent Architecture Decisions

Spec 018 (agent architecture cleanup) shipped 2026-05-27. 194 commits on
`feat/018-inbox-routing-redesign`. Key architectural decisions that affect
cross-component docs and the Tomo architecture overview.

## Decisions

### 1. Skills own pipelines end-to-end — conductors are pure routers

Conductors (suggestion-conductor, synthesis-conductor) no longer contain
pipeline logic. Each pipeline mode is a self-contained skill:
- `suggest-handling/SKILL.md` — Pass 1 suggest (dispatch → reduce → render → write → mark)
- `force-atomic-handling/SKILL.md` — Pass 1 fan-resolve (dispatch → reduce → render → write)

The conductor reads the routing plan, branches on action, and defers to
the loaded skill. ~60 lines instead of ~200.

**Why:** When a skill is loaded, it takes over the execution context. Pipeline
steps in the agent spec after the skill-load point are never reached. Making
skills self-contained is the only reliable pattern.

### 2. Synthesis-conductor dispatched on Haiku (not impersonated on Sonnet)

synthesis-conductor v0.7.0 runs as a dispatched subagent on Haiku 4.5.
Previously it was impersonated by the parent session on Sonnet 4.6.

**Why:**
- Impersonation inherits the parent's full toolset — `tools: [Bash]` restriction was cosmetic
- Sonnet improvised (loaded template-render skill, read doc content, tried to create MOCs manually)
- Haiku follows literal scripts perfectly — zero improvisation
- 74% cost reduction ($0.24 vs $0.94)

**Architecture rule:** Agents that only call scripts and make zero decisions → dispatch on Haiku.
Agents that dispatch leaf subagents (need Agent tool) → impersonate on Sonnet.

### 3. MOC proposal parser as separate script

`moc-proposal-parser.py` v0.2.0 — dedicated parser for MOC proposal docs.
`suggestion-parser.py` handles suggestions/fan-resolve only. No code sharing
(completely different markdown structures).

`suggestion-parser.py` retains `parse_moc_proposal_doc()` for
`squelch_persist.py` (different output format, cluster-level data).

### 4. Tomo-side related:: aggregation (contract confirmed)

Per instructions-json.md §882-886: Tomo reads existing `related::` values
from the vault, merges with new links, and emits one `add_relationship`
action per target note with the combined `line`. Hashi always does replace.

No `mode` field on actions — the contract stays simple.

### 5. doc-frontmatter source_* → sources[] array

Shipped in 018-P1. `source_suggestions`, `source_moc_proposal` string keys
replaced by typed `sources: [{path, checksum}]` array. Hashi notified via
separate handoff.

### 6. Inbox triage state coverage

`inbox-triage.py` v0.7.0 queries all 6 tomo states: pending-approval,
pending-accept, captured, approved, accepted, plus doc_type=instructions.
Previously only queried 4 — docs with state=approved/accepted fell through
as fresh sources and got re-classified.

## Impact on Kokoro

- Tomo architecture overview needs update: conductor model, skill-owned pipelines, haiku dispatch
- F-47 ADR draft (pending in outbox) references old source_* pattern — update to sources[]
- Cross-component state contract (also pending) should reference the 6-state query model

## References

- Branch: `feat/018-inbox-routing-redesign` (194 commits)
- Spec: `docs/XDD/specs/018-agent-architecture-cleanup/`
- Cost log: `docs/evolution/inbox-cost-log.md`
- Hashi handoff: `_outbox/for-hashi/2026-05-27_tomo-to-hashi_sources-array-migration.md`

