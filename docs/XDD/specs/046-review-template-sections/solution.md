---
title: "/review: review material for the user's own template sections"
status: draft
version: "1.0"
---

# Solution Design Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Architecture pattern is clearly stated with rationale
- [ ] **All architecture decisions confirmed by user**
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
- [x] Implementation examples use actual schema column names (not pseudocode), verified against migration files
- [x] Complex queries include traced walkthroughs with example data showing how the logic evaluates

Notes on two gates: there are no database migrations; "column names" means the field names of the JSON schemas, the vault-config keys and `read.json` / `meta.json`, checked against `tomo/schemas/*.json` and the code on `main` (2026-11-14). The traced walkthroughs are the section detection under Complex Logic and the template analysis example.

---

## Output Schema

### SDD Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| architecture | ArchitectureSummary | Yes | Architecture overview |
| sections | SectionStatus[] | Yes | Status of each SDD section |
| adrs | ADRStatus[] | Yes | Architecture decision statuses |
| validationPassed | number | Yes | Validation items passed |
| validationPending | number | Yes | Validation items pending |
| nextSteps | string[] | Yes | Recommended next actions |

### ArchitectureSummary

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| pattern | string | Yes | Selected architecture pattern |
| keyComponents | string[] | Yes | Main system components |
| externalIntegrations | string[] | No | External services integrated |

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_DECISION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What decision is needed or what's in progress |

### ADRStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | ADR identifier (e.g., ADR-1) |
| name | string | Yes | Decision name |
| status | enum: `CONFIRMED`, `PENDING` | Yes | Confirmation state |

---

## Constraints

- CON-1 Spec 045's architecture stays (its ADR-1, ADR-2, ADR-12): the `/review` skill owns the flow, scripts own state, reads, writes, checks and rendering, and the model's only output is `proposals.json`. Python 3 stdlib plus the repo's `lib/` only; scripts run in the container and on the host (`./venv/bin/python`). Runtime prose (`tomo/dot_claude/**`) holds imperatives only; every WHY goes to `docs/tomo/<mirrored-path>.md` first. Every edited managed file bumps `# version:`.
- CON-2 Nothing of spec 045 is removed (PRD Constraints): without a mapping every path behaves byte-for-byte as on `main`; the month's `read.json` keys and the proposals' `groups` keep their names. Files stay within the L2 size guide (300–500 lines of dense logic): new logic goes into new modules, not into the already large `review-instructions.py` (511), `lib/review_actions.py` (463), `lib/period.py` (486), `lib/review_period.py` (421).
- CON-3 Privacy (spec 045 ADR-9, Feature 7): no note text in Tomo's logs, stderr, cost records or `tomo-tmp` state. Section headings, descriptions and keywords are setup text the user confirmed and may sit in the vault config and `read.json`; headings and content found in the target note may not enter `meta.json` or `delivered_plan`. Marker ids are opaque and never derived from text.
- CON-4 Tomo writes only to the inbox; the vault changes through the instruction set the user applies in Hashi or by hand. Kado is the only vault access (Constitution L1/L2).
- CON-5 Cross-repo: the new Hashi action and the wire bump go to Hashi through `_outbox/for-hashi/` (owner-orchestrated), with an FYI to Kokoro (Constitution Architecture L2); the PR merges only after Tomo and Hashi work together in the test vault (PRD Constraints).
- CON-6 Eval gate: no gated file is planned to change (`synthesis-conductor.md`, `suggestion-conductor.md`, `suggest-handling/SKILL.md`, `commands/inbox.md`, `settings.json`). If one must change, the full suite runs before merge.

## Implementation Context

**IMPORTANT**: You MUST read and analyze ALL listed context sources to understand constraints, patterns, and existing architecture.

### Required Context Sources

#### Documentation Context
```yaml
- doc: docs/XDD/specs/046-review-template-sections/requirements.md
  relevance: HIGH
  why: "PRD v1.2 — the 48 criteria this design satisfies; the amendments to spec 045"
- doc: docs/XDD/specs/045-weekly-monthly-review/solution.md
  relevance: HIGH
  why: "Base design (v1.25): ADR-1..13, the review section, marker, staged delivery, privacy, pacing"
- doc: docs/XDD/specs/045-weekly-monthly-review/live-walk.md
  relevance: HIGH
  why: "Measured March numbers (165 Kado calls, read.json 274.7 KB over the Read limit, peak 147.5k tokens) and the walk-found Templater/Kado caveats"
- doc: docs/XDD/specs/035-wire-schema-versioning/solution.md
  relevance: HIGH
  why: "Rule 9: a new action kind is consumer-affecting → schema_version bump; the wire gate and manifests"
- doc: docs/tomo/dot_claude/skills/periodic-review.md
  relevance: HIGH
  why: "WHY layer of the /review skill; every new rule lands here before the runtime text"
- doc: evals/README.md
  relevance: MEDIUM
  why: "Which files are gated (none planned here)"
- doc: ~/Kouzou/projects/miyo/miyo-handoff-protocol.md
  relevance: MEDIUM
  why: "Hashi handoff and Kokoro FYI mechanics"
```

#### Code Context
```yaml
- file: tomo/dot_claude/skills/periodic-review/SKILL.md
  relevance: HIGH
  why: "Flow owner (24,278 chars): setup step 2, read step 4, proposals step 5, parse step 6, preview step 7, deliver step 8"
- file: tomo/scripts/review-session.py
  relevance: HIGH
  why: "start / match / setup-input; _INPUT_KEYS :240, writer_input :245, setup_input :263"
- file: tomo/scripts/lib/review_match.py
  relevance: HIGH
  why: "propose :91-198; anchor precedence :142; own_sections pass-through :177"
- file: tomo/scripts/lib/review_templates.py
  relevance: HIGH
  why: "resolve_template :81, template_candidates :56, template_anchor_candidates :129"
- file: tomo/scripts/lib/review_md.py
  relevance: HIGH
  why: "body :47, fence_state :58, headings :69, section_end, QUERY_FENCES/EMBED_FENCES :26 — reused by the template analysis"
- file: tomo/scripts/lib/template_syntax.py
  relevance: MEDIUM
  why: "templater_spans :256 / _templater_inner_line_indexes :265 — made public for the analysis"
- file: tomo/scripts/lib/review_config.py
  relevance: HIGH
  why: "ReviewSetup ~99-122, review_setup 194-266, input_problems 319, writer_edits 335, GRANULARITY :47"
- file: tomo/scripts/lib/vault_config_edit.py
  relevance: HIGH
  why: "render_scalar 109, render_leaf 121, render_tree 127 — cannot render a list of mappings or quote keys today"
- file: tomo/scripts/vault-config-writer.py
  relevance: MEDIUM
  why: "cmd_review 950-1000 with the read-back check"
- file: tomo/scripts/review-read.py
  relevance: HIGH
  why: "_PERIOD_RE :78, period_from :91, run :164-199, json indent=2 :195"
- file: tomo/scripts/lib/review_period.py
  relevance: HIGH
  why: "_PeriodRead: _find_weeklies :214, _weekly_entries :227, _is_periodic :245, _link_differences :259, run :346, report :397"
- file: tomo/scripts/lib/period.py
  relevance: HIGH
  why: "KINDS :28-31, Period :123-176, tokens :37, format_kind :221, parse_args :384, _parse_period_word :426, _parse_at :473"
- file: tomo/scripts/review-doc.py
  relevance: HIGH
  why: "render_and_write :220-265, _write_meta :193"
- file: tomo/scripts/lib/review_doc.py
  relevance: HIGH
  why: "load_proposals :123, Sources :165, _check_item :209, check_items :236, DocInput :265, item_lines :296, render_document :324, _LABELS :82, group_labels :108"
- file: tomo/scripts/lib/review_doc_parse.py
  relevance: HIGH
  why: "_ITEM :53, _HEADING :54, _APPROVED :55, _parse_body :182, approved_review :124"
- file: tomo/scripts/review-instructions.py
  relevance: HIGH
  why: "load_run :254, preview :294, deliver :342, _overwrite_step :322"
- file: tomo/scripts/lib/review_actions.py
  relevance: HIGH
  why: "marker :71, ACTION_ID :60, fenced_mask :223, hashi_headings :237, bare :252, _marker_index :257, _first/_resolved :264-273, _insertion :295, rerun :357, new note :411-449"
- file: tomo/scripts/lib/review_delivery.py
  relevance: HIGH
  why: "REFUSING/NOTICES :70, second_set :141, plan_record :262, replan_differs :274, resume_refusal :284"
- file: tomo/scripts/lib/review_state.py
  relevance: MEDIUM
  why: "SECTION_ACTIONS :83, all_applied/any_applied :123, _infer_kind :323"
- file: tomo/scripts/lib/render_md.py
  relevance: MEDIUM
  why: "insert_under_marker :312, replace_section :336 — the readable instructions"
- file: tomo/scripts/lib/wire_shape.py
  relevance: MEDIUM
  why: "classify :716 — a new action kind is consumer-affecting"
- file: tomo/schemas/hashi-instructions.schema.json
  relevance: HIGH
  why: "Vendored Hashi schema (byte-identical to Hashi src/schema/instructions.schema.json); schema_version const \"3\" :10"
- file: tomo/schemas/instructions.schema.json
  relevance: HIGH
  why: "Tomo's producer schema; insert_under_marker ~:271, replace_section ~:300"
- file: tomo/schemas/review-proposals.schema.json
  relevance: HIGH
  why: "Closed proposals shape (additionalProperties false)"
- file: tomo/schemas/vault-config-review.schema.json
  relevance: HIGH
  why: "review.<g> config; place :57-71; own_sections :72"
```

