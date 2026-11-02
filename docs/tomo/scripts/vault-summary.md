
## Why the tracker count sums field lists instead of taking a length

`_extract_tracker_field_count` used to read:

    daily = len(trackers.get("daily_note_trackers") or [])
    eod   = len(trackers.get("end_of_day_fields") or [])

Both keys hold objects, not lists. `daily_note_trackers` is
`{section, today_fields, yesterday_fields}` and `end_of_day_fields` is
`{section, fields}` — so `len()` counted keys. The live config, with fifteen
configured fields and no end-of-day block, reported **3**.

That is the whole reason it survived: 3 is a plausible number of trackers. A
count that came back as 0, or as 700, would have been questioned on sight.

**The fixture was the other half.** `tests/test_vault_summary.py` modelled the
section as flat lists of strings — `"daily_note_trackers": ["mood", "energy",
"focus"]` — a shape `vault-config-trackers.schema.json` does not permit. The
test asserted 5 and got 5, because three list items happened to equal three
dict keys. Correcting the fixture to the real nested shape *still* passed: the
new containers carried 3 and 2 keys, and 3 + 2 is 5 again.

The assertion only became capable of failing once the fixture used a field
count that could not coincide with a key count — four `today_fields`, one
`yesterday_fields`, two `end_of_day_fields.fields`, expecting 7 where the
key-based sum yields 5. A second test pins the live shape directly: one
container, one `section` key, fifteen fields, no end-of-day block.

**The rendered wording changed too.** `N tracker field group(s) detected` now
reads `N tracker field(s) detected`. "Group" described what the broken count
actually measured — containers — and would have read as correct forever.

## Guard

`tests/test_vault_summary.py::TestTrackerAndCalloutStats` — both tests proven
RED by restoring the `len()` implementation.

## Why markers come from the relationship types

`vault-config-writer.py relationships` writes one object per type (`parent`, `peer`), and
the schema has no `markers` list. The summary read `relationships.markers`, and its test
fixture used that invented shape, so every real config reported no markers. The fixture now
mirrors the writer.

## Why the template counts say mapped, not found

The counts come from `templates.mapping` alone, so a file named there can still be missing.
They were called found and missing, and a live run reported 0 missing with two files absent.
Only Kado can show that a file exists, which is what vault-explorer Step 8 does.
