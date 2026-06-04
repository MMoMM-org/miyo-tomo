# XDD 015 — MSP Condition B: Accumulation Detection

**Status:** PRD complete · OQs resolved · **SDD complete (2026-06-04)** · plan pending
**Current phase:** [solution.md](solution.md) written (ADR-1…7 confirmed) — ready for `/xdd-plan`
**Backlog origin:** F-34 (Must)

> **✅ Topic extraction (2026-06-04):** Kado shipped
> `kado-search operation="listNotes"` with `fields=["links","headings","tags"]` —
> one paginated, metadata-cache-sourced call returns path + mtime + tags +
> outlinks + headings per note, **no body read**. Contract:
> `Kado/docs/api-reference.md` §listNotes + `Kado/_outbox/for-kokoro/2026-06-04_kado-to-kokoro_listnotes-contract.md`.
> Kado branch `feat/listnotes-search-op` (not yet merged — version TBD at release).
>
> **✅ Classification `up::` (2026-06-04, Kado decided):** `listNotes` will **not**
> project inline dataview fields — Kado keeps its body-free invariant.
> Rationale: `links`/`headings`/`tags` come from Obsidian's **core**
> `CachedMetadata`, but `key:: value` inline fields are a **Dataview** construct
> *not* in that cache — surfacing them would force per-note body reads or a hard
> Dataview dependency. So **A5 uses the existing
> `kado-read operation="dataview-inline-field"`**, called **only on cluster
> candidates** (notes already sharing a topic — a bounded subset, not the vault).
> Decision: `_inbox/from-kado/2026-06-04_kado-to-tomo_listnotes-inline-fields-decision.md`.
>
> **Kado defines these contracts; F-34 adjusts to them.**

## Problem in one paragraph

The Mental Squeeze Point feature surfaces "you should make a MOC for
this" when topic clusters accumulate without organisation. Today only
**Condition A** (in-batch cluster of 3+ inbox items) and **Condition C**
(placeholder MOC trigger — F-35, shipped 2026-05-07) fire end-to-end.
**Condition B** — the case where the inbox item's topics match 2+
existing atomic notes that already sit in the vault without an `up::`
link — is unimplemented. Latent clusters keep growing, the user
discovers them retroactively, and Tomo misses the moment when surfacing
the cluster would have been most useful.

## Solution in one paragraph

Pre-compute an accumulation index once per `/explore-vault` run: a new
`atomic-note-indexer.py` issues one `kado-search operation="listNotes"`
(paginated) over the atomic-note base path with
`fields=["links","headings","tags"]`, feeds each note's structured signals
to `topic-extract.py`'s new field-based entry point, checks for `up::`
presence, groups notes by topic, and emits clusters of size ≥
`min_cluster_size` (default 3). The cache stores it; `shared-ctx-builder`
surfaces it (size-budgeted to fit the 15 KB envelope); `inbox-analyst`
Step 4 fires Condition B when an item's topic matches a cluster key —
setting `needs_new_moc=true` with `proposed_moc_topic = <topic>`. No
per-item Kado searches at /inbox time, so Pass-1 cost stays unchanged.

## Files

- [requirements.md](requirements.md) — product requirements (PRD)
- [solution.md](solution.md) — technical design (SDD), **complete** — ADR-1…7, against the Kado contracts
- plan/phase-N.md — implementation plan, pending

## Tracking

- Backlog entry: `docs/XDD/backlog.md` → F-34
- Architecture decisions (locked 2026-05-07):
  - **Option (b)** — accumulation index pre-computed in shared-ctx pipeline
  - **Index shape** — `topic → list of stems`
- Branch when implementation starts: `feat/f-34-msp-condition-b-accumulation`
- Related specs: F-35 (shipped 2026-05-07, commit `5b3a031`),
  F-36 (new section proposal — natural follow-up),
  F-43 (MOC-creation skill — complementary)
- Constraint memory: `feedback_near_mvp_no_breakage.md` —
  additive only on hot paths.

## Open questions — RESOLVED (brainstorm 2026-06-04)

All seven OQs from requirements.md §8 are locked. Stakeholder: Marcus.

| OQ | Resolution |
| --- | --- |
| OQ1 scanner home | New `atomic-note-indexer.py` (separate script — `moc-tree-builder.py` is already 722 LOC, near the Constitution L2 cap). |
| OQ2 note discovery | **`kado-search operation="listNotes"`** on `atomic_note.base_path`, `fields=["links","headings","tags"]` (returns path + mtime + structured signals in one paginated call, no body read). *(Was `listDir`; superseded by Kado's purpose-built `listNotes`.)* |
| OQ3 run mode | **Always run** on `/explore-vault` (cold path; single code path; benchmark-then-reconsider). |
| OQ4 normalisation | Lowercase + whitespace-collapsed string equality (matches F-35). |
| OQ5 min cluster size | **Configurable** `vault-config.tomo.accumulation.min_cluster_size`, **default 3** (quieter than the spec literal of 2). |
| OQ6 read depth | **Dissolved** — no body reads. Scanner consumes the `listNotes` projection: `tags[]` (`#`-prefixed), `links[]` (`{target,kind}`), `headings[]` (`{heading,level}`). |
| OQ7 cache schema | Additive at `cache_version: 1`, missing field = empty dict (F-35 precedent). |

**Two SDD decisions locked (2026-06-04, against the `listNotes` contract):**

- **SDD-D1 — `topic-extract.py` gains a structured entry point.**
  Add `extract_topics_from_fields(title, headings, links, tags)` that consumes
  Kado's structured projection directly (H1→title, level==2→subtopics,
  `link.target`→linked titles, `#`-stripped tags). The existing raw-`content`
  path is retained for other callers. (Resolves the old parking-lot question;
  rejected the pseudo-markdown round-trip.)
- **SDD-D2 — links projection: `kind=='link'` only.**
  Drop `kind=='embed'` (images/excalidraw/PDF assets) before topic extraction —
  embeds inject non-topical filename noise. Matches topic-extract's original
  `[[wikilink]]`-only intent.
- **SDD-D3 — `up::` classification via per-candidate `dataview-inline-field` read.**
  A5's "unclassified" test needs `up::` presence. Kado declined to project inline
  fields into `listNotes` (they're a Dataview construct outside Obsidian's core
  cache; bulk projection would mean per-note body reads or a Dataview dependency).
  So the scanner classifies in two steps: (1) bulk `listNotes` → topics → cluster
  on shared topic ≥ `min_cluster_size`; (2) for **cluster candidates only**,
  `kado-read operation="dataview-inline-field"` to test `up::` presence. The
  expensive read is bounded to the small candidate set, not the ~281-note vault.

**Design reshape:** The PRD assumed Tomo reads note *bodies* to extract topics
(OQ6 was "full body vs head-only"). The brainstorm reframed this to *structured*
signals; Kado then shipped `listNotes` to serve exactly those signals from the
metadata cache. Faster and more accurate than body-parsing, with the dependency
satisfied.

## Notes

**F-47 schema requirement (2026-05-21):** Any new renderer this spec introduces that emits workflow documents (suggestions-fan, instructions docs, or similar pipeline outputs) MUST emit the `tomo:` block per `tomo/schemas/doc-frontmatter.schema.json` (F-47 Phase 1 SoT). Use `build_tomo_block()` from `tomo/scripts/lib/doc_frontmatter.py`. When this spec reaches SDD/plan phase, renderer-touch tasks must include "emits `tomo:` block per F-47 schema". See `docs/XDD/specs/017-tomo-lifecycle-tags/solution.md` §Data Models for the canonical field definitions.
