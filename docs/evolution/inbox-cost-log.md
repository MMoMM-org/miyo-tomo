# /inbox Cost Log

Running log of token usage and estimated cost per live `/inbox` run.
Tracks cost trajectory across implementation versions to catch regressions
and validate optimizations.

**How to add an entry**: After a live run, execute from the repo root:
```bash
python3 scripts/tomo-session-stats.py --session-latest
```
Copy the output into a new row below. Note the conductor/analyst versions
from `tomo/dot_claude/agents/*.md` headers.

**Pricing**: Sonnet 4.6 list rates ($3/$15/$3.75/$0.30 per M tokens for
input/output/cache_create/cache_read). Actual billed cost may differ
(volume discounts, batch API).

---

## Log

### DEFERRED — F-41 multi-topic cost regression (spec 016, GH #32, CON-3)

| Key | Value |
|-----|-------|
| **Date** | PENDING (deferred manual in-container run) |
| **Phase** | Pass 1 (suggest) — F-41 cost regression vs F-32 baseline |
| **Items** | ~20 mixed (single-thread + multi-thread), Privat-Test |
| **Vault** | Privat-Test |
| **Versions** | inbox-analyst (F-41 build, Step 7.5 segmentation), TBD |
| **Baseline** | F-32 (`docs/XDD/specs/016-multi-topic-atomic-notes/README.md:55` nominal ~$26/run on opus; recorded current-architecture anchor ~$10–12 / 18-item Pass-1, 2026-05-26 rows below) |

**Acceptance criterion:** measured Pass-1 main-thread cost increase **≤ +10%**
vs the same-architecture baseline (PRD CON-3 / C2, §7, §10).

| Metric | Baseline (control) | F-41 (segmentation) | Delta |
|--------|--------------------|---------------------|-------|
| Pass-1 main cost | TBD | TBD | TBD (≤ +10%) |
| Total cost | TBD | TBD | — |
| Per-item avg | TBD | TBD | — |
| Items > 200 words | TBD | TBD | — |
| Multi-thread items | — | TBD | — |

**Notes:**
- DEFERRED per user decision: analytical bound documented now in
  [`docs/XDD/specs/016-multi-topic-atomic-notes/cost-analysis.md`](../XDD/specs/016-multi-topic-atomic-notes/cost-analysis.md);
  live measured run is a manual in-container step (host runs hit Kado 429 on
  the heavy read storm — see auto-memory).
- Procedure: run a control (pre-F-41 / single-thread-forced) ~20-item batch and
  an F-41 (segmentation-on) ~20-item batch; capture both via
  `python3 scripts/tomo-session-stats.py --session-latest`; compute the Pass-1
  main-thread delta; confirm ≤ +10%.
- Projected analytical bound (not a measurement): the >200-word gate
  (`inbox-analyst.md:199-203`) means short items pay zero extra; only long
  items pay the one-time ~500–1000-token segmentation prompt (`solution.md:239`)
  → typical ~30%-long batch adds single-digit-% reasoning tokens, inside +10%.
- No fabricated figures: measured columns left TBD until the run is logged.

### 2026-06-16 — Pass 1 (suggest), 21 items, spec-023 T5.1 live validation

| Key | Value |
|-----|-------|
| **Date** | 2026-06-16 |
| **Phase** | Pass 1 (suggest) — MOC placement-fit confidence live walk |
| **Items** | 21 dispatched, 21 `done`, 0 errors (21 subagents, 398 turns) |
| **Vault** | Privat-Test |
| **Versions** | suggestions-reducer v1.10.8, instruction-render v0.24.10, inbox-analyst v0.18.0, moc-tree-builder v0.6.1, shared-ctx-builder v1.5.1 |

| Metric | This run | Baseline (2026-05-26, 18 items) | Delta |
|--------|----------|----------------------------------|-------|
| Main session cost | $2.33 | — | — |
| Subagents cost | $10.45 | — | — |
| **Total cost** | **$12.77** | $10.71 | +$2.06 (3 more items) |
| **Per-item** | **$0.61** | $0.59 | **+2%** (within noise) |
| Model | Sonnet 4.6 | Sonnet 4.6 | — |

