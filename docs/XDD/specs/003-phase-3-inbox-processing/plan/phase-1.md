---
title: "Phase 1: Python Scripts"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Python Scripts

## Phase Context

**Specification References**:
- `docs/specs/tier-3/inbox/state-tag-lifecycle.md` — state machine, tag format, discovery priority
- `docs/specs/tier-3/templates/token-vocabulary.md` — token resolution system
- `docs/specs/tier-3/inbox/suggestions-document.md` — suggestions format for parser

**Dependencies**: Phase 1+2 complete (kado_client, profiles, config, discovery cache)

---

## Tasks

- [ ] **T1.1 State Scanner** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/specs/tier-3/inbox/state-tag-lifecycle.md]`
  2. Test: Discovers items by lifecycle state via Kado tag search; supports all 7 states (captured, proposed, confirmed, instructions, applied, active, archived); returns JSON with paths, states, timestamps; handles configurable tag prefix; implements run-to-run discovery priority (applied→confirmed→captured)
  3. Implement: Create `scripts/state-scanner.py` — uses kado_client to search by tag `#<prefix>/<state>`, outputs JSON. Flags: `--config`, `--state STATE`, `--discover` (auto-priority), `--help`
  4. Validate: Syntax check passes; `--help` works
  5. Success: Script discovers items by state and implements priority ordering

- [ ] **T1.2 Token Renderer** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/specs/tier-3/templates/token-vocabulary.md]`
  2. Test: Resolves all 5 token categories (generated, config-sourced, content, metadata, custom); generates uuid/datestamp/updated; reads config defaults for optional fields; handles YAML list formatting for tags/aliases; preserves Templater syntax; skips tokens inside code blocks; handles required vs optional (error vs empty string); supports `\{\{` escaping
  3. Implement: Create `scripts/token-render.py` — reads template from stdin or `--template FILE`, takes token values as JSON via `--tokens FILE` or `--tokens-json STRING`, outputs rendered content to stdout. Uses vault-config.yaml for config-sourced tokens.
  4. Validate: Syntax check; render sample template with sample tokens
  5. Success: Templates render correctly with all token types; Templater syntax preserved

- [ ] **T1.3 Suggestion Parser** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/specs/tier-3/inbox/suggestions-document.md]`
  2. Test: Parses confirmed suggestions document; extracts per-item sections (S01, S02...); reads checkboxes (approved/skipped/deleted); reads user-modified fields (title, MOC, tags, classification); outputs JSON with confirmed items and their parameters
  3. Implement: Create `scripts/suggestion-parser.py` — reads suggestions markdown from file or stdin, parses sections and checkboxes, outputs JSON array of confirmed items with their field values
  4. Validate: Syntax check; parse sample suggestions document
  5. Success: Parser extracts confirmed items with all user modifications

- [ ] **T1.4 Phase Validation** `[activity: validate]`

  - All 3 scripts pass syntax check. token-render.py renders sample template. suggestion-parser.py parses sample document.
