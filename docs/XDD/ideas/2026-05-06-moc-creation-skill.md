# MOC-Creation Skill (F-43)

> Brainstorm spec for proactive MOC creation/proposal outside the inbox flow.
> Created: 2026-05-06 via `/brainstorm`. Next step: `/xdd` to produce PRD.
> Backlog ID: F-43 (Must). Roadmap track: #1 in `docs/XDD/roadmap-obsidian-power.md`.
> **Hashi launch gate: ✅ satisfied 2026-05-07** — Hashi 0.2.0 ships the `create_moc` destination-collision guard + `add_relationship → create_moc` cascade (verified in `Hashi/src/actions/createMoc.ts:40` + `Hashi/src/executor/planner.ts:217`). Handoff pair archived in `_archive/outbox/2026-05/`. F-43 implementation is now unblocked once promoted to spec 013.

## 1. Goal

Add proactive MOC creation/proposal capability to Tomo. Today MOCs are only proposed as a side-effect of inbox processing (Conditions A/B/C in `tier-3/lyt-moc/new-moc-proposal.md`). F-43 adds the **standalone** path: user can ask Tomo to scan a topic-area, the whole vault, or a specific title, and get a MOC proposal that lands in the inbox folder for review and Pass-2 application.

This is the foundation for the rest of the Obsidian-power roadmap (F-44 Garden-Audit, F-45 Weekly Review, F-46 Tag-Audit) — those tracks reason about MOCs as first-class structures.

## 2. Problem It Solves

The inbox-driven MOC trigger is reactive: the user must wait for inbox items to accumulate before a cluster surfaces. Real-world need: the user already knows a topic area is under-organised ("I have shell/zsh/iTerm notes scattered everywhere") and wants to create the MOC now, without waiting for inbox accumulation. F-43 makes the implicit `/scan-mocs` from existing spec a real command, plus adds focused-scope variants.

## 3. Scope

### In-scope (MVP)

- **Three user surfaces, single command**: `/moc-propose` with prefix-routed args (or no args = whole-vault scan).
- **Discovery against existing vault**: candidates pulled via Kado MCP (search byTag, listDir, cache). No new MCP tool needed.
- **Profile-aware**: MiYo (Dewey suffix `(MOC)`, classification 2000-2900) and LYT (plain titles).
- **Single template** (`t_moc_tomo`) for all generated MOCs.
- **Reuse 2-pass pipeline**: proposal-doc lands in inbox → `/inbox` Pass 2 picks up → `instruction-render.py` emits existing `create_moc` + `add_relationship` actions → Hashi applies.
- **Bidirectional linking on creation**: children get `up::` to new MOC; existing `up::` preserved as `related::` (lossless).
- **Reference-skill `obsidian-markdown`** imported as side-effect (lazy-loaded, not user-invocable).

### Out-of-scope (parking lot — see §13)

Bases-integration, multi-mode CLI combo (`folder:X tag:Y`), cascade parent creation, typed templates, LLM sub-cluster H3 sectioning, convenience aliases, granular per-children up:: override, synthetic test vault.

## 4. CLI Surface

Single command, multiple input modes via prefix (whitelist-routed):

| Input | Interpretation | Example |
|-------|----------------|---------|
| (no args) | Whole-vault density scan (= `/scan-mocs` from existing spec) | `/moc-propose` |
| `tag:<prefix>` | Topic-tag scan via `kado-search byTag` | `/moc-propose tag:topic/applied/zsh` |
| `folder:<path>` | Recursive folder scan via `kado-read listDir` | `/moc-propose folder:Atlas/202 Notes/2611 Code Snippets/` |
| `class:<NNNN>` | Profile-aware classification bucket | `/moc-propose class:2600` |
| `title:"<text>"` | Title-seeded discovery | `/moc-propose title:"Shell & Terminal"` |
| `<text>` (no recognized prefix) | Free-text topic match | `/moc-propose "shell und terminal"` |

**Routing rule:** Whitelist-only. Recognized prefixes are exactly `tag:`, `folder:`, `class:`, `title:`. Anything else (including unrecognized `foo:bar`) is treated as free-text. Disambiguates against e.g. `Shell: A Survey` as a title.

**Aliases (parking lot):** `/scan-mocs` ⇔ `/moc-propose` (no args); `/moc-create <title>` ⇔ `/moc-propose title:"<title>"`.

## 5. Architecture

