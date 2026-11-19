# WHY: lib/review_instructions_run.py

> Rationale for decisions in `tomo/scripts/lib/review_instructions_run.py`.
> Split out of `review-instructions.py` at spec 046 T6.4; the script's own
> page is `docs/tomo/scripts/review-instructions.md`.

## WHY the Run and Its Builder Are a Lib

`review-instructions.py` stood at 510 lines (constitution L2: 300 to 500).
The context of one call carries no CLI knowledge: it is data (`Run`), the way
two exits are signalled (`Refused`, `NotFound`) and the reads that fill it. It
moved unchanged so the four subcommands and `main` stay in the script.

## WHY `build_run` Receives the Vault and the Document Read

The script constructs `Vault(KadoClient)` and calls `read_document`, because
the tests replace those two names on the script module. Passing the results
in keeps the lib free of any client construction and of an import back into
the script; `Refused` and `NotFound` live here so both sides import them from
one place.

## WHY the Set Is Read Before the Target Note

Hashi applies a set at any time. Reading the note first and the set after
could pair a stale note with an applied set and plan a second insert. With
the set first the worst case is a set newer than the note, which `deliver`
treats as a set to write over (`set_replaced`). Fixed at T6.2 and pinned by
`test_the_set_is_read_before_the_target_note`; T6.4 kept it through the split.

## WHY `set_paths_of` and `setup_of` Are Public

`drop` needs the same setup lookups and the same refusals as `load_run`
(`setup-missing`, `setup-invalid`, `inbox-not-configured`). One function per
lookup keeps the refusal tokens in one file; the skill tests read them from
here.
