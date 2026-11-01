# WHY: token-render.py

> Rationale for decisions in `tomo/scripts/token-render.py`.

## Note Tokens Use Local Time, `date_iso` Stays UTC (#202)

WHY: `uuid`, `datestamp` and `updated` end up in the owner's notes and were two hours
off, with the wrong date near midnight. `date_iso` prints a literal `Z`, so it must
stay UTC to remain true.