#### External APIs (if applicable)
```yaml
- service: MiYo Kado (MCP gateway)
  doc: _inbox/from-kado/ and reference memories (kado-write cheat sheet)
  relevance: HIGH
  why: "All reads (list_dir, read note) and inbox writes; 429 pacing (20 calls / 5 s per IP)"
- service: MiYo Tomo Hashi (instruction-set executor)
  doc: /Volumes/Moon/Coding/MiYo/Hashi/src/{schema,actions,executor} (read-only)
  relevance: HIGH
  why: "insert_under_marker / replace_section semantics, planner KIND_ORDER, validator; the new replace_between_markers action"
```

### Implementation Boundaries

- **Must Preserve**:
  - Spec 045 without a mapping, byte-for-byte: the `groups`, the "Tomo Review" section with its `%% tomo-review <period> %%` marker, `insert_under_marker` / `replace_section`, `%%tN%%` items, the month's `read.json` keys (`only_in_weekly_links`, `dailies_not_in_weekly`, `weekly`), `pass1_counts`.
  - `own_sections` and its two spec 045 roles: the weekly notes' own sections read as sources for a month; the "Tomo Review" section never placed in them.
  - The staged delivery, resume and #258 refusals.
  - The vendored Hashi schema stays byte-identical to Hashi's.
- **Can Modify**: the review scripts and libs named above; `review-proposals.schema.json`, `vault-config-review.schema.json`, both instruction schemas (with the version bump); `vault_config_edit.py` (additive rendering); the `/review` skill and its WHY doc; `commands/review.md` (quarter wording); `tomo/config/vault-example.yaml`.
- **Must Not Touch**: the eval-gated files (CON-6); the Hashi repo (handoff only); Kado; `tomo-privat`; the test vault (read-only; never quote journal text).

### External Interfaces

#### System Context Diagram

```mermaid
graph TB
    User[Reviewer / vault keeper] -->|/review, /review setup, /review quarter| Skill[periodic-review skill]
    Skill --> Scripts[review-session / review-read / review-doc / review-instructions]
    Scripts -->|list, read| Kado[Kado MCP]
    Scripts -->|write review doc, instruction set, readable MD| Kado
    Scripts -->|vault-config-writer review| Config[(config/vault-config.yaml)]
    Kado --> Vault[(Obsidian vault)]
    User -->|apply| Hashi[Tomo Hashi]
    Hashi -->|insert_under_marker, replace_between_markers, replace_section, move_note| Vault
```

#### Interface Specifications

```yaml
# Inbound Interfaces (what calls this system)
inbound:
  - name: "/review command"
    type: Claude Code slash command → skill
    format: "/review [setup | week | month | quarter | 2026-W13 | 2026-03 | 2026-Q1 | Q1 | @note]"
    authentication: none (local container session)
    doc: tomo/dot_claude/commands/review.md
    data_flow: "Period request, setup dialogue answers, Approved review document"

# Outbound Interfaces (what this system calls)
outbound:
  - name: "Kado MCP"
    type: MCP over HTTP (kado_client)
    format: JSON-RPC
    authentication: bearer key (instance)
    doc: reference memories kado-*
    data_flow: "Reads of dailies, weekly/monthly/quarterly notes, templates, target note; writes to the inbox"
    criticality: HIGH
  - name: "Hashi instruction set"
    type: file contract (inbox JSON read by Hashi)
    format: hashi-instructions.schema.json, schema_version "4"
    authentication: none (user applies)
    doc: tomo/schemas/hashi-instructions.schema.json
    data_flow: "insert_under_marker, replace_between_markers (new), replace_section, move_note"
    criticality: HIGH

# Data Interfaces
data:
  - name: "Vault config"
    type: YAML file in the instance
    connection: vault-config-writer.py review (never hand-written)
    doc: tomo/schemas/vault-config-review.schema.json
    data_flow: "review.<g>.sections.<template>, review.<g>.off_limits.<template>, review.quarterly.*"
  - name: "tomo-tmp/review/<stem>/"
    type: files in the instance
    connection: atomic_write_text
    doc: spec 045 SDD (meta.json)
    data_flow: "read.json (or read-index.json + read-<YYYY-MM>.json), proposals.json, meta.json (content-free)"
```

### Cross-Component Boundaries (if applicable)

- **API contracts**: the instruction wire is shared with Hashi. Adding `replace_between_markers` bumps `schema_version` "3" → "4" for every Tomo producer (inbox, `/note`, `/review`); Hashi accepts one `const`, so Tomo and Hashi release together (ADR-5).
- **Team ownership**: Hashi builds the action from the handoff; the owner orchestrates and walks both in the test vault before the Tomo PR merges.
- **Shared resources**: the vault config file (one writer); the inbox folder.
- **Breaking change policy**: the version bump makes a v3 set unappliable by the new Hashi and a v4 set unappliable by an old one; pending v3 sets are re-delivered (owner decision 2026-11-14). The migration path goes into the Kokoro FYI.

### Project Commands

```bash
# Discovered from pyproject.toml, venv/ and evals/README.md (same as spec 045)
Install: none — the repo's ./venv carries pytest and ruff; the container image needs no change
Test:    ./venv/bin/python -m pytest tests/ -q
Test one area: ./venv/bin/python -m pytest tests/test_review_*.py tests/test_period.py tests/test_vault_config_writer_review.py tests/test_tomo_schema_parity.py tests/test_hashi_instructions_schema.py -q
Lint:    ./venv/bin/ruff check tomo/scripts scripts tests
Wire gate: ./venv/bin/python -m pytest tests/test_035_wire_gate.py tests/test_035_wire_manifests.py -q
Integration (opt-in, Privat-Test): ./venv/bin/python -m pytest -m integration tests/
Quarter read dry run (no model, owner go): python3 scripts/review-read.py --kind quarter --period 2026-Q1 --stem <stem> --measure
Sync to the test instance (owner instruction only): scripts/update-tomo.sh --instance tomo-instance --yolo
Cost: python3 scripts/tomo-session-stats.py --session <jsonl>
```

## Solution Strategy

- **Architecture pattern**: spec 045's script-owned 2-pass flow, extended along its existing seams. The model still writes one file (`proposals.json`); every rule a script can check is checked by a script; delivery stays an instruction set.
- **Integration approach**: four additions, each in its own module so the large files do not grow:
  1. *Setup*: a deterministic template analysis offers headings; the model only words descriptions and keywords; the confirm table also carries off-limits marks; the writer stores rows per template.
  2. *Pass 1*: the section definitions ride in `read.json`; the single model pass writes `sections` beside `groups`; scripts check caps, double placement, sources and marks, and render one document part per section with a section checkbox.
  3. *Pass 2*: per kept section, Tomo reads the target note, finds the heading and its own block as Hashi will, and emits `insert_under_marker` (first time) or `replace_between_markers` (re-run), with user choices for missing, ambiguous, broken or moved cases.
  4. *Quarter*: the month reader becomes a period reader with a child-review level (month → weekly notes, quarter → monthly notes); a quarter's read is split per month for the model.
- **Justification**: it keeps every spec 045 guarantee testable without an AI (Constitution L1), adds one Hashi action instead of moving logic into Hashi, and costs no extra model pass or setup turn.
- **Key decisions**: ADR-1 … ADR-13 below.

## Building Block View

### Components

```mermaid
graph LR
    Skill[periodic-review SKILL.md] --> Session[review-session.py]
    Session --> Match[lib/review_match.py]
    Match --> Mapping[lib/review_mapping.py NEW]
    Mapping --> MD[lib/review_md.py]
    Session --> Config[lib/review_config.py]
    Config --> Writer[vault-config-writer.py + lib/vault_config_edit.py]
    Skill --> Read[review-read.py]
    Read --> PeriodRead[lib/review_period.py]
    PeriodRead --> Children[lib/review_children.py NEW]
    PeriodRead --> Period[lib/period.py]
    Skill --> Doc[review-doc.py]
    Doc --> Sections[lib/review_sections.py NEW]
    Doc --> DocLib[lib/review_doc.py]
    Doc --> Parse[lib/review_doc_parse.py]
    Skill --> Instr[review-instructions.py]
    Instr --> SectionPlan[lib/review_section_plan.py NEW]
    Instr --> Actions[lib/review_actions.py]
    Instr --> Delivery[lib/review_delivery.py]
    Instr --> RenderMD[lib/render_md.py]
```

