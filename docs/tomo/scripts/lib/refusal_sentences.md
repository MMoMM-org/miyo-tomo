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
and reintroduce the very corruption the refusal exists to stop. The
`unsafe_sequence` sentence also avoids spelling `{{` and `<%` literally, for the
same reason.

## Folder sentences

T2.2 adds the folder-name sentences beside `typed_name_sentence` in this module.
