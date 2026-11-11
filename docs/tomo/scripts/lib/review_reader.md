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

## WHY One Cache, Keyed by Kind

WHY: SDD same-day reading, step 1 ("a living task note is read once for the
period, not per day") and F3-AC12. `read_day` asks for a task note or a
same-day note on every day that links it; the cache answers the second ask
without a call. The same cache lets `finish()` re-run a day for free: the
daily text, the resolved stems and the linked notes are all there.

A note's key is its vault path, bare: `<path>`. The other three kinds carry
a mark that tells them apart from a path and from each other —
`name:<stem>`, `dir:<folder>`, `notes:<folder>?<fields and filter>` —
because the first version keyed everything by the bare string and argued
that a note (`.md`), a folder (`/`) and a stem could not collide. They can,
and each mark that stays is one a test shows missing
(`tests/test_review_period_end_pass.py`, "cache keys"):

- `name:` — a link stem is text as written in a daily, and Obsidian accepts a
  full-path link (`[[Efforts/300 Planner/DP-2026-03-25.md]]`); without the
  mark such a stem keys into the text of the note already read at that path,
  and `target()` then reads that text as a path. With the mark the stem is
  looked up by name like any other (and resolves to nothing: `byName` matches
  the basename, which never equals a full path).
- `dir:` — a task note configured with the daily folder's string (a
  misconfiguration, but one `vault-config.yaml` can hold: `task_notes` is
  taken as written) would otherwise be served the cached listing as its text
  and crash the task parser; with the mark the note read reaches Kado, which
  refuses a non-`.md` path (`VALIDATION_ERROR`, a `KadoToolError` that
  propagates like a connection error).
- `notes:…?<query>` — the created-notes query (`listNotes` over `/` with a
  `createdAfter` filter) and an unfiltered MOC listing over the same prefix
  are two different questions to Kado that a path-only key would answer with
  one cached result; the query's `fields` and `filter` are part of the key
  (sorted, JSON), so one period never reads two queries as one. The `?` and
  the braces are what separate a query key from a bare path (a vault name
  cannot contain `?`); the word `notes:` in front is a label for whoever
  reads a pacer trace, and no test can show it missing.

A path carries no mark because nothing could be shown to need one: the
other three kinds are marked, and a vault path cannot contain the `:` a
mark would have to collide with (Obsidian forbids it in a name), so a
`read:` prefix separated a path from nothing a vault can produce. The first
version had one, and every test stayed green without it; a mark that no test
can show missing is a claim the module cannot keep, so it went. The marks
are internal: the key is what the pacer records and what `finish()` merges
by, while `not_read` and `missing` carry the plain path, stem or folder the
caller asked for, which is what the report prints and what `review-read.py`
hands to `pacer.summary`.

`answered(key)` is the one test for "Kado answered with nothing" against
"Kado has not answered" (pending or failed); it takes the full key, built by
`dir_key()` / `notes_key()`, so the period reader asks about exactly the
listing or query it made. No other method decides that question — a second
one would drift from this one, and the access hint (`kado_empty`) and the
growth "returned none" name both rest on it.

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

WHY: the pacer stores late values in `recovered` (key → value) rather than
calling back; the reader copies them over its pending keys, leaving None for
what still failed, so a re-run reads only the cache and makes no call for a
key in `not_read`.

A read made after `finish()` — the dailies and weekly notes of a folder
listing the end pass recovered (`review_period.md`, "WHY the Module Calls
`finish()`") — is a plain paced read with no further end pass behind it, so
one that outlasts the client's retries is final: it goes straight to
`not_read` (and `_failed`), never to `pending`, so the report marks it
`failed` instead of leaving it pending forever. There is no second end pass
because the pacer's `finish()` restores the client's interval once and a
period is read once; the memory of the end pass (`finished`) is what tells
`_get` which rule applies.
