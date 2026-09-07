# 034 T5.3 — no-clash action-list baseline

`actions.json` is the **whole** action list `lib.render_actions.build_actions`
emits for `input.json`, a run in which no two items claim one destination.

- **Recorded at commit `9afcf73`** — spec 034, Phase 5, with **no T5.3 code
  written**. That order is the point: a baseline recorded after the validation
  pass exists would pin whatever the new code happens to produce, which proves
  nothing. Recorded before, it is evidence that the pass changes nothing on a
  clean run `[ref: PRD/Feature 7]`.
- Produced by `record.py` in this directory (`./venv/bin/python
  tests/fixtures/034-t5-3-actions-golden/record.py` from the repo root), with
  `kado_client=None` so no vault is touched (CON-7).
- Asserted whole-list, not field-by-field, by
  `tests/test_034_t5_3_destination_validation.py`. Action ids are counter-based
  and every path, title and reason is derived deterministically from the input,
  so no normalisation is needed — and none should be introduced: a normaliser
  is a place for a real regression to hide.

The fixture deliberately spans every action kind the pass must leave alone:
`create_moc`, three `move_note` (one at the inbox root, two in different
subfolders), `move_asset`, `link_to_moc` from both emission paths,
`update_log_entry`, and all four `delete_source` flavours — the explicit
skipped-item delete, the daily-only delete, the origin-consumed delete, and the
audio-peer delete. The last two are the ones a dropped move must take with it.

Regenerate only for a deliberate, reviewed behaviour change — then the diff of
`actions.json` is the review.
