---
title: "Live runbook — 037 T4.3 and T4.4"
status: ready
---

# Live runbook — T4.3 and T4.4

Three live `/inbox` runs against the **Privat-Test** vault, one per remedy.
Everything below was verified on 2026-09-28 before the first run.

`tomo-privat` is never touched. The instance is `tomo-instance`. Every write
goes to `/Volumes/Moon/Coding/MiYo/temp/Privat-Test`.

---

## The fixture, verified

| Path | sha256 (12) | Size |
|---|---|---|
| `100 Inbox/Scans/karte.png` | `fa86a6e447ff` | 69 B |
| `Atlas/290 Assets/295 Attachments/karte.png` | `0fb588dae23c` | 69 B |

**Two different pictures with one name.** That is the 2026-09-15 case, intact.
Do not "tidy" either file — the spec exists because of this pair.

The owning note is **`100 Inbox/Dresden.md`**, which embeds:

```
![[100 Inbox/Scans/karte.png]]
```

A **path-prefixed** embed, so this run exercises T3.3's path-prefix branch. The
rewrite should produce the bare basename `![[karte (2).png]]`.

> **Dresden.md's body was rewritten on 2026-09-28, and this is load-bearing.**
>
> The original body read: *"Diese Karte gibt es zweimal im Inbox — einmal unter
> Images/, einmal unter Scans/. Erwartung: als `ambiguous` gemeldet, keine
> Aktion."* An earlier version of this runbook called that text "stale …
> harmless." **It was not harmless.** The 11:39 run measured what it does: the
> classifier scored the item `worthiness: 0.2, suppressed: true`, and
> `detect_attachment_conflicts` deliberately skips suppressed items
> (`suggestions-reducer.py:596-600`) — a sub-worthy atomic stays in the inbox,
> so its attachments claim no destination and there is no collision to report.
> The run produced no `attachment_conflicts` at all. Every component was
> correct; the fixture told the classifier not to act.
>
> The replacement body is a note *about the scanned map*, deliberately not
> about Dresden travel planning: `Atlas/202 Notes/Dresden.md` already exists as
> a genuine 40 KB travel-planning note covering Frauenkirche, Zwinger and the
> Fürstenzug, and a body overlapping it invites a second sub-worthy score for
> redundancy. The embed stays path-prefixed so T3.3's path-prefix branch is
> still exercised. Frontmatter was never touched.
>
> The baseline was retaken after the rewrite, so `restore` between T4.4's runs
> preserves the working fixture instead of reverting it. The pre-rewrite
> baseline is kept at `~/.tomo-spec037-fixture-baseline-pre-bodyfix`.

---

## Step 0 — snapshot the fixture FIRST

```bash
bash scripts/spec037-fixture.sh snapshot
```

**This is genuinely your first action** — run it before anything else, in your
own terminal. The baseline lands at `~/.tomo-spec037-fixture-baseline`, a fixed
path rather than `$TMPDIR`, because `$TMPDIR` differs between a Claude session
and a login shell and a baseline taken in one would be invisible to the other.

I could not take it for you: the sandbox blocks writes to `$HOME`, and it should
be taken by whoever runs the test, on the state they are actually about to test.

The script refuses to overwrite an existing baseline. `status` shows drift,
`restore` puts the vault back. Round-trip tested on 2026-09-28 against an
isolated replica of this exact layout: a simulated run-plus-apply (note filed,
source deleted, asset renamed, new documents written) was detected in full, and
restore removed exactly the created files, left the pre-existing stale documents
alone, and returned all three fixture files byte-identical.

The plan's Success line cites `scratchpad/restore-trigger-notes.sh`. **That
script does not exist anywhere in the repo.** This replaces it.

---

## Step 1 — update the instance

Every changed script is version-bumped, so the version gate will pass them.
Verified 2026-09-28:

