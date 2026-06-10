# F-34 / MSP — Post-Live-Validation Analysis & Open Design Questions

> **Status:** analysis hand-off, written 2026-06-05 before a `/clear`. Picks up after the F-34
> live validation on the real ~281-note vault. Branch: `feat/f-34-msp-condition-b-accumulation`.
> Read this first in the next session, then decide the three threads (a/b/c) at the end.

---

## TL;DR — the headline finding

F-34 Condition B (vault-side accumulation → propose MOC) **never fired** in the live `/inbox`
run, even though `/explore-vault` worked. Forensic chain (all evidence-backed below):

1. `/explore-vault` built the cache correctly → `discovery-cache.yaml.unclassified_topic_clusters` = **118 clusters**.
2. `shared-ctx-builder` built the `accumulation_index` from those 118 clusters.
3. **But the 15 KB shared-ctx budget (A4) trimmed the accumulation_index to ZERO** (`accumulation_clusters_total=118 accumulation_clusters_kept=0`), so the field was omitted from `shared-ctx.json`.
4. With no `accumulation_index`, inbox-analyst Step 4 Condition B silently no-op'd (A6).
5. The MOC proposals the user saw came **only** from the in-batch/classification-guard path (the inbox items happened to be MOC-stub notes) — **not** from the vault.

**Why the budget trimmed everything:** the shared-ctx was **54.5 KB** (3.5× the 15 KB budget),
dominated by **`placeholder_mocs` = 397** (never trimmed) + 89 `mocs`. The A4 trim sacrifices
accumulation clusters **first/only** (pass 6, after tracker fields and moc-topics), so accumulation
is always fully dropped while placeholders stay untouched.

**And the 397 is itself a bug:** the placeholder targets are mostly **block-reference links**
(`[[Note#^9c2026]]`) and heading refs, not genuine dead MOC links. Over-detection inflates the
envelope → starves accumulation → Condition B dies. Three chained problems.

---

## Evidence (so we don't re-derive it)

- shared-ctx of the live run had **no** `accumulation_index`; top keys: `schema_version, run_id, mocs, tag_prefixes, classification_keywords, placeholder_mocs, daily_notes`.
- Re-running the instance `shared-ctx-builder` (v1.0.0, which DOES have `build_accumulation_index`) against the current cache:
  `accumulation_clusters_total=118 accumulation_clusters_kept=0 ... placeholder_mocs=397 mocs=89 ... bytes=54537`.
- `enforce_budget` pass order (`tomo/scripts/shared-ctx-builder.py:559-625`): 1 tracker descs → 2-4 tracker keyword lists → 5 shorten `mocs[].topics` (879 dropped) → **6 drop `accumulation_index` clusters tail-first**. `placeholder_mocs` is **never** in the trim path.
- `placeholder_mocs` samples from the cache: `'LYT Classification System#^9c2026'`, `'2000 - Knowledge Management#^a7982e'`, … all `referenced_by: Atlas/200 Maps/200 Maps.md`. These are `#^block` / `#heading` anchored links, plus duplicate plain/anchored variants of the same target.
- Cluster overlap (separate but related, measured on the 118-cluster index): **68 % of notes appear in >1 cluster**; one note in 20; 64 cluster pairs at Jaccard ≥ 0.5, many J=1.0 (e.g. `kyoto`/`nara`/`tokyo`/`kamakura` = same 3 notes).
- shared-ctx is read **per inbox item** by every `inbox-analyst` subagent (`inbox-analyst.md:3` "Reads shared-ctx … Invoked per-item"; conductor cats it into each subagent).

Diagnostic technique used (reusable): ran instance scanners/builders from the **host** against live Kado via `KADO_URL=http://127.0.0.1:23027/mcp` + token from `tomo-instance/.mcp.json`, sandbox off. See memory `reference_run_tomo_scripts_from_host_against_kado`.

---

## What shipped this session (branch `feat/f-34-msp-condition-b-accumulation`, commits `976d683..bed7867`)

All two-stage reviewed (spec-compliance → code-quality), tests green (full suite 770 pass; 8 pre-existing `ide_bridge` failures are environmental, unrelated).

- **F-34 015 Phases 4-5**: inbox-analyst Step 4 Condition-B trigger (A3/A6/A7), vault-explorer Step 9 runs the scanner + graceful degrade, E2E test `test_f34_e2e.py`, docs, spec finalized → Implemented (T5.2 live-validation was the open gate).
- **Topic-extraction quality v1/v2** (`topic-extract.py` → v0.4.0): dropped level-2 headings (template noise), tags restricted to a configurable `topic/`-prefix array (`tomo.accumulation.topic_tag_prefixes`), no title single-word split, date-shaped link filter. Live: 166 → ~118 thematic clusters, zero heading/bracket/date noise.
- **Kado rate-limiting** (`kado_client.py` → v0.7.0): retry-with-backoff on 429/503 (Retry-After-aware, clamped). Live: 44 → 0 dropped `up::` reads.
- **vault-explorer Step 10 determinism** (`vault-summary.py` NEW + `vault-explorer.md` v0.12.0): aggregates pre-computed stats → JSON, no inline `python3 -c` → no permission prompt. Also dropped `$(date)` from Step 9.
- **Docs**: `usage.md` (MOC-proposal paths + cache freshness), tier-2 `lyt-moc-linking.md`, `tomo-help.md` v0.2.7 one-liner.
- **Suggestions MOC-proposal rendering (b+c kept, a guarded, d reverted)** — `suggestions-reducer.py` v1.5.0 + `suggestions-render.py` v0.6.0:
  - (b) Proposed-MOC name normalized to `(MOC)` convention (reuse `_ensure_moc_suffix`).
  - (c) Proposed-MOC entry now renders real supporting **note titles** + a **Why** reason line (`_enrich_proposed_mocs`).
  - (a) item↔proposal dedup: was already correct; now test-guarded.
  - (d) overlap-merge: built then **reverted** — inert in `/inbox` (each item yields one topic, so reducer clusters never share notes; real overlap is in the cold-path index / `/moc-propose`, which already has Jaccard-0.80 dedup).

