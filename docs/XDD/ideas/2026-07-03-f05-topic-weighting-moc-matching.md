# F-05 — Topic Weighting in MOC Matching

> Brainstorm output — validated design, ready for `/xdd`.
> Epic #17 MOC Intelligence (P0, MVP-Polish). Fenced out of spec 022 (022 = insertion-point / WHERE inside a MOC; F-05 = MOC selection / WHICH MOC).

## Problem

Topic-set matching in the /inbox flow treats every topic with equal weight (flat Jaccard).
An inbox item/cluster can therefore match the wrong MOC when a **content keyword**
coincidentally overlaps, even though the **title-derived** topics disagree. Marcus has seen
this misfire live — **mainly on proposed MOCs** (duplicate detection) but also on **normal /
existing MOCs** (item→MOC link selection). The original inbox that produced it is archived and
not trivially recoverable.

**Goal:** weight title-derived topics higher than content keywords so title agreement wins
over incidental content overlap — applied consistently at both match sites.

## Scope — Two Match Sites, One Rule

The same weighting principle is expressed in two execution substrates:

| Site | Mechanism | Location | F-05 change |
|------|-----------|----------|-------------|
| **1 — Dedupe** ("proposed MOCs": does a new cluster already exist as a MOC?) | Deterministic Python scorer | `tomo/scripts/moc-discovery.py` → `_find_jaccard_match` (~line 1174), called at ~1279 in `phase6_dedupe` | Weighted-overlap scorer in a shared lib |
| **2 — Item→MOC link** ("normal MOCs": which existing MOC does an item link under?) | LLM recipe (inbox-analyst) | `tomo/dot_claude/agents/inbox-analyst.md` Step 4 "Match MOCs" (lines 116-120) | Title-weighting rule added to the overlap-ratio recipe |

Both say the same thing: **title-derived topics outweigh content keywords.** Site 1 is the
numerically precise implementation; Site 2 is a deliberately simplified, LLM-executable
version (see §Site 2).

## The Weighting Rule (shared definition)

For a note `N` and topic `t`:

```
w_N(t) = W_TITLE (2)  if  title_derived(t, N)
       = W_BASE  (1)  otherwise
```

**`title_derived(t, N) := normalize(t) is a substring of normalize(title_N)`**, where
`normalize()` is the existing `.strip().lower()` + whitespace-collapse already used for topics
(`moc-discovery.py` line ~1124). **No stemming, no n-grams.** Substring membership handles
multi-word topics cleanly (`"machine learning"` ⊂ `"Machine Learning Applications"`).

`W_TITLE` / `W_BASE` are **named constants** so a later config-driven variant (parking lot,
approach C) is a value swap, not a rewrite.

**Empty / missing title** → no topic is title-derived → the note contributes only `W_BASE`
weights. This is the **intended** graceful degradation (a note with no title matches on flat
weights), not a silent edge case.

## Site 1 — Deterministic Scorer

New module `tomo/scripts/lib/topic_match.py` (kept separate from `topic_signature.py`, which
owns hashing — no overloading). Public function computes weighted overlap:

```
score(A, B) = Σ_{t ∈ A∩B} min(w_A(t), w_B(t))
              ─────────────────────────────────
              Σ_{t ∈ A∪B} max(w_A(t), w_B(t))
```

**Convention (load-bearing):** a topic absent from a note contributes weight `0` on that side.
So a union-only topic `t` (present in only one note) scores `max(w_present, 0) = w_present` in
the denominator and never appears in the numerator.

`_find_jaccard_match` gains a `cluster_title` parameter and reads each candidate MOC's title
from the `map_notes` entry (`entry["title"]`, already present; falls back to path stem exactly
as `_find_exact_title_match` does at lines 1163-1169). Both titles are already in the cache —
no new data source.

### Score-scale behavior (corrected — do not overstate backward-compat)

The weighted formula reduces **identically** to flat Jaccard **only when neither note has any
title-derived topic at all** (all weights `W_BASE`). Because most real notes *do* have
title-derived topics, weighting **actively re-scores** the general case:

- An **unshared** title-topic on one side adds `W_TITLE` to the denominator (`max`), lowering
  the score — this is what pushes incidental content-only overlap below threshold (the fix).
- A match whose shared topics **are** title-aligned keeps a high score (true dups survive).

Worked sanity check (both sides have differing title-topics):
`A={x,y}` title→`{x}` (`w_A`: x→2, y→1); `B={x,z}` title→`{z}` (`w_B`: x→1, z→2); shared `{x}`,
union `{x,y,z}`:
- numerator = `min(w_A(x), w_B(x)) = min(2,1) = 1`
- denominator (treat a missing side as weight 0): `max(2,1)=2` (x) `+ max(1,0)=1` (y) `+ max(0,2)=2` (z) `= 5`
- **weighted score = 1/5 = 0.20** vs **flat Jaccard = 1/3 ≈ 0.33**

This lower score for incidental-overlap-with-title-disagreement is the intended discrimination.

### Threshold

`JACCARD_DUP_THRESHOLD = 0.80` is **kept**, but its validity under the new score scale is an
**in-scope done-criterion** (decision 2026-07-03): during implementation, run
`analyze-placement-confidence.py` on the personal vault to confirm 0.80 still separates
true-dups from incidental overlap. **Re-tune only if the data shows misseparation.** (Formal
threshold re-derivation as a standalone effort stays in the parking lot.)

### Squelch-signature invariance (explicit)

`compute_topic_signature` (the squelch registry key) continues to operate on the **flat** topic
set (`lib/topic_signature.py`) — it is **decoupled** from weighting. F-05 introduces **no**
cache schema change, **no** version bump, and **no** squelch-key churn. A golden-hash test
locks this.