| File | instance → repo |
|---|---|
| `scripts/suggestions-reducer.py` | 1.47.0 → **1.57.2** |
| `scripts/suggestion-parser.py` | 0.39.0 → **0.40.3** |
| `scripts/instruction-render.py` | 0.60.0 → **0.62.0** |
| `scripts/lib/render_actions.py` | 0.26.2 → **0.26.6** |
| `scripts/lib/render_md.py` | 0.21.0 → **0.24.1** |
| `scripts/suggestions-render.py` | 0.22.0 → **0.23.0** |
| `scripts/lib/attachment_conflict_states.py` | **new** |
| `scripts/lib/embed_rewrite.py` | **new** |
| `schemas/suggestions-doc.schema.json` | changed (ships bytewise, not version-gated) |

The two new lib files are picked up because `update-tomo.sh:444` globs
`scripts/lib/*.py` and `scan_versioned` returns `create` for a missing
destination — confirmed by reading, not assumed.

```bash
bash scripts/update-tomo.sh --instance tomo-instance --yolo
```

`--yolo` is required: the bare form stops at the voice prompt and copies
nothing. If it fails with "Operation not permitted" around `.claude/`, that is
the sandbox — rerun it in your own terminal.

**Then verify it actually landed** — a silent no-op here is the classic failure:

```bash
grep -m1 '^# version:' tomo-instance/scripts/suggestions-reducer.py   # expect 1.57.2
ls tomo-instance/scripts/lib/embed_rewrite.py                          # must exist
```

---

## Step 2 — T4.3, the rename (the 2026-09-15 case)

**Use `--pass1 --force`, not a bare `/inbox`.**

`Dresden.md` carries `tomo.state: captured` from the 2026-09-18 run, and
`inbox-triage.py:1223-1227` does **not** re-intake captured sources without
`--force`. A bare `/inbox` will skip it, raise no conflict, and the task will
look like it passed while testing nothing.

```
/inbox --pass1 --force
```

Do **not** hand-edit Dresden.md's frontmatter to force this — frontmatter is
written through Kado, never by regex.

### What to check in the suggestions document

1. Exactly **one** Attachment Conflicts entry, for `100 Inbox/Scans/karte.png`.
2. **Rename is pre-ticked.**
3. The proposed name is `karte (2).png` — a basename, not a path.
4. The file-comparison line says the vault holds a **different** file. If it
   says "the same file", the byte comparison is wrong and that is a finding.
5. "Embedded by" names `[[Dresden]]`.

Accept the default (leave rename ticked), then run Pass 2 and apply via Hashi.

### What to capture

- the suggestions document (`.md` and `.json`)
- the instruction set (`.md` and `.json`)
- the Hashi run log
- `tomo-tmp/` cost output — **`base_kado_calls` must still read 2**, the spec
  034 T6.4 baseline, since the reducer is a separate process. Record
  `folder_listing_calls` too; it should rise by at most one.

### Pass condition

Zero `move_asset` failures — the row that was red on 2026-09-15 is green — and
the filed note embeds `![[karte (2).png]]`, not the vacated inbox path.

---

## Step 3 — restore, then T4.4 keep-in-inbox

```bash
bash scripts/spec037-fixture.sh restore
```

```
/inbox --pass1 --force
```

**Untick rename, tick "Keep in inbox."** Then Pass 2 and apply.

Expect: **no `move_asset` emitted**, no Hashi failure, `karte.png` still in
`100 Inbox/Scans/`, and — per your 2026-09-27 ruling — **Dresden.md still
filed**, because keep-in-inbox names the attachment, not the note.

The instruction document should carry both, with no sentence repeated:

```
- ⚠️ **Conflict remains:** `100 Inbox/Scans/karte.png` — it was not filed over
  the occupied destination `…/karte.png`, so it stays unmoved
- ⚠️ **Attachment not filed:** `100 Inbox/Scans/karte.png` — kept in inbox: …
  no action needed — this is what the owner chose; …
```

