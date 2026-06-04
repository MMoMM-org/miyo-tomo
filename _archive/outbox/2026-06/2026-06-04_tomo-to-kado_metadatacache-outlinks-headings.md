---
from: tomo
to: kado
date: 2026-06-04
topic: Structured outlinks + headings from metadataCache (no body read) — capability feasibility
status: done
status_note: Implemented as kado-search operation=listNotes with fields=[links,headings,tags] (no body read). Embeds folded into links; out-of-scope link targets returned raw per source-note disclosure boundary. See _outbox/for-kokoro/2026-06-04_kado-to-kokoro_listnotes-contract.md and docs/api-reference.md (listNotes). Branch feat/listnotes-search-op.
priority: normal
requires_action: true
---

# Can Kado serve a note's outlinks + headings without shipping the body?

## What we're asking

Tomo's **XDD 015 / F-34 (MOC accumulation detection)** needs to build a topic
index over every atomic note in the vault, once per `/explore-vault` run
(~281 notes on Marcus's real vault). To extract topics, Tomo's deterministic
`topic-extract.py` consumes exactly **four signals per note**:

1. **Title** — from filename / H1
2. **H2 headings** — structural sub-topics
3. **Outlinks** — `[[wikilink]]` targets
4. **Tags** — frontmatter **and** inline `#tags`

Two of these four Kado already serves cheaply. **Two it does not** — and we'd
like your read on whether (and how) Kado could.

## Why this is a Kado question, not a Tomo workaround

The naive path is `kado-read operation='note'` per atomic note and regex the
body Tomo-side. For ~281 notes that's **~1 MB of markdown over the wire just to
extract a few small structured fields** — and Tomo would be re-parsing
structure that Obsidian has already indexed.

Obsidian's `metadataCache.getFileCache(file)` already exposes `links`,
`headings`, `tags`, and `frontmatter` per note **without reading the file body**.
Serving those structured fields is squarely the pattern your own tool
descriptions advocate ("for listing/filtering … without loading content at all,
use kado-search"; op-symmetry / minimal-payload rule) and what MiYo Constitution
L2 Performance prescribes ("use Obsidian's metadata cache rather than
re-implementing full vault scans"). So this feels like a natural extension of
Kado's surface rather than a new concern.

## What Kado already covers (for completeness)

- **Tags** ✅ — `kado-read operation='tags'` returns
  `{frontmatter[], inline[], all[]}`, and `kado-search listDir` results already
  carry `tags` (plus `path`, `created`, `modified`, `size`) **with no body
  read**. This is a superset of what Tomo extracts today — we currently miss
  inline tags entirely, so adopting Kado's tags is a strict improvement.
- **Path / title-from-filename / mtime** ✅ — all from `listDir`.

## The gap

- **Outlinks** ❌ — no operation returns a note's `[[wikilink]]` targets.
- **Headings** ❌ — no operation returns a note's heading outline (H1/H2…).

Both are present in `metadataCache` (`cache.links`, `cache.headings`).

## Action required

We're **not** prescribing an API shape — the vault surface is yours to design.
We'd like your assessment of:

1. **Feasibility** — can Kado expose outlinks + headings sourced from
   `metadataCache` (no body read), under the existing permission gates?
2. **Surface** — whichever fits Kado's architecture. Two shapes we considered,
   for discussion only:
   - **Per-note read derivative** — e.g. `kado-read operation='links'` /
     `'headings'` (or a combined `'structure'`), symmetric with the existing
     `'tags'` op.
   - **Bulk enrichment** — an optional `fields=[links,headings]` on a
     `listDir`-style `kado-search` op, so one call returns
     path + tags + outlinks + headings for N notes. This fits our "index every
     atomic note" use-case best (collapses the whole scan into a handful of
     metadata-cache calls), but it's a bigger change to your search surface.
3. **Permissions** — what gate should outlinks/headings sit behind? They're
   body-derived metadata; `operation='tags'` already audits as a `note` read and
   requires `note.read` for inline tags. Same model presumably applies.

## What's blocked on this

Tomo's F-34 SDD. We can build the indexer skeleton against the two existing
signals (tags + path via `listDir`), but **topic quality stays degraded until
outlinks + headings land** — wikilinks and H2s are two of the four topic
sources. No rush on a delivery date; we just need to know if the capability is
on the table so the SDD can design the scanner against the right contract.

## References

- Tomo spec: `docs/XDD/specs/015-msp-condition-b-accumulation/` (PRD + this
  session's resolved open questions)
- Tomo consumer: `tomo/scripts/topic-extract.py` (the 4 extraction methods)
- Constitution L2 Performance — metadata-cache-over-rescan rule
- Cross-component interface change → if a new contract lands, it should be
  reflected in Kokoro per Architecture L2 (we'll raise that once the shape is
  agreed).
