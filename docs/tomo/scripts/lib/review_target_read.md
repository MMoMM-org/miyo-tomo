# WHY: lib/review_target_read.py

> Rationale for decisions in `tomo/scripts/lib/review_target_read.py`.
> The module holds the Kado reads Pass 2 of `/review` makes around the
> target note: a note's text, the period's note among the configured paths
> and elsewhere in the vault, and the template a new note is built from
> (spec 045 T4.2, ADR-13; split out of `review-instructions.py` at spec 046
> T6.2).

## WHY a Module of Its Own (spec 046 T6.2)

`review-instructions.py` stood at 536 lines against its 540-line cap. The
three readers are a cohesive seam — Kado in, texts out — that needs none
of the script's `Run`; the choice of target itself stays in
`review_actions.locate_target`, which has no Kado. They moved unchanged
except for one thing: an unparsable period returns None instead of raising
the script's `Refused`, so the lib has no import back into the script; the
script raises `setup-invalid` with the same pointer, before any note read,
as before. The order of reads `load_run` makes (the set before the note) is
the script's, not this module's.

## WHY the Candidates Are Read in Order and the Search Is the Fallback

The configured folder may hold the note flat or in a sub-folder; the
candidates are read in that order and the first that exists stops the
reads, so a week costs one read when the note is where the setup says. Only
when no candidate exists does a by-name search run — a moved note is found
and reported (`target_moved`, `duplicates`) instead of planning a second
note. The staged copy in the inbox (a new note this delivery wrote) is
never a hit: it is Tomo's own, and taking it would plan an insert into a
note Hashi has not created yet.

## WHY a NOT_FOUND Is None and Every Other Failure Stops

A missing note is a state the plan handles (a new note). A denied or failed
read is not absence: reading it as absent would plan a new note over one
that exists (`review_vault.kado_stops` turns it into `Stopped`).
