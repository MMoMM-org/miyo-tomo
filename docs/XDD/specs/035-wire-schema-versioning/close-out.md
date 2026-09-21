# Spec 035 — close-out record (T4.5)

Written 2026-09-12, after T4.4 refreshed the three vendored consumer copies against Hashi's `main`
and the detection reached zero. Recorded here rather than in the plan because it walks two tables
the plan only points at, following spec 034's precedent.

One correction to the plan's own wording before the tables: T4.5 says "every PRD criterion in
**F1–F8**". There are **F1–F9** — F9 was added by T4.2b when the daily-side widening landed, after
the phase plan was written. All 33 are traced below, not 28.

## Quality Requirements (SDD)

| Quality | Target | Measured |
|---|---|---|
| Performance | Three schema walks per suite run, no network on the mandatory path | ✅ Full suite 116 s for 3960 tests; `test_wire_snapshot_parity.py` alone 0.67 s. Offline path proven under a dead proxy during T4.2 (`43 passed, 3 skipped`, the skips naming "Connection refused") |
| Usability | A failure names document, pointer, property, whether it obliges the consumer, and the next action | ✅ `test_035_wire_gate.py::test_affecting_change_with_version_unmoved_fails_and_demands_both_actions`, `::test_non_affecting_change_fails_and_demands_regeneration_only` |
| Security / Privacy | Metadata only — document names, pointers, property names, counts | ✅ `test_035_t4_2b_daily_source_identity.py::test_log_entries_content_never_appears_in_the_message`, plus a second non-parametrized guard that cannot be dropped by editing a parametrize list. This row is the one that was **violated and fixed** during T4.2b — see below |
| Reliability | Zero shape changes reach a published wire without a failing test or a regenerated manifest; after F6 the detection reports nothing across all three | ✅ `test_gate_passes_silently_on_the_real_committed_tree` (all three permitted) and a refused case per wire; detection at zero — the closing condition, below |

### The row that was violated in flight

The Security / Privacy row is not a clean pass on the first attempt and should not be recorded as
one. T4.2b's raise was specified to "name the entry's discriminating value" without checking what
that field is per bucket; for `log_entries` it is `content`, so the message quoted a user's daily-
note text into a `ValueError` — the exact thing MiYo Constitution L2 forbids. The test added
alongside asserted the value was *present*, so it encoded the violation. Fixed by mapping each
bucket to a permitted locator (`field`, `source_stem`, `target_stem`) and by two independent guards.
Recorded here because a close-out that shows only the final green hides the mechanism that produced
it.

## PRD Acceptance Criteria — all 33

Two criteria are **consumer-owned**: their condition is an act by Hashi, not by us. Both are now
discharged, and one of them acquired a test in the process.

### F1 — The detection sees a shape change (5)

| AC | Evidence |
|---|---|
| F1-AC1 | `test_035_wire_diff.py::test_added_property_reported_with_pointer_and_name`; depth by `test_035_wire_shape.py::test_nested_objects_under_items_reached_at_every_depth`; document naming by `test_035_wire_gate.py::test_two_wires_changed_in_one_edit_are_both_reported_independently` |
| F1-AC2 | `test_035_wire_diff.py::test_removed_property_reported_with_pointer_and_name`, `::test_required_added_reported_when_a_field_joins_required`, `::test_required_removed_reported_when_a_field_leaves_required`, `::test_openness_change_is_its_own_kind` |
| F1-AC3 | `test_035_wire_shape.py::test_no_defs_schema_yields_nodes_for_inline_objects` + `test_wire_snapshot_parity.py::test_defs_free_schema_is_compared_non_vacuously` |
| F1-AC4 | `test_035_wire_shape.py::test_description_only_difference_is_manifest_identical` + `test_035_wire_classify.py::test_prose_only_edit_produces_no_change` |
| F1-AC5 | `test_035_wire_gate.py::test_gate_passes_silently_on_the_real_committed_tree`, `test_035_wire_manifests.py::test_manifest_round_trips_against_committed_file`, `test_035_wire_diff.py::test_real_manifests_diff_against_themselves_are_empty` |

### F2 — The bump rule distinguishes consumer-affecting changes (5)