**Spec-023 success metrics:**
- **AC-1/4/11 (tier-1 confidence %)** — ✅ live. `under \`## Thinking Frameworks\` (confidence: 90%)` (FPT strong fit) + 50–90% across the run.
- **AC-5/6/7/13 (footer tier-2, the 022 regression)** — ✅ live. Japanese-city notes became `new section \`## Japanische Städte\`/\`Japanische Geographie\`/\`Hokkaido\` (before the footer)` with `## Content` demoted to the **Other sections** advisory — NOT filed under the structural `## Content` heading. Intra-cluster consistency held.
- **No `fit_confidence` leak** — ✅ suggestions doc shows `%`, raw field absent (0 occurrences).
- **AC-9 (no-footer `(at the end of the MOC)`)** — ⚠️ **NOT triggered live this run**: no inbox item fell to tier-2 against a footer-less MOC (Concepts (MOC) only drew the FPT *tier-1* hit). Surfacing + last-body-line resolution are unit-covered (`test_moc_insertion_resolution.py`, `test_suggestions_reducer_t6_1_placement.py`). Accepted on unit coverage (user decision 2026-06-16).

**Notes:**
- Cost envelope held: 023 added zero new LLM passes and zero new Kado reads by design; the +$2.06 is entirely item-count-driven (21 vs 18). Per-item +2% is within run-to-run noise.
- MOC structure cache rebuilt via `/explore-vault` first so `has_footer` was fresh (Concepts (MOC)=false, Japan (MOC)=true, both confirmed in cache).
- Pass-2 (`instructions.json`) not executed this walk; the no-`fit_confidence`-in-action-anchor check rides on `TestEmitFitConfidenceNoLeak` (unit) + the clean Pass-1 doc.

### 2026-06-09 — Pass 1 (suggest), 18 items, spec-021 T4.3 live validation

| Key | Value |
|-----|-------|
| **Date** | 2026-06-09 |
| **Phase** | Pass 1 (suggest) — `/inbox --recover`, full re-process |
| **Items** | 18 dispatched, 18 `done`, 0 errors → 14 sections, 6 daily updates, 5 proposed MOCs |
| **Vault** | Privat-Test (clean, post-reset) |
| **Versions** | moc-tree-builder v0.5.0, placeholder_detect v0.2.0, shared-ctx-builder v1.4.0, inbox-triage v0.8.0 |

**Spec-021 success metrics (all green):**
- **M1/M5/M9/F7** — confirmed (earlier runbook + 206-orphan scan).
- **M2/M4** — placeholder links 397→196 unique (detection: 224-fix + 23 date-shaped periodic-note FPs removed); Condition C feed filtered to 38 MOC-named (`(MOC)`/` MOC`). `placeholder.build`/`moc-cache.build` telemetry now emitted to stderr.
- **M3** — `accumulation_index` absent.
- **M6** — shared-ctx envelope **35,664 bytes** (≤36KB; was 54.5KB).
- **M7** — 0 `X/` template-vault leaks in cache/`shared_ctx.mocs`.
- **M8** — 63 MOCs in `shared_ctx.mocs`, 0 `X/` leaks.

**Notes:**
- `--recover` was broken pre-021 (action flipped but empty dispatch list) — fixed in inbox-triage v0.8.0; this run is the first where all 18 captured items re-dispatched.
- No cutoff on the heavy 18-item dispatch (the original concern): all `done`, no stuck/running, no missing `result.json`.
- Token cost NOT captured this run — in-container validation run, not instrumented via `tomo-session-stats.py`. Metrics validation was the goal; cost-trajectory measurement deferred to a future instrumented run.
- ~~Follow-up #49~~ **closed as not-a-bug 2026-06-10**: the created MOC name uses the normalized `proposed_mocs[].name` field, which DOES apply the convention (`Notemaking`→`Notemaking (MOC)`, `AI MOC`→`AI (MOC)`); test-locked. The initial finding misread the raw `topic` field instead of `name`.

### 2026-05-26 — Pass 1 (suggest), 18 items, batch dispatch

| Key | Value |
|-----|-------|
| **Date** | 2026-05-26 |
| **Phase** | Pass 1 (suggest) |
| **Items** | 18 fresh sources |
| **Vault** | Privat-Test |
| **Model** | Sonnet 4.6 |
| **Versions** | suggestion-conductor v0.3.0, inbox-analyst v0.12.0, inbox-triage v0.4.0, /inbox v0.10.0 |
| **Batch size** | 5 (default) |

