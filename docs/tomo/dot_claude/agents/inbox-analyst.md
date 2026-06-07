# WHY: inbox-analyst

> Rationale for decisions in `tomo/dot_claude/agents/inbox-analyst.md`.
> The agent classifies ONE inbox item per invocation: reads shared-ctx + note
> content via Kado, writes a structured result.json, updates the state-file.

## Condition B (Accumulation Cluster Trigger) Retired — T3.2 (spec 021 ADR-10)

WHY: Step 4 originally had three conditions: A (Classification Guard), B
(Accumulation cluster trigger), C (Placeholder MOC trigger). Condition B
matched item topics against `shared_ctx.accumulation_index` — a map of
topic strings that had accumulated enough notes to warrant a new MOC — and
set `needs_new_moc: true` + `proposed_moc_topic` on a hit.

Condition B was retired for two reasons rooted in spec 021 and F-34 Condition
B viability analysis:

1. The accumulation index was sourced from `unclassified_topic_clusters` in
   the MOC-cache, which was produced by `atomic-note-indexer.py`. Spec 021
   moved vault-wide MOC discovery to `/moc-propose` (a dedicated command). The
   inbox pipeline no longer needs to scan for accumulation-worthy clusters per
   item — that is the job of `/moc-propose`. Keeping Condition B in the inbox
   analyst would create a parallel, lower-quality discovery path that conflicts
   with the dedicated command.

2. `shared_ctx.accumulation_index` was removed from the shared-ctx schema in
   T3.1. With the field gone from the schema, Condition B was harmless-but-dead:
   the `absent → skip silently` guard meant it never fired. T3.2 removes the
   dead prose to keep the agent spec lean and unambiguous.

Condition C (Placeholder MOC trigger) is the retained value: it surfaces
deliberate dead wikilinks the user already wrote as `needs_new_moc` signals,
which is a higher-confidence source of intent than freshly-inferred topic
clusters. The placeholder-wins precedence (F4#4) was expressed in the
A7-vs-B STRICT block that guarded against Condition B overwriting Condition C.
Since Condition B is gone, the STRICT block is also removed — the precedence
is now implicit in ordering: C runs before B ran, and B no longer exists.

## A7 STRICT Block Removed With Condition B

WHY: The STRICT block `# STRICT — A7 (Condition C wins over Condition B)`
existed solely to prevent Condition B from overwriting a `proposed_moc_topic`
already set by Condition C. With Condition B removed, the enforcement context
is gone. The placeholder-wins intent is preserved structurally: Condition C
runs and sets `proposed_moc_topic`; nothing afterwards can overwrite it.

## Condition A and Condition C Text Fully Preserved (T3.2 regression gate)

WHY: T3.2 only removes Condition B and its associated STRICT block. Condition A
(Classification Guard — prevents pre-checking `is_classification: true` MOCs)
and Condition C (Placeholder link trigger — verbatim casing on `proposed_moc_topic`,
F4#2; placeholder-wins-over-inferred precedence, F4#4; silent skip when
`placeholder_links` absent/empty) are unchanged. Test
`tests/test_inbox_analyst_no_condition_b.py` asserts both are intact.

## Version 0.15.0

WHY: Bumped from 0.14.0 for terminology rename: `placeholder_mocs` →
`placeholder_links` / "Placeholder MOC trigger" → "Placeholder link trigger"
(behavior-identical rename). `update-tomo.sh` skips unchanged versions
silently — the bump is required for the edit to ship to the Docker instance.