---

## Step 4 — restore, then T4.4 ignore

```bash
bash scripts/spec037-fixture.sh restore
```

```
/inbox --pass1 --force
```

**Untick rename, tick "Ignore."** Then Pass 2 and apply.

**This run is supposed to fail**, and that is the point. Expect exactly **one**
failure, naming `move_asset`, with Hashi refusing the occupied destination in
the same terms as 2026-09-15. That proves ADR-5's dependency on Hashi's
existing refusal is real and not assumed.

Capture the run log. Assert the failure count is exactly 1.

> The vault keeps a refused action in its log afterwards. Expected, not damage.

---

## Step 5 — restore

```bash
bash scripts/spec037-fixture.sh restore && bash scripts/spec037-fixture.sh status
```

Must end with **"Vault matches the baseline."** T4.4's Success line requires the
fixture restored so the next run starts from the same state.

---

## Things that would invalidate a run

- A bare `/inbox` — captured sources are skipped, no conflict raised.
- Forgetting `--yolo` — the instance silently keeps old scripts.
- Editing either `karte.png`, or deleting one.
- `base_kado_calls` ≠ 2 — a cost regression, not a pass.
- **Dresden coming back `suppressed: true`.** Check this first in
  `suggestions-doc.json` before reading anything else — a suppressed item
  claims no destination, so an empty `attachment_conflicts` is the correct
  output and proves nothing. Ticking Force Atomic Note does **not** rescue the
  run: detection already ran and skipped the item (see the open item below).
  The fix is the note body, not the tick.

## Stale generated documents — removed, and why "harmless" was wrong

An earlier version of this section said the stale 2026-09-18 documents in
`100 Inbox/` were harmless because `--pass1 --force` overrides routing. That is
true of **routing** and false of **input**. The 11:35 routing plan listed
`2026-09-18_1124_suggestions.md` under `approved_suggestions` — it was live
Pass-2 input, and synthesizing it would have produced instructions for a
ten-day-old eight-item run alongside the one under test. The 11:39 run then
added a second `pending-approval` suggestions document built from the
suppressed classification, with no Attachment Conflicts section.

All six files were moved out of the vault on 2026-09-28 (moved, not deleted —
they are at `scratchpad/stale-inbox-docs/` in that session's directory) and the
baseline retaken against the clean inbox.

Two files still match the `Atlas/202 Notes/Dresden*.md` glob and are correctly
recorded as pre-existing: `Dresden.md` and `Dresden Elbland.md`. Both are
genuine user notes created 2025-11-19, unrelated to the 2026-09-15 incident.
`restore` leaves them alone. Note that `Atlas/202 Notes/Dresden.md` being
occupied means the filed note will hit `resolve_destination_clashes` and be
retitled — expected, and independent of the attachment conflict, whose
destination comes from `_asset_dest_join(asset_folder, basename)` and not from
the note's title.

## Open: force_atomic bypasses conflict detection entirely

Found while diagnosing the 11:39 run; **traced in code, not yet measured.**

`detect_attachment_conflicts` runs in the reducer, in Pass 1, and skips
suppressed items. Ticking **Force Atomic Note** un-suppresses the item in Pass
2, so the note is filed and its attachment moves — but the conflict scan has
already run and skipped it. `_build_move_asset_actions`'s docstring is explicit
that a source absent from `attachment_conflict_remedies` *"is treated as a
plain attachment — same as `ignore`"*, and there is no occupancy check anywhere
in Pass 2 (`rg 'path_exists' tomo/scripts/instruction-render.py
tomo/scripts/lib/render_actions.py` returns nothing).

So a sub-worthy note whose attachment collides can still reach Hashi with no
remedy and no warning — the 2026-09-15 failure, reachable through a supported
owner action that spec 037 does not cover. Not in this spec's scope; recorded
here and in `docs/XDD/backlog.md` rather than fixed in flight.
