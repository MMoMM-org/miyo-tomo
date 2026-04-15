# Phase 2 — Phase A: Shared Context + State File

## Goal

Produce a validated `shared-ctx.json` (≤ 15 KB) and an `inbox-state.jsonl` for
a given run. Nothing is dispatched yet; this is pure preparation.

## Acceptance Gate (from SDD Acceptance Criteria)

- [ ] `WHEN /inbox is invoked AND discovery-cache.yaml exists, THE SYSTEM
  SHALL produce tomo-tmp/shared-ctx.json ≤ 15 KB within 5 seconds`
- [ ] `WHEN Phase A enumerates the inbox, THE SYSTEM SHALL write one line per
  item to tomo-tmp/inbox-state.jsonl with status: "pending"`
- [ ] `IF a MOC has no extracted topics, THEN THE SYSTEM SHALL use the MOC
  title as the topics fallback`

## Tasks

### 2.1 `shared-ctx-builder.py`

Inputs (CLI flags):
- `--cache config/discovery-cache.yaml`
- `--vault-config config/vault-config.yaml`
- `--run-id <run_id>`
- `--output tomo-tmp/shared-ctx.json`

Outputs (stdout log lines):
- `mocs_total=N mocs_included=M dropped_for_size=K`
- `tag_prefixes_included=N`
- `bytes=N schema_valid=true|false`

Logic:
1. Load discovery cache (YAML → dict)
2. Load vault-config, extract `tomo.suggestions.proposable_tag_prefixes`
   (default `["topic"]`), `excluded_tag_prefixes`, and
   `calendar.granularities.daily` (for daily_notes section — gated)
3. Build MOC list: for each MOC from cache, emit `{path, title, topics[],
   is_classification}`. If `topics` is empty, fall back to `[title]`.
4. Build tag-prefix list: intersect discovered prefixes with
   `proposable_tag_prefixes`, subtract `excluded_tag_prefixes`
5. Build `classification_keywords` from active profile (load profile YAML
   based on `vault-config.yaml` `profile` field)
6. Build `daily_notes` section ONLY IF `calendar.granularities.daily` is set
   (see Phase 4 for tracker_fields population — Phase 2 leaves it as
   `{"enabled": true, "path_pattern": "...", "date_formats": [...], "tracker_fields": []}`)
7. Serialise, check size ≤ 15 KB; if over, shorten `mocs[].topics` until under
8. Validate against `tomo/schemas/shared-ctx.schema.json`
9. Write to `--output`

### 2.2 `state-init.py`

Inputs:
- `--inbox-path "100 Inbox/"` (or from vault-config)
- `--run-id <run_id>`
- `--output tomo-tmp/inbox-state.jsonl`

Logic:
1. Call Kado `listDir` on the inbox path (via `kado_client`)
2. For each item whose filename does NOT end in a suggestions-doc suffix
   (`_suggestions.md`, `_instructions.md`), emit one state line:
   `{"run_id", "stem", "path", "status": "pending", "attempts": 0,
     "started_at": null, "completed_at": null, "error": null}`
3. Sort deterministically by filename
4. Validate each line against `tomo/schemas/state-entry.schema.json`
5. Write to `--output`

### 2.3 Resume Detection (in orchestrator prep)

The `/inbox` command (Phase 3 will fully wire this) inspects
`tomo-tmp/inbox-state.jsonl` on entry. For Phase 2 we only need the detection
primitive: add a small helper `state-summary.py` (optional — can inline in
orchestrator prompt) that reports counts of `pending`/`running`/`done`/`failed`
given a state file.

### 2.4 Integration Test

Write `scripts/test-phase2.sh` checks:
- Given a fixture `discovery-cache.yaml` with 3 MOCs and a `vault-config.yaml`,
  running `shared-ctx-builder.py` produces a valid ≤ 15 KB JSON
- Given an inbox with 3 items (one suggestions doc among them), running
  `state-init.py` produces exactly 2 state lines (suggestions doc excluded)

## Tests

- [ ] `bash scripts/test-phase2.sh` exits 0
- [ ] Running `shared-ctx-builder.py` against the live instance's
  `discovery-cache.yaml` produces a file ≤ 15 KB
- [ ] Running `state-init.py` against the live Kado inbox produces valid
  JSONL with every line passing the schema

## Hand-off to Phase 3

Phase 3 gets working Phase-A scripts. Orchestrator in Phase 3 will call them
in sequence before fan-out.
