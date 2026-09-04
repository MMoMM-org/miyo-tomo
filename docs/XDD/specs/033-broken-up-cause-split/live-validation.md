# Spec 033 — Live validation (T5.1, T5.4)

> What was confirmed on real vault data, the one config intervention it needed, and the
> single number this spec exists to move.
> Run: 2026-09-04, after `update-tomo --yolo` → `/explore-vault` → `/garden-audit`.

## The run

Instance synced 14:30 (10 files), cache rebuilt 14:48, audit rendered 14:51.

## T5.1 — the cache learned the cause

| | before (2026-09-03) | after (2026-09-04) |
|---|---|---|
| cache entries | 359 | **359** |
| `up_state: broken` | 42 | **41** |
| of those carrying `up_broken_reason` | 0 | **41 — all** |
| `not-a-moc` | — | **19** |
| `unresolved` | — | **22** |

The key is on **every** broken entry. That presence-not-value distinction is ADR-3 — the
`_MISSING` sentinel distinguishes "the cache does not know this field" from "the cause does
not apply", and it is what stops a pre-033 index being silently classified as `unresolved`.

**On the drift from the measured baseline.** The decisions log recorded 20 `not-a-moc` /
22 `unresolved` on 2026-09-03; this run found 19 / 22, with the total down 42 → 41. The plan
(T5.1 step 2) requires re-measuring rather than concluding a defect when the numbers move.
The `unresolved` bucket matches **exactly**; only `not-a-moc` moved, by one, and the total
moved by the same one. A classifier fault would be unlikely to leave one bucket intact while
shifting the other by precisely the amount the total shifted. One `not-a-moc` finding
resolved between the two scans — the parent was tagged, renamed, or removed. Vault change,
not regression.

## The one config intervention

`tomo-instance/config/garden-audit-exclusions.yaml` carries a temporary blanket rule:

```yaml
- target: {type: path, value: Atlas/}
  checks: all
  mode: temporary
  until: '2026-10-19'
```

The cache's `scope_paths` are `Atlas/200 Maps/` and `Atlas/202 Notes/` — **329 of 359 entries
and all 41 broken ones sit under `Atlas/`**. Measured before the run: 41 findings without
exclusions, **0** with them. A live run would have proven nothing.

The rule was narrowed for the run to its five non-parent checks (`unparented`, `orphan`,
`dead_link`, `duplicate_stem`, `stale_moc`), leaving everything else it suppresses untouched,
then **restored byte-for-byte and verified identical**. Spec 032's live validation hit the
same wall and called this "the one config intervention the last step needs".

## T5.4 — the number this spec exists to move

Both columns are the **same rebuilt cache**. "Before" is the pre-spec check loaded from git
`8d866bb` — one code change against one dataset, not two datasets against two code versions.

| | before (git `8d866bb`) | after (spec 033) |
|---|---|---|
| findings emitted | 41 | **41** — nothing dropped |
| by check | `broken_up: 41` | `broken_up: 22`, `parent_not_moc: 19` |
| approvable fixes | 41 | **22** |
| **destructive offers** | **19** | **0** |

**19 offers to delete a working parent link are gone.** Each was a note whose `up::` target
is a real, present note that simply carries no MOC tag — the link worked, and the audit
invited the user to remove it.

Nothing was lost to achieve that: 41 findings before, 41 after. The 19 did not disappear,
they became advisories that name the target and say what to actually do.

## The rendered report

45 findings total (22 integrity, 4 structure, 19 advisory). Verified programmatically across
all 19 `parent_not_moc` blocks:

- 0 with an Apply checkbox, 0 with a `Repoint to:` field, 0 with a Suggest opt-in — CON-2
  holds because the code path does not exist, not because nothing took it
- 0 containing the words "broken" or "remove"
- 19 of 19 name their target
- `Flagged parents: 41 — 22 not found in the audited area, 19 not yet tagged as a MOC` — the
  arithmetic reconciles

The grouping block earned itself on real data:

```
**Untagged parents — 6 targets, 14 findings, one tag each settles the group:**

- [[Lebensziele]] — 2 findings (F08, F09)
- [[Architects & Gardeners]] — 3 findings (F14, F22, F23)
- [[Elbsandsteingebirge]] — 2 findings (F16, F37)
- [[Nordböhmische Bergwelten]] — 2 findings (F24, F33)
- [[Map]] — 2 findings (F25, F27)
- [[Notemaking]] — 3 findings (F28, F35, F39)
```

**Six tags settle 14 of the 19 advisories.** The advisory text reads, on a real finding:

> `_[[Lebensziele]] is a real note, not yet tagged as a MOC. Tag [[Lebensziele]] as a MOC —
> the link stays as it is. 2 findings in this report point at [[Lebensziele]]; tagging it once
> resolves both (see "Untagged parents" below)._`

Note "resolves **both**" at a group of exactly two — the plural branch added after a TDD gate
asked what a group of two would render. A fixture of three would never have exercised it.

## What the withholding path showed

Before the rebuild, the same live cache produced **41 findings, 41 withheld, 0 approvable** —
T4.4's disclosure working on production data. After the rebuild, **0 withheld**: the
cause-unknown state correctly stopped applying the moment the index could classify. The
withholding is temporary by construction, which is what makes it honest rather than
obstructive.
