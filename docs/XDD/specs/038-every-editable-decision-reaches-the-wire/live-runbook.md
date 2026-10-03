---
title: "Live runbook — 038 T5.3"
status: ready
prepared: 2026-10-03
---

# Live runbook — T5.3, the live run

Three `/inbox` runs against the **Privat-Test** vault, one per feature under test.
Everything in the "verified" sections below was measured on 2026-10-03, on the state
you are about to test. Where a claim was inherited from the 037 runbook rather than
re-measured, it says so.

`tomo-privat` is never touched. The instance is `tomo-instance`. Every write goes to
`/Volumes/Moon/Coding/MiYo/temp/Privat-Test`.

**What T5.3 owes** `[ref: plan/phase-5.md]`:

| Success line | Run |
|---|---|
| A remedy survives a wire edit in a real run `[ref: PRD/F1]` | A |
| A typed name files the attachment and rewrites the embeds `[ref: PRD/F2]` | B |
| A refused name holds the note and is reported `[ref: PRD/F3]` | C |
| The cost log is updated, as after every live run | after each |

---

## Step 0 — the instance is already synced, with one caveat you need to know

Done 2026-10-03 — **do not re-run it blind**, read this first.

`bash scripts/update-tomo.sh --instance tomo-instance --yolo` landed 8 runtime scripts
and 3 schemas, and **failed on exactly one file**: `agents/synthesis-conductor.md`,
reported only as `cp failed`. That is the sandbox refusing a write under `.claude/`, and
the reason was swallowed because the copy at `update-tomo.sh:852` is
`cp "$src" "$dst" 2>/dev/null`.

That one file is the **only** verification T4.5's shell relay can ever get, so it was not
left failed. It was copied by hand after confirming at `update-tomo.sh:852` that the agent
sync is a plain `cp` with no transformation — so the manual copy is equivalent rather than
a shortcut past a step. The instance copy is now byte-identical to the repo's and carries
`# version: 0.21.0`.

**If you re-run the sync yourself, run it in your own terminal**, not through a sandboxed
session, or that file will fail again and the relay will silently not exist.

Verified after the sync, by sweeping every `tomo/scripts/**/*.py` and every
`tomo/dot_claude/agents/*.md`:

| | |
|---|---|
| Runtime scripts, instance vs repo | **all match** — no drift |
| Agents, instance vs repo | **all match** — no drift |
| `scripts/lib/typed_name_check.py` | created in the instance (it was absent; new in this spec) |
| `schemas/suggestions-wire.schema.json` | updated (ships bytewise, not version-gated) |

`schemas/suggestions-decision-inventory.json` also landed. It is read by tests only — no
runtime script reads it — so its presence or absence in the instance changes nothing.

### The relay path, resolved rather than assumed

The wiring guard in the suite pins the prompt's string against the writer's constant. It
does **not** resolve the path. Resolved here, inside the instance:

| | |
|---|---|
| the prompt's Step 3b invocation | `--output-dir tomo-tmp/rendered` |
| the writer | `out_dir.parent / WITHHELD_ATTACHMENTS_RELAY` |
| `WITHHELD_ATTACHMENTS_RELAY` | `"withheld-attachments.md"` |
| so the relay lands at | `tomo-tmp/withheld-attachments.md` |
| and Step 4 `cat`s | `tomo-tmp/withheld-attachments.md` |

They agree. Nothing in the suite checks that, because nothing in the suite knows what
`--output-dir` the prompt passes.

---

## Step 1 — the fixture, verified on 2026-10-03

| Path | sha256 (12) | Size |
|---|---|---|
| `100 Inbox/Scans/karte.png` | `fa86a6e447ff` | 69 B |
| `Atlas/290 Assets/295 Attachments/karte.png` | `0fb588dae23c` | 69 B |

**Two different pictures with one name**, confirmed by `cmp` and not by the sizes — both
are 69 B, so size parity would have hidden it. The 2026-09-15 case is intact. Do not
"tidy" either file; the spec exists because of this pair. `karte (2).png` is free, so the
computed name will be `karte (2).png`.

The owning note is `100 Inbox/Dresden.md`, embedding:

```
![[100 Inbox/Scans/karte.png]]
```

**Path-prefixed**, so every run exercises the path-prefix branch of the embed rewrite, and
an accepted rename should produce a **bare basename** embed.

`bash scripts/spec037-fixture.sh status` reports `CHANGED 100 Inbox/Dresden.md`. **That is
the documented benign drift, and it was diffed rather than assumed** — the only difference
is the frontmatter `Updated:` line (`2026-09-28 13:18` → `2026-09-29 12:51`), which
Obsidian rewrites. Body and embed byte-identical. No `NEW` files, so no suggestion or
instruction documents are left over from earlier runs.

