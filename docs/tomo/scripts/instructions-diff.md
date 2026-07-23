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
