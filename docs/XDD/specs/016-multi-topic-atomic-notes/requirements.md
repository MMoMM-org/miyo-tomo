# XDD 016 — Requirements (PRD)

> **Status:** draft (2026-05-07)
> **Spec ID:** 016
> **Title:** Multi-topic detection — emit one `create_atomic_note` per substantive concept per inbox item
> **Backlog ref:** F-41 (Should)
> **Related:** F-33 / XDD 012 (Force Atomic Note synthesis — workaround for some single-thread cases); XDD 009 (voice-memo transcription — produces the multi-thread inputs that surface this gap most often).
> **Triggering incident:** 2026-05-01 /inbox run, voice memo `Apothekerpfädchen 11__2026-04-22 10-14-41.md`. 183-sec transcript, two clear threads: (1) medical appointment (daily-log relevant), (2) Tomo/PKM architecture thoughts (atomic-note worthy). Analyst emitted only `update_daily`. The PKM thread was lost.

## 1. User story

> As a Tomo user capturing voice memos (or any inbox item) that
> traverse multiple distinct concepts in one note, I expect Tomo to
> recognise each substantive thread and propose a separate atomic note
> per thread — not collapse the whole item into a single classification.
> Today: a 183-sec voice memo combining a medical-appointment thread
> with a Tomo/PKM-architecture thread emits exactly one action
> (`update_daily`), losing the architecture thread entirely. The user
> has no way to recover that information short of re-listening to the
> audio and hand-creating the missed atomic.

## 2. Problem today

- **Step 7 worthiness gate is single-pass.** The analyst scores the
  whole item once (`atomic_note_worthiness` 0-1, ≥0.5 → emit one
  `create_atomic_note`). The score reflects "does this item contain
  worthy material" — not "how many distinct worthy concepts does this
  item carry".
- **Step 8 emits at most one atomic action.** Even when Step 7 fires,
  Tomo emits a single atomic with one suggested title, one MOC match,
  one tag set. Multi-thread items are forced into a single conceptual
  bucket.
- **XDD 012 (FAN) only handles the single-thread case.** Force-Atomic
  recovers items the analyst judged sub-worthy as a whole, but still
  emits ONE atomic per source. The Apothekerpfädchen 11 case is
  beyond FAN's coverage: even with FAN ticked, only one atomic would
  ship.
- **Voice memos make it acute.** Long-form voice transcripts naturally
  carry multiple threads (the user thinks aloud about three things in
  one walk). The current architecture biases against capturing that
  reality.
- **Workarounds all hurt.** Splitting the audio into multiple files
  per thread defeats the spontaneous-capture model. Re-typing the
  PKM thread into a fresh note duplicates work and loses provenance
  (which voice memo did this thought come from?).

## 3. Goals

- **G1 — Detect topical splits.** When an inbox item carries multiple
  conceptually distinct, individually atomic-note-worthy threads, the
  analyst MUST identify them as distinct units (not lump them).
- **G2 — Emit one `create_atomic_note` per substantive thread.** Per-
  thread suggested title, per-thread MOC match, per-thread tags,
  per-thread `tags_to_add`. Each atomic is reviewable independently
  in the suggestions doc.
- **G3 — Preserve provenance.** Every atomic emitted from a multi-
  topic item carries a back-reference to the source (`source_stem`,
  the audio path embed for voice cases). The user can see which
  source produced which atomic.
- **G4 — Respect existing per-action UX.** Multi-topic atomics surface
  in the suggestions doc as separate per-item Accept blocks (not
  nested checkboxes). The user approves/rejects each independently.
- **G5 — Compatible with Force-Atomic (XDD 012).** The FAN resolve
  subflow respects multi-topic emission: a force-atomic'd log_entry
  with multi-topic content yields multiple atomic proposals in the
  resolve doc, not one.
- **G6 — Compatible with daily-log + atomic mix.** A multi-topic
  item can produce: 1× `update_daily` (medical appointment thread)
  + 2× `create_atomic_note` (PKM-architecture thread, plus another
  thread). The action emitter handles N≥2 atomic actions cleanly
  alongside daily/log actions.

