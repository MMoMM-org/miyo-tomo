---
title: "MOC insertion-point intelligence"
status: draft
version: "1.0"
---

# Solution Design Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Architecture pattern is clearly stated with rationale
- [x] **All architecture decisions confirmed by user** — all 7 ADRs confirmed 2026-06-15
- [x] Every interface has specification

### QUALITY CHECKS (Should Pass)

- [x] All context sources are listed with relevance ratings
- [x] Project commands are discovered from actual project files
- [x] Constraints → Strategy → Design → Implementation path is logical
- [x] Every component in diagram has directory mapping
- [x] Error handling covers all error types
- [x] Quality requirements are specific and measurable
- [x] Component names consistent across diagrams
- [x] A developer could implement from this design

---

## Output Schema

### SDD Status Report

| Field | Value |
|-------|-------|
| specId | 022-moc-insertion-point-intelligence |
| pattern | Pipeline relocation: move a deterministic render-time decision into the Pass-1 LLM stage, surface it for review, honor it at render |
| keyComponents | moc-structure lib (NEW), moc-tree-builder, shared-ctx-builder, inbox-analyst, suggestions-reducer, instruction-render |
| externalIntegrations | Kado (read), Hashi (apply — no new shape) |
| validationPassed | 12 |
| validationPending | 2 (ADR-2, ADR-3) |

---

## Constraints

- **CON-1 (2-pass model):** The placement decision MUST be produced in Pass-1 (`inbox-analyst`) and
  surfaced in the suggestions document before the confirm gate. Pass-2 honors it; it does not
  re-decide. (PRD R4 / AC-13)
