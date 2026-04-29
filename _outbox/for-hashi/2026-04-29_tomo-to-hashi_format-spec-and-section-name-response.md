---
from: tomo
to: hashi
date: 2026-04-29
topic: format-spec-and-section-name-response
status: pending
status_note:
priority: high
requires_action: true
---

# Response — Format conventions doc + section_name template fallback

Closing Ask 1 and Ask 2 from
`2026-04-29_hashi-to-tomo_format-spec-and-test-coverage`. Ask 3 (fresh
inbox emission with synthetic source notes) is deferred to a follow-up
session — see "Ask 3 plan" below.

---

## Ask 1 — Format conventions section: DONE

New section landed in `Tomo/docs/instructions-json.md`:
**"Format conventions per syntax / position mode"** (after "Common
invariants", before "Path Shape Contract"). Cross-references added from
the action-kind sections so the line-shape contract is reachable from
both ends.

Commit: `23fab95 docs(instructions-json): explicit format conventions
per syntax/position mode`.

### Confirmations / corrections vs. Hashi's tables

#### `update_tracker.syntax`

| Mode | Hashi's table guess | Tomo contract (now documented) |
|---|---|---|
| `inline_field` | `<field>::` token, optional bullet, optional whitespace | **Confirmed.** Match by token only. Bullet/indent variants on the matched line are preserved on overwrite. Hashi's `startsWith(field + "::")` was wrong because it required the field at line-start; correct is "token anywhere on the line within the named section." |
| `callout_body` | `> <field>::` (Hashi asked: does Tomo emit single-colon `> field:`?) | **Double-colon only.** Single-colon (`> field:`) is **not** a Tomo-supported syntax. Hashi can match `::` only; if Tomo ever needs single-colon for a profile, that's a new syntax enum value, not an undocumented variant of `callout_body`. |
| `checkbox` | `- [ ] <field>` / `- [x] <field>` | **Confirmed.** |

#### `update_log_entry.position` — **Divergence from Hashi's guess**

Hashi guessed: `at_time` → `HH:MM - <content>` (no bullet, em-dash separator).
Real format on user's vault: `- 16:00: <content>` (bullet, time, colon).

**The contract has been clarified to the hybrid form** (Hashi composes
the line; Tomo emits structured fields):

| Position | Hashi composes |
|---|---|
| `after_last_line` | `- <content>` (verbatim trigger-phrase prose) |
| `before_first_line` | `- <content>` |
| `at_time` | `- <time>: <content>` (e.g. `- 14:30: ...`) — sort-inserted using `<time>` as key |

This means `update_log_entry.content` is **bare prose** (no bullet, no
time prefix). Tomo emits the time as a separate `time` field. Hashi
formats the line at execute time.

#### `update_log_link.position` — **Contract change vs. prior prose**

The previous prose contract said: at_time line shape is `HH:MM - - [[stem]]`
(no bullet, em-dash separator, then a second bullet). Hashi's plan
deviation T3.4 flagged the "two hyphens" as suspicious — and was right
to. That shape produces visually-inconsistent lines next to
`update_log_entry` content in the same Daily Log section.

**The contract has been aligned with `update_log_entry`:**

| Position | Hashi composes |
|---|---|
| `after_last_line` | `- [[<target_stem>]]` |
| `before_first_line` | `- [[<target_stem>]]` |
| `at_time` | `- <time>: [[<target_stem>]]` (e.g. `- 14:30: [[Asahikawa — ...]]`) |

The two action kinds now share a single time-prefix shape since they
coexist in the same Daily Log section.

**Hashi action**: any prototype matching the old `HH:MM - - [[stem]]`
form needs to be updated to the new symmetric form. PRD F4 (and
related at_time tests) should be re-anchored on `- HH:MM: <payload>`.

#### Profile-driven format — flagged as Tomo-side gap

The `- HH:MM: ` time-prefix shape is hardcoded as the canonical default
for the **miyo** profile in Tomo 0.8.x. Profile-driven discovery is
flagged as a post-MVP follow-up (`daily_log.entry_time_format` template
string, source: vault discovery). Until that ships, Hashi should:

- Hardcode `- HH:MM: ` for miyo profile entries.
- For non-miyo profiles, refuse to apply at_time entries unless
  explicitly opted in (or document the format expected per profile).

This was raised inside the response doc, not in the spec — let me know
if you want it tracked as a separate Tomo handoff (it would land on the
`daily_log` shared-context block in `shared-ctx-builder.py`).

#### `link_to_moc.section_name` pointing to a heading (Hashi's coverage gap 6)

Tomo currently does not emit `section_name` matching an `## H2` /
`### H3` heading — only callout-line shapes (`[!blocks]`,
`[!compass]`, etc.). The renderer's `resolve_section_names` is
callout-only. If/when heading-targeting links are needed (e.g. for
non-callout MOC layouts), it'll be a separate spec change with a
matching emission path. For now Hashi's heading-branch in `linkToMoc.ts`
is dead code — keep it as a documented future-extension and don't
exercise it in v0.1 release-gate QA.

### Why I diverged from Hashi's "read template from `tomo/config/templates/`" suggestion

Hashi's Ask 2 proposed reading the template body from
`tomo/config/templates/<template>` (filesystem path inside the Tomo
source tree). I did not follow that — the renderer's existing
`read_template()` helper at `instruction-render.py:145` reads templates
**via Kado from the vault**, not from the source tree. This is
intentional:

1. Templates live in the vault (`Atlas/900 Templates/` by miyo
   convention), not in the source tree, at runtime.
2. The Tomo Docker container only sees `$INSTANCE_PATH` + `/home/coder`
   — the `tomo/config/templates/` host path is unreachable from inside
   the running container (memory: `reference_tomo_container_visibility`).
3. Reading via Kado gives us live profile/vault state, not stale
   source-tree copies.

The Ask 2 fix uses the same `read_template()` helper — same I/O path
the rest of the renderer uses. See commit `794f219`.

---

## Ask 2 — Template-fallback in resolve_section_names: DONE

Tier-2 fallback added to `tomo/scripts/instruction-render.py`'s
`resolve_section_names`. Strictly additive (existing tier-1 path
unchanged); only fires when tier-1 returns None.

Algorithm:

1. **Tier 1**: read live MOC at `target_moc_path` via Kado, scan for
   the highest-priority editable callout. (Same as before.)
2. **Tier 2 (new)**: if tier 1 returns None AND there is a same-set
   `create_moc` whose `destination` matches `target_moc_path` AND that
   `create_moc` has a `template` field, read the template body via
   Kado (`read_template` helper, accepts bare stems or full paths),
   and run the same editable-callout scan against the template body.

Caching:
- Tier-1 cache is per MOC path (unchanged).
- Tier-2 cache is per **template name** — a single template body is
  read at most once even when many sibling create+link pairs share it.

Docstring at line 907 updated to reflect the new fallback. Renderer
version bumped to **0.8.0** (additive change).

Verified for `t_moc_tomo.md`: tier-2 resolves to `[!blocks] Key Concepts`
(template line 25), matching the convention used for existing MOCs and
avoiding the [!connect] (navigation) callout that was the previous
fallback target at Hashi-execute time.

### Regression test — DONE

New file: `tests/test-resolve-section-names.py` (6 tests):

1. **tier-1: existing MOC resolves to [!blocks]** — regression for the
   prior path.
2. **tier-2: in-set create_moc falls back to template's [!blocks]** —
   the core new test. Asserts a create_moc(template="t_moc_tomo.md") +
   sibling link_to_moc(target_moc_path=destination) emits
   `section_name: "[!blocks] Key Concepts"`, not null.
3. **tier-2 cache: template read once across 3 sibling links** —
   asserts I/O is amortised.
4. **no-template create_moc → no fallback, section_name stays null** —
   degraded-emission case.
5. **no in-set create_moc + Kado fails → both tiers fail, section_name
   null** — orphan-link case.
6. **pre-set section_name preserved without I/O** — already-resolved
   actions skip both tiers.

All 6 pass. All existing tests (`test-008-phase1`'s
`resolve_section_names` block, `test-instructions-diff`,
`test-vault-config-writer`, `test-shared-ctx-tags`, voice tests) still
pass.

---

## Ask 3 — Plan: separate session

Deferred to a follow-up session per user direction:

1. User clears `Privat-Test` inbox AND `tomo-instance` so Pass 1 / Pass 2
   start clean.
2. User authors mock fleeting notes (Sport.md-style) covering the 6
   handler/mode gaps Hashi listed:
   - `update_log_entry.position = at_time` — fleeting note with explicit
     clock time triggering time-sorted insertion.
   - `update_log_entry.position = before_first_line` — habit-marker
     style note that should land at the start of the day's log.
   - `update_log_link` (entire action kind) — atomic note big enough
     for `move_note` + at least one `update_log_link` (default and
     `at_time` variants).
   - `update_tracker.syntax = callout_body` — fleeting note targeting a
     callout-body tracker (e.g. weather: Temperature, Feels Like,
     WindSpeed).
   - `update_tracker.syntax = checkbox` — fleeting note for a
     checkbox-mode habit/task tracker.
   - heading-targeting `link_to_moc` — **not in scope**; Tomo doesn't
     emit heading targets. See Ask 1 confirmation above.
3. User runs `/inbox` Pass 1 + Pass 2 in the Tomo container. Resulting
   `*_instructions.json` + `*_instructions.md` will exercise:
   - The new tier-2 section_name template fallback (every in-set
     create+link pair will resolve to `[!blocks]` instead of null).
   - The aligned `at_time` line shape (`- HH:MM: <payload>`) for both
     log_entry and log_link.
   - All 8 handler kinds × position/syntax sub-modes.
4. User drops the resulting JSONs into `Hashi/test/Hashi/100 Inbox/` for
   the next manual round.

This will land in a separate Tomo session — when the synthetic notes
are ready and the container is cleared, ping Tomo to drive the
emission.

---

## Hashi-side counterparts noted

Items Hashi flagged as Hashi-side fixes (independent of this response):

1. `handleInlineField` / `handleCalloutBody` — actually persist after
   matching (currently checks values without writing). **No Tomo
   action needed.**
2. `handleInlineField` — match bullet-prefixed lines (`- Sport:: false`).
   **Confirmed in spec**: `inline_field` token-anchored matching now
   explicitly allows bullet/indent. Hashi can drop the
   `startsWith(field + "::")` form.
3. Cross-set `findDependencyFailure` — action ID collision in batch
   mode. **No Tomo action needed.**
4. PRD F4 (`update_tracker` "different value → fail" → "different
   value → set it"). **Tomo's contract aligns**: spec now says
   "Tomo's intent wins" on overwrite (`update_tracker` idempotency
   section). Hashi PRD F4 revision can land.

---

## References

- Tomo commits: `23fab95` (docs), `794f219` (renderer + test)
- Updated doc: `Tomo/docs/instructions-json.md` § Format conventions per
  syntax / position mode (new), §§ Action kinds (cross-references).
  "Last reviewed: 2026-04-29".
- Updated renderer: `Tomo/tomo/scripts/instruction-render.py` v0.8.0,
  function `resolve_section_names` lines 897–1014.
- New test: `Tomo/tests/test-resolve-section-names.py`.
- Branch: `feat/format-spec-section-name-fallback` (not yet merged to
  main pending review).
- Original handoff: `Tomo/_inbox/from-hashi/2026-04-29_hashi-to-tomo_format-spec-and-test-coverage.md` (status: in-progress → will be flipped to done after this reply lands).

---

## Addendum 2026-04-29 — Token-name matching contract: 3 Dataview positions

After the initial response above shipped, Marcus reviewed the
"Format conventions per syntax / position mode" section and flagged
that the matcher contract was incomplete. The doc was extended (commit
`a7cf1dd`); read the full updated section in
`Tomo/docs/instructions-json.md` § Token-name matching contract.

### What changed in the contract

The matcher now formally recognises **all three Dataview inline-field
positions**, not just line-anchored:

| Position | Form | Example |
|----------|------|---------|
| 1 — Line-anchored | `<field>:: <value>` (with optional bullet/whitespace/`> ` prefixes) | `- Sport:: true` |
| 2 — Inline-bracketed | `[<field>:: <value>]` anywhere on a line | `Heute Workout. [Sport:: true]` |
| 3 — Inline-parenthesized | `(<field>:: <value>)` anywhere on a line | `Bewegt heute (Sport:: true)` |

Hashi's matcher MUST recognise all three. Match priority:
line-anchored beats inline; first occurrence wins. When overwriting,
Hashi preserves the line's existing prefixes/brackets/parens byte-for-
byte and rewrites only the value portion.

### What stays the same

- **Insertion format for NEW fields stays line-anchored only.**
  Bracketed and parenthesized forms exist purely to recognise existing
  user-authored fields, not as Tomo emission targets.
- The `inline_field` vs `callout_body` distinction is still about
  **section locator** (heading-area vs callout-body) and **insertion
  format** (no `> ` prefix vs `> ` prefix), not about the matcher.
  Both syntax values use the same three-position matcher.

### Multi-word field names

Some real Privat-Test trackers have multi-word names (`For Me`,
`Learned Words`, etc.). Hashi's matcher must regex-escape the field
name OR use literal-string scanning that handles whitespace inside the
name verbatim. The contract section now shows examples:

```
- For Me:: morgen früh aufstehen
[For Me:: Tee mit Yuki]
```

### Implementation note for Hashi v0.1

If Hashi's current matcher is line-anchored only, that's a
straightforward extension — three regexes evaluated in priority order,
unified value-extraction. The bracketed/parenthesized forms are
**read-only** for Hashi (find + overwrite); Hashi never writes new
brackets/parens.

### Why this came up

User authoring style varies. Marcus's daily notes use line-anchored
form (`- For Me:: ...`), but other vault authors embed inline fields
mid-prose for readability. Tomo's contract must accept all three since
the analyst reads notes as they were written, not in a normalised
form. The Tomo-side analyst is LLM-driven so it tolerates all three
naturally; the contract change formalises the same tolerance for
Hashi's deterministic matcher.