| AC | Evidence |
|---|---|
| F2-AC1 | `test_035_wire_classify.py::test_property_added_to_closed_node_is_affecting` |
| F2-AC2 | `::test_property_added_to_open_node_is_not_affecting`, `::test_property_added_to_open_node_nested_inside_a_closed_one_is_not_affecting` |
| F2-AC3 | `::test_added_and_removed_enum_value_classify_oppositely` |
| F2-AC4 | `::test_required_field_removed_is_affecting` **and** `::test_optional_field_removed_is_not_affecting` — the criterion says "if required and not otherwise", so both halves are needed |
| F2-AC5 | `test_035_wire_gate.py::test_affecting_change_with_version_unmoved_fails_and_demands_both_actions` + `::test_affecting_change_with_version_moved_and_manifest_regenerated_passes`. Wording corrected 2026-09-10 during T2.3 — see the PRD's own note |

### F3 — A renderer reads its version (3)

| AC | Evidence |
|---|---|
| F3-AC1 | `test_035_wire_shape.py::test_no_renderer_hardcodes_schema_version` — under ADR-5 a literal is itself the defect, so this is stronger than the original wording |
| F3-AC2 | `test_035_wire_version.py::test_{suggestions,garden_audit,instruction}_render_emits_its_schemas_declared_version` |
| F3-AC3 | The same three: each redirects the renderer at a scratch schema declaring a different version and asserts the emitted value follows, with no code edit |

### F4 — The handover (5)

| AC | Evidence |
|---|---|
| F4-AC1 | `test_035_wire_schema_versioning.py::test_handoff_schema_attachment_byte_identical` — passing, but **conditional**: it skips when `_outbox/for-hashi/` holds no attachment, and that directory is gitignored. It passed in the checkout that shipped this |
| F4-AC2 | Not testable here — a property of the handoff document. Confirmed by the consumer instead, which is better evidence than a test: Hashi's reply §2 says "we could tell in one read which change broke us, which was benign, and which was not travelling" |
| F4-AC3 | Same, and confirmed the same way — their §1 table reproduced the "breaks now" vs "benign" split row for row against their own validators, with no correction |
| F4-AC4 | Not testable — nothing in the code enforced the suspension. Evidenced by the fact that it held: no run was emitted between 2026-09-11 and the reply on 2026-09-12. It held because it was written down and honoured, which is the honest way to record it |
| F4-AC5 | **Consumer-owned.** Discharged 2026-09-12: Hashi merged PR #134 (`f799588`), and T4.4 refreshed and resumed. The version was emitted only after confirmation |

### F5 — The two instruction documents (3)

| AC | Evidence |
|---|---|
| F5-AC1 | `test_035_schema_identity.py::test_producer_id_differs_from_canonical` + `::test_contract_id_unchanged_at_canonical_url` |
| F5-AC2 | `::test_producer_identifies_its_role`. Narrowed by owner decision to the producer copy only — a line in the verbatim mirror dies at the next re-vendor, and T4.4 re-vendored, which would have proved the point |
| F5-AC3 | `test_wire_snapshot_parity.py::TestHashiSchemaParity::test_link_to_moc_props_match_snapshot`, `::test_move_note_props_match_snapshot`, `::test_snapshot_carries_tomo_block` |

### F6 — The garden-audit disclosure (3)

| AC | Evidence |
|---|---|
| F6-AC1 | Not testable — a property of the handoff document, which stated the two fields have been emitted since spec 030. Hashi's §1 confirms they read it that way and accepted both as benign |
| F6-AC2 | **Consumer-owned.** Discharged, and it acquired a test: `test_wire_snapshot_parity.py::test_garden_audit_comparison_a_is_clean_offline` |
| F6-AC3 | `::test_garden_audit_comparison_a_is_clean_offline`, `::test_suggestions_comparison_a_is_clean_offline`, `::test_instructions_comparison_a_is_clean_apart_from_sanctioned` |

### F7 — The failure says what to do (2)

| AC | Evidence |
|---|---|
| F7-AC1 | `test_035_t4_2b_daily_source_identity.py::test_widened_log_links_unmoved_version_fails_and_demands_move` |
| F7-AC2 | `test_035_wire_gate.py::test_non_affecting_change_fails_and_demands_regeneration_only` |

### F8 — The upstream freshness check (2)

| AC | Evidence |
|---|---|
| F8-AC1 | `test_wire_snapshot_parity.py::TestHashiSchemaParity::test_snapshot_matches_upstream_hashi` and its `_suggestions_` / `_garden_audit_` siblings. Each is a **run-dependent pass**: it compares only when the fetch succeeds and otherwise skips, which is F8-AC2's behaviour, not a failure. On the close-out run, two compared and one skipped on `IncompleteRead`. All three have been observed passing across T4.2–T4.4 |
| F8-AC2 | `::TestUpstreamFetchSkip::test_fetch_failure_skips_and_offline_checks_still_run`, parametrized over three exception families because `IncompleteRead` does not inherit from `OSError` |