- **CON-2 (no new Hashi shape):** Emitted placements use only anchor/placement combinations the
  landed Hashi insert primitive (PR #65) already applies — `anchor.type ∈ {callout, heading, line}`,
  `placement ∈ {inside, before, after}`. Verified in Hashi `src/actions/anchorResolver.ts` +
  `src/schema/instructions.schema.json:99` (heading matches any level incl. H1; `line` matches any
  body line).
- **CON-3 (Kado-only):** All MOC-structure reads route through `KadoClient` (Constitution L1).
  Heading inventory is derived from bytes already read — no new Kado calls.
- **CON-4 (additive / near-MVP):** Hot-path scripts (`inbox-analyst`, `shared-ctx-builder`,
  `suggestions-reducer`, `instruction-render`, `moc-tree-builder`) take additive changes only; no
  breaking change to existing inbox behavior. New schema fields are OPTIONAL so old artifacts still
  validate (`additionalProperties:false` schemas get explicit field additions).
- **CON-5 (Constitution L2):** Relocating the decision Pass-2→Pass-1 changes the Tomo↔Hashi
  interaction model → a Kokoro ADR / design-note accompanies implementation.
- **CON-6 (Python 3, venv):** Tests run under `./venv/bin/python` (system python3 lacks
  `jsonschema`). bash 3.2 host.

## Implementation Context

**IMPORTANT**: All listed sources were read by the agent-team research and are file:line-grounded
in `research-synthesis.md`.

### Required Context Sources

#### Documentation Context
```yaml
- doc: docs/XDD/specs/022-moc-insertion-point-intelligence/research-synthesis.md
  relevance: CRITICAL
  why: "Full agent-team findings (Requirements/Technical/Integration/UX), all file:line grounded"
- doc: docs/XDD/specs/022-moc-insertion-point-intelligence/requirements.md
  relevance: CRITICAL
  why: "16 ACs the design must satisfy"
- doc: ~/Kouzou/projects/miyo/miyo-constitution.md
  relevance: HIGH
  why: "L1 Kado-only + testing; L2 cross-repo Kokoro reflection obligation"
```

#### Code Context
```yaml
- file: tomo/scripts/instruction-render.py
  relevance: CRITICAL
  why: "resolve_section_names (:1479-1679), _pick_anchor (:1585-1601), _build_link_to_moc_actions (:739-827), _emit (:765-785), DEFAULT_NEW_SECTION_TITLE (:1476), FOOTER_CALLOUTS (:1471), callout_re/heading_re (:1510-1511)"
- file: tomo/scripts/moc-tree-builder.py
  relevance: CRITICAL
  why: "Body-read site raw_by_path (:292); per-MOC structure-cache entry (:290-323) — heading inventory parsed here"
- file: tomo/scripts/shared-ctx-builder.py
  relevance: HIGH
  why: "build_mocs (:210) emits mocs[]; enforce_budget trim-pass pattern (:561-612)"
- file: tomo/dot_claude/agents/inbox-analyst.md
  relevance: HIGH
  why: "Step 4 MOC match (:113-150), pre_check threshold (:612-615), classification guard (:121-126)"
- file: tomo/scripts/suggestions-reducer.py
  relevance: HIGH
  why: "render_link_to_moc (:324-331) — the **Placement:** line goes here"
- file: tomo/schemas/item-result.schema.json
  relevance: CRITICAL
  why: "candidate_mocs[] (:67-79) gets the anchor field; dead link_to_moc.section_name (:188-197)"
- file: tomo/schemas/shared-ctx.schema.json
  relevance: HIGH
  why: "mocs[] (:12-24), additionalProperties:false → schema bump for headings[]"
- file: tomo/schemas/instructions.schema.json
  relevance: HIGH
  why: "link_to_moc (:78-92), anchor (:94-102) — new_section field decision (ADR-3)"
```

### Implementation Boundaries

- **Must Preserve:** existing inbox Pass-1/Pass-2 flow and all current action types; the verbatim
  insert contract (Tomo owns whitespace; Hashi inserts `line_to_add` raw); old result/instruction
  artifacts must still validate (optional fields only).
- **Can Modify:** the four scripts + three schemas above; `DEFAULT_NEW_SECTION_TITLE` is retired;
  the heading/callout regexes move into a shared lib.
- **Must Not Touch:** Hashi apply code (no new shape); `FOOTER_CALLOUTS` profile-ization (#35/F-55);
  per-item context-shaping mechanism (#45); MOC-selection scoring (F-05).

### External Interfaces

#### System Context Diagram

```mermaid
graph TB
    Inbox[/inbox flow]
    subgraph Tomo
      MTB[moc-tree-builder]
      SCB[shared-ctx-builder]
      IA[inbox-analyst Pass-1 LLM]
      SR[suggestions-reducer]
      IR[instruction-render Pass-2]
      LIB[moc_structure lib NEW]
    end
    Kado[(Kado MCP — vault reads)]
    Hashi[Hashi executor — apply]
    User((Marcus))

    Kado --> MTB
    MTB --> LIB
    LIB --> MTB
    MTB --> SCB
    SCB --> IA
    IA --> SR
    SR --> User
    User --> IR
    IR --> LIB
    IR --> Hashi
```

#### Interface Specifications

```yaml
outbound:
  - name: "Kado read_note"
    type: HTTP/MCP
    format: JSON
    authentication: Bearer token
    data_flow: "MOC body bytes → heading/callout inventory (parsed in moc-tree-builder, no extra calls)"
    criticality: HIGH
  - name: "Hashi instruction apply"
    type: file (instructions.json)
    format: JSON (instructions.schema.json)
    authentication: n/a (vault file produced by Tomo, applied by Hashi)
    data_flow: "link_to_moc actions with resolved anchor/placement — existing shapes only"
    criticality: HIGH
```

### Project Commands

```bash
# Discovered from repo
Test (unit):   ./venv/bin/python -m pytest tests/        # system python3 lacks jsonschema
Sync to instance: ./scripts/update-tomo.sh               # bump # version: on edited managed files
Host-vs-Kado:  KADO_URL=127.0.0.1:<port>/mcp + token from instance .mcp.json (sandbox off)
```

### Cross-Component Boundaries

- **API Contracts:** `instructions.schema.json` link_to_moc is the Tomo→Hashi contract. Any field
  addition must keep existing shapes valid; Hashi already applies all anchor/placement combos used.
- **Team Ownership:** Tomo owns Pass-1/Pass-2 emission + suggestions doc; Hashi owns apply.
- **Breaking Change Policy:** none permitted — new fields optional; a confirmation handoff +
  real-walk closes the Tomo↔Hashi drift gate.

## Solution Strategy

- **Architecture Pattern:** *Decision relocation.* The four-tier insertion logic already exists at
  Pass-2 render (`resolve_section_names`). 022 (a) adds a semantic tier-0 that only an LLM can do,
  (b) moves the per-(note,MOC) decision into Pass-1 so it is reviewable, and (c) leaves the
  existing deterministic resolver in place as a pure fallback for actions Pass-1 didn't decide.
- **Integration Approach:** Enrich the MOC structure cache (where bytes are already read) with a
  heading + editable-callout inventory; feed it into `shared-ctx` so the Pass-1 LLM can judge fit;
  carry the chosen anchor on `candidate_mocs[]`; thread it through render so the existing
  `anchor.value`-populated guard makes the heuristic fallback-only.
- **Justification:** Smallest blast radius that satisfies CON-1/CON-2. No new Kado calls (CON-3), no
  new Hashi shape (CON-2), additive schemas (CON-4). The hard part (semantic fit) lives where
  semantic judgment already happens — the Pass-1 LLM.
- **Key Decisions:** ADR-1 carrier; ADR-2 cost trim; ADR-3 new-section encoding; ADR-4 inventory
  source; ADR-5 honor-via-existing-guard; ADR-6 H1 last-resort / no new shape; ADR-7 cross-repo.

## Building Block View

### Components

```mermaid
graph LR
    Kado --> MTB[moc-tree-builder]
    MTB -->|parse headings/callouts| LIB[moc_structure lib]
    MTB -->|headings[] in cache entry| Cache[(moc-structure-cache)]
    Cache --> SCB[shared-ctx-builder]
    SCB -->|mocs[].headings + editable_callouts| Ctx[(shared-ctx.json)]
    Ctx --> IA[inbox-analyst]
    IA -->|candidate_mocs[].anchor| Result[(item result.json)]
    Result --> SR[suggestions-reducer]
    SR -->|**Placement:** line| SuggDoc[(suggestions.md)]
    SuggDoc -->|user review/edit| IR[instruction-render]
    Result --> IR
    IR -->|_emit stamps anchor| Instr[(instructions.json)]
    IR -->|fallback only when no anchor| LIB
    Instr --> Hashi
```

### Directory Map

**Component**: Tomo pipeline
```
tomo/
├── scripts/
│   ├── lib/
│   │   └── moc_structure.py            # NEW: shared heading/callout parse (regexes lifted from instruction-render)
│   ├── moc-tree-builder.py             # MODIFY: call moc_structure on raw_by_path; add headings[]+editable_callouts[] to cache entry
│   ├── shared-ctx-builder.py           # MODIFY: copy headings/editable_callouts into mocs[]; enforce_budget drops them first
│   ├── suggestions-reducer.py          # MODIFY: render_link_to_moc emits the **Placement:** line + ← hint
│   └── instruction-render.py           # MODIFY: _emit stamps Pass-1 anchor; retire DEFAULT_NEW_SECTION_TITLE; import moc_structure
├── dot_claude/agents/
│   └── inbox-analyst.md                # MODIFY: Step 4 emits per-candidate anchor (semantic fit / new-section / fallbacks)
└── schemas/
    ├── item-result.schema.json         # MODIFY: candidate_mocs[].anchor (optional); new_section naming
    ├── shared-ctx.schema.json          # MODIFY: mocs[].headings[], mocs[].editable_callouts[] (optional)
    └── instructions.schema.json        # MODIFY (ADR-3): explicit new_section field on link_to_moc
```

**Component**: Cross-repo
```
_outbox/for-hashi/                      # NEW handoff: Pass-1 emission exercises existing shapes + real-walk request
(Kokoro)/.../adr/                       # NEW ADR: insertion-point decision relocated Pass-2 → Pass-1
```

### Interface Specifications

#### Data Storage Changes

Not a database — JSON caches/artifacts. Schema changes (all additive, optional):

```yaml
# moc-structure-cache entry (written by moc-tree-builder.py:290-323)
ADD: headings: [ { text: string, level: 2|3 } ]      # ordered, content headings before footer
ADD: editable_callouts: [ string ]                   # full callout opening lines present, in order

# shared-ctx.schema.json mocs[] (:12-24, additionalProperties:false)
ADD: headings: [ { text, level } ]                   # optional; trimmed/capped per ADR-2
ADD: editable_callouts: [ string ]                   # optional

# item-result.schema.json create_atomic_note.candidate_mocs[] (:67-79)
ADD: anchor: {                                       # optional; present only when Pass-1 decided
       type: "heading" | "callout" | "line",
       value: string | null,
       placement: "inside" | "before" | "after",
       new_section: string | null                    # set when proposing a new H2 (tier-2)
     }

# instructions.schema.json link_to_moc (:78-92) — ADR-3 (PENDING)
ADD (if ADR-3=explicit): new_section: string | null  # the H2 title to create; render builds line_to_add from it
```

#### Application Data Models

```pseudocode
ENTITY: MocStructure (NEW, lib/moc_structure.py)
  FUNCTIONS:
    + parse_headings(body: str) -> list[{text, level}]      # H2/H3 before footer (footer = FOOTER_CALLOUTS)
    + parse_editable_callouts(body: str, editable: list[str]) -> list[str]
    + footer_index(lines: list[str]) -> int                  # shared with render fallback
  NOTE: regexes lifted verbatim from instruction-render.py:1510-1511 so build-time inventory
        and render-time fallback agree (single source of truth).

ENTITY: CandidateMoc (MODIFIED, item-result candidate_mocs[])
  FIELDS:
    path: string
    score: number
    pre_check: boolean
    + anchor: Anchor | absent   (NEW, optional — the Pass-1 placement decision)

ENTITY: Anchor (mirrors _pick_anchor return, instruction-render.py:1591-1600)
  FIELDS: type, value, placement, new_section?
```

#### Integration Points

```yaml
- from: moc-tree-builder
  to: shared-ctx-builder
  protocol: discovery-cache.yaml (map_notes entries)
  data_flow: "per-MOC headings[] + editable_callouts[] inventory"

- from: inbox-analyst (Pass-1)
  to: instruction-render (Pass-2)
  protocol: item result.json (candidate_mocs[].anchor)
  data_flow: "the resolved placement decision per (note, MOC)"

- from: instruction-render
  to: Hashi
  protocol: instructions.json (link_to_moc, existing shapes)
  data_flow: "anchor + placement + line_to_add — no new shape"
```

### Implementation Examples

#### Example: `_emit` stamping the Pass-1 anchor (the honor path)

**Why this example:** This is the crux — how a Pass-1 decision becomes fallback-suppressing at
render with a minimal diff. `resolve_section_names` already skips actions whose `anchor.value` is
truthy (the `if anchor.get("value"): continue` guard ~`:1652`). So if `_emit` stamps the anchor,
the heuristic auto-suppresses; if not, the heuristic runs as today.

```python
# instruction-render.py  _build_link_to_moc_actions._emit  (today ~:765-785)
# BEFORE: anchor hardcoded null, placement "after"
def _emit(target_moc, source_title, anchor=None):
    action = {
        "action": "link_to_moc",
        "target_moc": target_moc,
        "anchor": anchor or {"type": "callout", "value": None},   # null → Pass-2 heuristic resolves
        "placement": (anchor or {}).get("placement", "after"),
        "line_to_add": f"- [[{source_title}]]",
    }
    # ADR-3 explicit-field variant: if anchor.new_section set, carry it through; render builds
    # line_to_add = f"## {anchor['new_section']}\n\n- [[{source_title}]]\n" at serialize time.
    return action

# Caller threads the per-candidate anchor: match confirmed item's candidate_mocs[] by target stem
for parent in item.get("parent_mocs") or []:
    cand = _find_candidate(item, _moc_stem(parent))   # candidate_mocs entry for this MOC
    _emit(_moc_stem(parent), source_title, anchor=cand.get("anchor") if cand else None)
```

**Traced walkthrough (First Principles Thinking → a MOC with no fitting H2):**
- Pass-1 reads `mocs[].headings` for the pre-checked MOC; none fits "First Principles Thinking".
- Pass-1 emits `candidate_mocs[].anchor = {type:"callout", value:"[!video] Action Items",
  placement:"before", new_section:"First Principles"}` (footer anchor for the new section).
- `_emit` stamps that anchor; `resolve_section_names` sees `anchor.value` truthy → skips.
- Serialize builds `line_to_add = "## First Principles\n\n- [[First Principles Thinking]]\n"`.
- Hashi applies `placement:before` on the `[!video]` footer → new H2 before footer, correct spacing.

#### Test Examples as Interface Documentation

```python
# tests/test_moc_insertion_resolution.py  (NEW)
def test_tier_order_heading_beats_callout(...):
    # MOC has both an editable callout AND a fitting H2 → tier-1 (heading) wins
    assert anchor["type"] == "heading"

def test_semantic_fit_keyword_would_mispick(...):
    # note shares tokens with WRONG heading; fits RIGHT heading semantically
    # (LLM-stage fixture / contract test) → resolves to the semantically-right heading
    assert chosen_heading == "Reasoning Techniques"

def test_new_section_named_from_topic_not_key_concepts(...):
    assert anchor["new_section"] and anchor["new_section"] != "Key Concepts"

def test_last_resort_anchors_on_h1_title(...):
    # no headings, no editable callout → anchor on H1 title, placement after
    assert anchor["type"] == "heading" and anchor["placement"] == "after"

def test_pass1_anchor_suppresses_render_heuristic(...):
    # action arriving with populated anchor.value is not re-resolved
```

## Runtime View

### Primary Flow: `/inbox` resolves and surfaces placement

1. `moc-tree-builder` reads each MOC body (already does) → `moc_structure.parse_*` → cache entry
   gains `headings[]` + `editable_callouts[]`.
2. `shared-ctx-builder` copies (trimmed) inventory into `mocs[]`.
3. Pass-1 `inbox-analyst`, for each pre-checked candidate MOC, applies the four-tier order against
   that MOC's headings/callouts and emits `candidate_mocs[].anchor`.
4. `suggestions-reducer` renders one `**Placement:**` line per link with a `←` edit hint.
5. User reviews, optionally edits the heading / renames the new section, checks `Approved`.
6. Pass-2 `instruction-render` `_emit` stamps the anchor; heuristic runs only for un-decided actions;
   serialize builds `line_to_add`; `instructions.json` emitted.
7. Hashi applies — existing shapes.

```mermaid
sequenceDiagram
    actor User
    participant MTB as moc-tree-builder
    participant SCB as shared-ctx-builder
    participant IA as inbox-analyst (Pass-1)
    participant SR as suggestions-reducer
    participant IR as instruction-render (Pass-2)
    participant Hashi
    MTB->>SCB: cache + headings[]/editable_callouts[]
    SCB->>IA: shared-ctx mocs[].headings
    IA->>SR: candidate_mocs[].anchor (four-tier decision)
    SR->>User: **Placement:** line + ← hint
    User->>IR: approve (optionally edited)
    IR->>IR: _emit stamps anchor; heuristic = fallback
    IR->>Hashi: instructions.json (existing shapes)
```

### Error Handling

- **Kado read fails for a MOC** → no inventory for that MOC; Pass-1 cannot judge fit → falls to
  tier-3/4 deterministically; render heuristic remains as the safety net (today's behavior). Never
  blocks the run.
- **MOC absent / path null** → existing missing-target surfacing pattern (I38) applies; no link
  emitted into a non-existent MOC.
- **User edits to a non-existent heading (EC-6)** → Pass-2 treats an unknown user-supplied heading
  as a new-section request (creates that H2). Documented in the `←` hint contract.
- **Budget pressure** → `enforce_budget` drops `headings[]`/`editable_callouts[]` from `mocs[]`
  first (before topics); Pass-1 degrades to no-inventory (tier-3/4) rather than failing.

### Complex Logic — four-tier resolution (Pass-1)

```
ALGORITHM: resolve_placement(note, moc_inventory)
INPUT: note (topic/summary), moc_inventory {headings[], editable_callouts[], h1_title, footer?}
OUTPUT: anchor {type, value, placement, new_section?}

1. IF moc.is_classification: EXCLUDE (never a target)            # EC-5, pre-step
2. TIER-1: heading = LLM_pick_fitting(note, headings)           # semantic, not keyword
   IF heading: RETURN {type:heading, value:heading, placement:after}
3. TIER-2: IF headings non-empty AND none fit:
   RETURN {type:callout, value:footer, placement:before, new_section: topic_name(note)}
4. TIER-3: IF editable_callouts non-empty:
   RETURN {type:callout, value:editable_callouts[priority], placement:inside}
5. TIER-4: RETURN {type:heading, value:h1_title, placement:after}   # last-resort
   (if no H1 → {type:line, value:first_body_line, placement:after})
```

## Deployment View

No change to deployment topology. Changes ship via `scripts/update-tomo.sh` into the instance
(bump `# version:` on every edited managed file — else update-tomo silently skips). Cross-repo: one
Kokoro ADR and one `_outbox/for-hashi/` handoff. No Hashi code/version dependency (existing
primitive). No feature flag needed — behavior is additive and degrades to current behavior when
inventory is absent.

## Cross-Cutting Concepts

### Pattern Documentation

```yaml
- pattern: shared parse lib (lib/moc_structure.py) (NEW)
  relevance: HIGH
  why: "Single source of truth for heading/callout parsing so build-time inventory == render-time fallback"
- pattern: optional-field schema additions under additionalProperties:false
  relevance: HIGH
  why: "Additive, backward-compatible (CON-4); old artifacts still validate"
- pattern: existing anchor.value guard as the honor mechanism
  relevance: CRITICAL
  why: "Minimal diff — populated anchor auto-suppresses the heuristic (instruction-render.py:~1652)"
```

### System-Wide Patterns

- **Security/Privacy:** inventory is heading text + callout opening lines only (structure, not note
  content); audit/logs stay metadata-only (Constitution L2 Privacy). No new external surface.
- **Error Handling:** degrade-not-fail — missing inventory → deterministic fallback; never blocks.
- **Performance:** zero new Kado calls (CON-3); inventory parsed at existing read site; budget trim
  drops inventory first. (See ADR-2.)
- **Logging/Auditing:** add the tracking events from the PRD (tier fired, override, new-section,
  honored-vs-resolved, cost) using the existing lifecycle.discovery event channel.

### Multi-Component Patterns

- **Communication:** async file handoff (instructions.json) Tomo→Hashi; existing contract.
- **Data Consistency:** the shared parse lib guarantees build-time and render-time agree on what
  counts as a heading/footer/editable-callout.

## Architecture Decisions

- [x] **ADR-1 Anchor carrier = `candidate_mocs[].anchor`**: attach the Pass-1 placement to each
  `create_atomic_note.candidate_mocs[]` entry (optional object mirroring `_pick_anchor`'s return).
  - Rationale: this is the live synth path (`_build_link_to_moc_actions`); the Pass-1
    `link_to_moc.section_name` field is dead (consumed nowhere).
  - Trade-offs: a second link_to_moc concept (Pass-1 display vs Pass-2 executable) persists; we keep
    them separate rather than reconcile now.
  - User confirmed: **Yes** (README Decisions Log, 2026-06-15).

- [x] **ADR-2 Cost strategy = A-trimmed (eager headings-only inventory)**: include heading inventory
  for thematic MOCs eagerly in shared-ctx, headings-only (no callout bodies), cap ~8 headings/MOC,
  skip Dewey/classification MOCs; add an `enforce_budget` pass that drops inventory first under
  pressure.
  - Rationale: measured ~7 KB for 63 MOCs vs 40 KB budget — fits; simplest that keeps Pass-1
    single-shot (option C's 2-pass analyst is a heavy refactor; option B's lazy fetch can't be done
    cheaply mid-subagent).
  - Trade-offs: every subagent carries all thematic MOCs' headings even though each item touches
    1–2 → real per-item token regression, explicitly deferred to #45 for shaping.
  - User confirmed: **Yes** (2026-06-15).

- [x] **ADR-3 New-section encoding = explicit `new_section` field on instructions link_to_moc**:
  carry the new H2 title as a structured field; render builds `line_to_add` from it at serialize.
  - Rationale: cleaner than today's `line_to_add` string mutation; render/consumers don't
    reverse-engineer "is this a new section?" from prose. No Hashi change (Hashi still receives a
    final `line_to_add`; the field is Tomo-internal up to serialize).
  - Trade-offs: one more optional schema field vs zero-schema-change keeping the mutation. If you
    prefer minimal schema churn, the alternative is to keep encoding it in `line_to_add` (current
    behavior) and just move the naming decision to Pass-1.
  - User confirmed: **Yes** (2026-06-15).

- [x] **ADR-4 Heading inventory parsed in moc-tree-builder + shared parse lib**: derive headings at
  the existing `raw_by_path` body-read; lift regexes into `lib/moc_structure.py`.
  - Rationale: zero new Kado calls (avoids 429); single source of truth with the render fallback.
  - Trade-offs: bumps the moc-structure-cache schema; coordinate with the F-34 scoped cache work.
  - User confirmed: **Yes** (README Decisions Log, 2026-06-15).

- [x] **ADR-5 Honor via existing `anchor.value` guard**: `_emit` stamps the Pass-1 anchor; the
  heuristic in `resolve_section_names` already skips populated anchors → fallback-only automatically.
  - Rationale: minimal diff; keeps the deterministic resolver as a safety net for un-decided actions.
  - Trade-offs: two code paths (Pass-1 decision + Pass-2 fallback) coexist; acceptable and tested.
  - User confirmed: **Yes** (design follows locked relocation decision).

- [x] **ADR-6 Last-resort = H1-title heading anchor; no new Hashi shape**: tier-4 anchors on the H1
  title with `placement:after`; `type:line` on first body line if no H1.
  - Rationale: Hashi `type:heading` matches any level incl. H1; `type:line` matches any body line —
    verified in Hashi `anchorResolver.ts`. Avoids a new `end_of_note` placement + Hashi handoff.
  - Trade-offs: "under the note title" is a slightly arbitrary spot; acceptable as a rare last-resort.
  - User confirmed: **Yes** (README Decisions Log, 2026-06-15).

- [x] **ADR-7 Cross-repo: Kokoro ADR + Hashi confirmation handoff + real walk**: document the
  Pass-2→Pass-1 relocation in Kokoro (L2); send a `_outbox/for-hashi/` note that the new emission
  uses existing shapes and request the real walk (AC-14/AC-15).
  - Rationale: Constitution L2 + standing "real walks > synthetic fixtures" rule (#28 owes a walk).
  - Trade-offs: cross-repo coordination overhead; unavoidable per governance.
  - User confirmed: **Yes** (governance obligation).

## Quality Requirements

- **Performance:** zero new Kado calls on the `/inbox` hot path; shared-ctx growth ≤ ~7 KB
  (headings-only, capped); `enforce_budget` keeps total within the existing `--max-bytes` budget.
- **Usability:** every MOC link shows exactly one skimmable `**Placement:**` line with an `←` edit
  hint; no bare `[[Target#]]`.
- **Reliability:** no resolvable link left unresolved (tier-4 catch-all); missing inventory degrades
  to deterministic fallback, never blocks a run.
- **Security/Privacy:** inventory carries structure (heading text, callout opening lines) only;
  metadata-only logging preserved.

## Acceptance Criteria (EARS — system-level, traces to PRD ACs)

**Main Flow (PRD AC-1..AC-3, AC-11..AC-13):**
- [ ] WHEN Pass-1 resolves a pre-checked candidate MOC, THE SYSTEM SHALL evaluate the four tiers in
  order and emit `candidate_mocs[].anchor` for the first that succeeds.
- [ ] THE SYSTEM SHALL render exactly one `**Placement:**` line per MOC link with an `←` edit hint
  and never a bare `[[Target#]]`.
- [ ] WHEN Pass-2 renders an action whose `anchor.value` is populated, THE SYSTEM SHALL NOT
  re-resolve it (honor the Pass-1 decision).

**New section (PRD AC-4..AC-6):**
- [ ] IF a MOC has headings but none fits, THEN THE SYSTEM SHALL emit a new-section anchor whose
  name derives from the note topic (NOT "Key Concepts").
- [ ] WHEN a new-section placement is applied, THE SYSTEM SHALL insert the H2 before the footer with
  the trailing-newline spacing contract preserved.

**Fallbacks (PRD AC-7..AC-10):**
- [ ] IF a MOC has no headings but an editable callout, THEN THE SYSTEM SHALL place the link inside
  that callout (config priority), reached only when no heading exists.
- [ ] IF a MOC has no headings and no editable callout, THEN THE SYSTEM SHALL anchor on the H1 title
  (`placement:after`); IF no H1, THEN on the first body line (`type:line`).

**Edge cases (PRD EC-2/EC-5/EC-6):**
- [ ] WHERE the target MOC does not yet exist (in-run create_moc), THE SYSTEM SHALL judge heading
  fit against the create-MOC template body.
- [ ] IF the target is a classification-layer MOC, THEN THE SYSTEM SHALL exclude it as an insertion
  target before tier-1.
- [ ] IF the user edits placement to a heading the MOC lacks, THEN THE SYSTEM SHALL create that H2
  (new-section) rather than fail or silently append.

**Live walk (PRD AC-14/AC-15):**
- [ ] WHEN `/inbox` runs on `First Principles Thinking` against a MOC with no fitting H2, THE SYSTEM
  SHALL propose a renamable new section in suggestions and, on apply, land it before the footer.

## Risks and Technical Debt

### Known Technical Issues

- `resolve_section_names`/`_pick_anchor` deterministic logic is duplicated conceptually with the new
  Pass-1 LLM tiers — mitigated by the shared parse lib (structure only; the *judgment* differs by
  design: Pass-1 = semantic, Pass-2 = deterministic fallback).
- `instruction-render.py` is ~1870 LOC (D-07 / #42) — adding `_emit` threading nudges it further;
  out of scope to refactor here but noted.

### Technical Debt

- Pass-1 `link_to_moc.section_name` remains dead after this spec (we add to `candidate_mocs[]`
  instead). Cleanup (remove the dead field) is a separate tidy, not this spec.
- Per-item context cost regression is real and intentionally deferred to #45.

### Implementation Gotchas

- `# version:` bump required on every edited managed file or `update-tomo` skips it silently.
- Schemas are `additionalProperties:false` — new fields MUST be declared or validate-result strips
  them and the consumer reads `None` (spec-schema-consumer drift class; fix schema BEFORE consumer).
- Kado note read is `.md`-only — normalize paths before reads.
- Run tests under `./venv/bin/python` or `jsonschema` is missing → phantom collection failures.
- `FOOTER_CALLOUTS` stays hardcoded (#35/F-55); the shared lib must take the footer set as a param,
  not re-hardcode, to stay future-compatible.

## Glossary

### Domain Terms

| Term | Definition | Context |
|------|------------|---------|
| MOC | Map of Content — an index note linking related notes | Insertion target |
| Editable callout | A callout the user treats as a content/scaffold region (`callouts.editable`) | Demoted tier-3 fallback |
| Footer callout | Trailing scaffold callouts (video/calendar/puzzle/compass) marking content end | New-section anchor; #35/F-55 hardcoded |
| Tier | One of the four ordered placement strategies | Resolution order |

### Technical Terms

| Term | Definition | Context |
|------|------------|---------|
| Pass-1 / Pass-2 | Suggestion (analyst) vs Instruction (render) stages of `/inbox` | Decision relocation |
| Anchor | `{type, value, placement}` locating an insertion point | Carried on candidate_mocs[] |
| Honor path | Render skipping resolution when `anchor.value` is already set | ADR-5 |

### API/Interface Terms

| Term | Definition | Context |
|------|------------|---------|
| `link_to_moc` | The Tomo→Hashi action inserting a link into a MOC | instructions.schema.json |
| `candidate_mocs[]` | Per-item scored MOC matches emitted by the analyst | item-result.schema.json |
| `new_section` | (ADR-3) explicit H2 title to create | instructions link_to_moc |
