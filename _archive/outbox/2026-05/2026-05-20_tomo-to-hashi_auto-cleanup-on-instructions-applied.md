---
from: tomo
to: hashi
date: 2026-05-20
topic: Auto-cleanup-on-applied — delete instructions + linked source-suggestions / source-moc-proposal when last action [x] Applied
status: done
status_note: Superseded by 2026-05-21 schema-lock handoff
priority: normal
requires_action: true
---

# Auto-cleanup-on-applied — delete instructions + linked sources when execution completes

> **Early-warning handoff.** F-47 (Tomo Lifecycle Tags, XDD spec 017 in tomo) is in PRD phase. The frontmatter schema referenced below is **not yet finalised** — this handoff is to align on the contract early so Hashi can plan the work. **Do not implement until Tomo sends a follow-up "schema locked" notice during F-47.P1 implementation** (estimated 1–2 weeks).

## What's Changing in Tomo

F-47 introduces a unified lifecycle on every Tomo-produced doc in the inbox: hierarchical lifecycle tag `#<tag_prefix>/<doc-type>/<state>` + a `tomo:` frontmatter block with explicit cross-doc references. The doc-type / state matrix:

| doc-type | states (replace, not accumulate) |
|---|---|
| `source` | `pending` (untagged) → `captured` |
| `suggestions` | `pending-approval` → `approved` |
| `moc-proposal` | `pending-accept` → `accepted` |
| `instructions` | `pending-apply` → `applied` |

Pass 2 (instruction-builder) writes a new `*_instructions.md` from one of two upstream sources:

- a `*_suggestions.md` (standard `/inbox` Pass 2 path)
- a `tomo-moc-proposal-*.md` or new-style `YYYY-MM-DD_HHMM_moc-proposal-<slug>.md` (F-43 MOC-acceptance path — covered by F-47.P4)

The instructions doc carries explicit references back to its upstream input(s) in its `tomo:` frontmatter block:

```yaml
tomo:
  doc_type: instructions
  state: pending-apply
  run_id: 2026-05-20T13-57-17Z-4e4326
  updated_at: 2026-05-20T15:42:17Z
  source_suggestions: "100 Inbox/2026-05-20_0834_suggestions.md"   # if Pass 2 came from a suggestions doc
  source_moc_proposal: "100 Inbox/2026-05-20_1359_moc-proposal-notemaking.md"  # if Pass 2 came from a moc-proposal
# (exactly one of source_suggestions / source_moc_proposal will be present — never both, never neither)
```

## What We're Asking Hashi to Do

When Hashi finishes executing the last action of an instructions set (all per-action checkboxes are `[x] Applied`):

1. **Flip the instructions doc's `#<prefix>/instructions/pending-apply` tag to `#<prefix>/instructions/applied`** via `kado-write operation=frontmatter` (`tomo.state` field too, atomic with the tag swap). Kado 0.9.6 ships this op — see `_inbox/from-tomo/2026-05-20_tomo-to-kado_kado-write-operation-frontmatter.md` (or the equivalent landed in your inbox).
2. **Read the `tomo.source_suggestions` and `tomo.source_moc_proposal` fields** from the instructions doc's frontmatter.
3. **Delete the instructions doc + its `.json` peer + the `-diff.md` if present** (Obsidian trash — `vault.trash(file, system=true)` so the user can recover via OS trash).
4. **Delete the upstream source doc** (the one named in `tomo.source_suggestions` or `tomo.source_moc_proposal`, whichever is set). Same `vault.trash` mechanic.
5. **Audit log entry** capturing what was deleted, paths only — no body content (matches existing audit-log discipline + Constitution L2 Privacy).

## Why

F-47 unifies file-lifecycle but explicitly **does NOT introduce a Tomo-side cleanup script**. Reasoning:

- Inbox volume is small (rarely > 5 active docs) — automation cost > marginal benefit for orphan cases.
- The instructions-applied moment is the **natural "this work is done"** signal. Tying cleanup to it makes the lifecycle atomic: when the user sees the last action ticked, the input docs are gone too.
- Orphans (abandoned `pending-approval` suggestions, abandoned `pending-accept` moc-proposals) stay as manual delete in Obsidian — fast enough and intentional that they need user awareness.
- Hashi already owns the per-action-applied checkbox flips, so it's the natural place to detect "all applied" and trigger cleanup.

## Action Required (Sequenced — Don't Start Yet)

1. **Acknowledge this handoff** with `status: received, target_version: 0.X.Y` — so Tomo can plan F-47.P4 around your timeline.
2. **Hold implementation** until Tomo sends a "schema locked" follow-up confirming the exact `tomo.source_suggestions` / `tomo.source_moc_proposal` field names + value semantics (vault-relative paths, leading slash?, etc.).
3. **Implement when unblocked**:
   - Detect "all actions applied" in your existing per-action-tracking code path
   - Use `kado-write operation=frontmatter` (Kado 0.9.6+) to flip the instructions tag/state atomically
   - Read upstream refs via frontmatter parse (existing `processFrontMatter`-style access)
   - Trash instructions + its peers + upstream source via Obsidian Vault API
4. **Test against Tomo Privat-Test** before release — Tomo will provide a sample instructions set with both source variants (`source_suggestions` and `source_moc_proposal`) for end-to-end verification.

## Edge Cases to Confirm in Reply

- **Partial application**: user manually checks `[x] Applied` on some actions then runs `/inbox` to apply the rest. Hashi already handles per-action atomicity — confirm "all applied" detection works regardless of which agent (Hashi or other) flipped each checkbox.
- **Source doc missing**: user already deleted the source-suggestions before Hashi reached "all applied". Should Hashi: (a) skip the source-delete silently, (b) log a warning, (c) abort the cleanup entirely? **Suggestion: (b) — proceed with instructions delete, log warning for missing source.**
- **Failed last action**: instructions set has 50 actions, 49 applied, last one errored. Don't trigger cleanup. Confirm "all applied" means literal 100%.
- **User manually ticked all `[x] Applied` without Hashi running**: should Hashi proactively run cleanup when it next opens the doc? Probably yes — Hashi has authoritative view of `applied` state.

## Compatibility / Migration

- Pure additive on the Hashi side — current execution path unchanged, cleanup is an extra step at the end.
- Tomo F-47.P1 writes the new frontmatter shape; until Hashi implements this handoff, the new fields are ignored (no breakage). The manual-delete workflow continues to work in parallel.
- Once Hashi ships, both auto-cleanup and manual delete coexist (user can delete inputs manually before Hashi gets there — see "Source doc missing" above).

## References

- Tomo spec **017-tomo-lifecycle-tags** — `docs/XDD/specs/017-tomo-lifecycle-tags/README.md` (PRD in progress; F-47.P4 will use this Hashi behavior to close F-43's MOC-acceptance gap)
- Tomo F-47 backlog entry — `docs/XDD/backlog.md` row F-47
- Tomo F-43 T6.2 pause note — `docs/XDD/specs/013-moc-creation-skill/plan/phase-6.md` T6.2 (live-validation context that surfaced F-47)
- Kado 0.9.6 `kado-write operation=frontmatter` — `_inbox/from-kado/2026-05-20_kado-to-tomo_kado-write-frontmatter-shipped.md` (the op Hashi will use for the tag-flip in step 1)
- Existing Hashi contract — `docs/instructions-json.md` (per-action `[x] Applied` flip — extended in this handoff, not replaced)