| Metric | Main | Subagents (18) | Total |
|--------|------|----------------|-------|
| Turns | 54 | 300 | 354 |
| Input tokens | 3,224 | 351 | 3,575 |
| Cache read | 1,749,587 | 9,783,686 | 11,533,273 |
| Cache create | 100,554 | 1,326,230 | 1,426,784 |
| Output tokens | 63,394 | 62,423 | 125,817 |
| Total context | 1,752,811 | 9,784,037 | 11,536,848 |
| Peak turn ctx | 56,320 | 47,252 | — |
| **Est. cost** | **$1.86** | **$8.85** | **$10.71** |

**Per-item average**: $0.49/item (subagent only), $0.60/item (total).

**Notes**:
- First run with the 018 architecture (triage → routing plan → conductor → batch dispatch).
- Previous architecture (opus main thread + sequential dispatch) cost ~$26 for comparable item count.
- Subagents dominate cost (83%). Next optimization: reduce per-analyst context loading.
- Shared-ctx-builder ran correctly (STRICT block enforced). Batch dispatch 5-at-a-time confirmed.

---

### 2026-05-26 — Transcription stop-gate, 2 audio files (all cached)

| Key | Value |
|-----|-------|
| **Date** | 2026-05-26 |
| **Phase** | Transcribe (stop-gate, all cached) |
| **Items** | 2 audio files, both already transcribed |
| **Model** | Sonnet 4.6 (main), Haiku 4.5 (voice-transcriber) |
| **Versions** | /inbox v0.9.0, voice-transcriber v0.4.0 |

| Metric | Main | Subagents (1) | Total |
|--------|------|---------------|-------|
| Turns | 8 | 15 | 23 |
| Context | 117,301 | 190,535 | 307,836 |
| Output | 960 | 4,296 | 5,256 |
| **Est. cost** | **$0.32** | **$0.30** | **$0.62** |

**Notes**: Minimal cost — stop-gate exits immediately when all audio is cached.

---

### 2026-05-26 — Pass 1 (suggest), 18 items, skill-owned pipeline

| Key | Value |
|-----|-------|
| **Date** | 2026-05-26 |
| **Phase** | Pass 1 (suggest) |
| **Items** | 18 fresh sources |
| **Vault** | Privat-Test |
| **Model** | Sonnet 4.6 |
| **Versions** | suggestion-conductor v0.6.0 (pure router), suggest-handling skill v0.1.0, inbox-analyst v0.12.1, inbox-triage v0.5.0, /inbox v0.10.0 |
| **Batch size** | 5 (default) |

| Metric | Main | Subagents (18) | Total |
|--------|------|----------------|-------|
| Turns | 51 | 373 | 424 |
| Input tokens | 81 | 409 | 490 |
| Cache read | 1,479,900 | 13,140,028 | 14,619,928 |
| Cache create | 117,000 | 1,415,707 | 1,532,707 |
| Output tokens | 56,266 | 68,600 | 124,866 |
| Total context | 1,479,981 | 13,140,437 | 14,620,418 |
| Peak turn ctx | 48,654 | 50,609 | — |
| **Est. cost** | **$1.73** | **$10.28** | **$12.01** |

**Per-item average**: $0.57/item (subagent only), $0.67/item (total).

**Notes**:
- First run with skill-owned pipeline (suggest-handling v0.1.0). Conductor is now a pure 60-line router.
- Pipeline compliance: 7/7 scripts called, 0 errors across main + 18 subagents.
- Batch dispatch working: 4 batches (5/5/5/3), parallel within each batch.
- Cost up ~12% vs previous run ($12.01 vs $10.71). Subagent cache read +34% (13.1M vs 9.8M) — likely due to skill context loading adding to each analyst's prompt. Main session slightly cheaper ($1.73 vs $1.86).
- Coexistence enforcement (reducer v1.2.0) active — no duplication bugs observed.

---

### 2026-05-26 — Fan-resolve, 3 items, skill-owned pipeline (fixed path)