| Component | Single responsibility |
|---|---|
| `lib/review_mapping.py` (new) | Template analysis (offered / left-out headings with reasons), heading identity (text, level, parent, occurrence), row ids, off-limits resolution, dropped headings after a template change |
| `lib/review_config.py` | Reading and validating `review.<g>.*` incl. `sections` and `off_limits`; writer edits |
| `lib/vault_config_edit.py` | YAML rendering: block-style list of mappings, quoted keys, removal on empty |
| `lib/review_match.py` | The setup proposal (adds `sections` and `template_not_found`; anchor precedence by template) |
| `lib/period.py` | Period kinds incl. `quarter`, names, the `Q` token, argument parsing |
| `lib/review_period.py` | Reading a period: dailies, the child-review level, marks parameterised by `CHILD` |
| `lib/review_children.py` (new) | Finding and reading child-review notes (weekly for a month/quarter, monthly for a quarter) and their status report |
| `review-read.py` | Writes `read.json` (week, month) or `read-index.json` + `read-<YYYY-MM>.json` (quarter), compact, with the section definitions |
| `lib/review_sections.py` (new) | Pass 1 section side: definitions for `read.json`, proposal section checks (keys, caps, double placement, sources, marks), rendering of a section part |
| `lib/review_doc.py` / `review-doc.py` | Group side as today; assembles section parts + groups; `meta.json` incl. `pass1_sections` |
| `lib/review_doc_parse.py` | Parses section parts and section checkboxes back |
| `lib/review_section_plan.py` (new) | Pass 2 per kept section: heading resolution as Hashi does, own-block detection, the mode (insert / replace / skip / review / broken / moved), the section's action and preview lines |
| `lib/review_actions.py` | The "Tomo Review" section as today; composes the whole plan (section actions first, then Tomo Review), numbered `I01…In` |
| `lib/review_delivery.py` | Refusals, `delivered_plan` incl. `sections`, overwrite of a partly applied set |
| `lib/render_md.py` | Readable instructions incl. `replace_between_markers` |

### Directory Map

**Component**: Tomo runtime and scripts
```
tomo/
├── dot_claude/skills/periodic-review/SKILL.md   # MODIFY: setup table, step 5 sections, step 6 warnings, step 7/8 choices, quarter
├── dot_claude/commands/review.md                # MODIFY: quarter in the argument hint
├── config/vault-example.yaml                    # MODIFY: documented sections / off_limits / quarterly example
├── schemas/
│   ├── review-proposals.schema.json             # MODIFY: sections[], item mark, quarter groups
│   ├── vault-config-review.schema.json          # MODIFY: sections, off_limits, quarterly
│   ├── instructions.schema.json                 # MODIFY: replace_between_markers, schema_version "4"
│   ├── hashi-instructions.schema.json           # REPLACE verbatim from Hashi after its release
│   └── shapes/instructions.shape.json           # REGENERATE
└── scripts/
    ├── review-session.py                        # MODIFY: sections/off_limits in _INPUT_KEYS, template-not-found refusal, quarter
    ├── review-read.py                           # MODIFY: quarter period, compact JSON, split per month, --measure
    ├── review-doc.py                            # MODIFY: call section checks, pass1_sections, read parts
    ├── review-instructions.py                   # MODIFY: --section-choice / --confirm-moved, partly applied overwrite (thin)
    ├── vault-config-writer.py                   # MODIFY: review subcommand writes rows
    └── lib/
        ├── review_mapping.py                    # NEW
        ├── review_sections.py                   # NEW
        ├── review_section_plan.py               # NEW
        ├── review_children.py                   # NEW
        ├── period.py                            # MODIFY: QUARTER, Q token, months(), parsing
        ├── review_period.py                     # MODIFY: CHILD table, generic marks, _is_periodic
        ├── review_weekly.py                     # MODIFY: content split reused for monthly notes
        ├── review_config.py                     # MODIFY
        ├── review_match.py                      # MODIFY
        ├── review_templates.py                  # MODIFY: KIND_WORDS quarter
        ├── review_md.py                         # MODIFY: AUTOMATIC_FENCES, shared inline-field/embed regexes
        ├── template_syntax.py                   # MODIFY: templater span helpers public
        ├── review_doc.py                        # MODIFY: per-kind group tables, assemble parts
        ├── review_doc_parse.py                  # MODIFY: section parts
        ├── review_actions.py                    # MODIFY: action numbering, compose
        ├── review_delivery.py                   # MODIFY
        ├── review_state.py                      # MODIFY: SECTION_ACTIONS, _infer_kind, partly applied
        ├── vault_config_edit.py                 # MODIFY
        └── render_md.py                         # MODIFY
docs/tomo/                                       # MODIFY/NEW: WHY mirror for every file above (written first)
tests/                                           # NEW/MODIFY: see Acceptance Criteria and Implementation Examples
```

### Interface Specifications

#### Interface Documentation References

```yaml
interfaces:
  - name: "Review proposals"
    doc: tomo/schemas/review-proposals.schema.json
    relevance: HIGH
    sections: [sections, groups, items]
    why: "The model's only output; closed shape"
  - name: "Review vault config"
    doc: tomo/schemas/vault-config-review.schema.json
    relevance: HIGH
    sections: [review.<g>.sections, review.<g>.off_limits, review.quarterly]
    why: "Setup storage"
  - name: "Instruction set"
    doc: tomo/schemas/hashi-instructions.schema.json + Hashi docs/action-reference.md
    relevance: HIGH
    sections: [replace_between_markers, insert_under_marker, schema_version]
    why: "Wire to Hashi"
```

#### Data Storage Changes

No database. Vault config (YAML, through the writer only):

```yaml
review:
  weekly:                      # GRANULARITY: weekly | monthly | quarterly
    sections:
      "t_week_privat.md":      # key = templates.mapping.<g> name (not the _tomo variant), quoted
        - id: s1               # opaque, ^s[0-9]{1,3}$, unique per template, stable (ADR-10)
          heading: "What Went Well This Week?"   # verbatim template text, %% fold %% kept
          level: 4             # 2..6
          parent: "In my own words"              # nearest higher heading, null at top
          occurrence: 1        # 1-based among identical (heading, level, parent)
          description: "What went well: finished tasks, good days, things that worked"
          keywords: [erledigt, geschafft]        # optional, ≤ 12
          groups: [done, themes]                 # optional spec 045 starting points (F2-AC7)
          placement: end       # before | under | end
          cap: 8               # 1..30, default 8
    off_limits:
      "t_week_privat.md":
        - {heading: "Reflections", level: 3, parent: "Review of the Week", occurrence: 1, with_subsections: true}
  quarterly:                   # new: folder, format, template mapping, place, language as for monthly (spec 045 Feature 1)
    folder: "Calendar/304 Quarterly"
    format: "YYYY-[Q]Q"
```

`own_sections` is unchanged. `tomo-tmp/review/<stem>/meta.json` gains `pass1_sections: [{key, count, empty}]` (keys and counts only) and `delivered_plan.sections: [{key, mode, placement, scope_level}]` plus `choices_given: bool` (ids and enums only).

#### Internal API Changes

```yaml
# Script subcommands (CLI JSON contracts)
- review-session.py match --kind <k> [--template T] [--anchor A] [--previous-rows <file>]
  response adds:
    sections: {template, candidates: [{key: {heading, level, parent, occurrence}, state: offered|left-out,
               reason: templater|link|per-period-parent|off-limits|automatic|null, flags: [mixed|container|under-own],
               defaults: {placement, cap}, saved: <row or null>}],
               off_limits: [<saved rows>], dropped: [{heading, level, parent}]}
    template_not_found: {name, source: typed|configured} | absent   # with template: null and candidates listed
- review-session.py setup-input --kind <k> --confirmed <file>
  accepts sections[] and off_limits[] (rows as above); refuses: template-not-found, section-left-out,
  section-off-limits, duplicate-section, bad-section-id
- review-read.py --kind week|month|quarter --period <name> --stem <stem> [--measure]
  writes read.json (week, month) or read-index.json + read-<YYYY-MM>.json (quarter); adds `sections` (definitions);
  quarter adds `monthly`, `only_in_monthly_links`, `dailies_not_in_monthly`, report.monthly_status/monthly_notes
  --measure: no file for the model; prints calls, waits, bytes per part
- review-doc.py write --stem <stem> --proposals <path>
  new refusal errors: unknown-section, over-cap, double-placement, mark-not-allowed (plus spec 045's)
  status written: counts per group and per section key
- review-instructions.py preview|deliver --stem <stem> [--place-anchor A] [--section-choice <key>=skip|review ...]
                                          [--confirm-moved <key> ...]
  new stops: section-missing, section-ambiguous, section-broken, section-moved, block-in-review-section,
             choices-needed, section-checkbox-missing
  new notices: section-dropped (with user item count), section-empty, block-replaced, block-moved-confirmed
```