## 4. Non-goals

- **N1 — Auto-segment short items.** Items under a worthiness floor
  (e.g. < 100 words total) skip topical-segmentation entirely. The
  cost of running multi-topic detection on a 30-word fleeting note
  outweighs any signal.
- **N2 — Cross-item topic clustering.** Within a single inbox item,
  not across items. Cross-item clustering is Condition A (already
  implemented in suggestions-reducer.py).
- **N3 — User-driven manual split via UI.** No "split this item into
  three" button. Detection is automatic; the suggestions doc surfaces
  the result; the user approves/rejects per atomic.
- **N4 — Sub-segmentation beyond top-level threads.** "Two clearly
  distinct concepts" is in scope; "three nested sub-points within a
  concept" is not. First cut emits at the top level only.
- **N5 — Re-classification of already-shipped atomics.** This feature
  changes how new atomics are emitted, not how existing atomics are
  organised. Garden-audit (F-44) is the natural home for retroactive
  multi-topic cleanup.

## 5. Acceptance criteria

**A1 — Topical-segmentation pass in Step 7+8.** `inbox-analyst.md`
gains a topical-segmentation phase between Steps 7 and 8 that emits
a list of `threads[]`, each with: `title_hint`, `summary`, `topics[]`,
`worthiness_score` (per-thread, scored against the thread's content
not the whole item), `dominant_classification`. For single-thread
items, `threads[]` has length 1 (current behaviour preserved).

**A2 — Multi-thread emission.** Step 8 iterates `threads[]`; each
thread with `worthiness_score >= 0.5` (or matching the
`force_atomic` override per XDD 012) emits its own
`create_atomic_note` action with thread-scoped title / MOC match /
tags. Threads with sub-worthiness scores can still contribute to a
shared `update_daily` (or other non-atomic) action.