| Key | Value |
|-----|-------|
| **Date** | 2026-05-26 |
| **Phase** | Fan-resolve (force atomic) |
| **Items** | 3 (Furano, Sapporo, Beppu Onsen) |
| **Vault** | Privat-Test |
| **Model** | Sonnet 4.6 |
| **Versions** | suggestion-conductor v0.6.0, force-atomic-handling skill v0.3.0, inbox-analyst v0.12.1, inbox-triage v0.5.0 |

| Metric | Main | Subagents (3) | Total |
|--------|------|---------------|-------|
| Turns | 30 | 60 | 90 |
| Input tokens | 43 | 66 | 109 |
| Cache read | 778,912 | 2,037,470 | 2,816,382 |
| Cache create | 20,638 | 285,788 | 306,426 |
| Output tokens | 12,555 | 14,384 | 26,939 |
| Total context | 778,955 | 2,037,536 | 2,816,491 |
| Peak turn ctx | 31,153 | 46,960 | — |
| **Est. cost** | **$0.50** | **$1.90** | **$2.40** |

**Per-item average**: $0.63/item (subagent only), $0.80/item (total).

**Notes**:
- v0.3.0 fix: analysts now get `<inbox_path>/<stem>.md` instead of `source_path` (suggestions doc). Previous run classified suggestions doc content as "Knowledge Management".
- All 3 dispatched in parallel (single batch). Pipeline compliance: 6/6 scripts, 0 errors.
- Per-item cost slightly higher than suggest ($0.80 vs $0.67) due to fixed overhead amortized over fewer items.

---

### 2026-05-26 — Pass 2 (synthesize), 2 source docs

| Key | Value |
|-----|-------|
| **Date** | 2026-05-26 |
| **Phase** | Pass 2 (synthesize) |
| **Items** | 2 source docs (suggestions + suggestions-fan) → 57 actions |
| **Vault** | Privat-Test |
| **Model** | Sonnet 4.6 |
| **Versions** | synthesis-conductor v0.2.0, inbox-triage v0.6.0, /inbox v0.10.0 |

| Metric | Main | Subagents | Total |
|--------|------|-----------|-------|
| Turns | 41 | 0 | 41 |
| Input tokens | 48 | — | 48 |
| Cache read | 1,392,248 | — | 1,392,248 |
| Cache create | 62,656 | — | 62,656 |
| Output tokens | 19,286 | — | 19,286 |
| Total context | 1,392,296 | — | 1,392,296 |
| Peak turn ctx | 44,394 | — | — |
| **Est. cost** | **$0.94** | **—** | **$0.94** |

**Notes**:
- Pure script pipeline: parse → render → upload → state-flip → coverage diff. No subagents needed.
- Coverage audit: 57/57 actions reconciled — full parity.
- Pipeline compliance: 7/7 scripts called, 0 errors.
- Required inbox-triage v0.6.0 fix (filename-based doc_type inference) — v0.5.0 misclassified fan docs as suggestions, causing infinite fan-resolve loops.

---

### Full /inbox cycle summary — 2026-05-26

| Phase | Items | Cost | Notes |
|-------|-------|------|-------|
| Pass 1 suggest | 18 | $12.01 | suggest-handling v0.1.0 |
| Fan-resolve | 3 | $2.40 | force-atomic-handling v0.3.0 |
| Pass 2 synthesize | 2 docs / 57 actions | $0.94 | No subagents |
| **Total** | **18 sources → 57 actions** | **$15.35** | **3 /inbox invocations** |

---

### 2026-05-27 — MOC Propose, tag `topic/knowledge/lyt`, 30 candidates

| Key | Value |
|-----|-------|
| **Date** | 2026-05-27 |
| **Phase** | MOC Propose (moc-architect) |
| **Items** | 30 candidates → 11 clusters (6 overflow) |
| **Vault** | Privat-Test |
| **Model** | Sonnet 4.6 |
| **Versions** | moc-architect v0.4.0, moc-discovery.py, suggestions-reducer moc-proposal mode |

