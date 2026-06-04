---
phase: 2
title: "Scanner — atomic-note-indexer.py"
status: pending
---

# Phase 2: Scanner — atomic-note-indexer.py

## Phase Context

**GATE**: Read all referenced files before starting.

**Specification References**:
- `[ref: SDD/Runtime View/Primary Flow]` — the 7-step build flow + sequence diagram
- `[ref: SDD/Complex Logic]` — `build_accumulation_clusters` algorithm + traced walkthrough
- `[ref: SDD/Architecture Decisions/ADR-1, ADR-5, ADR-6]` — new script, per-candidate `up::`, configurable size
- `[ref: PRD/A5, A6]` — `up::` detection; empty-vault graceful degrade

**Key Decisions**: scanner is a NEW script (ADR-1), NOT a `moc-tree-builder.py` edit.
`up::` reads bounded to candidate-group members (ADR-5). `min_cluster_size` default 3 (ADR-6).

**Dependencies**: Phase 1 (`list_notes`, `read_inline_fields`, `extract_topics_from_fields`).

## Tasks

### T2.1 — `atomic-note-indexer.py` scanner `[activity: domain-logic]`

1. **Prime**: Read `[ref: SDD/Complex Logic]` (the algorithm + traced walkthrough) and `[ref: SDD/Runtime View/Primary Flow]`. Read `tomo/scripts/moc-tree-builder.py` for the topic-extract reuse + Kado-walk pattern and stem derivation (`basename_no_ext`). Read `tomo/scripts/read-config-field.py --help` for reading `concepts.atomic_note.base_path` and `tomo.accumulation.min_cluster_size` (default 3). Confirm the script's home matches the sibling `moc-tree-builder.py` location (SDD Directory Map note — `tomo/scripts/`, invoked as `scripts/` inside the instance).
2. **Test**: `tests/test_atomic_note_indexer.py` (inject a fake `KadoClient`): `test_cluster_emitted_when_min_unclassified_members` (3 unclassified sharing a topic → cluster); `test_classified_note_excluded_via_up_marker` (the traced-walkthrough case: a 4th member with `up::` dropped, group of 3 survives); `test_group_below_min_never_read_for_up` (assert `read_inline_fields` NOT called for sub-threshold groups — bounds cost, ADR-5); `test_up_read_dedup_across_overlapping_groups` (a stem in two candidate groups read once); `test_min_cluster_size_config_default_3`; `test_min_cluster_size_config_override`; `test_inline_field_read_error_treats_note_classified` (SDD Error Handling — conservative); `test_empty_vault_emits_empty_dict` (A6); `test_kado_unreachable_emits_empty_dict_and_nonzero_log`. Use a fixture mirroring the SDD traced walkthrough.
3. **Implement**: Create `tomo/scripts/atomic-note-indexer.py` (`# version: 0.1.0`, stdlib + `kado_client` + `topic-extract` only). CLI: `--config <vault-config.yaml>`, optional `--max-notes` (test bound). Flow per SDD §Complex Logic: `list_notes(base_path, fields=["links","headings","tags"])` → `extract_topics_from_fields` per note → `groups[topic].add(stem)` → candidate gate (`len >= M`) → per-candidate-member `read_inline_fields` (cache stem→unclassified, honour `relationships.parent.marker`, default `up::`) → keep groups whose unclassified count `>= M` → emit `{topic: sorted(stems)}` JSON to stdout. Module docstring states ADR-1/ADR-5 rationale. **Stderr-only logging** (never pollute stdout JSON — memory `feedback_never_redirect_stderr_into_json`).
4. **Validate**: `pytest tests/test_atomic_note_indexer.py -v`; `ruff check tomo/scripts/atomic-note-indexer.py`; run against a fixture, confirm stdout is valid JSON of the `{topic:[stems]}` shape; confirm `read_inline_fields` call count equals candidate-member count (cost bound).
5. **Success**: Clusters match the algorithm `[ref: SDD/Complex Logic]`; `up::` filter correct both ways `[ref: PRD/A5]`; empty vault → `{}` `[ref: PRD/A6]`; reads bounded to candidates `[ref: SDD/ADR-5]`.

> **Deviation watch** (SDD Risk §2): before locking, run `read_inline_fields` against a
> real note whose `up::` sits inside a `> ` callout. If Kado's `dataview-inline-field`
> does NOT return it, escalate per the Deviation Protocol — A5 then needs a
> body-regex fallback and the SDD must be updated.
