---
phase: 1
title: "Schema + config"
status: completed
depends_on: []
---

# Phase 1 — Schema + Config

## Phase Context

**GATE:** Phase 2 cannot start until `update_daily.updates[]` in
`item-result.schema.json` accepts polymorphic `tracker | log_entry | log_link`
entries AND `vault-config.yaml` example shows tracker descriptions +
`daily_log` section.

**Spec refs:**
- `solution.md` §Interface Specifications (vault-config schema, shared-ctx,
  item-result schema polymorphic updates[])
- `requirements.md` Features 1–4, 6 (tracker-semantics config, polymorphic
  updates, multi-daily split, cutoff, time-extraction)

**Key decisions (ADRs):**
- ADR-2 Polymorphic `updates[]` rather than new top-level action kinds.
- ADR-4 Cutoff at `date_relevance.date` (default 30 days).
- ADR-5 `auto_create_if_missing` flags all `false` in MVP.

**Dependencies:** none — this phase lays the contract surface.

## Acceptance Gate

- [ ] `item-result.schema.json` validates a result whose `update_daily`
  contains mixed `tracker` / `log_entry` / `log_link` entries.
- [ ] `validate-result.py` flags malformed polymorphic entries with
  actionable errors.
- [ ] `template-from-schema.py` regenerates a template skeleton that
  includes an example of each of the three update kinds.
- [ ] `tomo/config/vault-example.yaml` documents `tracker_fields[]`
  descriptions + `daily_log` section with all keys.
- [ ] Existing Spec-004 tests still pass.

## Tasks

### Task 1.1 ✅ — Extend `item-result.schema.json` with polymorphic `updates[]` [activity: schema-design] [ref: SDD/§Interface Specifications — item-result.schema.json]

**Prime:** read current `update_daily` branch in
`tomo/schemas/item-result.schema.json`.

**Test:** validator fixture with mixed tracker / log_entry / log_link →
passes; fixture with legacy no-kind entry → passes with migration warning;
fixture with forbidden alias (`text:` inside log_entry) → fails with hint.

**Implement:** add three `$defs` (`update_tracker`, `update_log_entry`,
`update_log_link`); replace `updates[].items` with a `oneOf` discriminator.
`update_daily` at the action level stays unchanged.

**Validate:** `jsonschema`-based validation round-trip on fixtures.

**Success:** schema accepts all three variants + rejects forbidden aliases.

### Task 1.2 — Extend `validate-result.py` for polymorphic `updates[]` [activity: validation-logic] [ref: SDD/§Interface Specifications — validation]

**Prime:** read current `FORBIDDEN_PER_KIND_ATOMIC` + validation loop.

**Test:** legacy migration fixture (no `kind` field on update) → passes
with warning, canonicalises to `kind: "tracker"` in returned dict;
forbidden-alias fixtures fail with per-kind hints.

**Implement:** new `FORBIDDEN_PER_UPDATE_KIND` constant with hints per
variant. Update `validate_hand()` and jsonschema path to iterate
`updates[]` and apply per-kind required-field check.

**Validate:** all fixtures from Task 1.1 run through `validate-result.py`
and produce expected exit codes + stderr lines.

**Success:** 100% fixture pass; drift-hint messages clear.

### Task 1.3 — Regenerate `item-result.template.json` [activity: tooling] [ref: SDD/§Template-from-schema]

**Prime:** confirm Task 1.1 schema is valid JSON.

**Test:** generated template validates against the new schema;
validator's forbidden-alias checks do NOT trip on the generated template.

**Implement:** run `scripts/template-from-schema.py --schema ...
--output tomo/templates/item-result.template.json`. Commit the generated
file.

**Validate:** `python3 scripts/validate-result.py --result
tomo/templates/item-result.template.json` exits 0.

**Success:** template contains one example each of `tracker`, `log_entry`,
`log_link` inside an `update_daily` action.

### Task 1.4 — Update `tomo/config/vault-example.yaml` with tracker semantics + `daily_log` section [activity: documentation] [ref: SDD/§Interface Specifications — vault-config.yaml]

**Prime:** read current `trackers:` and post-tracker sections of
`tomo/config/vault-example.yaml`.

**Test:** the YAML parses cleanly; `shared-ctx-builder.py` (Phase 2 will
add, currently a stub) does not crash on the new shape.

**Implement:**
- Add `description`, `positive_keywords`, `negative_keywords` to every
  `today_fields[]` and `end_of_day_fields[].fields[]` entry with realistic
  MiYo examples (e.g. Sport, WakeUpEnergy, Highlights).
- Add new top-level `daily_log:` section with every key documented via
  inline YAML comments.

**Validate:** `python3 -c "import yaml; yaml.safe_load(open('tomo/config/vault-example.yaml'))"`
(inside venv with PyYAML).

**Success:** file parses; structure matches SDD §Interface Specifications.

### Task 1.5 — Write `scripts/test-005-phase1.sh` acceptance tests [activity: testing] [ref: requirements.md/Features 1–4]

**Prime:** read `scripts/test-004-phase3.sh` as stylistic reference.

**Test:** the test script itself must exit 0 on green, non-zero on red.

**Implement:** shell-driven Python assertions covering:
- Polymorphic updates[] round-trips through validator (all three kinds).
- Legacy no-kind update → migration passes.
- Forbidden aliases (`text:` inside log_entry, `target:` inside log_link)
  → validation fails with correct hint.
- Regenerated template validates against schema.
- `vault-example.yaml` parses.

**Validate:** `chmod +x scripts/test-005-phase1.sh && bash scripts/test-005-phase1.sh`
exits 0.

**Success:** script green; Spec-004 tests (`test-004-phase{2,3,4}.sh`)
still pass as regression.

## Hand-off to Phase 2

Phase 2 populates shared-ctx with tracker descriptions + daily_log
settings. Schema + validator already accept the shape.
