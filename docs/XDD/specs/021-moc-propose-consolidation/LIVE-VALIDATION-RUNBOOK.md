# Spec 021 — Live Validation Runbook (T4.3)

> Hand-off for the live-vault validation step that was deferred from the `/implement` run.
> Phases 1–4 (automated) are code-complete and merged on `feat/f-34-msp-condition-b-accumulation`;
> the full host test suite is green (864 passed; the only failures are 8 pre-existing `tests/ide_bridge`
> tests from spec 019, unrelated). This runbook confirms the success metrics on the **real vault**.
> Once the metrics below pass, the spec can be finalized to **Implemented** (see step 5).

## 0. Prerequisites
- The Tomo Docker instance is installed and Kado is running (Obsidian + Kado plugin on `127.0.0.1`).
- You are on branch `feat/f-34-msp-condition-b-accumulation`.

## 1. Sync the instance
```bash
./scripts/update-tomo.sh --yolo
```
Version discipline note: every 021-modified runtime file was version-bumped, so `update-tomo`
will ship them. If a file you expect isn't in the sync output, grep the instance copy — an
un-bumped `# version:` makes `update-tomo` skip it silently.

## 2. Run the three flows (inside the instance / Tomo session)
1. `/explore-vault` — force-rebuilds the MOC-structure cache (ADR-3). First run pre-warms
   `config/moc-structure-cache.yaml`.
2. `/moc-propose` (plain, whole-vault scan) — **post-Feature-6 (ADR-11):** candidates are now the
   **orphan notes** (`up_state==absent`) sourced from the cache (no live `list_dir`, no LLM topic
   extraction). On the real vault that is ~206 orphans < the new cap (500) → it should **no longer
   abort** with `candidate-cap-exceeded`; it emits the proposal-doc (clusters → proposed MOCs, plus
   case-(a) link-or-create). Requires a re-sync first (instance must be `moc-discovery` ≥ 0.13.0 —
   run `update-tomo --yolo`). A **scoped** run (`folder:`/`tag:`/`class:`/`title:`) still considers
   ALL in-scope notes (not orphan-filtered) — use it to make a MOC for a specific theme.
3. `/inbox` — Conditions A + C only (Condition B / accumulation is gone). Placeholder nudge (C)
   should fire from the corrected lean placeholder list.

## 3. Capture metrics (host-vs-Kado technique where scriptable)
Use `KADO_URL=http://127.0.0.1:<port>/mcp` + token from `tomo-instance/.mcp.json`, sandbox off
(see memory `reference_run_tomo_scripts_from_host_against_kado`). Confirm each target:

| Metric | Target | How to read it |
|--------|--------|----------------|
| **M1** | `/moc-propose` does **0** full whole-vault MOC tree-builds when the cache is fresh | second same-day `/moc-propose` should not rebuild (check `last_scan` unchanged; no scan in stderr) |
| **M2/M4** | placeholder false-positives **397 → ~171** | inspect `placeholder_mocs` count in the moc-structure-cache / discovery-cache after `/explore-vault` |
| **M5** | dual-`up` no longer false-orphans frontmatter-`up:` MOCs | a note with frontmatter `up:` (no inline `up::`) is classified `valid`, not orphan, in Phase 6.5 |
| **M6** | inbox shared-ctx envelope **54.5KB → ~34–36KB** | size of the shared-ctx payload for an `/inbox` run |
| **M7** | **0** daily/template notes in `/moc-propose` candidates | scan the proposal-doc — no `Calendar/301 Daily/…` or template-vault entries |
| **M8** | inbox `shared_ctx.mocs` **includes** notes-area `#type/others/moc` MOCs, **excludes** template-vault (`X/…`) MOCs | inspect `shared_ctx.mocs` for an `/inbox` run |
| **M9** | plain `/moc-propose` (scan) proposes from the ~206 **orphans** — no `candidate-cap-exceeded` abort; 0 live `list_dir`; scoped runs still see all notes | run plain `/moc-propose`; confirm a proposal-doc is written (not the abort message) |

Also confirm **no regression** in Condition A/C output vs the captured golden baseline
(`tests/fixtures/021-ac-baseline/ac-baseline.json`).

### Feature 7 (Phase 6) — scan output-quality cleanup

Verified 2026-06-06 against the live vault (host→Kado rebuild of the MOC-structure cache):

| Metric | Target | Result |
|--------|--------|--------|
| **F7-1** | `X/` template-vault excluded from the cache (config-driven) | ✅ rebuilt cache 339 entries / 63 MOCs (was 357/81); **0** `X/…` entries |
| **F7-2** | default scan orphan pass = notes only (no MOC noise) | ✅ `emit_orphan_suggestions(entries)` → 206 emitted, **all `note`** (0 MOCs) |
| **F7-3** | output ordered link_existing-first | ✅ 3 link_existing precede 203 create_new |
| **F7-4** | `orphan_display_cap` truncates with overflow | ✅ unit-tested (60→50 shown, overflow 10); arithmetic over the real 206 → 50 shown / 156 overflow |
| **F7-5** | `/moc-propose check:moc-uplinks` MOC-only, no clustering | ✅ E2E through `main()` on real cache: mode `check-moc-uplinks`, 28 MOC orphans, `topic_clusters` empty |

**Gap (env, not code):** the full default-scan E2E through `main()` (Phase 6.5 reads notes)
hit Kado **HTTP 429** rate-limiting and could not complete in one pass. The cap/notes-only/
ordering are covered by the unit suite + the real-cache orphan-pass dump above; re-run the
plain `/moc-propose` scan E2E inside the container (where Kado is local) to close it.

## 4. Record the run
Add an entry to `docs/evolution/inbox-cost-log.md` via `tomo-session-stats.py`
(see memory `reference_inbox_cost_log` — baseline was 18 items = \$10.71). Note token cost +
the metric outcomes.

## 5. Finalize (after metrics pass)
When M1–M8 are confirmed on real data with no A/C regression:
- Run `Skill(tcs-workflow:xdd-meta)` with `finalize 021-moc-propose-consolidation -- <shippingNotes>`
  (shippingNotes = branch + the headline metrics, e.g. "placeholder 397→N, envelope →NKB, M1 0-rebuild confirmed").
- This flips the spec README to **Implemented** and writes the decision-log row.
- Confirm GitHub issue **#45** (epic #24) still tracks the deferred per-item context shaping.

If any metric misses target, capture the gap and reopen the relevant phase task — do not finalize.
