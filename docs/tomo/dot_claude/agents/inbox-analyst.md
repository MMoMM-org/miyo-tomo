# WHY: inbox-analyst

> Rationale for decisions in `tomo/dot_claude/agents/inbox-analyst.md`.
> The agent classifies ONE inbox item per invocation: reads shared-ctx + note
> content via Kado, writes a structured result.json, updates the state-file.

## Condition B (Accumulation Cluster Trigger) Retired — T3.2 (spec 021 ADR-10)

WHY: Step 4 originally had three conditions: A (Classification Guard), B
(Accumulation cluster trigger), C (Placeholder link trigger). Condition B
matched item topics against `shared_ctx.accumulation_index` — a map of
topic strings that had accumulated enough notes to warrant a new MOC — and
set `needs_new_moc: true` + `proposed_moc_topic` on a hit.

Condition B was retired for two reasons rooted in spec 021 and F-34 Condition
B viability analysis:

1. The accumulation index was sourced from `unclassified_topic_clusters` in
   the MOC-cache, which was produced by `atomic-note-indexer.py`. Spec 021
   moved vault-wide MOC discovery to `/moc-propose` (a dedicated command). The
   inbox pipeline no longer needs to scan for accumulation-worthy clusters per
   item — that is the job of `/moc-propose`. Keeping Condition B in the inbox
   analyst would create a parallel, lower-quality discovery path that conflicts
   with the dedicated command.

2. `shared_ctx.accumulation_index` was removed from the shared-ctx schema in
   T3.1. With the field gone from the schema, Condition B was harmless-but-dead:
   the `absent → skip silently` guard meant it never fired. T3.2 removes the
   dead prose to keep the agent spec lean and unambiguous.