| Metric | Main | Subagents | Total |
|--------|------|-----------|-------|
| Turns | 33 | 0 | 33 |
| Input tokens | 45 | — | 45 |
| Cache read | 1,270,106 | — | 1,270,106 |
| Cache create | 194,068 | — | 194,068 |
| Output tokens | 49,083 | — | 49,083 |
| Total context | 1,270,151 | — | 1,270,151 |
| Peak turn ctx | 66,504 | — | — |
| **Est. cost** | **$1.85** | **—** | **$1.85** |

**Notes**:
- No subagents — moc-architect runs as impersonated agent with deterministic scripts.
- Topic extraction for 30 cache-miss candidates drove most of the output tokens (49K).
- 6 overflow clusters beyond max_results reported — re-run with narrower query if needed.

---

### 2026-05-27 — Pass 2 (synthesize), MOC proposal, dispatched haiku

| Key | Value |
|-----|-------|
| **Date** | 2026-05-27 |
| **Phase** | Pass 2 (synthesize) — MOC proposal |
| **Items** | 1 MOC proposal (4 accepted MOCs, 1 rejected) |
| **Vault** | Privat-Test |
| **Model** | Sonnet 4.6 (main) + Haiku 4.5 (synthesis-conductor) |
| **Versions** | synthesis-conductor v0.6.0 (haiku, dispatched), moc-proposal-parser v0.1.0, /inbox v0.11.0 |

| Metric | Main | Subagents (1) | Total |
|--------|------|---------------|-------|
| Turns | 9 | 15 | 24 |
| Input tokens | 12 | 74 | 86 |
| Cache read | 179,886 | 139,462 | 319,348 |
| Cache create | 37,731 | 26,148 | 63,879 |
| Output tokens | 1,400 | 1,997 | 3,397 |
| Total context | 179,898 | 139,536 | 319,434 |
| Peak turn ctx | 25,045 | 12,778 | — |
| **Est. cost** | **$0.22** | **$0.17** | **$0.39** |

**Notes**:
- First run with haiku-dispatched synthesis-conductor. Pipeline compliance: 5/5 scripts called in exact order. Zero improvisation.
- 59% cheaper than Sonnet-impersonated run ($0.39 vs $0.94). Haiku follows literal scripts perfectly.
- Partial failures (not conductor bugs):
  - upload-rendered.py: Kado 429 rate limit — 4 MOC notes failed to upload. Instructions + manifest landed.
  - state-promoter.py: exit 1 — missing expectedModified argument. Need to pass from routing plan.
- Kado 429 likely appears because haiku is faster than Sonnet, so upload-rendered fires rapid kado-write calls. Will also affect normal Pass 2 at scale.

---

### 2026-05-27 — Pass 2 (synthesize), MOC proposal, all fixes validated

| Key | Value |
|-----|-------|
| **Date** | 2026-05-27 |
| **Phase** | Pass 2 (synthesize) — MOC proposal |
| **Items** | 1 MOC proposal (4 accepted MOCs, 1 rejected) → 38 actions |
| **Vault** | Privat-Test |
| **Model** | Sonnet 4.6 (main) + Haiku 4.5 (synthesis-conductor) |
| **Versions** | synthesis-conductor v0.7.0, moc-proposal-parser v0.2.0, instruction-render v0.17.0, kado_client v0.5.0, inbox-triage v0.7.0, upload-rendered v0.3.0 |

| Metric | Main | Subagents (1) | Total |
|--------|------|---------------|-------|
| Turns | 8 | 15 | 23 |
| Input tokens | 11 | 67 | 78 |
| Cache read | 187,513 | 129,608 | 317,121 |
| Cache create | 2,044 | 23,444 | 25,488 |
| Output tokens | 1,238 | 1,730 | 2,968 |
| Total context | 187,524 | 129,675 | 317,199 |
| Peak turn ctx | 23,945 | 11,433 | — |
| **Est. cost** | **$0.08** | **$0.15** | **$0.24** |

**Notes**:
- All fixes validated in one clean run: exact stem match (no duplicates), callout up:: regex, Rule 4.2 (old up:: → related::), append mode for related::, state-promoter MODIFIED, 429 retry, triage approved/accepted exclusion.
- 5 children had existing up:: in callout blocks — all correctly detected and preserved as related:: (I30/I32/I34/I36/I38).
- Cost down to $0.24 from initial $0.94 (Sonnet impersonated) — 74% reduction.

---

