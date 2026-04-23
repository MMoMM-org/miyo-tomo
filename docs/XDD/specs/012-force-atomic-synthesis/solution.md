# XDD 012 — Solution Design (SDD)

## 1. High-level flow

```
 Run N  (Pass 2, first attempt after user ticked FAN on Furano)
 ────────────────────────────────────────────────────────────────
   instruction-builder (main thread)
     │
     ├─ Step 1  load config
     ├─ Step 2  parse suggestions.md → parsed-suggestions.json
     │          parser detects: Furano has FAN + no per-item section
     │          parser output carries pending_fan_resolutions: [ "Furano" ]
     │
     ├─ Step 2.5  FAN RESOLVE SUBFLOW  (new)
     │   │
     │   ├─ dispatch inbox-analyst (force_atomic=true) for Furano
     │   ├─ reducer --fan-resolve-mode
     │   ├─ render → tomo-tmp/suggestions-fan-rendered.md
     │   └─ kado-write <inbox>/<YYYY-MM-DD_HHMM>_suggestions-fan.md
     │
     └─ HALT  (report to user, skip Step 3+)

 ░░░  User reviews <date>_suggestions-fan.md, ticks [x] Approved  ░░░

 Run N+1  (Pass 2, reconciliation)
 ────────────────────────────────────────────────────────────────
   instruction-builder (main thread)
     │
     ├─ Step 1  load config
     ├─ Step 2  parse MULTI-DOC mode:
     │            main doc suggestions.md + companion suggestions-fan.md
     │          parser merges atomic sections from fan doc into main doc
     │            items by stem
     │          parsed-suggestions.json has Furano as confirmed_item w/
     │            create_atomic_note AND update_daily — ready to render
     │          pending_fan_resolutions is empty → proceed
     │
     ├─ Step 3  render + write notes + instructions.{md,json}
     ├─ Step 4  write outputs to vault (unchanged from current flow)
     ├─ Step 5  coverage audit
     └─ Step 6  report

 ░░░  User applies instructions  ░░░

 Run N+2  (cleanup)
 ────────────────────────────────────────────────────────────────
   vault-executor  —  archives BOTH suggestions docs
```

## 2. Data shape changes

### 2.1 `parsed-suggestions.json` — new top-level key

```jsonc
{
  "confirmed_items": [...],
  "daily_updates":   [...],
  "skipped":         [...],
  "pending_fan_resolutions": [          // NEW — empty when nothing pending
    {
      "stem":        "Furano",
      "source_path": "100 Inbox/Furano.md",
      "log_entry_summary": "Journey notes — Furano + Biei day trip"
    }
  ],
  "total_sections": N,
  "total_approved": M,
  "total_skipped":  K
}
```

`pending_fan_resolutions` is populated by the parser ONLY when (a) a FAN
log_entry has no matching per-item section in the primary doc, AND (b) no
companion fan-resolve doc provides a matching atomic section. This
prevents infinite loops (once the resolve doc is present, the item stops
appearing in pending).

### 2.2 Suggestions-doc shape — **unchanged**

The fan-resolve doc uses the SAME `suggestions-doc.schema.json`. It is a
valid Suggestions document. Differences are data-driven, not schema:
- `daily_updates: []` (empty — resolve doc only re-proposes atomics).
- `items: [...]` — one per force-atomic target.
- Top-level `- [ ] Approved` checkbox present as usual.
- Title string carries `Force-Atomic Resolve` as a human-readable
  discriminator (set by reducer in resolve mode).

### 2.3 `item-result.json` — no schema change

`inbox-analyst` with `force_atomic=true` simply emits a `create_atomic_note`
action it would otherwise have suppressed. No new fields needed.

## 3. Component responsibilities

### 3.1 `scripts/suggestion-parser.py`

**New inputs.** `--file` (existing) + `--fan-resolve-file` (optional). If
`--fan-resolve-file` is omitted, parser auto-discovers a sibling
`*_suggestions-fan*.md` in the same directory as `--file` (when called
with a local tomo-tmp path this means a sibling in tomo-tmp; the agent
arranges both files to exist there side by side before calling).