#### Application Data Models

```pseudocode
ENTITY: SectionRow (vault config)            # see Data Storage Changes
ENTITY: OffLimitsRow (vault config)          # {heading, level, parent, occurrence, with_subsections}
ENTITY: TemplateHeading (review_mapping)
  FIELDS: key{heading, level, parent, occurrence}, line, state, reason, flags
ENTITY: SectionDefinition (read.json "sections")
  FIELDS: key (= row id), heading, level, parent, description, keywords, groups, cap
ENTITY: Proposals (proposals.json)
  FIELDS: language, sections: [{key, items: [{text, sources, mark?}]}], groups: {...spec 045...}
  mark: weekly_only | not_in_weekly (month) | monthly_only | not_in_monthly (quarter)
ENTITY: SectionPart (DocInput)
  FIELDS: key, heading, placement, landing (heading, level, parent), items, empty
ENTITY: ParsedDoc (review_doc_parse) adds
  FIELDS: sections: Dict[key, bool | None], items carry group = key for section items
ENTITY: SectionPlan (review_section_plan)
  FIELDS: key, mode: insert|replace|skip|review|broken|moved, anchor (Hashi text), hashi_placement, scope?, lines,
          notices
```

#### Integration Points

```yaml
- from: Tomo (review-instructions.py)
  to: Hashi
  protocol: instruction-set JSON in the inbox, schema_version "4"
  doc: Hashi docs/action-reference.md (after the handoff)
  endpoints_used: [insert_under_marker, replace_between_markers, replace_section, move_note]
  data_flow: "One action per kept section, then the Tomo Review action, ids I01…In"

- from: Tomo
  to: Hashi team (handoff)
  protocol: _outbox/for-hashi/<date>-replace-between-markers.md
  data_flow: "Contract below + schema fragment + version bump + file/test list"
```

**The `replace_between_markers` contract (handoff content):**

```json
"replace_between_markers": {
  "type": "object",
  "required": ["id", "action", "target_path", "start_marker", "end_marker", "content"],
  "additionalProperties": false,
  "description": "Replace only the lines strictly between a start-marker line and its end-marker line in an existing note; the marker lines and every other line stay byte-identical. Modify-only.",
  "properties": {
    "id": {"$ref": "#/$defs/action_id"},
    "action": {"const": "replace_between_markers"},
    "target_path": {"type": "string", "minLength": 1},
    "start_marker": {"type": "string", "minLength": 1, "pattern": "^\\S([^\\n]*\\S)?$"},
    "end_marker":   {"type": "string", "minLength": 1, "pattern": "^\\S([^\\n]*\\S)?$"},
    "scope": {
      "type": "object", "required": ["heading", "level"], "additionalProperties": false,
      "properties": {"heading": {"type": "string", "minLength": 1},
                     "level": {"type": "integer", "minimum": 1, "maximum": 6}}
    },
    "content": {"type": "string", "description": "Lines between the markers joined by \\n, no trailing newline; \"\" = zero lines."},
    "applied": {"$ref": "#/$defs/applied_field"}
  }
}
```

Match rules (Hashi): split on `\n`; mask fenced lines with `fencedLineMask`; a marker line is unfenced, starts at column 0, and `line.trimEnd() === marker`. Start lines are counted over the whole note: 0 → `failed "start marker not found"`, > 1 → `failed "start marker duplicated"`. The end is the first end-marker line after the start: none → `failed "end marker missing"`; an end line before the start or a second end → `failed "end marker duplicated or out of order"`; `start_marker === end_marker` → `failed "markers equal"`. With `scope`, the first heading with `heading === scope.heading && level === scope.level` gives `locateSection`'s range: not found → `failed "scope heading not found"`; a marker outside it → `failed "markers outside scope"`. Missing target → `failed "target note missing"`. Lines between already equal `content` → `skipped-already`; otherwise those lines are replaced → `applied`. **The markers are resolved inside the `vault.process(path, current => …)` callback**; if they no longer resolve there, the result is `failed` and nothing is written. Planner: `KIND_ORDER` directly after `replace_section`; no `depends_on`; `buildSummary` = `${target_path} :: ${start_marker}` (metadata only). Hashi files and tests to change: `src/schema/instructions.schema.json` (`$def`, `oneOf`, `schema_version` "4"), `src/schema/types.ts`, `src/actions/replaceBetweenMarkers.ts` (new), `src/actions/index.ts`, `src/executor/planner.ts`, `src/instruction-fixer/transforms.ts`, `noteSpots.ts`, `src/ui/instruction-fixer/cards/renderActionCard.ts`, `targetFields.ts`, `docs/action-reference.md`, `docs/instruction-fixer.md`, `docs/hooks.md`, `README.md`, `CHANGELOG.md`; tests `test/unit/actions/replaceBetweenMarkers.test.ts` (new: each outcome, fenced, indented, CRLF, scope miss, equal markers, byte-identical body, outside text unchanged, in-`process` re-resolve), `actions/index.test.ts`, `schema/validator.test.ts`, `types.test.ts`, `executor/planner.test.ts`, `instruction-fixer/transforms.test.ts`, `noteSpots.test.ts`, `ui/instruction-fixer/cards/renderActionCard.test.ts`, `targetFields.test.ts`.

### Implementation Examples

#### Example: Template analysis (first matching rule wins)

**Why this example**: the left-out rules decide what the user can map; a wrong "automatic" verdict cannot be undone by the user because F2-AC4 refuses left-out headings.

```python
# lib/review_mapping.py — shape, not final code
REASONS = ("templater", "link", "per-period-parent", "off-limits", "automatic")

def analyse_template(text, off_limits) -> list[TemplateHeading]:
    lines = review_md.body(text)                       # frontmatter stripped (a YAML '# x' is no heading)
    inner = template_syntax.templater_inner_lines(lines)   # lines inside <%* ... %> are not headings
    heads = [h for h in review_md.headings(lines) if h.line not in inner and h.level >= 2]
    for h in heads:
        h.key = (h.text, h.level, parent_of(h, heads), occurrence_of(h, heads))
        h.state, h.reason = "offered", None
        if "<%" in h.text:                h.left_out("templater")
        elif "[[" in h.text:              h.left_out("link")
        elif per_period(h, heads):        h.left_out("per-period-parent")  # ancestor left out by templater/link;
                                                                            # same (level,text) under ≥ 3 parents;
                                                                            # container of only such headings
        elif covered_by(h, off_limits):   h.left_out("off-limits")         # own row, or ancestor row with_subsections
        else:
            kind = body_kind(h, lines)    # line classes outside fences: automatic | neutral | own-writable
            if kind == "automatic-only":  h.left_out("automatic")
            elif kind == "mixed":         h.flags.add("mixed")
            elif kind == "empty" and has_children(h): h.flags.add("container")
    return heads
```

Line classes: **automatic** = a fence in `AUTOMATIC_FENCES` (dataview, dataviewjs, quoth, dynbedded, tracker, chartsview, calendar-nav, meta-bind-button, toc, tasks), `![[…]]` lines, inline fields `Name:: v`, `` `=…` `` inline queries, `BUTTON[` lines, a Templater line other than `tp.file.cursor`; **neutral** = blank, `<% tp.file.cursor(n) %>`, callout lines, `%%…%%`; **own-writable** = everything else. "automatic-only" needs at least one automatic and no own-writable line; an empty container is left out only when all its descendants are left out as automatic. A heading under an off-limits ancestor without `with_subsections` is offered with flag `under-own`.

Traced on the test vault's `t_week_privat` (structure only): "Overview" and its four children → `automatic` (tracker/dataview fences); the seven day headings → `templater`; their children "My final thoughts for that day" → `per-period-parent`; "Review of the Week" → container of per-period headings only → `per-period-parent`; "Learnings of the Week" → `automatic` (dataview + inline field); "What Went Well This Week?" → body `<% tp.file.cursor(1) %>` only → neutral → **offered**. With "In my own words" marked off-limits *heading only*, its four children stay offered (`under-own`); marked *with sub-sections*, they become `off-limits`.

#### Example: One section part in the review document

```markdown
## What Went Well This Week? %%s1%%
- [x] Abschnitt übernehmen %%s1%%
*Landet: am Ende von „What Went Well This Week?" (Ebene 4, unter „In my own words")*
- [x] Steuererklärung abgeschickt ([[2026-03-24]]) %%t1%%
- [x] Drei Abende ohne Bildschirm ([[2026-03-25]], [[2026-03-27]]) %%t2%%
```

The id on the heading keeps a section recognisable when the user edits the heading text, and keeps a user section named like a group label ("Done") from being read as that group. The checkbox line is matched before `_ITEM`; the italic landing line has no column-0 structure and is ignored by the parser. An empty section shows `- nothing found` (`words['nothing']`) and its checkbox starts `- [ ]`.

#### Example: The block in the note, first delivery and re-run