## Spec 032 — property-resident broken-parent fix (T6.5 live validation)

| Key | Value |
|-----|-------|
| **Date** | 2026-09-03 |
| **Phase** | `/garden-audit` → `/inbox` → Hashi apply (garden path, `tomo_skip_inbox_analysis: true`) |
| **Items** | 42 `broken_up` findings surfaced, 1 approved → 1 action (`edit_frontmatter`) |
| **Vault** | Privat-Test |
| **Versions** | garden-audit 0.5.0, garden-audit-parser 0.14.0, garden-audit-render 0.18.2, render_actions 0.8.0, moc-tree-builder 0.9.1, up_parse 0.2.5 |

**Kado calls**

| Measure | Value |
|---|---|
| MCP-level `kado-*` tool calls by the model | **0** |
| Model tool calls total | 41 (34 Bash, 6 Read, 1 Agent) |
| Script-level HTTP calls to Kado | **not measured** — see caveat |

Caveat, stated rather than glossed: the count above comes from `tool_use` blocks in the container
session JSONL, so it measures what the *model* invoked. Tomo's scripts reach Kado over HTTP through
`kado_client`, which never appears as a `tool_use` block. The zero therefore proves the model added
no MCP round-trips; it does not enumerate script-level traffic.

CON-3 ("no added Kado calls") is nevertheless satisfied **structurally**, which is the stronger
guarantee: `_check_broken_up` takes no `graph_audit_fn` / `list_dir_fn` parameter and so cannot call
out at all, and `up_value` is read from content that `moc-tree-builder.py:410` already parsed for
`up_target`. The new field rides along on an existing read.

**Token table: absent.** `measure-f47-token-cost.py --session-latest` keys on `lifecycle.discovery`
events, which the garden-audit path does not emit (it sets `tomo_skip_inbox_analysis: true` and
never runs discovery). The tool exits with *"No lifecycle.discovery events found"*. Measuring this
flow would need a separate hook — noted here as a gap in the measurement tooling, not as a cost of
this spec.

**Notes**:
- The emitted action was byte-identical to the prediction computed from the wire before the run, and
  validated against the mirrored Hashi schema.
- Routed as `edit_frontmatter` with `operation: "remove"`; after the apply the note's `up:` key is
  gone from its frontmatter, sibling keys and body untouched.
