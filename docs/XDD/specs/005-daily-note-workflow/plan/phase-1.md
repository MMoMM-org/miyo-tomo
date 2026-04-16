# Phase 1 — Schema + Config

## Goal

Lock the new data contracts: polymorphic `updates[]`, extended
`vault-config` schema for tracker descriptions and `daily_log`, regenerate
the result-template. Nothing runs end-to-end yet; this is the foundation.

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

### 1.1 Schema extension

Update `tomo/schemas/item-result.schema.json` `update_daily` branch:

- `updates[]` becomes `oneOf` of `update_tracker` / `update_log_entry` /
  `update_log_link` (three `$defs`).
- `update_tracker`: existing shape (`{field, value, syntax, confidence}`)
  plus required `kind: "tracker"`, plus optional `reason`, optional
  `section`.
- `update_log_entry`: `{kind: "log_entry", content, reason, confidence,
  time?, time_source?}`.
- `update_log_link`: `{kind: "log_link", target_stem, reason, confidence,
  time?, time_source?}`.

One item can emit multiple `update_daily` actions (different
`daily_note_stem`s). No schema change needed at the action level — just
allow N `update_daily` entries in `actions[]`.

### 1.2 Validator extension

`scripts/validate-result.py`:

- Recognise and validate the polymorphic `updates[]` shape.
- Forbidden-aliases extension for `update_daily` inner entries:
  - In a `tracker` entry: reject `"type": "tracker"` (use `kind:`).
  - In a `log_entry`: reject `"text":` (use `content:`).
  - In a `log_link`: reject `"target":` (use `target_stem:`).
- Migrate legacy entries without `kind` → treat as `kind: "tracker"`
  (emit a warning, not an error).

### 1.3 Template regeneration

Run `scripts/template-from-schema.py` against the updated schema to
regenerate `tomo/templates/item-result.template.json`. Verify the new
template includes one example of each update kind.

### 1.4 vault-config.yaml example extension

Update `tomo/config/vault-example.yaml`:

- Tracker fields: add `description`, `positive_keywords`,
  `negative_keywords` columns to each `today_fields[]` entry (with
  realistic MiYo examples).
- New top-level section `daily_log` with every key documented
  (inline YAML comments explain each).

### 1.5 Fixtures & tests

Create `scripts/test-005-phase1.sh`:

- Given a result with mixed tracker + log_entry + log_link updates → validator passes.
- Given a result with `tracker` entry missing `kind:` field → validator migrates (warns) and passes.
- Given a result with `log_entry` using forbidden `text:` alias → validator fails with hint.
- Given a regenerated template → `python3 scripts/validate-result.py --result templates/item-result.template.json` passes.

## Tests

- [ ] `bash scripts/test-005-phase1.sh` exits 0.
- [ ] `bash scripts/test-004-phase3.sh && bash scripts/test-004-phase4.sh` still pass.

## Hand-off to Phase 2

Phase 2 populates shared-ctx with tracker descriptions + daily_log
settings. Schema + validator already accept the shape.
