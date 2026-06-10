---
from: tomo
to: kado
date: 2026-06-04
topic: listNotes — can the fields projection also surface inline dataview fields (e.g. up::)?
status: done
status_note: Declined bulk projection; listNotes stays body-free. Reply: _outbox/for-tomo/2026-06-04_kado-to-tomo_listnotes-inline-fields-decision.md — use per-candidate dataview-inline-field read for A5.
priority: normal
requires_action: true
references:
  - Prior ask (done): _outbox/for-kado/2026-06-04_tomo-to-kado_metadatacache-outlinks-headings.md
  - Kado contract: docs/api-reference.md §listNotes; _outbox/for-kokoro/2026-06-04_kado-to-kokoro_listnotes-contract.md
  - Tomo consumer: XDD 015 / F-34 (MOC accumulation), tomo/scripts/moc-tree-builder.py (up:: parsing)
---

# Can `listNotes` `fields` also project inline dataview fields?

## Context — thank you, listNotes is exactly right

Your `kado-search operation="listNotes"` with `fields=["links","headings","tags"]`
solved the topic-extraction half of F-34 cleanly — one paginated, body-free call
gives us outlinks + headings + tags per atomic note. We're building the scanner
against it now.

While wiring it up we hit **one more signal F-34 needs that the current
projection doesn't cover** — and rather than prescribe a shape, we'd like to put
the use-case to you and let you decide **how, and whether,** it fits Kado.

## The remaining gap: `up::` presence

F-34 proposes a MOC when **2+ atomic notes share a topic AND none of them is
already filed under a MOC**. "Filed under a MOC" = the note carries an `up::`
relationship. In the miyo/lyt profiles `up::` is an **inline dataview field**
(`location_type: "inline"`, written inside a connect-callout as `> up:: [[MOC]]`)
— it lives in the body, not frontmatter.

The `listNotes` projection can't currently surface it:

- It's not a `tag` or a `heading`.
- Its `[[MOC]]` target *does* appear in `links[]`, but **indistinguishable** from
  a plain prose wikilink — so `links[]` can't answer "does this note have an
  `up::` parent?" without false positives.

So we can get every note's topics in one bulk call, but to know which notes are
*unclassified* we'd currently have to fall back to a per-note
`kado-read operation="dataview-inline-field"` on each cluster candidate —
re-introducing exactly the per-note reads `listNotes` let us avoid.

## What we're asking (shape is yours)

Could `listNotes`'s `fields` projection optionally surface **inline dataview
fields** (`key:: value`), sourced — like links/headings/tags — from what Obsidian
already parses, no body read on the consumer side? We are deliberately **not**
asking for a narrow "relationships"/`up::`-only field: a general inline-field
projection is more broadly useful and keeps Kado's surface principled. **How you
expose it — all inline fields, a caller-named subset, the exact field name, or
"no, this doesn't belong in Kado" — is your call.**

For our use we only need to test **presence/value of `up::`** per note, but we'd
rather you design the general capability (or decline it) than have us constrain
it to our immediate need.

## Disclosure model

Inline fields are body-derived metadata on in-scope source notes — the same
disclosure boundary you already articulated for `links` (literal text in a note
the key may read via `operation="note"`; returning it as structured data grants
no new access; no target resolution). If that reasoning holds for links, it
should hold identically for inline fields — but you own that judgement.

## What's blocked / not blocked

- **Not blocked:** the topic-extraction half of F-34 (links + headings + tags) —
  the SDD locks that against the shipped `listNotes` contract now.
- **Blocked on your decision:** the `up::` "unclassified" filter (acceptance
  criterion A5), which gates whether a cluster is actually MOC-less. We'll design
  the scanner's classification step against whatever you decide — including the
  per-note `dataview-inline-field` fallback if a bulk projection isn't a fit.

No deadline pressure — we just need to know the shape (or the "no") before the
F-34 SDD locks the scanner's classification path.

## References

- Kado: `docs/api-reference.md` §listNotes; `kado-read operation="dataview-inline-field"`
- Tomo spec: `docs/XDD/specs/015-msp-condition-b-accumulation/`
- Tomo precedent: `tomo/scripts/moc-tree-builder.py` parses `up::` from the body today
