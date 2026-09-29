# Specification: 037-asset-destination-collision-is-a-pass1-decision

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-15 |
| **Current Phase** | Implemented |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-09-29 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v2.0; 22 acceptance criteria across F1-F3, S1-S2, C1-C2 (the earlier "37" counted v1.0's, before the owner's scope cut) |
| solution.md | completed | v2.0; 5 ADRs, none open; 0 new wire fields, Hashi untouched |
| plan/ | completed | 4 phases, 19 tasks — 13 planned, 6 added from review findings |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-15 | Spec opened off a live failure, not a hypothesis | The 2026-09-15 Hashi run failed `I05 move_asset` with "Inconsistent state — both source and destination present". The destination held a different 69-byte PNG of the same name. Hashi's refusal was correct; the defect is that Tomo emitted an action it could have known was unappliable. |
| 2026-09-15 | Both the byte-identical and the differing case surface as a decision | Owner decision, correcting an earlier proposal to auto-resolve the identical case. Dropping the move and removing the inbox copy is still a vault mutation nobody approved, and the 2-pass model's rule is propose-never-execute. The byte comparison decides what the document *says* and which remedies it offers — not *whether* it asks. |
| 2026-09-15 | Hashi keeps its own final check | Owner decision. Defence in depth, not a replacement: the vault can change between Pass 1, Pass 2 and apply. Tomo detecting early does not make Hashi's guard redundant. |
| 2026-09-16 | Research phase skipped; PRD written directly | Owner decision. The problem is measured on a live run, the feasibility probed against live Kado, and the design choices already taken. Research agents would have restated the README. |
| 2026-09-16 | Spec documents ride `spec/035-wire-schema-versioning` | Owner decision. Documentation only, no code; 035 already carries every fix from this session and is the branch waiting on "tomo funktioniert ordentlich". Avoids a second unmerged branch stacked on an unmerged one. |
| 2026-09-15 | Overwrite is not a default remedy | Overwriting a file already filed in the Atlas destroys content the user placed there. Standing project constraint: deleting data a person painstakingly entered is not an option. If offered at all it must be explicit and never pre-ticked. |
| 2026-09-16 | Scope cut by the owner; both documents rewritten as v2.0 | v1.0 framed the defect as "a note must never be separated from its attachment" and proposed holding notes back, a fail-closed vault check and four remedies. The owner scoped it to: show the conflict, offer rename (default) / keep in inbox / ignore, leave Hashi and the instructions document alone. Both ADRs that were awaiting confirmation dissolved. |
| 2026-09-16 | The gap between passes is explicitly not modelled | Owner principle: "wir wissen nicht was zwischen pass1/pass2 und der Anwendung im Vault passiert". The only guarantee is that no component overwrites data; a failed check, a stale conflict and a late conflict all resolve the same way — Hashi reports, the owner fixes. |
| 2026-09-16 | Rename is pre-ticked, contradicting the usual no-default rule | A safe obvious answer exists: renaming overwrites nothing and loses nothing. Requiring a tick would charge attention for the common case. A cleared default resolves to `ignore` — the loudest outcome — because clearing it is itself a signal. |
| 2026-09-16 | **Decomposition tier: Incremental** | Classifier recommended Incremental and it was accepted. Signals: `change_type=fix`, `feature_count=3` (F1-F3), `ac_count=22`, `component_count=0` (no new surface — four existing files extended), `parallel_markers=false`. Rule 1 fires on `feature_count` alone and precedes rule 2, so breadth vetoes the `fix` escape. Noted for accuracy: F1 is not independently user-visible, so a reading that counts one capability would have reached Direct via rule 2. |
| 2026-09-29 | Implementation complete | All 4 phases, 19 tasks. An occupied asset destination is now a Pass-1 decision: the reducer detects it through the shared folder cache, the suggestions document offers three remedies with rename pre-ticked, and Pass 2 honours the tick — rename files under a free name and rewrites the owning notes' embeds, keep-in-inbox withholds the move, ignore sends it unchanged. ADR-5 held: no wire field, Hashi unchanged, proven by running their compiled validator on a real three-remedy set. `close-out.md` traces all 22 PRD criteria to tests that were EXECUTED — 30 node ids in one pytest invocation — not to tasks that mention them. Three live runs against Privat-Test, one per remedy: rename resolved the 2026-09-15 case end to end with zero failures; keep-in-inbox held the file and filed the note; ignore failed exactly once with Hashi's verbatim 2026-09-15 refusal text, which is what makes ADR-5's dependency measured rather than assumed. Suite 4379 passed, ruff clean. Rides `spec/037-asset-destination-collision` through `feb5eb9`; not merged. Four items recorded open rather than closed: force_atomic bypasses conflict detection, a delete outlives a refused attachment move, the embed rewrite cannot disambiguate a shared basename, and a byte-identical file still gets Rename pre-ticked. Spec 037 also reached the user docs — `usage.md`, `troubleshooting.md`, `instructions-json.md` — which no prior phase had touched. |

## Context

### The failure this spec exists to prevent

`tomo/scripts/lib/render_actions.py::_build_move_asset_actions` already has
collision machinery — case-folded destination keys (CON-6, spec 034 T6.0), a
`kind` of `"no_basename"` or `"collision"`, `owner_source_items` tracking, and a
skip-not-abort posture. Its input set is the **run's own manifest**: two
attachments resolving to one destination. It never asks the vault whether the
destination is already occupied.

`karte.png` was the only attachment in the 2026-09-15 run, so no in-run
collision existed and the pre-existing file was never consulted.

### Why the residue rule did not save it

Spec 034 ADR-6 says a note whose attachment is refused stays in the inbox *with
its file*. That rule is correct and did not fire, because it only sees
collisions Tomo knows about. Tomo emitted the move as appliable, so the owning
note was filed to `Atlas/202 Notes/` and `100 Inbox/Fotos/Kai.md` was deleted.

Observed end state: `Atlas/202 Notes/Kai- Gründung entscheidet über Kosten,
nicht Oberfläche.md` embeds `![[Scans/karte.png]]`, reaching back into
`100 Inbox/Scans/`. No data was lost, but the filing is half-finished and the
next inbox pass removes the file the Atlas note depends on.

This places the detection where the decision about the note's whereabouts is
made — Pass 1 — rather than where the failure surfaces.

### Feasibility, measured rather than assumed

Probed against live Kado on 2026-09-15:

```
source       exists=True   bytes=69   sha256=fa86a6e4…
destination  exists=True   bytes=69   sha256=0fb588da…
```

`KadoClient.path_exists` reports the occupied name and `read_file_bytes`
succeeds on a PNG, so Tomo can hash both sides and distinguish a byte-identical
duplicate from a genuine name clash. Cost shape: one `list_dir` of the asset
folder covers every attachment in a run; only names that actually collide pay
for a `read_file_bytes`.

### Remedies, per case

| Case | Remedies to offer |
|---|---|
| Identical bytes | use the existing file (drop the move, remove the inbox copy) · keep in inbox · file anyway under a new name |
| Differing bytes | rename, rewriting the embed · keep in inbox · use the existing file |

### Scope note carried in from the request

`instructions-diff` is a **paired consumer**: any new action source needs a
matching `derive_expected` or the Pass-2 coverage audit fails on a count
mismatch. The 2026-09-15 Pass 2 aborted on exactly that mechanism, so it is
known to bite.

---
*This file is managed by the xdd-meta skill.*
