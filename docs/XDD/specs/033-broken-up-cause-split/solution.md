---
title: "Say why a parent link is broken, and stop offering to delete the ones that work"
status: draft
version: "1.0"
---

# Solution Design Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] Every PRD Must-have feature maps to a component
- [x] Every architecture decision has a rationale
- [x] No unexplained magic — each non-obvious mechanism is traced
- [x] Constraints are stated as constraints, not preferences
- [x] Acceptance criteria are executable, not aspirational

### QUALITY CHECKS (Should Pass)

- [x] Reuses existing patterns where they fit, and says so
- [x] Names the places a wrong implementation would still look right
- [x] Every new field has a defined absence behaviour
- [x] Interactions with shipped specs are stated explicitly
- [x] Rejected alternatives are recorded with the reason

---

## Constraints

- **CON-1 — Zero added vault access.** `broken_up` is cache-only by construction:
  `_check_broken_up` takes no `graph_audit_fn` / `list_dir_fn` parameter and therefore *cannot*
  reach the vault. Every new distinction must be answerable from the discovery cache and the scan
  result already in hand. This is not a performance preference; it is the property that keeps the
  check runnable inside Kado's rate limit.
- **CON-2 — No advisory finding may carry an approvable fix.** Not "should not" — the report must
  make it structurally impossible, so no future edit can reintroduce a destructive checkbox by
  accident.
- **CON-3 — Output for every other check is byte-identical.** Proven by diffing against modules
  loaded from git, not by observing that tests still pass (the method spec 032 used, for the same
  reason).
- **CON-4 — A cache written before this spec must never produce a claimed cause.** Absence of the
  new information is a known state with its own behaviour, not a default.
- **CON-5 — `up_state`'s existing values are untouched.** `absent` / `valid` / `broken` have three
  consumers; redefining them is a migration this spec does not need.
- **CON-6 — Schema and its mirror stay bytewise identical** where a mirrored schema is touched, and
  carry no version header.

---

## Implementation Context

### Code Context

The whole change lives along one existing path. Nothing new is introduced between these hops.

| Site | Today | After |
|---|---|---|
| `moc-tree-builder.py:280` `_resolve_up_state` | `target in moc_stem_set` → `valid`, else `broken` | additionally reports **why** it is not valid |
| `moc-tree-builder.py:~421` cache entry | writes `up_state` | also writes `up_broken_reason` |
| `garden-audit.py:51` `_TIER` / `:60` `_FIXABLE` | six checks | gains `parent_not_moc` (advisory, not fixable) |
| `garden-audit.py:153` `_check_broken_up` | one finding per `up_state == "broken"` | splits into two checks by reason |
| `garden-audit-render.py:581` advisory branch | one fixed line for every advisory | per-check advisory message |
| `lib/garden_exclusions.py:30` `ALL_CHECK_NAMES` | six names | gains `parent_not_moc` |

**The discriminator already exists and is free.** `_resolve_up_state` receives `moc_stem_set`,
derived from `scan_result.moc_paths`. The very same `ScanResult` carries `in_scope_note_paths`
(`lib/moc_scan.py:54`), and the builder already reads every one of those paths at
`moc-tree-builder.py:~372`. Measured on the live cache: 64 entries with `kind: moc`, 295 with
`kind: note`. Deciding *"is this target a known in-scope note?"* is a set membership test over data
the function's caller is already holding.

This is the third time in this area the expensive-looking question turned out to be free. Spec 032
found the same for `up_source` and again for `up_value`. Worth stating as a pattern: **before
designing an I/O path to answer a question about the vault, check whether the cache builder already
had the answer in scope and discarded it.**

### Implementation Boundaries

**In scope:** the cause split, the new advisory check, the report wording for both groups, the
per-situation counts, and stale-cache behaviour.

**Out of scope, and why:**

- Splitting *unresolved* into *missing* vs *outside the scope* — see ADR-6.
- Changing what counts as a map. That is `moc_tag` configuration.
- Auto-tagging a target. Marking a note as a map changes how the whole vault reads; the user decides.
- Spec 032's routing. A `broken_up` finding that survives the split still routes by declaration
  site, unchanged. See ADR-7.

---

## Solution Strategy

`_resolve_up_state` learns the note-stem set and returns *why*, not just *whether*. The reason rides
into the cache entry as an additive field. The audit then emits **two different checks** from what
is today one, and the existing tier/fixability machinery does the rest.

