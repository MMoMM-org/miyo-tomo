# 034 T5.4 — duplicate-reference action-list baseline

`actions.json` is the **whole** action list `lib.render_actions.build_actions`
emits for `input.json`, a run in which **one** attachment is embedded by **two**
different notes. That is a duplicate reference, not a destination clash: the
file is filed once and both notes move. PRD Feature 8's third acceptance
criterion says this path is unchanged by T5.4, and this fixture is what
"unchanged" is measured against.

- **Recorded at commit `1edaccd`** — spec 034, Phase 5, with **no T5.4 code
  written**. That order is the point: a baseline recorded after the suppression
  pass exists would pin whatever the new code happens to produce, which proves
  nothing. Recorded before, it is evidence that the pass leaves the
  duplicate-reference path alone `[ref: PRD/Feature 8]`.
- Produced by `record.py` in this directory (`./venv/bin/python
  tests/fixtures/034-t5-4-duplicate-reference-golden/record.py` from the repo
  root), with `kado_client=None` so no vault is touched (CON-7).
- Asserted whole-list, not field-by-field, by
  `tests/test_034_t5_4_attachment_clash_suppression.py`. Action ids are
  counter-based and every path, title and reason is derived deterministically
  from the input, so no normalisation is needed — and none should be
  introduced: a normaliser is a place for a real regression to hide.

The fixture spans what the suppression pass must not disturb: `move_note` for a
root-level note and for two notes in different subfolders, the single
`move_asset` both subfolder notes reference, `link_to_moc`, and the two
`delete_source` flavours a suppressed move would have to withdraw — the
origin-consumed delete and the audio-peer delete. If the pass ever mistook a
second *reference* for a second *file*, both subfolder notes would lose their
move and all three of their deletes, and this list would change.

Regenerate only for a deliberate, reviewed behaviour change — then the diff of
`actions.json` is the review.