```
User
 │
 │  /moc-propose [args]
 ▼
┌─────────────────────────────────────────────────────────────┐
│  moc-architect agent (NEW — sonnet/medium)                  │
│  - Parses input args, picks discovery mode                  │
│  - Calls moc-discovery.py for candidates + topic scoring    │
│  - Calls moc-parent-resolver (or merged in discovery)       │
│  - Emits proposal data (JSON) to suggestions-reducer        │
└─────────────────────────────────────────────────────────────┘
 │
 ▼
┌─────────────────────────────────────────────────────────────┐
│  suggestions-reducer.py (EXTENDED)                          │
│  - New branch: render MOC-proposal sections                 │
│  - Writes <inbox>/tomo-moc-proposal-YYYYMMDD-HHmm-<slug>.md│
└─────────────────────────────────────────────────────────────┘
 │ (user reviews, ticks accept, optionally edits Title/Location/Template, Parent, Children, Override)
 ▼
┌─────────────────────────────────────────────────────────────┐
│  /inbox Pass 2 (UNCHANGED but parser extended)              │
│  - suggestion-parser.py recognises filename + frontmatter   │
│  - instruction-render.py emits create_moc + add_relationship│
│    + link_to_moc actions (all already in schema)            │
│  - instructions.json hands off to Hashi for execution       │
└─────────────────────────────────────────────────────────────┘
 │
 ▼
Hashi → MOC angelegt, children verlinkt
```

**Touchpoints on existing code:**
1. `tomo/scripts/suggestion-parser.py` — extend to recognise `tomo-moc-proposal-*` filename + frontmatter `tomo_skip_inbox_analysis: true`
2. `tomo/scripts/instruction-render.py` — verify `create_moc` action emission completeness (schema is ready)
3. `tomo/scripts/suggestions-reducer.py` — new branch for MOC-proposal rendering
4. `tomo/dot_claude/agents/inbox-analyst.md` — Step 0 pre-filter respects `tomo_skip_inbox_analysis: true` (additive, no hot-path logic change)

**NOT touched:** `inbox-analyst` analysis logic (hot path — additive only per `feedback_near_mvp_no_breakage.md`), `shared-ctx-builder.py`, `moc-tree-builder.py`.

## 6. Discovery Flow (6 phases)

### Phase 1 — Candidate Selection (mode-dependent)

| Mode | Candidate source |
|------|------------------|
| `tag:<X>` | `kado-search byTag` with prefix-match |
| `folder:<X>` | `kado-read listDir` recursive (`depth=10`, `type=md`) |
| `class:<NNNN>` | Profile subdir lookup (MiYo: `Atlas/202 Notes/<NNNN>*/`; LYT: cache filter) |
| `title:<X>` / free-text | Topic-match against `discovery-cache.yaml::map_notes[].topics` + `atomic_notes` topics |
| (no args) | All notes in `concept_defaults.atomic_note.{base_path,subdirectories}` |

**Strict pre-filter:** All input modes restrict candidates to paths inside `concept_defaults.atomic_note.{base_path,subdirectories}` (from profile). MOCs, daily notes, templates are excluded. `folder:<X>` outside the atomic-note path emits a warning ("path is outside atomic-note scope — proceeding with strict filter") and continues with the intersection.

**Hard cap:** `candidate_cap` (default 200) — exceeded → message + abort.

**Zero-candidates:** If Phase 1 returns 0 → user-facing message "Keine Notes zum Topic gefunden" + early exit. **No proposal-doc is written.**

### Phase 2 — Topic Extraction

- **Cache-first:** Use `discovery-cache.yaml` topics for candidates that have entries.
- **Cache-miss fallback:** `moc-architect` extracts topics on-demand via LLM (sonnet), batched ~10 notes per call.
- **Hard cap on cache-miss batches:** `cache_miss_max_batches` (default 5 = 50 notes max via LLM). Exceeding triggers abort with message "N notes have no cache entry — please run `/explore-vault` first to populate cache".
- **Cache-update (post-MVP):** newly extracted topics flow back into cache. **Out of scope for MVP** — read-only LLM extraction this run.

### Phase 3 — Cluster Detection

- Reuse `tomo/scripts/suggestions-reducer.py::topic_clusters` algorithm (line 507) — same algo, different input set.
- Threshold: ≥`min_notes` (default 3) candidates sharing a topic.
- Output: `clusters[]` — each cluster = `{topic_keywords, note_paths, confidence}`.
- **Multi-cluster shared notes:** highest-weight cluster wins (per existing reducer algorithm; spec references the file rather than re-implementing).

### Phase 4 — Title Generation

