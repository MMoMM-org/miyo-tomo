# WHY: lib/review_reader.py

> Rationale for decisions in `tomo/scripts/lib/review_reader.py`.
> The module owns the Kado access of a period read (spec 045, T3.3; PRD
> F3-AC10–F3-AC12; SDD ADR-4): one cache in front of `ReviewPacer.read` for
> notes, link-stem lookups, folder listings and `listNotes` queries, the
> pending/missing distinction, and the end-pass merge. `lib/review_period.py`
> decides what to read; this module reads it once.

## WHY a Third Module

WHY: Constitution L2 (dense files stay ~300–500 LOC) and the T3.3 brief
(`review_period.py` ≤ ~400 lines). After the weekly parsing moved to
`lib/review_weekly.py`, the period reader still held 453 lines; the paced
cache is the one part with a responsibility of its own — "reach Kado once per
key and survive a rate limit" — and no knowledge of days, weeks or growth.
`review_vault.Vault` (the session script's wrapper) was not reused: it maps
every `KadoError` to `Stopped`, which would turn the pacer's
`KadoRateLimitError` into a stop instead of a retry, and it is not paced.

## WHY One Cache Keyed by Path, Stem or Folder

WHY: SDD same-day reading, step 1 ("a living task note is read once for the
period, not per day") and F3-AC12. `read_day` asks for a task note or a
same-day note on every day that links it; the cache answers the second ask
without a call. The same cache lets `finish()` re-run a day for free: the
daily text, the resolved stems and the linked notes are all there. Keys
cannot collide: note keys end in `.md`, folder keys end in `/` or are `/`,
and a link stem is a bare basename without `.md` (`review_day._target`
strips it).

## WHY a Link Stem Is Resolved With One `byName`

WHY: `read_day` calls `read_note(target)` with the link text as written —
`DP-2026-03-26`, no folder, no `.md` — because a daily links by stem and the
day reader has no vault. `target()` runs one `byName` per stem (cached), takes
the hit whose basename is exactly that stem with `.md` (Kado's `byName`
matches substrings, so `DP-2026-03-26 Copy.md` and a `.png` are near misses
that must not win), and reads the note at that path. A stem that resolves to
nothing is "missing" for the day's `problems`, never "failed": nothing was
turned away.

## WHY Pending Is Not Missing

WHY: F3-AC12 and the pacer's `recovered`. `pacer.read` returns None both for
a `Path not found` (raised, caught here, remembered in `missing`) and for a
read that outlasted the client's retries (remembered by the pacer, here in
`pending`). The two must stay apart: a missing linked note is a finding to
report, a pending one may still arrive in the end pass. `hit_pending` flips
whenever a read is pending — on the first failure and on every later ask for
the same key — so the period reader can mark the day whose reads were
incomplete and re-run exactly those days after `finish()`. A listing or
query that is still pending is never counted as "Kado returned none"
(`answered()`), because the access hint would be wrong for a busy Kado.

## WHY `finish()` Merges Into the Cache

WHY: the pacer stores late values in `recovered` (path → value) rather than
calling back; the reader copies them over its pending keys, leaving None for
what still failed, so a re-run reads only the cache and makes no call for a
path in `not_read`. Folder listings are the first calls of a run and are not
re-run after the end pass: a listing that fails even after the pacer's widest
spacing means Kado was saturated before the read began, and the report names
it in `not_read` with its sources empty rather than reading a period twice.
