# WHY: lib/review_setup_rows.py

> Rationale for decisions in `tomo/scripts/lib/review_setup_rows.py`.
> The module holds the checks `review-session.py setup-input` runs on the
> section and off-limits rows of a confirmed setup before anything is saved
> (spec 046 T2.2; PRD F2-AC4, F2-AC11, F2-AC12, Rule 4; SDD Internal API
> Changes, Error Handling, ADR-3, ADR-10, ADR-13). It reads the rows file
> `match` wrote and the saved rows of the vault config; no Kado, no model.

## WHY the Checks Are a Module of Their Own

`review-session.py` was about 400 lines before T2.2. The refusals, the
evidence reading and the id assignment add about 150 more, which would push
the script past the constitution's L2 band (300–500 lines of dense logic).
The script keeps the argparse wiring and the order of the steps; this module
answers "may these rows be saved". The physical landing rule stays in
`lib/review_mapping.py`, the one owner of off-limits resolution (SDD component
table), so `setup-input` and the delivery plan cannot disagree.

## WHY the Evidence Is the Rows File `match` Wrote

ADR-3 keeps `setup-input` offline: it does not read the template from Kado
again, so a row's eligibility is checked against what `match` saw. Two
carriers were possible:

- the confirmed file the skill writes, with the `match` candidates copied into
  it, or
- `tomo-tmp/review/rows-<kind>.json`, which `match` itself writes (ADR-13).

The confirmed file is written by the model. A state, reason or heading list
carried there is one the model could change, drop or invent, and the check
would then confirm the model's own claim. The rows file is written only by a
script and the model writes no state file (CON-1), so `setup-input` reads the
evidence from there and ignores anything eligibility-shaped in the confirmed
file. This is as far as an offline check can go: a forged rows file is still
possible, but it takes a deliberate write to a script-owned file, not a
wrong field in the model's own output.

The rows file therefore carries, besides the rows shown (T2.1), the
template's heading outline — per heading its key, line, ancestors, body kind
and the structural reason (templater, link, per-period parent) — and the
template `match` resolved last with its kind (`resolved`). Off-limits and
`automatic` are not stored as verdicts: they depend on the off-limits rows,
and the user may mark new ones in the same Correct step. `setup-input`
re-runs those two rules (`review_mapping.from_outline`) with the confirmed
off-limits rows, so a heading the user just protected is refused at once.
Template headings are setup text (CON-3), the same text `match` already
prints in its candidates; no body line is stored.

## WHY `template-not-found` Reads `resolved`

ADR-13 / F7-AC1: a confirmed missing template is refused by a script, not by
prose (#267). `match` sets the proposal's template to null when Kado does not
find it, but the model could still put the name back. So `match` records in
`resolved` the name it tried and its kind (`missing` when not found), also
when it shows no rows, and `setup-input` refuses a confirmed template that is
not the one `match` resolved last, or that it resolved as missing.
This is conservative by design: `match` for A, then `match` for a B it does
not find, then confirming A is refused, because `resolved` now names B; the
user re-runs `match` with A.

Rows (sections or off-limits) need more: the outline must belong to the
confirmed template. Rows for a template whose outline the file does not hold
— no `match` ran, or the last readable template was another one — are
refused as `template-not-found` too: from `setup-input`'s side the template
the rows name was not found by `match`, and nothing can be checked.

Without any rows file, a confirmed setup without rows is accepted unchanged.
That is the spec 045 path (CON-2): every setup dialogue runs `match` first,
which now always writes the file, so a missing file means `setup-input` was
called without a dialogue; refusing it would break the saved-setup path for
nothing. An unreadable template (Kado refused the read) is `resolved` with its
own kind and is still accepted without rows, as in spec 045.

## WHY the Refusals Come in This Order

Per row, first rule wins, so the user sees the one reason that matters:

1. `section-not-in-template` — the heading key is not in the outline (also a
   saved row whose heading the template lost and the skill kept).
2. `section-off-limits` — the heading is covered by an off-limits row
   (`landing_off_limits`). Rule 4 comes before every other reason because it
   is the user's own mark.
3. For `placement: review` (an analysis row, F2-AC12): accepted only on a
   heading left out as `automatic`; an offered heading is
   `analysis-not-automatic`; a heading left out for another reason is
   `section-left-out` with that reason (the reason is the more useful answer).
4. For any other placement: a left-out heading is `section-left-out` with its
   reason (`templater`, `link`, `per-period-parent`, `automatic`); an offered
   heading is accepted, a `mixed` one included (F2-AC4).
5. `landing-off-limits` — a `before` or `end` placement whose lines would land
   in the body of a covered heading (`review_mapping.landing`): `before` lands
   in the heading above, `end` in the last heading inside the range. `under`
   lands in the mapped heading itself, already checked in 2.

The "Tomo Review" place (`place.anchor` + `place.placement`) runs the same
landing check (`before` as a row's `before`, `inside` as a row's `end`) on the
first template heading with the anchor text, the heading Hashi finds. An
anchor the template lacks is not checked here; the plan-time check on the
note still runs. The off-limits rows used are the confirmed ones, or the
saved ones of the template when the confirmed setup does not carry
`off_limits` — the place is saved either way.

Off-limits rows are not checked against the outline. A mark only restricts;
refusing an orphaned mark would force the user to remove a protection before
saving anything else.

`duplicate-section`, `duplicate-off-limits`, `duplicate-section-id` and a
malformed id (`schema` at its pointer) come from `review_config.input_problems`
before these checks run: an invalid row is never reasoned about.

## WHY Ids Are Assigned Before Validation

The schema requires an `id` on every section row (ADR-10), and the model must
not invent ids. `setup-input` gives every row without one its id first
(`review_mapping.assign_ids`): the id the saved row of the same heading key
holds — in the confirmed template, or in the configured one when the template
was corrected and keeps the heading — else the next number above every id
known. A row that already carries an id keeps it, so a malformed or repeated
one still reaches the schema and the duplicate check and is refused at its
pointer.

## WHY a Section Row Must Be Refused, Not Dropped

The skill could silently leave out a row the script would refuse. Then the
user believes a section is mapped that is not. Every refusal is
`status: invalid` with a pointer, and the skill shows it in the Correct step.
