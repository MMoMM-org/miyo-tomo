# WHY: tomo-trackers-wizard

> Rationale for decisions in `tomo/dot_claude/skills/tomo-trackers-wizard/SKILL.md`.

## Deactivate, not remove (#38, v0.5.0)

WHY: the user asked for a way to stop a detected tracker from being proposed.
Before v0.5.0 the wizard offered only Skip, which leaves the metadata blank
and the field active. An active field without keywords is still matched by
guesswork, and `/tomo-setup` Phase 3b warns about it on every run. The user
had no per-field way out.

The wizard switches the field off with `active: false`. It does not delete
the entry, for two reasons:

- **Deletion does not stick.** `/explore-vault` rediscovers tracker fields by
  scanning the daily notes and rewrites the whole `trackers:` block through
  `vault-config-writer.py trackers`. A deleted field that still appears in the
  daily notes comes back on the next scan, active and without keywords.
  `active` is in the writer's `TRACKER_CURATED_KEYS`, so a scan carries
  `active: false` forward (see `docs/tomo/scripts/vault-config-writer.md`).
  Making deletion stick would need its own ignore list, with a schema, a
  writer and a filter in the scan, for the same visible result.
- **Deletion throws work away.** Description and keyword lists are lost, and
  turning the tracker back on means filling them in again. The schema states
  this as the reason `active` exists.

The consumers already honour the switch: `inbox-analyst` matches only fields
whose `active` is not `false`, and `shared-ctx-builder` leaves inactive fields
out of the empty-keyword warning.

## Inactive fields are offered for reactivation, not hidden

WHY: once a field is off, the wizard is the only guided place to turn it back
on. If the wizard skipped inactive fields silently, reactivating one would mean
editing YAML by hand — exactly what the wizard exists to avoid. So an inactive
field is shown briefly with Keep off / Reactivate; Reactivate removes the
`active` line and continues with the normal walk for that field.

`active: true` is never written. Absent means active, matching the writer's
rendering rule; writing `true` would add a line to every field and make a
reactivated field differ from one that was never switched off.

## `active` is an allowed key

WHY: v0.4.0 listed the allowed per-field keys as a closed set to stop the model
inventing keys (`navigation:`, nested `keywords:`). `active` was added to the
schema later (commit e113c9dc) and never added to that list, so the wizard was
told not to write the one key that does what #38 asks. The list now matches
the writer's `TRACKER_FIELD_ALLOWED` minus `keywords`, which the wizard does
not curate. `tests/test_tracker_config_durability.py` checks that every
curated key the writer preserves is allowed by the wizard, so the next new
curated key cannot be silently forbidden again.