```markdown
#### What Went Well This Week?
Mein eigener Text bleibt hier.
%% tomo:s1 2026-W13 %%
- Steuererklärung abgeschickt ([[2026-03-24]])
- Drei Abende ohne Bildschirm ([[2026-03-25]], [[2026-03-27]])
%% /tomo:s1 2026-W13 %%

#### What Should I Start Doing?
```

First delivery: `insert_under_marker {anchor: {type: heading, value: "What Went Well This Week?"}, placement: inside, content: "%% tomo:s1 2026-W13 %%\n- …\n%% /tomo:s1 2026-W13 %%\n"}`. Re-run: `replace_between_markers {start_marker: "%% tomo:s1 2026-W13 %%", end_marker: "%% /tomo:s1 2026-W13 %%", scope: {heading: "What Went Well This Week?", level: 4}, content: "- …"}`. Placement mapping: `before` → Hashi `before`, `under` → Hashi `after`, `end` → Hashi `inside` (after any subsections; the preview says so when the section has subheadings). Item lines go through `item_lines` / `neutralised`, and a line that equals a marker line is escaped.

#### Test Examples as Interface Documentation

```python
def test_end_marker_lost_never_pairs_with_next_block():
    note = "#### A\n%% tomo:s1 2026-W13 %%\n- x\n\n#### B\nuser text\n%% tomo:s2 2026-W13 %%\n- y\n%% /tomo:s2 2026-W13 %%\n"
    plan = plan_section(row("s1", "A"), note, period="2026-W13")
    assert plan.mode == "broken"            # unique end markers: s1 has no end; s2's end is not s1's
    assert plan.action is None

def test_quarter_marks_at_monthly_level():
    # fixture: link only in a weekly note, link only in a monthly note, link only in a daily, link to stem 2026-02
    r = read_period(fake_quarter())
    assert r["only_in_monthly_links"] == ["Only-Monthly"]
    assert "Only-Weekly" not in r["only_in_monthly_links"] + flat(r["dailies_not_in_monthly"])
    assert "2026-02" not in flat(r["dailies_not_in_monthly"])
    assert read_period(fake_month_of_same_notes())["only_in_weekly_links"] == ["Only-Weekly"]

def test_month_read_unchanged_by_generalisation():
    assert read_period(FAKE_MARCH) == GOLDEN_MARCH   # captured on main before the refactor
```

## Runtime View

### Primary Flow

#### Primary Flow: a mapped month, first review then re-run

1. `/review month` → skill step 1 → `review-session.py start`: setup present with `sections` for the configured monthly template.
2. Step 4 → `review-read.py --kind month`: reads as spec 045, adds `sections` (definitions) to `read.json`, written compact.
3. Step 5: the model reads `read.json`, writes `proposals.json` with `sections` and `groups` → `review-doc.py write` → `review_sections.check` (keys, caps, double placement, sources, marks) → refusal with `errors` (the model rewrites once) or render → document in the inbox; `meta.json` with `pass1_counts` and `pass1_sections`.
4. The user edits, unticks a section, ticks Approved; `/review` again → step 6 parse: section checkboxes read; a missing expected key stops (`section-checkbox-missing`).
5. Step 7 → `review-instructions.py preview`: target read; per kept section `review_section_plan` resolves heading and block; stops for missing / ambiguous / broken / moved with their choices; preview lists each section's heading, placement, mode and lines, the dropped sections with the user's own item counts, the empty sections, the "Tomo Review" part.
6. The user chooses (Deliver, or a choice per named section) → step 8 `deliver` with the same flags → set `I01…In` + readable MD → staged delivery → document marked.
7. The user applies in Hashi. A later `/review 2026-03` finds `%% tomo:<id> 2026-03 %%` … `%% /tomo:<id> 2026-03 %%` per section → `replace_between_markers`; an unticked section emits nothing and keeps its block.

```mermaid
sequenceDiagram
    actor User
    participant Skill
    participant Read as review-read
    participant Doc as review-doc
    participant Instr as review-instructions
    participant Kado
    participant Hashi
    User->>Skill: /review month
    Skill->>Read: --kind month (sections from config)
    Read->>Kado: list + read dailies, weeklies
    Read-->>Skill: read.json (+ sections)
    Skill->>Doc: write --proposals (sections + groups)
    Doc->>Doc: check sections / groups
    Doc->>Kado: write review document
    User->>Skill: /review (Approved)
    Skill->>Instr: preview
    Instr->>Kado: read target note
    Instr-->>Skill: per-section plan + stops
    User->>Skill: Deliver (+ choices)
    Skill->>Instr: deliver --section-choice …
    Instr->>Kado: set JSON + MD
    User->>Hashi: apply
    Hashi->>Hashi: insert_under_marker / replace_between_markers (resolve in process)
```

### Error Handling