Per `tier-3/lyt-moc/new-moc-proposal.md` §7 patterns:
- MiYo: `<TopicName> (MOC)`
- LYT: `<TopicName>` plain
- `title:<X>` mode: use user input verbatim, skip generation
- `/scan-mocs` multi-cluster: one title per cluster

### Phase 5 — Parent Resolution

1. Match topic keywords against profile `classification.categories.keywords`.
2. Look up matching classification-MOC in `discovery-cache.yaml::map_notes[]` (filter: `level=1` OR `tags includes type/others/moc + dewey-id-pattern`).
3. Output `parent_options[]`: top scoring + 1-2 alternatives + "no parent" option.
4. **Fallback (no resolvable parent):** Proposal emitted with `parent_moc: null` (schema accepts this — `"parent_moc": {"type": ["string", "null"]}`). Suggestions doc shows warning "Kein Parent — wird Top-Level MOC". Hashi treats null as top-level (no `add_relationship up::`).

### Phase 6 — Duplicate / Repeat Prevention

Per `tier-3/lyt-moc/new-moc-proposal.md` §8:
- **Exact title match** with existing MOC → skip cluster.
- **80%+ topic overlap** with existing MOC (cache-derived from `map_notes[].topics`) → skip + suggest "Notes sollten an existing MOC linken". Stale-cache risk accepted for MVP.
- **3-run squelch** on rejected proposals (`squelch_runs: 3`). "Rejected" = proposal-doc archived without `[ ] Accept` ticked on the MOC section. Detection via parser scanning the archive.

### Phase 6.5 — Existing up:: Validation (NEW per gap review)

For each candidate-child note, validate any existing `up::` link:
- Resolve target path via Kado.
- If target file exists → existing `up::` is **present** (will be preserved as `related::` per default).
- If target file doesn't exist (broken/deleted) → existing `up::` is **absent** (default behaviour applies — new MOC becomes `up::`, no related preservation needed). Doc-body notes "broken existing up:: ignored" for transparency.

## 7. Suggestions Doc Shape

**Filename:** `<inbox_path>/tomo-moc-proposal-YYYYMMDD-HHmm-<topic-slug>.md`
- MiYo: `100 Inbox/tomo-moc-proposal-20260506-1430-zsh.md`
- LYT: `+/tomo-moc-proposal-20260506-1430-zsh.md`

**Frontmatter:**

```yaml
---
type: tomo-proposal
proposal_kind: moc
created: 2026-05-06 14:30
trigger: tag:topic/applied/zsh
status: pending
tomo_skip_inbox_analysis: true
---
```

**Body (one proposal — MiYo profile):**

```markdown
# MOC-Vorschlag

## 🔍 Shell & Terminal (MOC)

**Trigger:** tag:topic/applied/zsh
**Confidence:** 78%
**Cluster:** 5 Notes — shell, terminal, zsh, dotfiles

### Suggestion — [ ] Accept

- Title: `Shell & Terminal (MOC)`
- Location: `Atlas/200 Maps/`
- Template: [[t_moc_tomo]]

### Parent

- [x] up:: `[[2600 - Applied Sciences (MOC)]]` (confidence 0.85)
- [ ] up:: `[[Coding Tools (MOC)]]` (confidence 0.45)
- [ ] kein parent (top-level MOC)

### Children (5)

- [x] `[[oh-my-zsh]]` (existing up:: `[[2600 - Applied Sciences]]` → wird `related::`)
- [x] `[[zsh Aliases]]` (kein up:: bisher)
- [x] `[[iTerm Configuration]]` (existing up:: `[[2600 - Applied Sciences]]` → wird `related::`)
- [x] `[[Bash vs Zsh]]` (kein up:: bisher)
- [x] `[[Tmux Setup]]` (kein up:: bisher)

### up::-Handling Override

- [ ] **Bestehende up:: behalten, neue MOC als `related::`** (gilt für alle 5 Children)

### Why this proposal

5 Notes mit Topic-Overlap shell/terminal/zsh haben keine dedizierte MOC. 3 davon
haben up:: zur Klassifikation 2600 (zu generisch). Diese MOC würde die Lücke
füllen.

---
```

**Editable fields (text, no checkbox):** Title, Location, Template (wikilink). User edits inline.

**Choice fields (checkbox):** Top-level Accept, Parent (single-select among alternatives), Children (multi-select per child), Override (single sammel-toggle).

**Multi-MOC (`/scan-mocs`):** multiple `## 🔍 <Title>` sections in one doc, one per cluster, max `max_results` (default 5). Excess clusters listed at the bottom: "Weitere %N Cluster gefunden — re-run später".