### F9 — The daily side carries its source identity (5)

Added by T4.2b, after the phase plan was written.

| AC | Evidence |
|---|---|
| F9-AC1 | `test_035_t4_2b_daily_source_identity.py::test_bucket_declares_source_item_key_required`, parametrized over all three buckets |
| F9-AC2 | `::test_log_links_carries_source_item_key_when_emitted` — `log_links` is the bucket that could not be joined back by any means, and the one whose entries the parser had been silently dropping |
| F9-AC3 | `::test_display_fields_unchanged_alongside_the_new_identity` |
| F9-AC4 | `::test_restore_daily_item_keys_no_longer_exists`, `::test_nothing_calls_restore_daily_item_keys`, `::test_build_from_wire_needs_no_restore_step` |
| F9-AC5 | One handover, confirmed by the recipient: Hashi's §2 — "This message is the receipt for three documents across two of your specs" — and they asked for the format to be kept |

## The closing condition: the detection report is empty

The SDD names this as the risk the phase exists to retire — a mechanism whose report always carries
known noise is one nobody reads.

Measured 2026-09-12, after all three vendored copies were refreshed from Hashi's `main` and verified
byte-identical to what was sent:

| Document | Reportable | Sanctioned |
|---|---|---|
| `suggestions-wire.schema.json` | 0 | 0 |
| `garden-audit-wire.schema.json` | 0 | 0 |
| `instructions.schema.json` | 0 | 3 |

The three sanctioned entries are not noise being tolerated. They are the Tomo-owned
`properties.tomo` block, which by the 2026-06-20 handoff (miyo-tomo#74) evolves without a
round-trip and which Hashi ignores for execution, and the contract-only `$defs/replace_section`
definition that T3.2 gave the two documents distinct `$id`s over. Neither can reach Hashi's
validator, so counting them answers a question this comparison does not ask. They are partitioned
out by name, the partition returns what it excluded rather than discarding it, and the set is
pinned by three tests — the reasoning is in
`docs/tomo/scripts/lib/wire_snapshot_parity.md`.

**The instructions wire had never been measured whole-document before T4.4.** It carried only
targeted parity assertions, so its full delta was unknown in either direction when F6-AC3 was
written.

## Validation run

| Check | Result |
|---|---|
| Full suite | 3960 passed, 3 skipped |
| `-m integration` | 18 passed |
| `ruff check .` | clean |
| `scripts/wire-shape.py --check` | silent, exit 0 |

The three skips are `test_garden_audit_tomo_editor.py` (fixture absent from this checkout),
`tests/voice/test_transcriber.py` (needs a model directory), and one upstream-drift test whose fetch
returned `IncompleteRead`. That last one is **by design** — F8-AC2 requires an unreachable upstream
to skip rather than fail, and the count varies between runs because the fetch is genuinely flaky.
A run where all three upstream tests skip is as correct as one where none do.

## What the phase found that its tests did not

Recorded because the pattern generalises past this spec.

- **A detector is unproven until it has run against the real artefact.** Phases 1–3 shipped with
  ~3900 green tests and two review gates per task. The first run across the consumer's actual
  vendored schemas exposed two classifier defects — a false positive over-reporting live data 4:1,
  and a false negative where a vanished enum constraint reported silence — plus a live drift
  (`parent_not_moc`) from the very commit the spec's own decision log already cited for two other
  fields.
- **Reaching zero can make the tests that measured the delta vacuous.** Five tests asserted the
  known delta and went red the moment the copies were refreshed. Rewriting them to assert emptiness
  needed a mutation control, because `reportable == []` passes just as well against a comparison
  broken into always returning nothing. Proven by sabotage: 10 tests fail, including all three
  rewritten ones.
- **A vendored copy can be semantically current and not a literal mirror.** The instructions copy
  differed from upstream in five em-dash escapes; `json.loads` makes them identical, so the
  structural drift check read clean. Hashi named the mirror-image blind spot in their §7 — their
  diff compares structure, not bytes — and it applies in both directions.

## Still open at close-out

- **Hashi's §5 item 2**: a fixture exercising all three daily buckets including a real log link.
  It blocks their `SuggestionsTab.ts` fan-out fix and cannot be produced from any existing run —
  the four current-shape runs have empty daily buckets and the one run with daily content is
  pre-034. It needs a new run, which only became possible when emission resumed.
- **Spec 036's `depends_on` row** on the instructions wire. The release handoff told Hashi
  explicitly that it is not part of this release and why. Whether 036 supplies it in a follow-up
  message or waits for the next release is undecided.