- Two findings filed rather than folded in: the per-finding detail line still said `up::` for
  property-resident findings (fixed, `dd2712a`), and `broken_up` conflates three causes so its
  remedy is wrong for two of them (issue #157).
- The `Atlas/` audit exclusion had to be narrowed for the run and was restored afterwards
  (verified: 329/329 blocked again).

---

## Spec 033 — broken-parent cause split (T5.3 zero-added-vault-access validation)

| Key | Value |
|-----|-------|
| **Date** | 2026-09-04 |
| **Phase** | Phase 5 (`plan/phase-5.md` T5.3) — structural regression validation, not a live pipeline run |
| **Scope** | `garden-audit.py::_check_broken_up` — the single function issue #157's split routes into BOTH `broken_up` and the new `parent_not_moc` (spec 033 ADR-1) |
| **Versions** | garden-audit 0.6.1 |

**No `tool_use` table this entry.** This task validates a structural property of the scripts, not a
live `/inbox` run — there is no container session to pull a `tool_use` count from. Recorded anyway,
because the caveat spec 032 stated for its own T6.5 measurement applies here in advance, not just in
hindsight: a `tool_use` count (had one been taken) measures what the *model* invoked via MCP, not
what Tomo's scripts do over HTTP through `kado_client`. A zero (or an absent count, as here) proves
nothing about script-level traffic on its own — it takes the structural argument below to close that
gap.

CON-1 ("zero added vault access") is proven **structurally**, the same stronger guarantee spec 032's
entry above already leaned on for the pre-033 shape of this same function:
`tests/test_garden_audit_broken_up_no_vault_access.py` asserts (a) `_check_broken_up`'s signature —
`inspect.signature` — accepts no `graph_audit_fn` / `list_dir_fn` parameter (its full parameter set
is exactly `{entries, exclusions, counter}`), and (b) walking the AST of its body (docstring
excluded, so the prose "cache-only, NEVER triggers graph_audit" in its own docstring can't produce a
false hit) turns up no reference to a vault-callable identifier at all — closing the gap a
signature-only check leaves open (a module-level client or an inline `from lib.kado_client import
...` inside the function body would grant access without adding a parameter). Extended to
`_check_unparented` / `_check_duplicate_stem` (the other cache-only checks) for consistency, and
contrasted against `_check_stale_moc` (which legitimately takes `list_dir_fn`) so the guard is shown
to actually discriminate rather than describing every check identically.

Because spec 033 emits `parent_not_moc` from `_check_broken_up` itself — no second function was
added — this one structural proof covers both check outputs. The property is structural, so it
cannot regress silently: any future PR that threads a vault-callable into this function fails the
signature assertion immediately, without needing a live run to catch it.

**Notes**:
- `tests/test_garden_audit_broken_up_no_vault_access.py`: 5 tests, all green.
- `tests/test_garden_audit_render_con3_byte_identity.py` (T5.2, same session): loads
  `garden-audit-render.py` as of `8d866bb` (last commit before Phase 1) via `git show` + `importlib`,
  renders a 7-finding mixed document through both, and asserts every non-broken-parent finding block
  (`unparented`, `orphan`, `dead_link`, `duplicate_stem`, `stale_moc`) is byte-identical by F-id —
  scoped to blocks, not a changed-line count, per the CON-3 rationale in the file's own docstring.
  Guard proven to bite: a deliberate one-word mutation to the `dead_link` detail line (reverted
  immediately after) turned the test red on exactly that block before being reverted back to green.

---

## Spec 031 — ADR-4: `_count_kado_calls` corrected (T5.2)

| Key | Value |
|-----|-------|
| **Date** | 2026-09-05 |
| **Phase** | Phase 5 (`plan/phase-5.md` T5.2) — `inbox-triage.py`'s internal Kado-call estimator, not a live run |
| **Versions** | inbox-triage 0.28.0 → 0.29.0 |

**Discontinuity notice — read before comparing any `kado_calls=` figure across this date.**

`_count_kado_calls(state)` (the estimator behind the `kado_calls=` field in `inbox-triage.py`'s own
stderr metrics line and the `metrics.kado_calls` value in `routing-plan.json`) was **wrong before this
fix** and is a **different, larger number after it** for the same run — not because Tomo now makes
more Kado calls, but because the estimator now counts calls it previously missed entirely.

Before: `_count_kado_calls` returned `5 + body_reads`, while its own docstring claimed
`1 listDir + 7 byFrontmatter + N body reads` (= 8, not 5) — already inconsistent with itself — and
omitted three per-item read sites entirely: `enrich_instructions_frontmatter`'s per-instructions-hit
`read_frontmatter`, `resolve_handlers`' per-new-source `read_frontmatter` (tag-handler resolution),
and `_cache_wire_sibling`'s `read_file_bytes` (four call sites gated by doc_type/approval-state
combinations). T5.1 (same phase) also added a second, recursive `listDir` call, which the estimator
needed to learn about regardless.

After: `_count_kado_calls` returns `2 (listDir) + 7 (byFrontmatter) + instructions_frontmatter_reads +
tag_handler_reads + wire_sibling_reads + body_reads`, verified against a fake client's own observed
`.calls` invocation log (not a second hand-derived expectation) in
`tests/test_031_t5_2_kado_call_counter.py`.

**No entry above this line reports a `kado_calls=` figure**, so nothing in this log's existing token/
cost rows needs correction retroactively — this notice exists so that if/when a future entry logs
`kado_calls=` (from the stderr metrics line or `routing-plan.json`'s `metrics` block), no one
compares it against a pre-2026-09-05 run and mistakes the jump for a regression. The corrected number
is more accurate, not more expensive: real Kado traffic is unchanged by this fix.

**Notes**:
- Known residual approximation, unchanged by this fix and out of this task's narrow scope: `body_reads`
  still undercounts by one per `read_note` call that raises `KadoError` mid-run (the call happened; its
  result lands in `drift_indicators`, not one of the five summed buckets). Documented in
  `_count_kado_calls`'s own docstring.
- Full suite: 3171 passed, 1 skipped, 0 failed. `ruff` clean.