## 8. up:: Behaviour (Default vs Override)

**Default (Override unchecked):**
- Each accepted child: `up:: <new MOC>` set/replaced.
- If child had existing `up:: <X>` and `<X>` resolves to a real file → `related:: <X>` added (preserved).
- If existing `up::` was broken → just set new `up::`, no related-preservation.

**Override (checkbox ticked):**
- Each accepted child: existing `up:: <X>` kept as-is.
- New MOC added as `related:: <new MOC>`.
- If child had no existing `up::` → new MOC still becomes `up::` (Override only affects children with valid existing up::).

**Render output:** `instruction-render.py` emits `add_relationship` actions per child, with the child's specific existing-up:: target. Group-level checkbox just flips the **direction** of the move; per-child existing-up:: values are preserved individually.

## 9. Pass-2 Reconciliation

1. **Discovery:** `suggestion-parser.py` extension recognises `tomo-moc-proposal-*` filename OR `frontmatter.type == "tomo-proposal"`. Dispatches into MOC-branch.
2. **Parse:** Per `## 🔍 <title>` section with top-level `[ ] Accept` ticked: extract Title, Location, Template, Parent (single `[x]`), Children (all `[x]`), Override-flag.
3. **Action emission via `instruction-render.py`:**
   - 1× `create_moc` (source = inbox-path of rendered MOC, destination = Location/Title.md, `parent_moc` = stem from Parent (or null), `supporting_items` = children stems for link_to_moc expansion)
   - N× `add_relationship` per child (marker `up::` or `related::` per Override-flag, with the child's specific existing up:: target preserved as needed)
4. **Hashi apply:** Standard `instructions.json` hand-off. Hashi understands all action types (existing schema). **Pre-flight check:** Hashi MUST verify destination path doesn't exist before `create_moc` (filename-collision guard); if exists, action fails with `applied: false` + `error_msg`, user is informed via instruction-set status.
5. **Cleanup:** `instruction-set-cleanup` (existing) finds the proposal-doc post-apply, tags `status/done/✅`, archives.

## 10. Configuration

New keys in `vault-config.yaml::tomo`:

```yaml
tomo:
  moc_proposal:
    min_notes: 3                    # cluster threshold
    confidence_threshold: 0.15      # min topic-overlap to include candidate
    max_results: 5                  # max MOCs per /scan-mocs run
    candidate_cap: 200              # hard cap, cost-protection
    cache_miss_max_batches: 5       # hard cap on LLM cache-miss extraction (50 notes)
    squelch_runs: 3                 # rejected proposal silenced for N /inbox runs
```

Profile-bound settings (`map_note.paths`, `classification.categories`, title pattern) stay in `tomo/profiles/{miyo,lyt}.yaml` — no duplication.

**Reference-skill import:** `obsidian-markdown` skill imported as `tomo/skills/obsidian-markdown/` during this track (lazy-loaded, `user-invocable: false`). `moc-architect` agent references via frontmatter `skills:` for callout/wikilink/embed syntax correctness.

## 11. Testing Strategy

Per `feedback_test_scope_personal_vault.md` (pre-launch QA = MiYo architecture + Marcus's real vault, no synthetic test vault).

**Layer 1 — Unit tests** (`tests/test_moc_discovery.py`, `tests/test_suggestion_parser_moc_branch.py`):
- Phase 1 candidate selection per mode (mocked Kado)
- Phase 3 cluster detection (fixture topic-overlap matrices)
- Phase 4 title generation (MiYo + LYT)
- Phase 5 parent resolution + null fallback
- Phase 6 duplicate / squelch / overlap branches
- Phase 6.5 broken existing up:: handling
- Parser: skip-flag detection, single-MOC, multi-MOC, partial accept (some children unticked)

**Layer 2 — Integration** against `Privat-Test/`:
- Setup: ≥1 cluster of 3+ atomic notes without dedicated MOC
- One run per input mode (`tag:`, `folder:`, `class:`, `title:`, free-text, no-args)
- Verify proposal-doc shape, then `/inbox` → verify Pass 2 emits correct actions, Hashi applies, MOC lands in `Atlas/200 Maps/`, children get correct `up::`/`related::`.

**Layer 3 — Live-vault validation** (Marcus's real vault):
- Pre-merge: 1 run per input mode against a known cluster
- Review proposal quality, parent-resolution, up::-Override flow

**Coverage gates (CI):**
- 100% pass on new Python modules
- Smoke-integration: one `/moc-propose tag:` run against Privat-Test
- `ruff` + repo-style lint

## 12. Approaches Considered

**A. New agent + script + reuse Pass-2 (RECOMMENDED, chosen).** Additive, respects hot-path constraint, builds on XDD-012 FAN-resolve pattern, almost all schema work already done.

**B. Inbox-analyst mode-switch.** Rejected — violates `feedback_near_mvp_no_breakage.md` (inbox-analyst is hot path, additive only). Mode-switch is not additive.

**C. Bypass 2-pass — direct Hashi apply.** Rejected — breaks 2-pass invariant the user explicitly chose to preserve in §4 review-flow question.

## 13. Parking Lot

| Item | Future trigger |
|------|---------------|
| Bases-integration when MOC has uniform-frontmatter children | Post-F-43, separate F-ID |
| Multi-mode CLI combo (`folder:X tag:Y` AND-filter) | When single-mode insufficient (user signal) |
| Cascade parent creation (parent itself a placeholder) | F-44 Garden-Audit or later F-ID |
| Typed templates (`t_moc_project`, `t_moc_person`, etc.) | When `t_moc_tomo` shows as too generic |
| LLM sub-cluster + H3 sub-sectioning | Existing F-30 / F-36 backlog items |
| Convenience aliases `/scan-mocs`, `/moc-create` | When user friction with prefix system surfaces |
| Cache-update after on-demand topic extraction | Post-MVP optimisation |
| Granular per-child up:: override | When sammel-override too coarse in practice |
| Synthetic test vault with generated clusters | Post-launch QA expansion |
| Configurable thresholds via vault-config UX | Existing F-06/F-07/F-08 — not duplicated here |

## 14. Open Questions for `/xdd-prd`

The PRD needs to formalise:
- Exact slugification rule for `<topic-slug>` in proposal-doc filename (e.g. how to derive from a free-text input — strip umlauts? lowercase?)
- Exact format for "warning" rendering in suggestions doc (separate callout? inline italic? quote block?)
- Whether `confidence_threshold` and `max_results` cause the PRD to bump F-07/F-08 (`Could`) into MVP scope, or stay hardcoded for F-43 launch
- Behavioural spec for `/moc-propose` when invoked without `/explore-vault` ever having run (cache empty)
- Whether `moc-architect` should produce a JSON intermediate file (similar to per-item-result in inbox flow) or directly call `suggestions-reducer.py`
- **Action-payload split:** §9 Step 3 says `create_moc` carries `supporting_items` (children stems) but §8 describes per-child `add_relationship` actions that need each child's existing `up::` target. Decide whether `supporting_items` alone is enough to drive `link_to_moc` expansion, or whether `instruction-render.py` needs a richer per-child payload (e.g. `[{stem, existing_up}]`) to correctly preserve existing-up:: as `related::`.
- **Squelch archive scanning mechanism (§6 Phase 6):** Where are archived proposal-docs stored? How does the parser locate them for the 3-run squelch check? No existing reference implementation to lean on — PRD must spec the archive path convention and detection algo.
- **Multi-MOC filename slug:** For `/scan-mocs` producing multiple clusters in one doc, `<topic-slug>` is ambiguous (whose topic?). Options: (a) use a fixed slug like `scan` or `multi`, (b) concatenate top-N cluster slugs (`zsh-tmux-fzf`), (c) use only the highest-confidence cluster's slug. Pick one in PRD.

## 15. References

- `docs/XDD/reference/tier-2/workflows/lyt-moc-linking.md` — workflow context
- `docs/XDD/reference/tier-3/lyt-moc/moc-matching.md` — scoring algorithm (reused)
- `docs/XDD/reference/tier-3/lyt-moc/new-moc-proposal.md` — proposal shape, conditions, title patterns (reused)
- `docs/XDD/reference/tier-3/lyt-moc/section-placement.md` — section placement (touched indirectly)
- `tomo/schemas/instructions.schema.json` — `create_moc`, `add_relationship`, `link_to_moc` action shapes
- `tomo/profiles/miyo.yaml`, `tomo/profiles/lyt.yaml` — profile-specific conventions
- `tomo/config/templates/t_moc_tomo.md` — single MOC template
- `docs/XDD/specs/012-force-atomic-note/` — XDD-012 FAN-resolve, the architectural precedent for proposal-companion-doc + parser-extension pattern
- `docs/XDD/backlog.md` — F-34/F-35 (inbox-driven MOC triggers, complementary), F-13 (`/scan-mocs` originally YAGNI — superseded by F-43)
- `docs/XDD/roadmap-obsidian-power.md` — track #1, prerequisite for F-44/F-45/F-46