## Site 2 — Analyst Overlap Recipe

Modify `inbox-analyst.md` Step 4 (lines 116-120). Current:

```
overlap_ratio over item topics (tokenise body + tags, lowercase, strip stopwords)
Score = overlap_ratio + (0.1 depth_bonus if not classification)
Keep top 3 with score ≥ 0.15
```

F-05 change — a topic is weighted **`W_TITLE` (2)** if it is title-derived on **either side**
(Option A: title-derived in the item's title OR the MOC's title), else **`W_BASE` (1)**. This
applies to **both** shared topics and union-only topics (a one-sided topic is weighted by
whether it is title-derived on the side where it appears):

```
overlap_ratio = weighted_shared / weighted_union
```

The MOC title is in `shared_ctx.mocs[].title`; the item's H1/title is in the raw item — both
available, mirroring Site 1. `W_TITLE`/`W_BASE` values are stated **inline in the prompt** so
the recipe is auditable and honors the **same constants and the same rule** as Site 1 (title
agreement outweighs content overlap) — see the substrate-asymmetry note below for why the
numbers are not identical.

**Deliberate substrate asymmetry:** Site 1 uses exact `min/max` (Ruzicka); the analyst uses
the plainer "shared topic counts double if title-derived on either side" — LLMs execute a
simple ratio far more reliably than `min/max` bookkeeping. The two agree on the *decision*
(title agreement beats incidental content overlap); Site 1 is the numerically precise one. This
asymmetry is intentional and documented.

**Unchanged:** the `≥ 0.15` keep-gate, the `top 3` cap, **and the `+0.1` depth bonus for
non-classification MOCs** all survive — only the `overlap_ratio` computation changes. Weighting
re-ranks, it does not re-gate.

**Process:** the `inbox-analyst.md` edit goes through `tcs-helper:agent-author` (authoring
rule), not a raw hand-edit.

## Testing Strategy

**Site 1 (deterministic — Constitution L1: happy + rejection):**

- **Misfire fixture** — cluster & MOC share only incidental *content* keywords, title-topics
  disagree → **flat Jaccard ≥ 0.80 (false dup) but weighted < 0.80 (correctly rejected).**
  Fails without the fix, passes with it (the regression guard).
- **True-dup fixture** — title-topics agree → stays ≥ 0.80 (no regression on real duplicates).
- **Zero-title-topic property** — neither note has a title-derived topic → `weighted == flat`
  exactly (locks the only true reduction case).
- **Empty/missing-title fixture** — degrades to flat contribution, no crash.
- **Long-title case** — many title-derived topics on one side; assert scores stay bounded and
  sensible (weight is capped at `W_TITLE` regardless of title length).
- **Empty topic sets** → `(None, 0.0)` unchanged.
- **Squelch-invariance** — golden-hash assertion that `compute_topic_signature` output is
  byte-identical before/after.
- Both the scorer and the `_find_jaccard_match` call site are exercised.

**Site 2 (LLM recipe — honestly scoped, not deterministically unit-testable):**

- `agent-author` audit of recipe precision.
- A worked example embedded in the spec that the recipe can be checked against.
- **One live `/inbox` run** on the personal vault (batched per the "minimize live-test cycles"
  discipline).

**Gates:** tests under `./venv/bin/python`; `./venv/bin/ruff check` at the implement phase gate.

## Approaches Considered

- **A — Typed topics at extraction (schema change).** `topic-extract.py` emits `{topic,
  source}`; cache stores typed topics. Most principled (exact provenance) but: cache schema
  version-bump + full rebuild, wide plumbing changes, and squelch-signature stability risk.
  **Rejected** — too heavy for a "Could" item near MVP; the title-token proxy captures the same
  intent.
- **B — Title-derived weight at match time (CHOSEN).** No cache/schema/signature change; titles
  already in cache; `topic-extract` method-1 already derives title topics so the proxy is
  faithful; smallest blast radius; honors "near-MVP additive-only."
- **C — Config-driven weights.** B's mechanism with weights in vault-config (profile-agnostic,
  aligns epic #20). **Deferred** (parking lot) — YAGNI now; named constants make it a later
  swap.

## Parking Lot (explicitly out of scope)

1. **H3-heading topics as a weighting signal** — H1 ≈ note title, H2 is structural boilerplate
   ("Core Concepts", "Thinking Frameworks"), but H3 may carry real sub-topic beef. Unmeasured;
   own investigation.
2. **Recover the archived original inbox** to replay the exact real misfire as a golden fixture
   (upgrades the synthetic Site-1 fixture).
3. **Config-driven weights (approach C).**
4. **Standalone threshold re-derivation** beyond the in-impl validation (analyzer sweep to set
   a data-driven `JACCARD_DUP_THRESHOLD` / analyst `≥ 0.15` gate).
5. **Typed-topics-at-extraction (approach A)** — only if the title-token proxy proves
   insufficient in practice.

## Decisions Log

| Date | Decision |
|------|----------|
| 2026-07-03 | Both match sites in scope (dedupe + item→MOC selection). |
| 2026-07-03 | Approach B (title-derived weight at match time); no cache/schema/signature change. |
| 2026-07-03 | `title_derived` = normalized-substring test; no stemming/n-grams. |
| 2026-07-03 | Site 2 "either side" = Option A (item OR MOC title). |
| 2026-07-03 | Keep `JACCARD_DUP_THRESHOLD = 0.80`; validate via `analyze-placement-confidence.py` as an in-scope done-criterion; re-tune only if data shows misseparation. |
| 2026-07-03 | "Reduces identically to flat Jaccard" corrected — holds only when no topic is title-derived on either side; weighting actively re-scores the general case. |