Condition C (Placeholder link trigger) is the retained value: it surfaces
deliberate dead wikilinks the user already wrote as `needs_new_moc` signals,
which is a higher-confidence source of intent than freshly-inferred topic
clusters. The placeholder-wins precedence (F4#4) was expressed in the
A7-vs-B STRICT block that guarded against Condition B overwriting Condition C.
Since Condition B is gone, the STRICT block is also removed — the precedence
is now implicit in ordering: C runs before B ran, and B no longer exists.

## A7 STRICT Block Removed With Condition B

WHY: The STRICT block `# STRICT — A7 (Condition C wins over Condition B)`
existed solely to prevent Condition B from overwriting a `proposed_moc_topic`
already set by Condition C. With Condition B removed, the enforcement context
is gone. The placeholder-wins intent is preserved structurally: Condition C
runs and sets `proposed_moc_topic`; nothing afterwards can overwrite it.

## Condition A and Condition C Text Fully Preserved (T3.2 regression gate)

WHY: T3.2 only removes Condition B and its associated STRICT block. Condition A
(Classification Guard — prevents pre-checking `is_classification: true` MOCs)
and Condition C (Placeholder link trigger — verbatim casing on `proposed_moc_topic`,
F4#2; placeholder-wins-over-inferred precedence, F4#4; silent skip when
`placeholder_links` absent/empty) are unchanged. Test
`tests/test_inbox_analyst_no_condition_b.py` asserts both are intact.

## Version 0.15.0

WHY: Bumped from 0.14.0 for terminology rename: `placeholder_mocs` →
`placeholder_links` / "Placeholder MOC trigger" → "Placeholder link trigger"
(behavior-identical rename). `update-tomo.sh` skips unchanged versions
silently — the bump is required for the edit to ship to the Docker instance.

## Step 7.5 Topical Segmentation — T2.1 (F-41, XDD 016)

WHY this is the core behavioral change of F-41: a single multi-topic inbox item
(e.g. a long voice memo mixing an appointment with an architecture argument) used to
collapse into ONE atomic note, burying the distinct ideas. Step 7.5 splits the item
into conceptual threads and emits one atomic per worthy thread.

WHY agent-side, not a deterministic script (ADR-1): segmentation is a semantic
judgment ("are these the same idea or two?") that only the LLM can make. A regex/
heuristic splitter mis-segments nested quotes and topic drift (see the
nested-quote regex-extraction failure-mode memo, #15). The analyst already holds the
full item text and the scoring rubric, so segmentation lives where the context is.

WHY N actions, not a `threads[]` wrapper (ADR-2): downstream consumers (reducer,
instruction-render, Hashi) already iterate `actions[]` polymorphically. Emitting N
flat `create_atomic_note` entries reuses that contract with zero schema-shape change —
a wrapper object would force every consumer to learn a second nesting level. The
schema's `actions[]` already permits N≥2 `create_atomic_note` from one source.

WHY the >200-word gate (ADR-3): segmentation costs an extra LLM reasoning pass per
item. The overwhelming majority of inbox items are short single-thread captures that
gain nothing from a split. Gating on >200 words confines the cost to items long
enough to plausibly carry multiple threads, and guarantees the ≤200-word path stays
byte-identical to pre-F-41 single-note output (regression CON-2 / A1).

WHY per-thread scoring against each thread's own full text (OQ3): a worthiness score
is a property of a thread's content, not of the whole item. Scoring the merged item
would let a strong thread drag a weak one over the 0.5 gate (or vice versa). Each
thread gets its own worthiness, title, MOC match, and tags — mirroring the existing
voice-transcript "score the full original content" rule, applied per thread.

WHY sub-worthy threads collapse into ONE daily summary, not one update each (OQ4):
fragments that fail the atomic gate are daily-log material. Emitting an `update_daily`
per fragment would spam the daily note with disconnected one-liners. A single summary
of the daily-log-worthy material keeps the daily note coherent.

WHY `source_stem` on EVERY atomic, single- or multi-thread (ADR-4): uniformity.
Consumers must group N atomics back to their originating inbox item; making
`source_stem` conditional ("only when N≥2") forces every consumer to special-case the
single-thread shape. Stamping it always — it is the item's filename stem — gives one
provenance grouping key for all atomics. The schema marks it required on
`create_atomic_note` for exactly this reason.

WHY a single-default-thread fallback on ambiguity/failure: the item must never be
lost. If the LLM cannot confidently segment, it treats the whole item as one thread —
identical to the short-item path — so the worst case degrades to pre-F-41 behavior,
never to a dropped capture.

## Version 0.16.0

WHY: Bumped from 0.15.0 for T2.1 — added Step 7.5 (topical segmentation) and updated
Step 9 to iterate threads (N≥1) and stamp `source_stem` on every `create_atomic_note`
(ADR-4). New feature → minor bump. `update-tomo.sh` skips unchanged versions silently —
the bump is required for the edit to ship to the Docker instance.

## Step 7.5 — Two-Pass Segmentation Rewrite (2026-06-12, v0.17.0)

WHY changed: Live full-flow validation revealed consistent under-segmentation — Sonnet
returned 1 atomic note instead of 2-3 for clearly multi-topic items (voice memos mixing
an appointment, a PKM insight, and a hobby tip). The old wording anchored on "most items
are one thread" and "if unsure → collapse", which biased the model toward the single-note
outcome in the full pipeline's attention context.

WHAT changed: Three coordinated edits:

1. De-biased framing: removed the "most items are one thread" anchor and the
   "unsure → collapse" fallback. The new fallback is explicit: collapse ONLY when the
   body genuinely covers one topic; the model must NOT collapse merely because
   segmentation feels effortful or uncertain.

2. Two-pass enumerate-first structure (Pass A → Pass B): Pass A forces an inventory of
   ALL distinct topics as a flat bullet list BEFORE any merging judgment. Pass B then
   consolidates bullets that are facets of the same concept. The mandatory enumeration
   step is the primary anti-skip mechanism — the model cannot produce a single-thread
   output without first having listed the topics, making under-segmentation visible in
   the reasoning chain.

3. Sharper worked examples: examples now name domain differences explicitly ("three
   different domains → three threads") and include a filler/substance distinction
   (voice memo rambling is not a thread).

EVIDENCE and trade-offs: Isolated A/B testing (old vs new prompt, single-item runs)
showed no measurable advantage for either wording — both segmented correctly in isolation
(trial results: 3/2/1 threads as expected). The under-segmentation is a full-flow
attention problem, not a pure wording problem: in the full pipeline, Step 7.5 competes
with earlier steps for attention, and the "most items are one thread" anchor was the
lowest-resistance path. Enumerate-First is the plausible anti-skip lever because it
requires an intermediate output (the bullet list) before the collapse decision.

False-positive safety: tested against a single-topic essay (Oxygen Not Included, 1376
words, 4 sections) — all trials returned 1 thread with the new prompt; no over-split
observed.

TRIED AND REVERTED (2026-06-12): the two follow-up levers below were both implemented,
live-tested, and rolled back to this 0.17.0 state. The dead-end commits are preserved on
branch `backup/f41-forcing-field-experiment` if the schema field is ever wanted again.

1. Mandatory `topics_enumerated[]` schema field (was v0.18.0): made the Pass A enumeration
   a required, schema-validated output. INEFFECTIVE — the model dutifully enumerated 3–8
   topics yet still emitted the same number of atomics. Enumeration ≠ emission: forcing the
   list does not force action on it. Worse, the apparent "gap" (enumerated > emitted) was
   largely a MEASUREMENT ARTIFACT: the un-emitted enumerated topics were appointments and
   errands (e.g. Apotheke/Zahnarzt/Physio), which correctly route to the daily-log as
   `log_entry`/`log_link` actions and are NOT atomic-worthy by design. The voice memo
   genuinely has one evergreen idea, so 1 atomic is correct, not under-segmentation.

2. Opus 4.8 for the analyst step (was v0.19.0): same correct evergreen-vs-appointment
   discrimination as Sonnet, no measurable segmentation gain, at +57% run cost
   (20-item Pass-1: ~$22.6 opus-analysts vs ~$14.4 sonnet-analysts; 1.67× per-token).
   Reverted to Sonnet — not worth the cost for zero demonstrated win.

Conclusion: the 0.17.0 de-biased two-pass PROMPT is the right floor. Segmentation need not
be 100% (the user edits notes); appointment-vs-evergreen routing already works correctly.

## Version 0.17.0

WHY: Bumped from 0.16.0 for de-biased two-pass Step 7.5 segmentation rewrite
(anti-under-segmentation, F-41). Prompt-only change — no schema or Python touched.
`update-tomo.sh` skips unchanged versions silently — the bump is required for the edit
to ship to the Docker instance.