### `--pass1 --force` is mandatory, and a bare `/inbox` fails silently

`Dresden.md` carries `tomo.state: captured` with `run_id: 2026-09-28T09-34-28Z-350cc2`.
Triage does not re-intake a captured source without `--force`. A bare `/inbox` will skip
it, raise no conflict, and **every run below will look like it passed while testing
nothing.** This is the single easiest way to waste a run.

Do not hand-edit Dresden.md's frontmatter to work around this — frontmatter goes through
Kado, never a regex.

---

## Run A — F1: a remedy survives a wire edit

This is the spec's founding defect. Before 038 the wire carried **no remedy field at
all**, so an edited wire sent Pass 2 to rebuild from a wire that did not know the owner's
choice, and it silently reverted to the pre-ticked default.

```
/inbox --pass1 --force
```

Check in the suggestions document: exactly one Attachment Conflicts entry for
`100 Inbox/Scans/karte.png`; **Rename pre-ticked**; the target `karte (2).png` as a
basename, not a path; the comparison line saying the vault holds a **different** file
(if it says "the same file", the byte comparison is wrong and that is a finding); and
"Embedded by" naming `[[Dresden]]`.

**Leave the markdown alone.** Now set the remedy on the wire instead:

```bash
./venv/bin/python scripts/spec038-wire-edit.py \
  "/Volumes/Moon/Coding/MiYo/temp/Privat-Test/100 Inbox/<DATE>_suggestions.json" --show

./venv/bin/python scripts/spec038-wire-edit.py \
  "/Volumes/Moon/Coding/MiYo/temp/Privat-Test/100 Inbox/<DATE>_suggestions.json" \
  --remedy keep_in_inbox
```

**Why by script and not by hand.** The digest is canonical — sorted keys, no incidental
whitespace, and it excludes `emit_digest` itself — so it is **invariant to
re-serialization**. Opening the JSON in an editor and saving it with different formatting
does **not** stale it. Only a semantic change does. The script leaves `emit_digest` exactly
as the producer wrote it, and then asserts the recomputation now differs; it refuses to
write when the value you asked for is the one already there, because that edit would be a
no-op and Pass 2 would quietly take the markdown path.

The script stands in for Hashi's Suggestions Editor, which is what will normally do this.
It cannot today: Hashi's vendored schema still pins `schema_version` to `const: "2"` and
contains none of the remedy fields — re-measured 2026-10-03, and all six 038 field names
appear in **zero** files across its sources.

Then:

```
/inbox --pass2 --force
```

### Pass condition