**Behaviour.**

1. Parse the primary file (existing logic).
2. If `--fan-resolve-file` is provided (or auto-discovered), parse it
   into a lookup `{stem → atomic_section}`.
3. Reconcile FAN log_entries:
   - Per FAN log_entry, attempt in order:
     a. Primary-doc per-item section with matching stem → PROMOTE
        (existing behaviour from commit `2665f81`).
     b. Resolve-doc atomic section with matching stem → PROMOTE as
        confirmed_item with `force_atomic: true` marker + `from_resolve:
        true` for trace.
     c. Neither found → add `{stem, source_path, log_entry_summary}` to
        `pending_fan_resolutions[]`.
4. Emit the unified output. `total_approved` counts a through b as
   approved; c does not add to approved.

**Exit codes.** Unchanged. Parser always exits 0 on successful parse;
callers branch on the JSON content (`pending_fan_resolutions` non-empty
means "halt and resolve").

### 3.2 `dot_claude/agents/inbox-analyst.md`

**New input param.** `force_atomic: bool` (default false), passed by the
orchestrator/builder in the dispatch prompt.

**Behaviour change.**

- Step 7 (worthiness) gate: if `force_atomic=true`, ALWAYS emit
  `create_atomic_note` regardless of the computed score. The score is
  still reported in the result JSON for transparency, but is not a gate.
- All other steps run as usual (date_relevance, daily-note
  classification, MOC matching, tag proposals, etc.).

Legacy callers pass `force_atomic=false` by default — no regression.

### 3.3 `dot_claude/agents/instruction-builder.md`

**New Step 2.5 — FAN Resolve Subflow.**

Inserts between existing Step 2 (parse) and Step 3 (render). Runs ONLY
when `parsed-suggestions.json.pending_fan_resolutions` is non-empty.

```
Step 2.5 — FAN Resolve Subflow

If parsed-suggestions.json has pending_fan_resolutions entries, do NOT
render. Instead:

(a) Ensure scratch dirs:  mkdir -p tomo-tmp/items
(b) For each pending entry, dispatch `inbox-analyst` via Agent in one
    message (fan-out) with prompt carrying:
      stem, path, shared_ctx_path, state_path, items_dir, run_id,
      force_atomic: true
(c) Wait for all to reach `done`/`failed` in the state-file.
(d) Run reducer in resolve mode:
      python3 scripts/suggestions-reducer.py
        --state tomo-tmp/inbox-state.jsonl
        --items-dir tomo-tmp/items
        --run-id <RUN_ID>
        --profile <PROFILE>
        --fan-resolve
        --output tomo-tmp/suggestions-fan-doc.json
(e) Render:
      python3 scripts/suggestions-render.py
        --input tomo-tmp/suggestions-fan-doc.json
        --output tomo-tmp/suggestions-fan-rendered.md
(f) Write to vault:
      kado-write operation=note
        path="<inbox><YYYY-MM-DD_HHMM>_suggestions-fan.md"
        content=<file body>
(g) Report to user and HALT:
      "Pass 2 halted — N items need atomic proposals. Wrote
      <path>. Approve the atomic suggestions there, then re-run /inbox."
(h) Return. Do NOT proceed to Step 3.
```

**Step 2 parser invocation.** Extended to pass `--fan-resolve-file` when
a companion `<same-dir>/*_suggestions-fan*.md` is already present in
`tomo-tmp/` (the builder staged both via Read + Write before calling the
parser):

```
python3 scripts/suggestion-parser.py
  --file tomo-tmp/suggestions.md
  --fan-resolve-file tomo-tmp/suggestions-fan.md   # optional; omitted if no fan doc
  > tomo-tmp/parsed-suggestions.json
```

**Auto-detect.** The instruction-builder's Step 2 is reached only when
the `/inbox` auto-detect (in `commands/inbox.md`) has already identified
at least one approved `*_suggestions*.md` in the inbox. When multiple
approved docs exist, auto-detect hands them ALL to the builder (listed
by file); the builder is responsible for staging primary + companion
into tomo-tmp before calling the parser.