The core insight is that Tomo already models "a finding that must not be acted on" — it is called an
advisory tier, and it is driven entirely off the check name. So *"an untagged parent is advice, not
a repair"* is not a new behaviour to build; it is an existing behaviour to route into.

---

## Building Block View

### Components

| Component | Change | PRD feature |
|---|---|---|
| `_resolve_up_state` | returns `(state, reason)`; gains the note-stem set | F1 |
| cache entry writer | writes `up_broken_reason` unconditionally | F1, F6 |
| `_check_broken_up` | splits by reason into `broken_up` and `parent_not_moc` | F1, F2, F3 |
| `_TIER` / `_FIXABLE` | register the new check | F2 |
| `ALL_CHECK_NAMES` | register the new check | F2 |
| advisory renderer | per-check message with the inverted suggestion | F2 |
| `broken_up` fix wording | says *not found in the audited area* | F3 |
| summary renderer | per-situation counts | F5 |
| stale-cache path | withhold the cause claim, keep today's wording | F6 |

### Registration inventory — counted, not grepped

A new check name is a registration, and spec 032 was bitten five separate times by a site the
author did not know to look for. So the sites are enumerated here rather than left to a grep, and
the **must-not-register** list is given equal weight — a wrong entry there silently restores exactly
the destructive behaviour this spec removes.

**Must register `parent_not_moc`:**

| # | Site | Value |
|---|---|---|
| 1 | `garden-audit.py:51` `_TIER` | `"advisory"` |
| 2 | `lib/garden_exclusions.py:30` `ALL_CHECK_NAMES` | add — see ADR-4 |
| 3 | `garden-audit-doc.schema.json:57` check enum | add |
| 4 | `garden-audit-wire.schema.json:53` check enum | add |
| 5 | `garden-audit-configure.py:147` `_VALID_CHECKS` | add, or the wizard cannot configure an exclusion for it |
| 6 | `garden-audit-render.py:63` `_CHECK_LABEL` | a label that does not use the word "broken" |

**Must NOT register — each omission is load-bearing:**

| # | Site | Why not |
|---|---|---|
| 7 | `garden-audit.py:60` `_FIXABLE` | the entire mechanism of ADR-1. Adding it here attaches a `decision` block and the report grows an apply checkbox — CON-2 violated in one line |
| 8 | `garden-audit-render.py:574` suggest-targets tuple | offering to suggest repoint targets for a link that is not broken |
| 9 | `garden-audit-render.py:813` enrichment tuple | enrichment exists to fill a fix block; there is no fix block |

Two schema **descriptions** also enumerate the checks in prose (`garden-audit-doc.schema.json:63`
for `tier`, `:67` for `fixable`). They are documentation, not validation, so a stale one fails no
test — which is precisely why they are listed.

### Interface Specifications

#### Cache entry — one added field

```yaml
- path: Atlas/202 Notes/Some Note.md
  stem: Some Note
  kind: note
  up_state: broken          # unchanged: absent | valid | broken
  up_source: frontmatter    # spec 032
  up_value: ['[[X]]']       # spec 032
  up_broken_reason: not-a-moc   # NEW: not-a-moc | unresolved | null
```

`up_broken_reason` is `null` for every entry whose `up_state` is not `broken`. It is written
**unconditionally** — see ADR-3.

#### Finding — the split

```
up_state == "broken" and up_broken_reason == "unresolved"  →  check "broken_up"      (integrity, fixable)
up_state == "broken" and up_broken_reason == "not-a-moc"   →  check "parent_not_moc" (advisory, NOT fixable)
up_state == "broken" and up_broken_reason absent           →  check "broken_up" + stale-cache disclosure
```

---

## Architecture Decisions

### ADR-1 — A different situation is a different check, not a variant of one check

**Decision:** the untagged-parent case becomes its own check, `parent_not_moc`, rather than a
`broken_up` finding with a different tier.

**Why this is the whole design:** `tier` and `fixable` are derived from the check name
(`garden-audit.py:88-89`), not stored per finding. Registering `parent_not_moc` as
`_TIER["parent_not_moc"] = "advisory"` and leaving it out of `_FIXABLE` makes four PRD acceptance
criteria true **by construction rather than by new code**:

- no `decision` block is attached (`_finding` only adds one when `fixable`), so
- the report cannot render an apply checkbox or a repoint field — the fixable branch is never
  entered, and
- `garden-audit-parser.py` never routes it, because every routing site is inside a
  `check == "broken_up"` branch, so
- no instruction can be produced for it, satisfying CON-2 structurally.

**Rejected:** making `tier`/`fixable` per-finding overridable. It would touch the shared `_finding`
constructor for every check, and it would leave "an advisory that is nonetheless fixable"
expressible — the exact state CON-2 forbids.

### ADR-2 — `up_broken_reason` is additive; `up_state`'s values do not change

**Decision:** add a field rather than extend the `up_state` enum with `not-a-moc` / `unresolved`.

**Why:** `up_state` has three consumers (`_check_unparented` on `absent`, `_check_broken_up` on
`broken`, `_check_orphan`'s `setdefault`). New enum values would make every `== "broken"` test
silently wrong for the new values — a change that compiles, passes narrow tests, and drops findings.
An additive field leaves every existing test true and every consumer correct. This is the same
choice spec 032 made twice (`up_source`, `up_value`), for the same reason.

### ADR-3 — Freshness is signalled by the key's PRESENCE, not its value

**Decision:** write `up_broken_reason` on **every** entry, `null` where it does not apply, and treat
the key's *absence* as "cache predates this spec".

**Why:** `null` is a legitimate value here (a non-broken entry has no reason), so a `.get()`
returning `None` cannot distinguish "no reason applies" from "this cache never knew about reasons".
Consumers must use a module-level sentinel and membership tests, never `.get()` with a default.
Spec 032's ADR-3 established this pattern and its `_MISSING` sentinel; this spec reuses both
verbatim rather than inventing a parallel mechanism.

**The failure this prevents:** a pre-033 cache silently classified as `unresolved` for every finding
— which would keep offering the destructive fix on exactly the 20 findings this spec exists to
protect, while the report claimed it had checked.

### ADR-4 — Registering the new check changes what `checks: all` covers

**Decision:** add `parent_not_moc` to `ALL_CHECK_NAMES`, and state the consequence rather than
discover it.

**Consequences, both real:**

- An exclusion configured as `checks: all` **starts covering the new check**. This is correct — the
  user excluded everything under that path — and needs no migration.
- An exclusion that lists checks explicitly and names `broken_up` will **not** exclude
  `parent_not_moc`. Findings the user thought they had silenced can reappear, in the advisory tier.
  That is defensible (they are a different statement about a different note) but it is a visible
  behaviour change and belongs in the release note, not in a surprise.

### ADR-5 — The advisory message is per-check

**Decision:** the advisory branch (`garden-audit-render.py:581`) gains a per-check message table;
absent an entry, it renders today's generic line byte-for-byte.

**Why:** the generic line is *"Advisory — no automated fix. Review and handle manually."* For
`parent_not_moc` that is both true and useless: there **is** an action, it is just not one Tomo will
perform. The message must name the target and the action (mark it as a map), because a finding whose
advice the user cannot act on is noise, and noise is what erodes an audit's credibility.

The fallback-to-generic default keeps CON-3 true for `duplicate_stem` and `stale_moc` without
touching their path.

### ADR-6 — `unresolved` is not split further, and the report says so honestly

**Decision:** the report states *"not found in the audited area"* and does not claim the note is
missing.

**Why:** distinguishing the two requires knowing about notes outside `scope_paths`, which means
vault access — forbidden by CON-1, and forbidden for a good reason. The measured population shows
the group is genuinely mixed: eight of the 22 point at a target that provably exists in an unscanned
folder, one of them recorded by full path.

Naming the scan boundary is both honest and more actionable than a wrong certainty: it points at a
setting the user can change, rather than at a note they might delete.

### ADR-7 — Spec 032's routing is untouched, and its split line changes denominator

**Decision:** `broken_up` findings that survive the split still route by declaration site, exactly as
032 specifies. The declaration-site split line now counts the survivors only.

**Why it needs saying:** 032's line reads *"Broken parents: N findings — X in the note body, Y in a
note property."* After this spec, N is the unresolved group alone. That is correct — declaration
site only matters where a fix will be written, and no fix is written for advisories — but the number
will drop noticeably on the first run, and a reader who does not know why will suspect a regression.

The advisory group gets **no** site split: it would be information about a fix that is not offered.

---

## Cross-Cutting Concepts

### User Interface & UX

Three wordings change. The exact strings are the implementer's to draft; these are the constraints
they must satisfy.

**The advisory (`parent_not_moc`)** must name the *target* as the thing to change, must not use the
words "broken" or "remove", and must make the many-to-one relationship visible where several
findings share a target. It carries no checkbox and no input field.

**The integrity finding (`broken_up`, unresolved)** must say the target was not found **in the
audited area**, and must point at the audited scope as something the user controls. It must not
assert the note does not exist.

**The summary** states the per-situation counts. Where only one situation is present, it must not
render a breakdown implying a division that does not exist — the same rule spec 032 applied to its
declaration-site line, and the same trap.

### System-Wide Patterns

- **Absence as a signal** (ADR-3) — reused from 032, including the `_MISSING` sentinel.
- **Structural impossibility over discipline** (ADR-1) — the destructive path is not merely not
  taken; it does not exist for this check.
- **Under-claim rather than guess** (ADR-6) — inherited from 032's ADR-5, where falling back to a
  plausible answer was ruled out for the same reason.

---

## Quality Requirements

| # | Requirement | How it is proven |
|---|---|---|
| Q1 | The three situations are distinguished on real data | Run the real check over the live cache; counts must sum to the total flagged |
| Q2 | No advisory finding can carry an approvable fix | Assert over a whole mixed batch that no `parent_not_moc` finding has a `decision` block, and that the parser emits no action for one |
| Q3 | Zero added vault access | `_check_broken_up` and its sibling take no vault-callable parameter; asserted structurally, not by counting calls |
| Q4 | Every other check is byte-identical | Load the pre-spec modules from git, render a mixed document through both, diff |
| Q5 | A pre-033 cache claims no cause | Absence of the key produces the disclosure path and today's wording, never `unresolved` |
| Q6 | The new check is registered everywhere a check must be | Remove each registration in turn; a test must go red for each |

---

## Acceptance Criteria

- Given the live cache, when the audit runs, then flagged parents divide into the two groups with
  counts that sum to today's total.
- Given a finding whose target is a known in-scope note, when the report is written, then it appears
  as an advisory naming the target, with no checkbox and no repoint field.
- Given that report is approved and applied, then no instruction touching those notes is produced.
- Given a finding whose target is absent from the cache, when the report is written, then it says
  *not found in the audited area* and still offers remove/repoint.
- Given a cache without `up_broken_reason`, when the report is written, then no finding claims a
  cause and the report says how to refresh.
- Given any other check, when the report is written, then its output is byte-identical to today's.

---

## Risks and Technical Debt

### Implementation Gotchas

1. **`.get("up_broken_reason")` is the bug this spec is most likely to ship.** It collapses
   *"pre-033 cache"* into *"no reason applies"*, which reads as a healthy entry. Membership tests
   only, sentinel comparison only — the same discipline 032 needed for `up_value`, and the same
   place it would have failed.
2. **The reason must be resolved where the note-stem set is in scope.** Resolving it later, from the
   finding, would mean re-deriving the set — and a second derivation is a second place to get it
   wrong.
3. **Two emission sites, not one — and nine registration sites, not three.** Spec 032 hit this five
   separate times: a change is written at the site the author grepped, and a second site with a
   different name is missed. The registration inventory above exists because the first draft of this
   SDD listed three sites and there are nine. The parser's two routing sites (`:403` report, `:603`
   wire) are likewise counted, not assumed. Any task that touches a name must state the count it is
   working from.
4. **The all-advisory run.** If every flagged parent is `parent_not_moc`, the integrity section has
   no broken-parent entries. The renderer already has an all-advisory path (`:322-325`); confirm it
   reads correctly rather than assuming it does.
5. **Exclusion configs listing `broken_up` explicitly** will not silence the new check (ADR-4).
   Verify against the live config before concluding a finding "reappeared" is a defect.

### Technical Debt

- `garden-audit-render.py` is already 1059 LOC against the constitution's 300–500 guideline
  (backlogged). This spec adds to it. The per-check advisory table (ADR-5) is a natural seam if a
  split is attempted — but splitting the file is not this spec's job, and doing both at once would
  make the byte-identical proof (Q4) unreadable.
