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

## One remedy per withheld kind (spec 039 T5.4, owner ruling 2026-10-12)

`withheld_attachment_remedy` is the only place a withheld attachment's remedy
is written. Before T5.4 the "Not filed" section (`render_actions.
_attachment_suppression_reason`) and the "Attachments still in the inbox"
bullet plus shell relay (`render_md._render_skipped_asset_notice`) each carried
their own remedy, and an end-to-end read of one rendered document found the
same item told two different fixes ("retype a usable folder for it, then re-run
Pass 2" against "correct the folder in the suggestions document and run
`/inbox --pass2 --force`"). The owner ruled one remedy per kind, from one
source; both renderers now end their line with this function's text.

WHY the commands are the ones the owner types (`/inbox --pass2 --force`,
`/inbox --recover`), never "Pass 1 / Pass 2": the owner runs commands, not
passes.

WHY the before-apply route is `/inbox --pass2 --force`, verified against
`inbox-triage.py`: after Pass 2 the suggestions document is promoted to the
terminal `approved` state. A bare `/inbox` does not read terminal-approved
documents at all (`read_approval_state` caches them only under
`force_pass2`, `inbox-triage.py:1096`, called with `force_pass2 or force_all`
at `:1337`), so it cannot see an edit to one and goes idle. `/inbox --pass2`
alone would see an edited body as drift (`detect_drift`, `:1441`;
`compute_coverage` drops drifted paths from `covered`, `:1381`) and
re-synthesize — but a remedy that changes only the vault (free the target,
rename a file) leaves the body unchanged, so the document stays covered and
`--pass2` goes idle (`determine_action`, `:1565-1568`). `--pass2 --force`
synthesizes all approved documents regardless (`:1566`), so one command works
for every kind.

WHY the after-apply route is `/inbox --recover`, not a bare `/inbox`: every
kind except `vault_collision_held` holds the notes that embed the attachment,
so after applying those notes are still in the inbox with
`tomo.state: captured` (Pass 1 marked them). Triage never re-intakes a captured
source without being told to — `compute_new_sources` counts only notes in no
state bucket, and the captured fold runs only under `--force` (not with
`--pass2`) or `--recover` (`inbox-triage.py:1275`, `:1603`, `:1644-1654`);
measured live in spec 038's runbook, where a bare `/inbox` skipped a captured
note. `--recover` is the single-flag form the same runbook found robust.

WHY "before you apply" and "If you have already applied" are separate
sentences: the earlier "before applying, …; afterwards, it is still in the
inbox, …" read "afterwards" as "after the step just named", and "it" had no
clear antecedent. The after-apply sentence names "the attachment" and "every
note that embeds it" — count-neutral, because several notes can embed one
attachment and the "Not filed" list names each of them.

WHY `vault_collision_held` keeps "rename the attachment in the inbox and run
`/inbox` again" after applying: its notes are filed, not held, so `--recover`
has nothing to re-intake. That route is unchanged from spec 037 and was not
re-verified in T5.4.

## The case-only occupier is not AT the target (spec 039 T5.4)

The case-only `vault_occupied` sentence read "the vault already holds
`…/Belegt.png` at the target `…/belegt.png`" — but the occupier sits at its own
spelling, not at the target. It now reads "holds `…/Belegt.png`, which differs
from the target `…/belegt.png` only in case — the filesystem may treat them as
one file — so the attachment is not filed over it". The exact-spelling ("a file
at the target") and folder variants are unchanged.

## The unchecked target ends in an owner action (spec 039 T5.4)

The unchecked sentence stated what was not known and stopped, leaving the
owner nothing to do. It now ends "You can apply this move as it is; to be sure
first, check in the vault that nothing is at `<target>`" — still never calling
the target free (F3-AC6).

## The after-apply remedy promises only what Pass 1 renders (spec 039 T5.4)

Owner ruling 2026-10-13: the after-apply half of a withheld-attachment remedy
used to say "choose the folder again" or "name it again", promising a control
that Pass 1 may not render. A Folder/name line appears in the suggestions
document only for an `attachment_conflicts` entry, i.e. only when the target
is still taken as Pass 1 runs again. The sentences now say what the re-run
does: for a refused typed folder or name it proposes the default target, and
offers the folder or name again only if that target is taken (otherwise the
attachment is filed there); for an occupied or colliding target it offers the
name again only if the target is still taken. Verified live in T6.3.
