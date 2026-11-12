# WHY: lib/review_templates.py

> Rationale for decisions in `tomo/scripts/lib/review_templates.py`.
> The module owns the two questions `review-session.py match` can leave open
> for the setup dialogue (spec 045 F1-AC7, ADR-8): which template the
> periodic note of a kind uses when `templates.mapping` names none, and at
> which heading the review section sits when no template heading can be
> proposed.

## WHY This Left `review-session.py`

WHY: the script stood at 482 lines before the live-walk fix and the
Constitution caps dense files at ~300–500 LOC. Listing candidates and
reading the headings of recent periodic notes are two small rules with no
argparse and no proposal logic in them; the script keeps the precedence
(flag > mapping > candidates) and the output shape. What a template's
headings propose (`template_anchor_candidates`, `propose_anchor`,
`daily_sections_from`) and the join of a name onto `templates.base_path`
(`template_vault_path`) moved with them: they are template rules, and the
script stays under the cap with them gone.

## WHY the Candidates Come From a Listing, Not a Guess

WHY: the live walk (container session 5b959432): the owner's instance config
maps `daily`, `map_note`, `atomic_note`, `project` and `source` but not
`weekly` or `monthly`, while the templates folder holds `t_week.md`,
`t_week_privat.md`, `t_week_work.md` and their `t_month*` siblings. `match`
read the template only from `templates.mapping.<granularity>`, proposed
`template: null`, and — because the anchor comes from the template's headings
— `place.anchor: null`, a proposal `setup-input` rejects (`/place/anchor` is
a required trimmed string). The first draft's WHY said "no template search
is attempted when the mapping is absent: a guessed file would have to be
confirmed by the user anyway"; the walk showed the opposite cost — the user
cannot name a file the dialogue never showed. So `match` lists
`templates.base_path` once (the same `list_notes` call the periodic folder
gets, two levels deep, because template folders hold subfolders too) and
keeps the notes whose file name fits the kind: `week` or `woche` for a week,
`month` or `monat` for a month, case-insensitive. The words cover the
owner's English file names and German ones; a vault that names its templates
otherwise gets an empty list and the plain note, as before. The candidates
are sorted case-insensitively so the numbered question is the same on every
run and the user's "2" means the same file next time. Names are the path
below `base_path` without `.md` — what the user sees in Obsidian — and
`--template` takes that name with or without the extension; the proposal
and the saved mapping carry it with `.md`, as every other mapping entry.

The listing costs one Kado call and is spent only when neither the mapping
nor `--template` names a template; a `kado-none` answer (empty, or the key
does not reach the folder) gives an empty list and a hint that names the
folder, never "there are no templates" (Rule 6). No candidate is read before
it is chosen: reading three or four templates to show their headings would
spend reads on files the user is about to reject.

## WHY `--template` Refuses `..`, `\` and a Leading `/`

WHY: the name is joined to `templates.base_path` and read through Kado. A
name that climbs out of the folder would read a note outside the templates
folder and save that path into `templates.mapping`. The refusal is the
argparse type (exit 2, a bad invocation), the same class as a bad `--kind`,
so the skill shows the usage error and the user types another name. A `/`
inside the name is allowed: the candidates list subfolder entries as
`archive/Wochenplan alt`.

## WHY `needs_anchor` Reads the Two Most Recent Periodic Notes

WHY: `setup-input` requires an anchor, and the owner decided that the
dialogue asks for one rather than letting the proposal fail validation
after Confirm. Without a template heading to propose from — no template,
`0 none`, a template whose only heading is the title — the only headings
that exist before any review is written are those of the user's own
periodic notes. `match` reads the two notes with the latest period under
the proposed format and rule (one `read_note` each, two calls at most, spent
only when no anchor could be proposed) and lists their level-2-and-deeper
headings, most recent note first, document order, duplicates dropped. Two
notes, not one: the latest note may be a thin one the user has not filled
yet; not eight: the week inference already reads up to eight frontmatters,
and headings rarely change between weeks. A note whose read fails (the key
may not reach it) contributes nothing; an empty list still carries
`needs_anchor: true`, and the skill asks the user to type the heading. The
headings reach stdout by design — they are the structure of the user's
notes, the same text `review-instructions.py preview` prints as `headings`
for the place pick, and `tests/test_review_privacy.py` names the field.