**A3 — Provenance is preserved.** Each emitted atomic carries
`source_stem` (the inbox item's stem) so downstream consumers know
the origin. Voice transcripts additionally embed the audio
reference (per XDD 009 §F3 audio-peer pattern) in the rendered note.

**A4 — Suggestions-reducer renders one per-item Accept block per
atomic.** The reducer (`tomo/scripts/suggestions-reducer.py`) MUST
render N atomic proposals from a single source as N independent
per-item blocks, each with its own `[ ] Approved` toggle. The user
reviews and approves each independently. Renders MUST remain
scannable when N is small (typically 2-3); design for N=5 as the
upper realistic bound.

**A5 — Suggestion-parser handles N atomics per source.**
`suggestion-parser.py` MUST parse multiple atomic actions per
`source_stem` and emit them as separate entries in
`parsed-suggestions.json`. No silent collapsing into one.

**A6 — Instruction-render produces N rendered notes.**
`instruction-render.py` MUST template each atomic separately,
producing N distinct rendered notes per source-with-multi-topics.
Each rendered note has its own destination, frontmatter, body —
linked from the suggestions doc by independent action IDs.

**A7 — Schema validation.** `instructions.schema.json` MAY need an
update to confirm multiple `create_atomic_note` actions can share a
`source_stem`. Most likely additive (the schema already permits
multiple actions per source via the `actions[]` array). SDD must
verify before locking.

**A8 — FAN resolve flow handles multi-thread.** When the user ticks
Force Atomic Note on a single log_entry whose source content is
multi-thread, the resolve subflow (XDD 012) MUST emit multiple
`create_atomic_note` proposals in the resolve doc — not one. The
existing FAN merge-back mechanism MUST handle N≥1 atomics per
source-stem.

**A9 — Daily-log + atomic mix handled.** When an item produces
1× `update_daily` + 2× `create_atomic_note`, all three actions land
correctly in instructions.json. The cleanup phase
(instruction-set-cleanup) handles paired-delete decisions per the
existing rules (e.g. the source audio is deleted only after ALL
threads have been atomicised AND the daily-log entry is committed).

**A10 — Tests cover the multi-thread happy path and the edge cases.**
- Single-thread item → 1× atomic (no regression)
- 2-thread item → 2× atomic (happy path)
- 5-thread item → 5× atomic (stress test)
- Sub-worthiness multi-thread item → no atomics, single
  `update_daily` (worthiness gate still applies per-thread)
- Mixed-worthiness multi-thread item (1 high, 1 low) → 1× atomic
  + summary-only daily entry for the low-worthiness thread
- Voice-transcript multi-thread → 2× atomic + audio reference per
  thread
- FAN-ticked multi-thread → resolve doc emits 2× proposals
- Multi-thread items with overlapping topics → MOC matches deduped
  per atomic (no double-emission of the same `up::` link target)

**A11 — Documentation.** Tier-3 inbox-analysis spec
(`reference/tier-3/inbox/inbox-analysis.md`) MUST gain a
multi-topic section explaining when segmentation fires and the
expected output shape. Backlog F-41 marked code-complete on
implementation.

## 6. Out of scope (noted)

- **Configurable split threshold.** Whether 2 threads or 3 threads
  is the minimum for multi-topic emission stays hardcoded per the
  worthiness gate (per-thread ≥ 0.5). Configurability via
  `vault-config.tomo.multi_topic.min_threads` is post-MVP if the
  default proves wrong in practice.
- **Cross-language multi-topic detection.** First cut handles English
  + German content (Marcus's vault language). Other languages may
  produce poor segmentation; this is acceptable for MVP.
- **Confidence display in suggestions doc.** Per-thread
  `worthiness_score` is computed but not shown to the user. Future
  UX could surface "thread 1: 0.8, thread 2: 0.55" to help the
  user prioritise; out of scope for MVP.
- **Custom segmentation prompts per item type.** Voice transcripts
  may benefit from "treat each `> [!voice]` callout group as a
  potential thread". First cut runs the same segmentation logic
  regardless of item type.
- **Thread merging.** If the analyst over-segments (3 threads where
  2 would do), no automatic merging. User declines the redundant
  proposal in the suggestions doc.

## 7. Success signals

- A re-run of the 2026-05-01 Apothekerpfädchen 11 case produces:
  - 1× `update_daily` (medical appointment, 2026-04-22)
  - 1× `create_atomic_note` (PKM-architecture thread → atomic note
    in `Atlas/202 Notes/`)
  - both linked back to the source audio
  - both reviewable independently in the suggestions doc.
- The user no longer needs to listen to long voice memos with the
  worry that "Tomo will only catch one of the threads".
- F-41 marked closed in backlog. Tier-3 inbox-analysis spec
  cross-references this XDD.
- Pass-1 token cost does not regress significantly. Topical
  segmentation costs additional LLM cycles per multi-thread item;
  budget tolerance is +10% on Pass-1 average.

## 8. Open questions

> Answer before SDD locks the surface.

- **OQ1 — Where does segmentation live?**
  (a) New `Step 7.5 — Topical segmentation` between worthiness and
  emission, in `inbox-analyst.md` (LLM-driven, agent-side);
  (b) New script `tomo/scripts/topic-segment.py` invoked from
  `inbox-analyst.md` (deterministic + LLM hybrid, like
  `topic-extract.py`).
  **Lean:** (a) — segmentation is judgment-heavy (whether two
  threads are conceptually distinct), better suited to the LLM than
  a deterministic script.

- **OQ2 — How does the analyst decide N (number of threads)?**
  Single LLM prompt asking "list the distinct concepts in this
  content"? Prompt with explicit examples? Heuristic (paragraph
  break density)? **Lean:** LLM prompt with 2-3 worked examples
  in the agent body, similar to the worthiness scoring's prompt
  shape.

- **OQ3 — Per-thread vs whole-item topic extraction.** Today
  `topic-extract.py` runs once per item. With segmentation, do we
  run it once per thread? Or run once on the item and split topics
  by thread post-hoc? **Lean:** once per thread — topics are a
  property of the thread, not the source.

- **OQ4 — Daily-log emission with multi-thread.** When a 3-thread
  item has 1 daily-log thread + 2 atomic threads, does the daily-
  log entry summarise all three? Just the daily-log thread? Both
  options?
  **Lean:** the daily-log entry summarises the daily-log thread
  ONLY. The other threads produce atomic notes whose link the user
  can manually drag into the daily log if desired (or via future
  auto-link logic).

- **OQ5 — Suggestion-doc layout for N atomics from one source.**
  Group all N under a single source-block heading? Render as N
  independent per-item blocks? **Lean:** N independent blocks with
  the source-stem visible in each (so the user can mentally group
  them). Reduces visual nesting; matches existing per-item shape.

- **OQ6 — Source-deletion semantics.** When the source is a voice
  audio paired with a transcript, AND the multi-thread emission
  produces 2× atomic notes, when is the audio deleted? After all
  approved atomics are committed? After the transcript is
  committed? **Lean:** after ALL atomics are committed AND any
  daily-log entry is committed (preserve the source until every
  thread it produced is captured in the vault).

- **OQ7 — Token-cost budget for segmentation.** Adding a
  segmentation prompt per multi-thread-candidate item costs ~500-
  1000 tokens. Should segmentation only run when length > N words
  (cheap pre-check) to avoid penalising short items?
  **Lean:** yes — pre-check `body length > 200 words` before
  invoking the segmentation prompt. Short items skip directly to
  Step 8 with `threads = [single_default_thread]`.

- **OQ8 — Backwards compatibility for the schema.** The
  `instructions.schema.json` currently allows multiple actions per
  source. Verify SDD: does anything in the parser/render assume
  exactly one `create_atomic_note` per `source_stem`? If so, that
  assumption MUST be removed.
  **Lean:** verify in SDD; expect minor changes in parser (action
  list iteration) and render (per-action filename collision check).

## 9. Constraints

- **C1 — Existing pipeline shape unchanged.** This feature lives
  inside Steps 7+8 of the inbox-analyst, plus N=1 → N≥1 cardinality
  changes downstream. No new pipeline phase, no new artefact types.
- **C2 — Cost budget +10%.** Pass-1 main-thread cost on a typical
  /inbox batch can grow by at most 10% (vs F-32 baseline). If
  segmentation costs more, gate it behind the length-precheck (OQ7).
- **C3 — Compatible with FAN (XDD 012).** Force-Atomic resolve flow
  must produce N proposals when the source is multi-thread. The
  resolve doc parser (suggestion-parser.py:794 companion-doc
  handler) must accept N≥1 atomic proposals per source-stem.
- **C4 — Voice-transcript audio cleanup unchanged.** The pairing
  rules from XDD 009 (audio + transcript) must survive: audio is
  preserved until all derived atomics are committed (OQ6).
- **C5 — "Additive only on hot paths" memo.** Hot paths
  (suggestions-reducer, suggestion-parser, instruction-render) take
  cardinality changes (N=1 → N≥1) but no semantic changes for
  single-thread items. SDD must prove single-thread regression test.
- **C6 — Branch + commit discipline.** Implementation lands on
  `feat/f-41-multi-topic-atomic-notes`; no direct commits to main.

## 10. Definition of done

- All A1–A11 acceptance criteria pass.
- All OQ1–OQ8 open questions are resolved in the SDD.
- The 2026-05-01 Apothekerpfädchen 11 case re-runs end-to-end with
  both threads captured.
- Pass-1 cost regression test (vs F-32 baseline) shows ≤ 10% increase.
- Backlog F-41 marked code-complete; tier-3 inbox-analysis spec
  updated.
- Voice-transcript triggering case (#19 in context.md) resolved.

## 11. Validation hooks (for SDD/PLAN)

- Re-run of Apothekerpfädchen 11 fixture (or equivalent
  multi-thread voice memo) → 2 atomic proposals.
- Single-thread regression: existing /inbox runs that emit 1 atomic
  today MUST emit exactly 1 atomic post-implementation.
- Cost regression: 20-item /inbox batch with mixed single + multi
  threads — main-thread cost tracked vs the F-32 baseline.
- Schema-validation regression: instructions.json with N atomics per
  source still validates against `instructions.schema.json`.
- FAN resolve flow regression: existing FAN-on-single-thread cases
  produce 1 proposal (not regressed); FAN-on-multi-thread cases
  produce N proposals (new behaviour).