### 3.4 `scripts/suggestions-reducer.py`

**New flag.** `--fan-resolve`.

When set:
- Only include items whose result.json has `force_atomic=true` marker
  (plumbed by inbox-analyst in its result JSON when the dispatch prompt
  carried force_atomic). All other items are excluded.
- Do NOT emit `daily_updates[]` block — the resolve doc is atomic-only.
- Do NOT emit MOC proposal / tag-changes blocks — atomic classification
  already includes MOC/tag inside each item.
- Set the output doc's title/description to communicate "Force-Atomic
  Resolve" provenance.

The resulting `suggestions-doc.json` still conforms to
`suggestions-doc.schema.json`; only certain optional arrays are empty.

### 3.5 `commands/inbox.md`

**Auto-detect extension.** Current logic looks for `*_suggestions.md`
with `[x] Approved`. When multiple match, the current code processes
them as independent Pass-2 runs. NEW behaviour: if BOTH a
`<date>_suggestions.md` AND a `<date>_suggestions-fan.md` are approved
(fan doc is a companion, not a successor), the builder processes them
as ONE reconciliation run.

Rule of thumb: companion pairing is by same inbox directory + approved
state. Timestamps don't need to match (fan-doc written later than main
doc). The builder reads both into tomo-tmp before parsing.

## 4. Failure modes + handling

| Failure | Handling |
|---|---|
| `inbox-analyst` subagent fails in resolve subflow | Item marked `failed` in state-file. Resolve doc emitted with remaining approved items; failed item still listed in `pending_fan_resolutions` next run. User can re-run or uncheck FAN. |
| `kado-write` fails writing resolve doc | Keep `tomo-tmp/suggestions-fan-rendered.md`; user can re-run `/inbox` — builder detects pending items again and retries. |
| User ticks fan-doc Approved but forgets to tick atomic Accepts | Parser merges only approved atomics. Unapproved ones remain as pending_fan_resolutions → loop repeats (doc re-written). User must either Accept or manually remove the FAN tick on the original doc to exit the loop. Log this loop-state clearly. |
| Parser encounters fan-doc but no FAN ticks in primary (orphan) | Log warning, treat fan-doc as standalone atomic-only doc (its atomics get rendered anyway — they're approved and have full classification). No merge needed. |
| Multiple primary docs + multiple fan docs | Pair by timestamp proximity. If ambiguous, fall back to "treat each fan doc as companion of the nearest-older primary". Document this in the error log. |

## 5. Testing strategy

- **Unit**: parser with synthetic primary + synthetic resolve — assert
  merge yields `confirmed_items` with `force_atomic: true + from_resolve:
  true` for resolve-promoted entries.
- **Unit**: parser with FAN + no resolve doc — assert
  `pending_fan_resolutions` populated, `confirmed_items` excludes the
  pending item's atomic.
- **Integration (fixture)**: reducer with `--fan-resolve` flag on a
  single result.json → assert output `suggestions-doc.json` has only
  the atomic item and empty `daily_updates`.
- **Live smoke**: on branch, manually stage a FAN-only Wichtige-Notiz
  scenario, run end-to-end in Docker container. Document outcome in
  plan/phase-1.md completion notes.

## 6. Migration

- No schema migrations.
- Existing suggestions docs without FAN-without-section items continue to
  work (pending_fan_resolutions empty → skip Step 2.5).
- Existing FAN-with-section items continue to be PROMOTED (commit
  `2665f81` path preserved).
- Roll out in a single commit on `feat/inbox-tagging-fixes`. No feature
  flag — the behaviour is additive and does nothing when not triggered.

## 7. Cost envelope

Per FAN resolution: one `inbox-analyst` Sonnet run (~$0.30 per 2026-04-23
pricing observation). Plus one reducer + one render in Python (~$0).
Plus one extra Pass-2 invocation by the user (no pricing for user clicks).

Total added cost per FAN resolve: ~$0.30. Break-even vs. re-running full
Pass 1 (~$33 observed) is immediate.