| Case | Where | Behaviour |
|---|---|---|
| Typed template not found | `match` | `template_not_found` + candidates; template null; `setup-input` refuses `template-not-found`; nothing saved (F7-AC1) |
| User adds a left-out heading | skill + `setup-input` | refused with the reason (`section-left-out`); a `mixed` heading is never refused (F2-AC4) |
| A row on an off-limits heading | `setup-input` | `section-off-limits` |
| Writer cannot render | `vault-config-writer.py review` | read-back mismatch → exit with pointer; nothing half-written |
| Unknown section key / over cap / double placement / wrong mark | `review-doc.py write` | `proposals-invalid` with `errors` per item; the skill's rewrite-once loop |
| Section checkbox missing | parse | stop `section-checkbox-missing` naming the section and the line to restore; nothing delivered (F3-AC6) |
| Mapped heading missing / ambiguous | plan | stop; choices skip / review / Abort per section (F4-AC4) |
| Earlier block broken (start without end, duplicates) | plan | stop `section-broken`; choices skip / Abort (F5-AC3) |
| Block moved out of its section | plan | stop `section-moved` naming where it is; replace only with `--confirm-moved <key>` |
| Block inside the "Tomo Review" section | plan | stop `block-in-review-section`; skip / Abort (a `replace_section` of Tomo Review would wipe it) |
| Resume begun with choices, rerun without | delivery | refuse `choices-needed` (like #258 `anchor-needed`) |
| Set partly applied (one section failed at Hashi) | delivery | a new delivery overwrites the set through `_overwrite_step` with the `modified` guard; nothing stuck |
| Hashi `failed` outcomes | Hashi | nothing written for that action; others run; the next run plans from the note as it is |
| Quarter read rate-limited | reader | spec 045 pacing and "not read" report (F6-AC6) |

### Complex Logic (if applicable)

**Section detection per kept section (`review_section_plan.plan_section`)** — the mirror of Hashi's parse:

```
ALGORITHM plan_section(row, note_text, period, choices)
INPUT: mapping row, target note text (from Kado), period name, user choices
OUTPUT: SectionPlan
1. lines = split on "\n"; fenced = fenced_mask(lines)            # Hashi's fence regex
2. start = "%% tomo:<id> <period> %%", end = "%% /tomo:<id> <period> %%"
   is_marker(i, m) = not fenced[i] and lines[i] has no leading space and lines[i].rstrip(JS_WS) == m
3. S = [i | is_marker(i, start)], E = [i | is_marker(i, end)]
4. IF S == [] and E == []:                                        # first delivery
     H = hashi_headings(lines); mapped = find by (bare text, level, parent, occurrence)
     IF mapped is None: RETURN stop(section-missing) unless choice skip|review
     IF count(h in H where h.text == mapped.hashi_text) > 1: RETURN stop(section-ambiguous) unless choice
     IF mapped under an off-limits row: RETURN stop(section-off-limits)
     RETURN insert(anchor = mapped.hashi_text, placement = map(row.placement), content = start+lines+end)
5. IF len(S) == 1 and len(E) == 1 and E[0] > S[0]:                # re-run
     near = nearest heading above S[0]
     IF S[0] inside the Tomo Review section range: RETURN stop(block-in-review-section) unless skip
     IF near is the mapped heading's section (or, for before, the gap above it):
        scope = (near.text, near.level) if _resolved(near) else None
        RETURN replace(start, end, scope, lines)
     RETURN stop(section-moved, under = near) unless confirm-moved → replace with scope = near
6. RETURN stop(section-broken) unless choice skip                  # any other count/order
```

Traced example (re-run of `2026-W13`, s1 mapped to "What Went Well This Week?" L4): S = [12], E = [15]; the nearest heading above line 12 is "What Went Well This Week?" L4 at line 10; `_resolved` finds it as the first exact text → scope `{"What Went Well This Week?", 4}` → `replace_between_markers`. If the user had deleted line 15: S = [12], E = [] → step 6 → `section-broken`, and no action targets the note's later lines. If line 12 sat inside a ```` ``` ```` fence: S = [] (masked), E = [15] → step 6 → broken (Hashi would also fail; nothing is lost).

**Quarter marks**: `CHILD = {MONTH: WEEK, QUARTER: MONTH}`. For each day, `Period.containing(child_kind, day)` picks the child note; only read child notes count; `_is_periodic` knows the daily, weekly, monthly and quarterly formats, so a link to `2026-02` is never content. The month writes `only_in_weekly_links` / `dailies_not_in_weekly`; the quarter writes `only_in_monthly_links` / `dailies_not_in_monthly`, and its weekly notes go to `weekly` without marks.

**Double placement**: normalise each item's text (casefold, collapse whitespace, strip the link list) and its source set; two items with the same normalised text, or the same source set and the same normalised first line, anywhere across sections and groups → `double-placement` on the later one.

## Deployment View

### Single Application Deployment

- **Environment**: the Tomo container (scripts, skill) and the user's Obsidian with Hashi; synced by `update-tomo.sh` (owner instruction).
- **Configuration**: new optional keys `review.<g>.sections`, `review.<g>.off_limits`, `review.quarterly.*`; absent keys mean spec 045 behaviour.
- **Dependencies**: Hashi with `replace_between_markers` and `schema_version` "4".
- **Performance**: Pass 1 cost and time limits of the PRD; quarter read measured first with `--measure`.

### Multi-Component Coordination (if applicable)

- **Deployment order**: (1) the Hashi handoff goes out as soon as this SDD is confirmed; (2) Tomo implements against the contract with the schema copy updated from the handoff fragment; (3) Hashi releases; (4) the vendored schema is replaced verbatim from Hashi; (5) the owner walks Tomo + Hashi in the test vault (week, month, quarter; first delivery and re-run); (6) the Tomo PR merges; (7) the user re-delivers pending v3 sets.
- **Version dependencies**: Tomo ≥ this release ⇔ Hashi ≥ the release with schema "4".
- **Rollback**: revert both together; v4 sets in the inbox are dropped and re-delivered.
- **Kokoro**: FYI handoff on the wire change (schema "4", the new action, the release lockstep).

## Cross-Cutting Concepts

### Pattern Documentation

```yaml
# Existing patterns used in this feature
- pattern: script-owned 2-pass flow, model writes one schema-validated file (spec 045 ADR-1/ADR-12)
  relevance: CRITICAL
  why: "Every new rule is checkable without an AI"
- pattern: staged delivery with resume and refusals (lib/staged_delivery.py, #258)
  relevance: HIGH
  why: "Multi-action sets must rebuild byte-identically on resume"
- pattern: Hashi-parse mirror (review_actions.hashi_headings, fenced_mask, JS_WS)
  relevance: HIGH
  why: "Tomo's view must equal Hashi's at apply time"
- pattern: setup confirm loop with match → confirm → setup-input → writer (spec 045 ADR-5)
  relevance: HIGH
  why: "Mapping and off-limits ride the same turn"

# New patterns created for this feature
- pattern: opaque per-row block markers with unique end marker
  relevance: HIGH
  why: "Owner text can never be paired into a replace"
- pattern: child-review level table (CHILD)
  relevance: MEDIUM
  why: "One reader for month and quarter"
```

### User Interface & UX (if applicable)

**Information Architecture:** setup confirm table (one row per heading: offered or left-out with reason; offered rows show description, keywords, placement, cap; any row can be marked off-limits, heading only or with sub-sections); the review document (section parts in template order, then "Tomo Review"); the Pass 2 preview (per section: heading, placement, add/replace, lines, notices).

**Design System:** plain Markdown in the console and in the inbox note; German wording for `de` (`Abschnitt übernehmen`, `Landet:`), English otherwise; labels in `_LABELS`.

**Interaction Design:** no extra turn: corrections as plain text in the existing Correct step ("s3 Beschreibung: …", "Reflections tabu mit Unterabschnitten", "entferne s5", "füge ‚Planning' hinzu"); per-section choices in the existing Deliver step.

#### UI Visualization Guide

```
Setup (one turn)
┌ Monthly — t_month_privat.md ───────────────────────────────────────────────────┐
│ #  Heading (level, under)                    Description            Place  Cap │
│ s1 I look forward to (3, Outlook)             Suggestions: …         end    8   │
│ s2 This will be challenging (3, Outlook)      Suggestions: …         end    8   │
│ s3 Things I did well this month (4, In my…)   done, only-in-weekly   end    8   │
│ —  Overview (2): automatic (tracker, dataview)                                 │
│ —  Comments from this month (3): Templater                                     │
│ Off-limits: none                                                               │
│ 1 Confirm · 2 Correct · 0 Cancel                                               │
└────────────────────────────────────────────────────────────────────────────────┘
Review document → per section: heading %%sN%% · checkbox · landing line · items
Preview → per section: heading · placement · add|replace · lines · notices → Deliver | Abort
```

### System-Wide Patterns

- **Security / privacy**: no note text in `meta.json`, `delivered_plan`, stderr, cost records; opaque marker ids; `--measure` prints counts and bytes only (CON-3).
- **Error handling**: stops are named states the skill words; unknown names refuse (spec 045 `classify`).
- **Performance**: compact JSON (`separators=(",", ":")`); quarter split per month; pacing unchanged (ADR-4 of spec 045).
- **Logging/Auditing**: counts only, in `meta.json` and the scripts' JSON output; the live walk records the tracking events.

### Multi-Component Patterns (if applicable)

- **Communication**: file contract (instruction set) only; no runtime call between Tomo and Hashi.
- **Data consistency**: Hashi re-resolves every action inside `vault.process`; Tomo re-plans from the note as it is on every delivery.
- **Shared code**: none (Constitution L1, contracts not shared code); Tomo mirrors Hashi's parse in Python and pins it with fixtures.
- **Service discovery**: none.

## Architecture Decisions

- [x] ADR-1 Gathering: the single existing Pass 1 model pass writes `proposals.json` with `sections: [{key, items}]` beside the unchanged `groups`; the section definitions (key, heading, level, parent, description, keywords, groups, cap) ride in `read.json`, so the model reads one file.
  - Rationale: no extra pass or config read; the model cannot invent or rename a section (keys only); the closed schema stays closed.
  - Trade-offs: the skill grows by about 1,000 characters; the model's single pass carries more instructions.
  - User confirmed: 2026-11-14

- [x] ADR-2 Double placement: `review_sections.check` refuses an item proposed in two places (same normalised text, or same sources + first line); the semantic one-finding-one-place stays the model's; caps are refused (`over-cap`), never truncated, so the model merges on the rewrite-once loop; a moved month/quarter item keeps its mark in an optional `mark` field checked like its group.
  - Rationale: only what a script can check is promised (PRD v1.2 F1-AC6); refusing beats silent loss.
  - Trade-offs: a reworded duplicate passes; a refusal costs one rewrite turn.
  - User confirmed: 2026-11-14

- [ ] ADR-3 Config: `review.<g>.sections.<template>` (rows with opaque `id`, heading, level, parent, occurrence, description, keywords, groups, placement `before|under|end`, cap 1..30 default 8) and `review.<g>.off_limits.<template>` (heading key + `with_subsections`); `vault_config_edit` learns block-style lists of mappings, quoted keys and removal on empty; `setup-input` refuses rows on left-out or off-limits headings and duplicate keys. The location was confirmed; the field set and the placement names are proposed here.
  - Rationale: per-template keys keep variants apart (F2-AC8) and one template's save from touching another (F2-AC10); `under` avoids reusing spec 045's `inside`, which means "end of section" there.
  - Trade-offs: a writer extension with its own round-trip tests; `setup-input` stays offline, so a forged row's eligibility is checked against the `match` evidence the skill passes, not re-read from Kado.
  - User confirmed: _Pending_ (location confirmed 2026-11-14)

- [ ] ADR-4 Hashi action `replace_between_markers` as specified under Integration Points, with two safety rules beyond the confirmed shape: (a) unique end markers — start `%% tomo:<id> <period> %%`, end `%% /tomo:<id> <period> %%` — so a lost end marker can never pair with another block; (b) Hashi resolves the markers inside `vault.process`, never splicing indexes from an earlier read.
  - Rationale: a shared end marker or a stale index both delete the user's text; both are cheap to prevent in the contract.
  - Trade-offs: longer marker lines in the note (invisible in reading view); Hashi's existing handlers keep their stale-index pattern (named in the handoff as an observation, not a request).
  - User confirmed: _Pending_ (action shape confirmed 2026-11-14)

- [x] ADR-5 Wire `schema_version` "3" → "4" for all Tomo producers; Tomo and Hashi release in lockstep; pending v3 sets are re-delivered; Kokoro gets an FYI.
  - Rationale: spec 035 Rule 9; Hashi accepts one version.
  - Trade-offs: inbox and `/note` sets need the new Hashi too.
  - User confirmed: 2026-11-14

- [x] ADR-6 Quarter: `lib/period.py` gains `QUARTER`, `Period.quarter`, `months()`, the `Q` token and default format `YYYY-[Q]Q`; `lib/review_period.py` reads by a `CHILD` table (month → weekly notes with marks; quarter → weekly notes as sources + monthly notes with marks); the month's keys stay, the quarter has its own; child-note finding/reading moves to `lib/review_children.py`. A golden test pins the month result before the refactor; a disagreeing-notes fixture pins the quarter's level.
  - Rationale: one reader, the month shape unchanged, the file sizes kept.
  - Trade-offs: a refactor of a tested path; the golden test is the guard.
  - User confirmed: 2026-11-14

- [x] ADR-7 Quarter size: `review-read.py --measure` first (2026-Q1, no model); all `read*.json` compact; a quarter writes `read-index.json` (period, report, sections, part list) and one `read-<YYYY-MM>.json` per month that the model reads in turn; `review-doc.py` loads all parts for its checks; week and month stay one file.
  - Rationale: March's 275 KB was already over the Read limit; a quarter is about 0.8 MB.
  - Trade-offs: the skill gets a quarter branch in step 5; if the measured size stays too large, a quarter-level character budget is the next lever (Technical Debt).
  - User confirmed: 2026-11-14

- [x] ADR-8 Off-limits: marked per template heading in the same confirm table, heading only or with its sub-sections; nothing off-limits by default; off-limits means never written (read as a source stays allowed); `own_sections` keeps its spec 045 roles unchanged.
  - Rationale: owner, 2026-11-14 — "In my own words" as a built-in no-go is too strict; the material is for writing one's own words.
  - Trade-offs: the user must mark protection explicitly; the table grows by one mark per row.
  - User confirmed: 2026-11-14

- [ ] ADR-9 Template analysis in `lib/review_mapping.py`, deterministic, first rule wins (templater, link, per-period-parent, off-limits, automatic); conservative `automatic` verdict — only when every body line is automatic and nothing own-writable remains; `tp.file.cursor` placeholders, callouts and comments are neutral; `mixed` headings are offered and never refused; the per-period repeat threshold is 3 parents; headings are kept verbatim (incl. `%% fold %%`). The model only words descriptions, keywords and group hints.
  - Rationale: a wrong left-out cannot be undone by the user (F2-AC4); deterministic rules are testable on the owner's templates.
  - Trade-offs: some automatic-heavy sections are offered with a `mixed` flag; the threshold is a judgement pinned by tests.
  - User confirmed: _Pending_

- [ ] ADR-10 Marker identity and detection: the row `id` is assigned at save (next free `s<n>` per template), kept when a row is corrected and when a template correction keeps the same (heading, level, parent); per kept section Tomo reads the target and decides insert (no markers), replace (one start, one end after it, with `scope` from the nearest heading when `_resolved` confirms it), or a stop (broken, moved, block inside "Tomo Review", missing, ambiguous) as in Complex Logic; heading matches count exact Hashi text at any level.
  - Rationale: stable ids keep F5-AC5 (one block per section) across template edits; the strict count matches Rule 9.
  - Trade-offs: a heading that occurs twice in a note always needs a choice, even when the mapped one is first.
  - User confirmed: _Pending_

- [ ] ADR-11 Review document: a section part is `## <heading> %%sN%%`, the section checkbox `- [x] <label> %%sN%%` (unticked when empty), an italic landing line, then the items with global `%%tN%%` ids; `meta.json` stores the expected keys (`pass1_sections`), and a missing checkbox stops delivery.
  - Rationale: the parser's column-0 grammar would otherwise read a deleted checkbox's items as another heading's (F3-AC6); keys beat label matching (a user section named "Done").
  - Trade-offs: a visible `%%sN%%` in source view; one more meta field.
  - User confirmed: _Pending_

- [ ] ADR-12 Multi-action sets: ids `I01…In` in a fixed order (sections in mapping order, then "Tomo Review"); user choices are flags on `preview` and `deliver` (`--section-choice <key>=skip|review`, `--confirm-moved <key>`); `delivered_plan.sections` records keys and modes only, and `replan_differs` compares them; `choices-needed` refuses a resume without the original choices; a set with any applied action can be overwritten by a new delivery (`_overwrite_step` with the `modified` guard), so a partly applied set is never stuck.
  - Rationale: byte-identical resume payloads (#258) and no dead end after one failed section.
  - Trade-offs: `second_set` loosens: the old set's waiting actions are replaced by the new plan, which is built from the note as it is now.
  - User confirmed: _Pending_

- [ ] ADR-13 Template choice (#267, F7): `match` returns `template_not_found` with the candidates and a null template; `setup-input` refuses a confirmed missing template; the configured anchor is used only when the resolved template equals the configured one, and the skill drops `--anchor` when the template changes; the skill keeps the last shown rows in `tomo-tmp/review/rows-<kind>.json` and passes `--previous-rows`, from which `match` returns `dropped`.
  - Rationale: today a typo is saved and a corrected template keeps the old anchor; prose rules alone did not hold.
  - Trade-offs: one more tomo-tmp file (setup text only, no note text); a carve-out from the skill's "never drop a flag" rule.
  - User confirmed: _Pending_

## Quality Requirements

- **Performance**: weekly Pass 1 ≤ $0.50, monthly Pass 1 ≤ $2.00 and ≤ 7 min, Pass 2 ≤ $0.75 (test vault March 2026); quarterly Pass 1 ≤ $5.00 and ≤ 20 min on 2026-Q1; quarter read ≈ 460 Kado calls ≈ 2.3 min at 0.3 s pacing (measured with `--measure` before the model run); no `read*.json` part above 256 KB; setup adds no question turn.
- **Usability**: one confirm turn for the mapping and off-limits; every stop names the section and its choices in the review language; the preview names each section's heading, placement and mode.
- **Security / privacy**: 0 note-text strings in `meta.json`, `delivered_plan`, stderr and cost records (tested as in spec 045); marker ids match `^s[0-9]{1,3}$`.
- **Reliability**: 0 changed characters of the user's text outside Tomo's markers after an apply (tested in Tomo by plan fixtures and in Hashi by its unit tests); 0 sections with two Tomo blocks per period after a re-run; a lost end marker never yields an action; a partly applied set can always be re-delivered.

## Acceptance Criteria

**Main Flow Criteria: PRD F1 — material per section**
- [ ] F1-AC1 WHERE a mapping exists, THE SYSTEM SHALL read the same notes as without it and add the section definitions to `read.json`.
- [ ] F1-AC2 WHEN the model proposes for a section, THE SYSTEM SHALL accept items for any description, independent of the group set (no group filter on `sections`).
- [ ] F1-AC3 THE SYSTEM SHALL refuse a section item without a source resolving to a daily (or, for a review-only finding, a weekly/monthly note) of the period.
- [ ] F1-AC4 THE SYSTEM SHALL apply the same source rule to items of forward-looking sections.
- [ ] F1-AC5 IF a section has more items than its cap, THEN THE SYSTEM SHALL refuse the proposals with `over-cap` naming the section.
- [ ] F1-AC6 IF an item is proposed in two places (normalised text, or sources + first line), THEN THE SYSTEM SHALL refuse it with `double-placement`.
- [ ] F1-AC7 THE SYSTEM SHALL render the remaining groups as the "Tomo Review" part, omitting empty groups and the part when no group is left.
- [ ] F1-AC8 WHEN a section has no items, THE SYSTEM SHALL render `nothing found` and an unticked section checkbox.
- [ ] F1-AC9 WHERE the kind is month or quarter, THE SYSTEM SHALL accept a `mark` on section items only for that kind's marks and check it as for the group.
- [ ] F1-AC10 WHERE no mapping exists, THE SYSTEM SHALL produce the spec 045 document byte-for-byte (quarter: with its groups).

**Main Flow Criteria: PRD F2 / F7 — setup**
- [ ] F2-AC1 WHEN `match` runs for a kind with a readable template, THE SYSTEM SHALL return `sections.candidates` with key, state, reason, flags and defaults, and save nothing.
- [ ] F2-AC2 THE SYSTEM SHALL accept the confirmed rows from the one confirm turn (corrected, removed, added rows) through `setup-input`.
- [ ] F2-AC3 THE SYSTEM SHALL leave out headings by the five rules and give one reason per left-out heading.
- [ ] F2-AC4 IF the user adds a heading left out for a reason, THEN `setup-input` SHALL refuse it with that reason; a `mixed` or not-found heading is accepted.
- [ ] F2-AC5 THE SYSTEM SHALL key every heading by text, level, parent and occurrence and show level and parent in the table.
- [ ] F2-AC6 THE SYSTEM SHALL offer forward-looking headings like any other eligible heading.
- [ ] F2-AC7 THE SYSTEM SHALL accept `groups` on a row from the kind's group set and leave unnamed groups in "Tomo Review".
- [ ] F2-AC8 THE SYSTEM SHALL store rows under the template's name and apply only the rows of the configured template.
- [ ] F2-AC9 IF no heading is offered or no template exists, THEN THE SYSTEM SHALL return no candidates and save no rows.
- [ ] F2-AC10 WHEN rows are saved, THE SYSTEM SHALL change only `sections.<template>` / `off_limits.<template>` and continue the session.
- [ ] F2-AC11 WHERE a heading is marked off-limits, THE SYSTEM SHALL leave it (with sub-sections: its subtree) out of the candidates, refuse a row on it, and stop delivery into it; reading sources is unaffected.
- [ ] F7-AC1 IF a typed or configured template is not found, THEN THE SYSTEM SHALL return `template_not_found` with the candidates and `setup-input` SHALL refuse it.
- [ ] F7-AC2 WHEN the template changes in the dialogue, THE SYSTEM SHALL propose place and rows from the new template only.
- [ ] F7-AC3 WHEN `--previous-rows` is given, THE SYSTEM SHALL return the earlier rows the new template lacks as `dropped`.

**Main Flow Criteria: PRD F3 — document by section**
- [ ] F3-AC1 THE SYSTEM SHALL render section parts in template order, then "Tomo Review", with spec 045's header parts unchanged.
- [ ] F3-AC2 THE SYSTEM SHALL render one section checkbox per part with the kind's positive label, ticked unless empty.
- [ ] F3-AC3 THE SYSTEM SHALL render a landing line naming the heading and placement.
- [ ] F3-AC4 WHEN a section checkbox is unticked, THE SYSTEM SHALL drop the section and preview one line with the count of the user's own items dropped.
- [ ] F3-AC5 WHEN a ticked section has no ticked items, THE SYSTEM SHALL deliver nothing for it and preview it as empty.
- [ ] F3-AC6 IF an expected section checkbox is missing, THEN THE SYSTEM SHALL stop with `section-checkbox-missing` and deliver nothing.

**Main Flow Criteria: PRD F4 / F5 — delivery and re-run**
- [ ] F4-AC1 WHEN delivering to an existing note, THE SYSTEM SHALL emit one action per kept non-empty section plus the "Tomo Review" action when anything is left.
- [ ] F4-AC2 THE SYSTEM SHALL wrap each block in its start and end markers with no visible heading or prefix.
- [ ] F4-AC3 THE SYSTEM SHALL only insert or replace between markers; no action targets the user's text (no `replace_section` on a mapped section).
- [ ] F4-AC4 IF a mapped heading is missing or ambiguous, THEN THE SYSTEM SHALL stop with skip / review / Abort per section.
- [ ] F4-AC5 WHERE the note is new, THE SYSTEM SHALL splice blocks under plain-text headings found exactly once and route the rest to "Tomo Review", naming them before delivery.
- [ ] F4-AC6 THE SYSTEM SHALL preview per section heading, placement, mode and lines before Deliver or Abort.
- [ ] F4-AC7 THE SYSTEM SHALL render per section the copy-ready block, heading and placement (and for a replace both marker lines) in the readable instructions.
- [ ] F5-AC1 WHEN a kept section holds exactly one earlier block in its section, THE SYSTEM SHALL emit `replace_between_markers`; an unticked section SHALL emit nothing.
- [ ] F5-AC2 WHEN a kept section holds no earlier block, THE SYSTEM SHALL emit `insert_under_marker`.
- [ ] F5-AC3 IF an earlier block is broken, THEN THE SYSTEM SHALL stop with `section-broken` and offer skip / Abort.
- [ ] F5-AC4 WHEN a replace is planned, THE SYSTEM SHALL say in the preview that edits inside the block are replaced and text outside is kept.
- [ ] F5-AC5 THE SYSTEM SHALL never plan an insert for a section whose markers exist anywhere in the note.

**Main Flow Criteria: PRD F6 — quarter**
- [ ] F6-AC1 WHEN no quarterly setup exists, THE SYSTEM SHALL propose folder, format (from existing notes, else `YYYY-[Q]Q`), template, place, language and rows in one confirm turn.
- [ ] F6-AC2 THE SYSTEM SHALL resolve `quarter`, `2026-Q1`, `Q1` (year named) and an @-picked quarterly note; an open review is offered first.
- [ ] F6-AC3 IF the quarter is invalid or unfinished, THEN THE SYSTEM SHALL answer `invalid-period` / `unfinished-period` with an example and write nothing.
- [ ] F6-AC4 THE SYSTEM SHALL read the quarter's dailies, overlapping weekly notes (sources, clipped to the quarter) and monthly notes, and compute `only_in_monthly_links` / `dailies_not_in_monthly`.
- [ ] F6-AC5 THE SYSTEM SHALL report the monthly and weekly notes not found.
- [ ] F6-AC6 THE SYSTEM SHALL run document, Pass 2, re-run, privacy and habits for a quarter as for a month.

**Error Handling Criteria**
- [ ] WHEN a section is moved or sits inside "Tomo Review", THE SYSTEM SHALL stop and replace only with `--confirm-moved`, or skip.
- [ ] IF a resume lacks the original choices, THEN THE SYSTEM SHALL refuse with `choices-needed`.
- [ ] WHEN a set is partly applied, THE SYSTEM SHALL allow a new delivery to overwrite it.

**Edge Case Criteria**
- [ ] WHILE a marker line is fenced or indented, THE SYSTEM SHALL not count it (mirroring Hashi).
- [ ] IF an item line equals a marker line, THEN THE SYSTEM SHALL escape it.
- [ ] WHILE a week overlaps two quarters, THE SYSTEM SHALL read its weekly note for each, clipped to that quarter.

## Risks and Technical Debt

### Known Technical Issues

- Hashi's existing `insert_under_marker` and `replace_section` splice indexes from `cachedRead` into the `process` text (`insertUnderMarker.ts:~105`, `replaceSection.ts:~70`); a note changed during apply can misplace an insert. Named to Hashi in the handoff as an observation; the new action is built safe.
- `insert_under_marker` skips only a byte-identical block anywhere in the note; a block added by another set between plan and apply yields a second block (low likelihood; `set-exists` guards the common case).
- The pacer never narrows after a retry (`review_pacer.py:66-67`); one early 429 in a quarter stretches the read to ≈ 13 min.
- Week-level own-section text in the boundary weeks of a quarter cannot be clipped by day (as for a month today).

### Technical Debt

- `review-instructions.py` (511) and `lib/period.py` (486) stay near or over the L2 guide; this design adds only thin wiring there; a split of `period.py` (parsing vs model) is a follow-up.
- `setup-input` stays offline; eligibility of a row is checked against `match` evidence, not re-read.
- If the measured quarter parts still exceed 256 KB, the next lever is a quarter-level character budget per day (`max_chars_per_day` does not bind today).
- The skill text grows (~1,000 chars for sections, a quarter branch, choice flags); the trim is #259.

### Implementation Gotchas

- Python `rstrip()` is not JS `trimEnd()` (U+001C–1F, U+0085, U+FEFF); use `JS_WS` as `review_actions.py:73-82` does.
- `%% fold %%` suffixes are part of a heading's text for Hashi; never normalise them away when emitting an anchor.
- `own_sections` compares bare text without level; off-limits rows carry level and parent — do not mix the two.
- `group_labels()` maps label text to groups across languages; a section heading must never pass through it.
- The `pass1_counts` consumers in `review_state.py` / `review_delivery.py` must accept section keys.
- Resume byte-identity: the action order and ids must not depend on dict order or on which sections had stops.
- The test vault's quarterly template opens with a Templater block before its frontmatter, so the spec 045 frontmatter question fires; there is no `_tomo` quarter variant.
- Pytest touching review setup must not write the real instances registry (reference memory).

## Glossary

### Domain Terms

| Term | Definition | Context |
|------|------------|---------|
| Mapped section | A heading of the user's periodic template that receives review material | Setup rows, document parts, delivery |
| Off-limits | A heading (optionally with its sub-sections) Tomo never writes into | ADR-8, F2-AC11 |
| Reminder / item | One short line reminding the user of something the period shows, with source links | F1-AC3 |
| Child review | The shorter-period review notes read for a longer period (weekly for a month, monthly for a quarter) | ADR-6 |
| Tomo Review | Spec 045's Tomo-owned section, now for what no mapped section takes | F1-AC7 |

### Technical Terms

| Term | Definition | Context |
|------|------------|---------|
| Block | Tomo's lines in a mapped section between its start and end markers | F4-AC2, ADR-4 |
| Row id | Opaque `s<n>` per template row, used in markers, document ids and meta | ADR-10 |
| Hashi text | A heading's text as Hashi parses it (trimmed, closing hashes kept) | Anchor emission |
| `CHILD` | Table from period kind to its child-review kind | `lib/review_period.py` |
| Partly applied set | An instruction set with some actions applied and some not | ADR-12 |

### API/Interface Terms

| Term | Definition | Context |
|------|------------|---------|
| `replace_between_markers` | New Hashi action replacing only the lines between two marker lines | Integration Points |
| `schema_version` "4" | Instruction wire version after the new action kind | ADR-5 |
| `--section-choice` / `--confirm-moved` | Pass 2 flags carrying the user's per-section choices | ADR-12 |
| `pass1_sections` | `meta.json` list of expected section keys and counts | ADR-11 |
