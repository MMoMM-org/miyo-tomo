# WHY: lib/refusal_sentences.py

> Rationale for decisions in `tomo/scripts/lib/refusal_sentences.py`.

## One home for refusal prose (spec 039 T2.1, SDD K16)

WHY the sentences are not in `render_actions.py`.

`_typed_name_refusal_reason` used to hold them inline, and the folder-name
refusals (T2.2) need sentences too. Two renderers phrasing refusals in two files
drift apart; one module keeps the register consistent and lets a sentence be
tested without assembling a Pass 2 fixture. `_typed_name_refusal_reason` was a
one-line delegate for a while; it was removed in the spec 039 T4.3 tidy and
callers use `typed_name_sentence` directly.

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

**`blank` covers an unreadable folder line (spec 039 T5.1).** A malformed folder
line (no backticks, a lone backtick, text after the closing one) and two folder
lines that disagree both reach the plan as `""` and are refused `blank`. The
first wording, "the typed folder is blank", told those owners they left it
blank when they had typed something. The sentence now says the line "is blank
or could not be read as a single folder in backticks" — true of all three, and
cheaper than a tenth reason code that would have to cross the wire.

## The `vault_occupied` sentence (spec 039 T4.2, F3-AC5)

WHY it lives here and not in the plan: K16 is the one home for owner-facing
prose, including one sentence per new withheld kind (SDD K16). The plan only
chooses the sentence.

WHY it names the occupier as the vault spells it and appends a case note when
the spellings differ: Rule 2 treats a case-only match as occupied, and an owner
told `karte.png` is taken while the vault shows `KARTE.png` needs to see why.
It never says "a note already exists" — the note-clash sentence in
`render_actions` is written for notes and would misdescribe an attachment.
A folder at the target name has no file spelling to show, so that variant names
the target only.

## The case note needs a visible difference (spec 039 W7)

Since target keys normalise to NFC (`vault_paths.path_key`), an NFD target can
be found occupied by an NFC file of the same visible name. The `vault_occupied`
sentence appends its case note only when the two spellings differ after NFC
(`vault_paths.same_spelling`); an NFC/NFD pair reads as the plain sentence,
because "the names differ only in case" would describe a difference that does
not show. When the occupier is spelled exactly as the target, the sentence says
"a file" at the target instead of naming the same path twice.

## Sentences for a move that is emitted (spec 039 T5.1)

`unchecked_target_sentence`, `folder_created_sentence` and
`qualified_embed_sentence` live here for the same reason the refusal sentences
do: one home for owner-facing prose (K16). They state only what was verified.
The unchecked sentence says the vault did not answer and never calls the target
free (F3-AC6); its consequence clause ("if the move fails, the attachment and
the source note that embeds it stay in the inbox") is the origin-keeping
contract of ADR-10 (the sentence is read by an owner before apply, so it says
"before this move was put into the instructions"), the same one the Ignore disclosure states (F6-AC8).
"Will be created on apply" is the executor's documented contract (PRD A3).
`qualified_embed_sentence` raises `ValueError` on a reason other than
`ambiguous` / `unanswered`, like every function here that takes a code.