### Instance sync state (IMPORTANT for any re-run)
Synced to the running instance via `update-tomo --yolo` earlier today: **`atomic-note-indexer` 0.3.0, `topic-extract` 0.4.0, `kado_client` 0.7.0**.
**NOT yet synced** (committed in source only): `vault-summary.py` + `vault-explorer` 0.12.0, `tomo-help` 0.2.7, `suggestions-reducer` 1.5.0 + `suggestions-render` 0.6.0. Run `update-tomo --yolo` from the repo root before a re-run if you want the latest in the instance.

---

## The three open threads to analyze after /clear

### (a) Placeholder detection: break links down to NOTES, not block/heading refs
**Problem:** `moc-tree-builder` placeholder detection counts `[[Note#^blockid]]` and `[[Note#heading]]`
anchored links (and duplicate variants) as "placeholder MOCs" → 397, mostly false positives.
A genuine placeholder is a clean dead MOC-name link.
**Fix direction:** in placeholder detection (`moc-tree-builder.py`), strip the `#…` / `#^…` anchor
from each wikilink target and resolve to the **note** before the dead-link test; dedupe by note;
likely also restrict to MOC-shaped / MOC-folder targets. Expected effect: 397 → small number →
shared-ctx shrinks back toward budget → accumulation_index survives → **Condition B lives without
touching A4**. Also fixes Condition C firing on block-ref junk.
**This is the highest-leverage fix** — it is the root of the budget starvation.

### (b) Why does every per-item subagent read the FULL shared-ctx? Can we minimize?
**Observation:** `shared-ctx.json` (54 KB now, 15 KB budgeted) is `cat`'d into **every** inbox-analyst
subagent, every run → cost = size × N items × runs. Pass-1 is the dominant token center (F-32/#40).
**Questions to analyze:** Does each item need ALL of mocs + placeholder_mocs + classification_keywords +
accumulation_index? Could we (i) pass only the slices a given item needs, (ii) pre-filter per item
(e.g. candidate MOCs/clusters relevant to the item's topics) at the conductor level, (iii) reference a
shared file once instead of inlining per subagent, (iv) split the envelope (hot fields inline, cold
fields fetched on demand)? The 15 KB budget is a blunt instrument that currently just starves
accumulation; the real lever may be **per-item context shaping**, not a global byte cap.

### (c) Is the whole auto-MOC-creation concept viable as built? New agent/skill + different file?
**Tension surfaced:** F-34 (accumulation) + F-35 (placeholder) + Condition A (in-batch) all funnel
`needs_new_moc` through the same per-item inbox-analyst path and the same shared-ctx envelope, then
aggregate in the reducer. This couples MOC discovery to the per-item hot path and the size budget.
Plus: cluster overlap (68 %) means naive per-cluster proposals are redundant; MOC-stub notes in the
inbox get re-proposed as new MOCs (no "this item IS a MOC" detection).
**Question to analyze:** Should automatic MOC-creation detection be a **separate agent/skill** running
on the **cold path** (like `/moc-propose`/moc-architect already does on demand) writing to its **own
file** (a dedicated MOC-candidates doc), rather than riding the per-item inbox envelope? `/moc-propose`
(F-43, moc-discovery.py) already does live whole-vault discovery with Jaccard-0.80 dedup and parent
resolution — maybe Condition B should feed THAT, not the inbox shared-ctx. Decide the architecture
before patching more of the inbox path.

---

## Suggested next-session order
1. (a) first — it's the root cause and unblocks Condition B cheaply. Investigate `moc-tree-builder` placeholder detection, fix anchor-stripping + note-level dedup, re-measure shared-ctx size.
2. Then (b) — decide whether per-item context shaping is needed once the envelope is smaller.
3. Then (c) — the architecture question; may reframe how Condition B should surface (inbox vs cold-path agent + own file).
4. Marcus's experiment to see F-34 truly fire: reset vault to pre-first-inbox → `update-tomo --yolo` → `/explore-vault` → `/inbox` with **normal atomic notes** (not MOC stubs) whose topics match vault clusters. Only meaningful AFTER (a), else the budget still starves accumulation.

## Pointers
- Budget trim: `tomo/scripts/shared-ctx-builder.py:559-625` (`enforce_budget`), `build_accumulation_index:258`.
- Placeholder detection: `tomo/scripts/moc-tree-builder.py` (find the wikilink/dead-link scan).
- Condition B consumer: `tomo/dot_claude/agents/inbox-analyst.md` Step 4.
- Suggestions render: `tomo/scripts/suggestions-render.py:121-147` (`render_proposed_mocs`), reducer `_enrich_proposed_mocs`.
- /moc-propose cold-path: `tomo/dot_claude/agents/moc-architect.md`, `tomo/scripts/moc-discovery.py` (has Jaccard-0.80 dedup, parent resolution).
- Live diagnostic technique: memory `reference_run_tomo_scripts_from_host_against_kado`.
