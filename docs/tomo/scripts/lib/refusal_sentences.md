# WHY: lib/refusal_sentences.py

> Rationale for decisions in `tomo/scripts/lib/refusal_sentences.py`.

## One home for refusal prose (spec 039 T2.1, SDD K16)

WHY the sentences are not in `render_actions.py`.

`_typed_name_refusal_reason` used to hold them inline, and the folder-name
refusals (T2.2) need sentences too. Two renderers phrasing refusals in two files
drift apart; one module keeps the register consistent and lets a sentence be
tested without assembling a Pass 2 fixture. `_typed_name_refusal_reason` is now a
one-line delegate so existing callers and tests keep their entry point.

## Unknown code raises (spec 039 T1.5)

WHY `ValueError` on an unrecognised reason: the old final `return` announced
any unknown code as a blank name. A wrong sentence tells the owner something
false about their input; a crash is found in CI.

## The `breaks_link` sentence (F5-AC3)

WHY it says a link to the name "would break" and never that Obsidian forbids
it: the vault accepts such a filename. The refusal is about what the name does
to links, and the wrong claim would send the owner hunting for a vault rule
that does not exist.

## Control characters are escaped (F5-AC7)

WHY `_visible` rewrites control characters as `\xNN` before quoting the name:
a raw control character inside the sentence would reach the rendered markdown
and reintroduce the very corruption the refusal exists to stop. Only
the sentence's own template text avoids spelling `{{` and `<%`; the echoed typed
name is shown verbatim and may contain them. That is acceptable because the
reason text is prose in a skipped entry, which is not path-shape validated, and
the end-to-end run with such a name exits 0 (pinned in
`tests/test_039_t2_1_breaks_link_and_unsafe_sequence.py`). The control-character
test is `is_control_char` from `lib/typed_name_check.py`, the single definition.

## Folder sentences

T2.2 adds the folder-name sentences beside `typed_name_sentence` in this module.

`folder_sentence(reason, folder)` covers the nine `FOLDER_REFUSAL_REASONS`
(spec 039 F2-AC5). It speaks only about the folder; the caller (T5.1) adds the
attachment name. Same rules as the name sentences: the typed text is echoed
through `_visible`, an unknown code raises `ValueError`, no remedy text. The
`breaks_link` tail says the character "would break the link" rather than that
Obsidian forbids it, because it does not (owner ruling 2026-10-12). `blank`
quotes nothing: there is nothing to show.