- Pass 2's output carries `suggestions-json: edited wire is authoritative (JSON-only
  path)`. **Without this line the run proved nothing** — it means the markdown was parsed
  instead, and the digest, the JSON's parseability or its `schema_version` is why.
- **No `move_asset`** for `karte.png`. The wire's `keep_in_inbox` was honoured; a
  `move_asset` to `karte (2).png` is the pre-038 defect reappearing.
- `Dresden.md` is still **filed** — keep-in-inbox holds the file, not the note.
- The instruction document lists the attachment under "**Attachments still in the inbox**"
  with the keep-in-inbox remedy wording.
- The shell report relays that same line.

Apply via Hashi, then capture, then restore.

---

## Run B — F2: a typed name, accepted end to end

```bash
bash scripts/spec037-fixture.sh restore
```

```
/inbox --pass1 --force
```

In the suggestions document, **type over the backtick content** of the Rename line,
replacing `karte (2).png` with:

```
karte-1938.png
```

Legal, free, and meaningful — the note itself says *"ein Nachdruck der Ausgabe von 1938"*.
Leave Rename ticked. Change nothing else, and do **not** touch the wire: this run tests
the markdown surface, and an edited wire would take authority and make the markdown edit
irrelevant.

```
/inbox --pass2 --force
```

### Pass condition

- A `move_asset` whose destination is
  `Atlas/290 Assets/295 Attachments/karte-1938.png` — the typed name, not the computed one.
- **The destination is itself the proof** that the parser read your edit: the computed
  default is `karte (2).png`, so `karte-1938.png` cannot have arrived any other way.
- Optional corroboration — the provenance flag. It is **not** on the action and **not** in
  any schema; the code calls it "internal to this script's own output dict". It lives in
  `tomo-tmp/parsed-suggestions.json` under `attachment_conflict_remedies[]`, shaped
  `{source, remedy, proposed_name, name_is_owner_supplied}`. On the markdown path it is set
  by **comparison** against the document's bare name, so `true` there means the parser saw
  a name that differs from its own. Do not look for it in the instruction set — it never
  reaches it.
- The filed note's embed reads `![[karte-1938.png]]` — a **bare basename**, not the vacated
  inbox path and not path-prefixed.
- Apply via Hashi: **zero failures**, the file lands, the embed resolves in Obsidian.

Optional, and worth one extra restore if you have the appetite: repeat this run but set the
name on the **wire** via `--proposed-name "karte-1938.png"` instead of the markdown. That
exercises the path Hashi will actually drive once updated. Note the deliberate asymmetry
there: the wire sets `name_is_owner_supplied` **unconditionally**, because it cannot know
whether the consumer edited the field.

---

## Run C — F3: a typed name refused, and T4.5's shell relay

```bash
bash scripts/spec037-fixture.sh restore
```

```
/inbox --pass1 --force
```

Type over the backtick content with a name the **vault** forbids but macOS permits:

```
karte*1938.png
```

`*` is one of the forbidden characters. Leave Rename ticked.

```
/inbox --pass2 --force
```

### Pass condition

- **No `move_asset`** for this attachment. ADR-5: a typed name is refused, never
  sanitised — if the destination comes back as `karte-1938.png` with the `*` substituted,
  the general filename sanitiser got onto this path and that is the exact defect this spec
  closes.
- `instructions.json` carries, under `tomo.skipped_assets[]`, an entry whose `kind` is
  `"typed_name_refused"` and whose `reason` reads exactly:

  ```
  typed name refused: `karte*1938.png` contains a character Obsidian does not allow in a filename
  ```

  The projection carries `{source, destination, kind, reason}` and **`destination` will be
  `null`** — which is why `kind` is projected explicitly rather than derived: a no-basename
  skip also has no destination, so the two are no longer distinguishable without it.
  The enum behind that sentence (`forbidden_character`) is **in-process only** and reaches
  no file — do not go looking for it.
- **`Dresden.md` is HELD** — still in the inbox, **not** filed. This is where F3 diverges
  from keep-in-inbox, which files the note. Check this explicitly; it is the half of the
  behaviour that is newest and the half `docs/usage.md` had asserted the opposite of until
  T5.1 narrowed it.
- The instruction document carries this bullet under "**Attachments still in the inbox**
  — none of these were filed:", and it should match character for character, because both
  surfaces are rendered by one function. **The line below was produced by executing that
  renderer on 2026-10-03, not transcribed** — so a mismatch is a finding about the run, not
  a typo in this runbook:

  ```
  - ⚠️ **Attachment not filed:** `100 Inbox/Scans/karte.png` — typed name refused: `karte*1938.png` contains a character Obsidian does not allow in a filename. Type a usable name for it: before applying, correct the name in the suggestions document and run `/inbox --pass2 --force`; afterwards, it is still in the inbox, so re-run `/inbox` and name it again.
  ```

- **`tomo-tmp/withheld-attachments.md` exists and holds that same line**, and the Pass-2
  shell report relays it verbatim. If the two differ, that is a finding: they come from the
  same renderer by construction, and a divergence means something re-derived one of them.
  **This is T4.5's only possible verification** —
  `synthesis-conductor.md` Step 4 is produced by a model at runtime and no pytest can
  capture it. One line per withheld attachment, and **no count**, by ruling.
- Re-run `/inbox` afterwards: the held note is re-discovered and re-proposed, which is the
  "afterwards" half of the remedy the document prints.

---

## After every run

- Capture: the suggestions document (`.md` and `.json`), the instruction set (`.md` and
  `.json`), the Hashi run log, and `tomo-tmp/withheld-attachments.md` where it exists.
- `tomo-tmp/` cost output: **`base_kado_calls` must still read 2** — the spec 034 T6.4
  baseline, since the reducer is a separate process. Record `folder_listing_calls` too.
- Update the cost log, as after every live run.
- `bash scripts/spec037-fixture.sh restore`, then `status`, and **diff `Dresden.md` before
  concluding a restore failed** — the `Updated:` line alone is benign.

Filed notes are **not** named after their source: the note filed from `Dresden.md` in 037
was titled *"Historische Stadtkarte Dresden (vor 1945) im Vergleich zum heutigen
Stadtplan"*. Atomic titles come from the classifier and no name pattern predicts them,
which is why `restore`'s glob is the whole `Atlas/202 Notes/` folder and why the 308
pre-existing notes recorded in `preexisting.txt` are what keeps it from deleting anything
real.

## Read the output as the owner, not as the author

Step 4 of T5.3 asks for this specifically, and it is not ceremony: spec 037's four
defective sentences were caught by the owner reading shipped output, not by review. Two
of this spec's own documentation defects were caught the same way this week. Read the
rendered documents for what they claim, not for whether they ran.
