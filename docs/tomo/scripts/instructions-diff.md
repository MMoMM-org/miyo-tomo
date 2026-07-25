# WHY: instructions-diff.py

> Rationale for decisions in `tomo/scripts/instructions-diff.py`.
> Pass-2 coverage audit: parsed-suggestions.json vs instructions.json — the
> conductor's mandatory step 3e.

## Version 0.7.0 — dedicated garden-audit mode (2026-07-23)

WHY garden-shaped envelopes (confirmed_items carrying `garden_action`) route to
`run_diff_garden` instead of the suggestions math: `derive_expected` branches on
`item.action == "create_moc"` else counts a move_note — garden items carry
`garden_action`, not `action`, so EVERY garden fix was miscounted as an expected
move_note and the audit hard-failed (`move_note expected=N actual=0`) on any
garden-audit doc with confirmed items. Since the conductor's 3e is mandatory
("NEVER skip the coverage audit"), this pre-existing gap blocked every real
garden apply. The garden mode mirrors `render_actions.build_garden_audit_actions`
count math (edit_note_text→1, remove_up_link→1, add_relationship→1, file_note→
link_to_moc + add_relationship) plus path-anchored per-item coverage;
acked_advisories are displayed but expect no actions (they stamp the pushback
ledger, not instructions). Detection is shape-based (all items carry
garden_action) rather than a CLI flag so the conductor invocation stays unchanged.

## Version 0.8.0 — resolve_dead_link in the garden count math (2026-07-24)

WHY `_GARDEN_EXPECTED_KINDS` maps `resolve_dead_link → ("resolve_dead_link",)` (replacing the
`edit_note_text` entry) and `_garden_item_covered` anchors it on path + target: garden-audit's
dead_link fix moved from `edit_note_text` to the semantic `resolve_dead_link` action (see
garden-audit-parser.md 0.11.0), so the coverage audit must expect+match the new kind or every
dead-link fix would read as an uncovered item.
