# 034 T6.2 — flat-inbox instruction-set baseline

`instructions.md` is the **whole** human-readable instruction document the
Pass-2 chain produced for `suggestions.md` — three plain root-level notes, no
name collisions, no attachments. It is the Pass-2 counterpart to
`034-t3-4-flat-golden`, which pins Pass 1 for the same shape of inbox.

- **Recorded at commit `ee44cb3`** — the commit immediately preceding Phase 1,
  mirroring T3.4's choice. No pre-034 instruction-set golden existed:
  `034-t3-4-flat-golden` is a Pass-1 *suggestions document*, and the two action
  goldens are mid-Phase-5 JSON. `ee44cb3` is a verified clean baseline, not an
  assumed one — all 20 commits touching a Pass-2 file between it and HEAD
  (`instruction-render.py`, `suggestion-parser.py`, the three `lib/render_*.py`)
  are this spec's own `fix(034)`/`feat(034)` work, so the golden pins spec 034's
  changes and nothing else.
- Produced by `record.py` in this directory:

      ./venv/bin/python tests/fixtures/034-t6-2-instructions-golden/record.py

  It reaches the old code with `git worktree add <scratch> ee44cb3`, never with
  per-file `git show`. `instruction-render.py` at that commit imports fifteen
  `lib/*` modules and shells out to `token-render.py`; a single dependency
  resolved from HEAD would run the old renderer against a new helper and
  produce a baseline that is neither old nor new, with no visible symptom.
  `record.py` asserts afterwards that every loaded `lib.*` module came from the
  scratch tree, then tears that tree down. The repository's own worktree is
  never checked out to another commit.
- **Asserted by `tests/test_034_t6_2_pipeline_integration.py`**, class
  `TestFlatInboxInstructionGolden`, whole-document rather than field-by-field.

## Why the assertion is not a byte-compare

One change in this spec deliberately alters a *flat* inbox's instruction
document: T5.5 (`e3aefec`) replaced the hardcoded delete-source heading
`Delete source note (content captured in daily note)` — which stated one of the
five causes `delete_source` is emitted for, and contradicted the Action line
beneath it for the other four — with `Delete source note: <stem>`.

Re-recording the golden at HEAD would have absorbed that change and destroyed
the evidence. Instead the golden stays the OLD document and the test compares
against an enumerated `DELIBERATE_DELTAS` list. Anything diverging that is not
named there fails, even though it is one line; anything named there is reviewed
once, in that list.

## Files

| File | Role |
| --- | --- |
| `suggestions.md` | The approved Pass-1 document, checkbox pre-ticked, as a user hands Pass 2 |
| `suggestions-doc.json` | Its structured sidecar — `synthesis-conductor` passes both |
| `vault.json` | The fake vault: templates, the target MOC, and the three source notes |
| `vault-config.yaml` | The Pass-2 config both sides read |
| `fake_kado.py` | The read-only client both the recording and the replay use |
| `record.py` | Re-derives `instructions.md` from `ee44cb3` |
| `instructions.md` | The baseline |

Recording and replay share `fake_kado.py` and `vault.json` deliberately: a
baseline taken against a different fake than the replay would compare two
pipelines *and* two vaults, and nothing would say which one moved.

## Normalisation

Three render-time stamps are replaced, and nothing else — a normaliser is a
place a real regression can hide, so the set is kept minimal and the test
asserts that no other line carries a placeholder:

- `generated:` → `generated: <NORMALISED>`
- `  updated_at:` → `  updated_at: '<NORMALISED>'`
- the `YYYY-MM-DD_HHMM_` filename prefix → `<STAMP>_`

The `--upstream-path` argument is deliberately stamp-free, so every `<STAMP>`
in the golden is one the renderer minted rather than one the fixture handed it.

Regenerate only for a deliberate, reviewed change of baseline — and then the
diff of `instructions.md` is the review.
