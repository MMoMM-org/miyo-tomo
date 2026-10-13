---
title: "Live runbook — 039 T6.3 (c) and (c2)"
status: ready
prepared: 2026-10-13
---

# Live runbook — T6.3 (c) and (c2), the live runs

Two `/inbox` cycles against the **Privat-Test** vault:

- **Cycle 1** (Pass 1, owner edits, Pass 2, Hashi apply) runs **S1–S4 and E1 together**:
  five new inbox notes, one per scenario, all in one suggestions document.
- **Cycle 2** (`/inbox --recover`, Pass 1 only) is **S5**. It runs on the vault exactly
  as cycle 1's apply left it.

`tomo-privat` is never touched. The instance is `tomo-instance`. Every vault write goes
to `/Volumes/Moon/Coding/MiYo/temp/Privat-Test` (below: `$V`).

Every expected line marked **executed** below was produced by running the renderer at
branch HEAD `ff4317b0` on 2026-10-13, not transcribed. A mismatch is a finding about
the run, not a typo in this runbook.

**What T6.3 owes** `[ref: plan/phase-6.md T6.3 step 2]`:

| Line | Scenario | Cycle |
|---|---|---|
| (c) a conflict resolved by folder only | S1 | 1 |
| (c) a forced ambiguous basename | S2 (and S1) | 1 |
| (c) a refused folder | S3 | 1 |
| (c) an Ignore whose move fails at apply: the origin survives (F6-AC2) | S4 | 1 |
| (c2) `/inbox --recover` re-intakes a held note and offers its folder/name again (T5.4 owner ruling 2026-10-13) | S5 | 2 |
| Cheap extra evidence: F3-AC5 occupied wording, F2-AC8 folder will be created, shell relay, C1-AC1 cost entry | E1, S1, all | 1 |

**F3-AC6 ("not checked") is NOT reproduced here.** A target is "unanswered" only when
Kado's folder listing fails with an error other than `Path not found`. Getting that live
would mean breaking Kado mid-run (which also fails the rest of Pass 2) or changing the Tomo
Kado key's permissions. Both are out of scope for this runbook. F3-AC6 stays evidenced by
its tests. If you want to probe it on purpose, see "Optional probes" at the end.

---

## Hashi is on v3, so edits go through the markdown only

The installed plugin in the test vault is `miyo-tomo-hashi` **0.26.1** (read from
`$V/.obsidian/plugins/miyo-tomo-hashi/manifest.json`). Its vendored suggestions schema
pins `schema_version` to `"3"`. This branch publishes the suggestions wire at `"4"`. The
v4 handoff went out on 2026-10-13, and Hashi has not vendored it yet.

- **Do not open the run in Hashi's Suggestions Editor.** Its validator rejects a v4 wire
  with its fail-loud `schema_version` message. Every owner decision in this runbook is
  made in the **suggestions markdown**: tick boxes, type over backtick content, tick
  `- [x] Approved` by hand. A Hashi save normally ticks Approved for you. Here nothing
  does that, so tick it yourself.
- **Do not edit the `_suggestions.json`.** Cycle 1 tests the markdown path. An edited wire
  becomes authoritative and makes the markdown edits irrelevant. Convergence of the two
  paths is T6.3 (a), already covered by a test.
- **Hashi's apply path is unaffected.** The executor reads only the instruction set. The
  instructions wire stays at `schema_version: "3"` (Tomo's `instructions.schema.json`
  still pins `"3"`). This spec changed one thing in that schema: the **description** of
  `depends_on`. Its values are still strings. `depends_on` now also names `move_asset`
  ids, and Hashi's planner (`src/executor/planner.ts`) unions declared edges whatever
  the action kind. Nothing in any scenario needs Hashi's suggestions surface.

**Hashi v3 blocks no scenario.** It only blocks the editor-path variant of S1. That
variant is not part of (c).

---

## Step 0: sync the instance, and prove it arrived

Run all of this **in your own terminal**, not from a sandboxed Claude session. On
2026-10-03 the sandbox refused the `.claude/agents/` copy, and `update-tomo.sh:852`
swallowed the reason (`cp "$src" "$dst" 2>/dev/null`). `synthesis-conductor.md`
is the file that carries the shell relay, and it would silently not land.

```bash
cd /Volumes/Moon/Coding/MiYo/Tomo
git switch spec/039-attachment-conflict-hardening   # only if not already on it
git log --oneline -1                                 # record the SHA you synced from
bash scripts/update-tomo.sh --instance tomo-instance --yolo
```

- `--instance tomo-instance` is **mandatory**. Never let the script pick an instance.
  `tomo-privat` is live.
- `--yolo` is mandatory from any non-interactive context. Without it the script prints
  a plan, dies at the voice prompt and copies nothing.

On 2026-10-13 the instance was still at **main** versions
(`instruction-render.py 0.63.0`, `render_actions.py 0.26.12`, `suggestions-reducer.py
1.59.0`, `synthesis-conductor.md 0.21.0`, no `lib/vault_paths.py` at all). So expect
updates and creates, not "current".

### Expected versions: every `tomo/` file changed since `main`

From `git diff --name-only main...HEAD -- tomo` at `ff4317b0`:

| Repo file | Instance path | Expected `# version:` | Was on main |
|---|---|---|---|
| `tomo/dot_claude/agents/synthesis-conductor.md` | `tomo-instance/.claude/agents/synthesis-conductor.md` | `0.22.0` | 0.21.0 |
| `tomo/scripts/inbox-triage.py` | `tomo-instance/scripts/inbox-triage.py` | `0.39.4` | 0.39.2 |
| `tomo/scripts/instruction-render.py` | `…/scripts/instruction-render.py` | `0.67.0` | 0.63.0 |
| `tomo/scripts/instructions-diff.py` | `…/scripts/instructions-diff.py` | `0.22.1` | 0.22.0 |
| `tomo/scripts/suggestion-parser.py` | `…/scripts/suggestion-parser.py` | `0.42.2` | 0.41.2 |
| `tomo/scripts/suggestions-reducer.py` | `…/scripts/suggestions-reducer.py` | `1.60.4` | 1.59.0 |
| `tomo/scripts/suggestions-render.py` | `…/scripts/suggestions-render.py` | `0.25.0` | 0.24.1 |
| `tomo/scripts/lib/attachment_plan.py` | `…/scripts/lib/attachment_plan.py` | `0.4.0` | **new** |
| `tomo/scripts/lib/basename_census.py` | `…/scripts/lib/basename_census.py` | `0.2.3` | **new** |
| `tomo/scripts/lib/cost_history.py` | `…/scripts/lib/cost_history.py` | `0.3.0` | 0.2.0 |
| `tomo/scripts/lib/embed_rewrite.py` | `…/scripts/lib/embed_rewrite.py` | `0.5.1` | 0.4.2 |
| `tomo/scripts/lib/refusal_sentences.py` | `…/scripts/lib/refusal_sentences.py` | `0.5.1` | **new** |
| `tomo/scripts/lib/render_actions.py` | `…/scripts/lib/render_actions.py` | `0.30.0` | 0.26.12 |
| `tomo/scripts/lib/render_helpers.py` | `…/scripts/lib/render_helpers.py` | `0.5.0` | 0.4.0 |
| `tomo/scripts/lib/render_md.py` | `…/scripts/lib/render_md.py` | `0.35.1` | 0.33.0 |
| `tomo/scripts/lib/render_resolve.py` | `…/scripts/lib/render_resolve.py` | `0.5.1` | 0.5.0 |
| `tomo/scripts/lib/typed_name_check.py` | `…/scripts/lib/typed_name_check.py` | `0.3.1` | 0.1.3 |
| `tomo/scripts/lib/vault_folder_lookup.py` | `…/scripts/lib/vault_folder_lookup.py` | `0.2.0` | **new** |
| `tomo/scripts/lib/vault_paths.py` | `…/scripts/lib/vault_paths.py` | `0.2.2` | **new** |

Schemas carry no version header. They sync **bytewise**, so check them with `cmp`:
`suggestions-wire.schema.json`, `hashi-suggestions-wire.schema.json`,
`instructions.schema.json`, `suggestions-doc.schema.json`,
`suggestions-decision-inventory.json`.

`suggestions-wire.schema.json` is the one that matters at runtime.
`suggestions-render.py` and `suggestion-parser.py` read the wire's version **from the
instance's copy** (`wire_schema_version("suggestions-wire.schema.json")`). If the copy is
stale, the instance publishes v3 with a v4 shape. `tomo/schemas/shapes/` is not synced by
`update-tomo.sh` (it copies `schemas/*.json` only), and no pipeline script reads it.
Its absence from the instance is expected.

### Verify: do not trust the summary line

```bash
cd /Volumes/Moon/Coding/MiYo/Tomo
for f in $(git diff --name-only main...HEAD -- tomo/scripts); do
  i="tomo-instance/${f#tomo/}"
  printf '%-45s repo=%s  inst=%s\n' "${f#tomo/scripts/}" \
    "$(grep -m1 '# version:' "$f" | sed 's/.*version: //')" \
    "$(grep -m1 '# version:' "$i" 2>/dev/null | sed 's/.*version: //')"
done
grep -m1 '# version:' tomo-instance/.claude/agents/synthesis-conductor.md   # 0.22.0
for s in suggestions-wire hashi-suggestions-wire instructions suggestions-doc; do
  cmp "tomo/schemas/$s.schema.json" "tomo-instance/schemas/$s.schema.json" && echo "same $s"
done
cmp tomo/schemas/suggestions-decision-inventory.json tomo-instance/schemas/suggestions-decision-inventory.json && echo "same inventory"
grep -c '"const": "4"' tomo-instance/schemas/suggestions-wire.schema.json   # >= 1
```

Every `repo=` must equal its `inst=`. An empty `inst=` means the file did not land.
Also grep for a symbol that only exists in this spec, so a stale copy with a correct
header cannot pass:

```bash
grep -c 'def folder_created_sentence' tomo-instance/scripts/lib/refusal_sentences.py   # 1
grep -c -- '- Folder:' tomo-instance/scripts/suggestions-reducer.py                    # >= 1
grep -c 'cost-history' tomo-instance/.claude/agents/synthesis-conductor.md              # >= 1
grep -c 'withheld-attachments.md' tomo-instance/.claude/agents/synthesis-conductor.md   # >= 1
```

### Reset tomo-tmp, check the fixture is still broken, restart

```bash
bash scripts/reset-tomo-tmp.sh --pass1 --instance tomo-instance/tomo-tmp --dry-run
bash scripts/reset-tomo-tmp.sh --pass1 --instance tomo-instance/tomo-tmp
ls "/Volumes/Moon/Coding/MiYo/temp/Privat-Test/Calendar/301 Daily/" | tail -1   # 2026-09-12.md — leave it
bash scripts/spec037-fixture.sh status
```

- Pass `--instance tomo-instance/tomo-tmp` explicitly. The script looks for an
  `install_path` key that `tomo-install.json` does not carry and falls back to the repo's
  `tomo-instance/tomo-tmp`. That is correct today, but naming it costs nothing.
- The run-id filter (#116) makes the reset belt-and-braces, not required.
- The 037 fixture (`Dresden.md`, `karte.png` pair) is **not** part of cycle 1. A plain
  `/inbox` skips it, because `Dresden.md` is `captured`. It will be re-intaken in
  cycle 2, which is why `status` is recorded now.

Then **restart the Claude session inside the container** (`./begin-tomo.sh`, a fresh
session). Agent definitions are cached at session start, and an old session runs
`synthesis-conductor` 0.21.0 whatever the instance holds.

---

## Step 1: seed the test vault

The test instance's `config/vault-config.yaml` (read 2026-10-13):

| concept | value |
|---|---|
| `concepts.inbox` | `100 Inbox/` |
| `concepts.asset` | `Atlas/290 Assets/295 Attachments/` |
| `concepts.atomic_note.path` | `Atlas/202 Notes/` |

### Guard first: none of these names may already exist

```bash
V="/Volumes/Moon/Coding/MiYo/temp/Privat-Test"
cd "$V"
find . -path ./.obsidian -prune -o \( -iname 'leipzig-plan*' -o -iname 'pirna-markt*' \
  -o -iname 'goerlitz-altstadt*' -o -iname 'radebeul-weinberg*' -o -iname 'freiberg-dom*' \
  -o -iname 'Leipzig.md' -o -iname 'Pirna.md' -o -iname 'Goerlitz.md' -o -iname 'Radebeul.md' \
  -o -iname 'Freiberg.md' \) -print
ls -d "Atlas/296 Karten" "100 Inbox/Karten" 2>&1     # both: No such file or directory
```

The `find` must print **nothing**. If anything is printed, stop and clean it up first.
A leftover file changes every census count below.

### Record what already exists, for the cleanup

```bash
SNAP="$HOME/.tomo-spec039-live"
mkdir -p "$SNAP"
ls "$V/Atlas/202 Notes"                   > "$SNAP/notes-before.txt"
ls "$V/Atlas/290 Assets/295 Attachments"  > "$SNAP/attachments-before.txt"
ls "$V/100 Inbox"                         > "$SNAP/inbox-before.txt"
```

### Create the fixture

Bytes come from images already in the vault, so nothing is generated. **Different
source images mean different files.** S4 alone uses the same image twice, on purpose.

```bash
A="$V/Atlas/290 Assets/295 Attachments"
I="$V/100 Inbox"

# S1 — folder only. Inbox copy and occupier DIFFER.
cp "$A/flow-map.png"               "$I/Scans/leipzig-plan.png"
cp "$A/full-ooda-loop.png"         "$A/leipzig-plan.png"

# S2 — no conflict; the same basename exists ELSEWHERE in the vault (different bytes).
cp "$A/flow-zone-channel.jpg"      "$I/Bilder/pirna-markt.jpg"
cp "$A/Systems-thinkingFI-min.jpg" "$V/Atlas/290 Assets/293 Excalidraw/pirna-markt.jpg"

# S3 — refused folder. Inbox copy and occupier DIFFER.
cp "$A/simple-ooda-loop.png"       "$I/Scans/goerlitz-altstadt.png"
cp "$A/snoopy-flying.png"          "$A/goerlitz-altstadt.png"

# S4 — Ignore. Inbox copy and occupier IDENTICAL (the realistic reason to pick Ignore).
cp "$A/snoopytyping_1024x768.jpg"  "$I/Fotos/radebeul-weinberg.jpg"
cp "$A/snoopytyping_1024x768.jpg"  "$A/radebeul-weinberg.jpg"

# E1 — typed name onto an occupied target (F3-AC5). Inbox copy and occupier DIFFER.
cp "$A/SnoopyRelax.png"            "$I/Scans/freiberg-dom.png"
cp "$A/MiYo.png"                   "$A/freiberg-dom.png"

shasum -a 256 "$I/Scans/leipzig-plan.png" "$A/leipzig-plan.png" \
  "$I/Bilder/pirna-markt.jpg" "$V/Atlas/290 Assets/293 Excalidraw/pirna-markt.jpg" \
  "$I/Scans/goerlitz-altstadt.png" "$A/goerlitz-altstadt.png" \
  "$I/Fotos/radebeul-weinberg.jpg" "$A/radebeul-weinberg.jpg" \
  "$I/Scans/freiberg-dom.png" "$A/freiberg-dom.png" | tee "$SNAP/fixture-sha256.txt"
```

The five notes are below. Every embed is **path-prefixed**, as `Dresden.md`'s is. A bare
`![[leipzig-plan.png]]` would be ambiguous *before* the run, because the occupier holds
the same basename. That is the very defect F4 is about, and it would make discovery
depend on which copy wins. No frontmatter and no dates: the classifier should propose
one atomic note per item, and nothing should route to a daily note.

`$I/Leipzig.md`:

```markdown
# Leipzig

Stadtplan der Leipziger Innenstadt aus einem alten Reisefuehrer, abfotografiert. Er zeigt den Ring um die Altstadt mit Hauptbahnhof, Augustusplatz und Thomaskirche. Die Passagen zwischen Markt und Neumarkt sind eingezeichnet, die Maedlerpassage ist hervorgehoben.

Als Orientierung fuer einen Stadtrundgang reicht der Plan: vom Hauptbahnhof ueber die Nikolaikirche zum Markt und weiter zur Thomaskirche sind es kaum zwei Kilometer.

![[100 Inbox/Scans/leipzig-plan.png]]
```

`$I/Pirna.md`:

```markdown
# Pirna

Foto vom Marktplatz in Pirna mit dem Rathaus in der Mitte und den Buergerhaeusern ringsum. Canaletto hat genau diesen Blick im 18. Jahrhundert gemalt, und die Platzwand ist bis heute fast unveraendert.

Pirna ist der Ausgangspunkt fuer die Saechsische Schweiz flussaufwaerts; die Altstadt lohnt sich trotzdem fuer einen eigenen halben Tag.

![[100 Inbox/Bilder/pirna-markt.jpg]]
```

`$I/Goerlitz.md`:

```markdown
# Goerlitz

Luftbild der Goerlitzer Altstadt mit Peterskirche, Untermarkt und der Altstadtbruecke ueber die Neisse nach Zgorzelec. Die Stadt hat den Krieg fast ohne Zerstoerung ueberstanden, deshalb ist die Bebauung aus Gotik, Renaissance und Barock geschlossen erhalten.

Wegen dieser Kulisse wird Goerlitz oft als Drehort genutzt.

![[100 Inbox/Scans/goerlitz-altstadt.png]]
```

`$I/Radebeul.md`:

```markdown
# Radebeul

Blick ueber die Weinberge von Radebeul mit dem Spitzhaus oben am Hang. Die Steillagen an der Elbe gehoeren zum Anbaugebiet Sachsen, einem der kleinsten und noerdlichsten Weinbaugebiete Deutschlands.

Die Spitzhaustreppe fuehrt mit ueber dreihundert Stufen direkt durch die Rebhaenge nach oben.

![[100 Inbox/Fotos/radebeul-weinberg.jpg]]
```

`$I/Freiberg.md`:

```markdown
# Freiberg

Innenaufnahme des Freiberger Doms mit der Tulpenkanzel und der Silbermann-Orgel. Der Dom steht fuer den Reichtum, den der Silberbergbau der Stadt im Mittelalter gebracht hat.

Die Goldene Pforte am Dom gilt als eines der fruehesten Figurenportale in Deutschland.

![[100 Inbox/Scans/freiberg-dom.png]]
```

Wait until Obsidian has indexed the new files, then confirm that the `find` above now
prints exactly the 10 attachments and 5 notes.

---

## Cycle 1: S1, S2, S3, S4 and E1 in one run

### 1a. Pass 1

In the container session:

```
/inbox
```

A plain `/inbox`. The five notes are fresh, and every older inbox note is `captured`,
so only the five are proposed. **Not** `--recover` here: that would also re-intake
`Dresden.md`, `Bautzen.md` and the rest, and mix the 037 fixture into this run.

**Check the suggestions document before editing it.** Copy each of these into the
evidence table:

- `100 Inbox/<DATE>_suggestions.json` has `"schema_version": "4"`, and **every**
  `attachment_conflicts[]` entry carries `"proposed_dir": null` (F1-AC1).
- Exactly **four** entries under `## Attachment Conflicts`: `leipzig-plan.png`,
  `goerlitz-altstadt.png`, `radebeul-weinberg.jpg`, `freiberg-dom.png`. **No** entry for
  `pirna-markt.jpg`. Pass 1 only looks at the destination folder, and nothing named
  `pirna-markt.jpg` is there.
- Each entry has its own folder line directly under the Rename line, pre-filled with
  the asset folder **without** a trailing slash (F1-AC2):

  ```
  - [x] Rename to `Atlas/290 Assets/295 Attachments/leipzig-plan (2).png`
    - Folder: `Atlas/290 Assets/295 Attachments`
  - [ ] Keep in inbox
  - [ ] Ignore (send the move unchanged — if the name is still taken when you apply, the move fails and the attachment stays in the inbox)
  ```
- File comparison: **different file** for leipzig, goerlitz and freiberg; **"the same
  file already in the vault"** for radebeul. If radebeul says "different", the byte
  comparison is wrong. That is a finding.
- Every item proposes an atomic note into `Atlas/202 Notes/`. An item that comes back
  as anything else (skip, daily) files no note, so its attachment never reaches Pass 2's
  move logic. Record it, and fix the note text before you go on rather than reading a
  missing move as a pass.

### 1b. Owner edits, in the markdown only

Leave every per-item decision at its default. Change only the following:

| Scenario | Entry | Edit |
|---|---|---|
| **S1** folder only | `leipzig-plan.png` | Rename stays ticked. In the Rename backticks, replace **only the filename after the last `/`**: `leipzig-plan (2).png` → `leipzig-plan.png`. Change the Folder line's backtick content to `Atlas/296 Karten` (no trailing slash) |
| **S2** | (no entry) | nothing: the ambiguity is forced by the vault, not by an edit |
| **S3** refused folder | `goerlitz-altstadt.png` | Rename stays ticked, name untouched (`goerlitz-altstadt (2).png`). Change the Folder line to `100 Inbox/Karten` |
| **S4** Ignore | `radebeul-weinberg.jpg` | **Untick** Rename, **tick** Ignore. Exactly one box ticked. Leave the Folder line alone |
| **E1** occupied | `freiberg-dom.png` | Rename stays ticked. In the Rename backticks, replace the filename `freiberg-dom (2).png` → `freiberg-dom.png`. Leave the Folder line alone |

Why each edit is shaped this way:

- **S1** types the original basename back. A folder change alone is a valid rename
  (F1-AC10). Keeping the printed prefix `Atlas/290 Assets/295 Attachments/` in the Rename
  line is safe: the parser strips Tomo's own printed folder on an exact prefix match.
  **Do not type the new folder into the Rename line.** That is still refused as a path
  separator (F1-AC8), and it is not this scenario.
- **S1** also proves F4-AC2. After the run, `leipzig-plan.png` still exists twice (the
  occupier stays in `295 Attachments`), so the embed must carry the path.
- **S3** uses `inside_inbox`, the most natural mistake. `../Karten` (`escapes_vault`) is
  an equally valid choice if you prefer, but the expected line below is only for
  `100 Inbox/Karten`.
- **E1** is a name the owner typed onto a file that already exists. Before 039 that
  reached Hashi unchecked and failed at apply (PRD Problem 3).

Tick `- [x] Approved`. Save. Do not touch the `.json`.

### 1c. Pass 2

```
/inbox --pass2 --force
```

### 1d. Pass 2 evidence: before applying anything

**The parser read the markdown.** In `tomo-tmp/parsed-suggestions.json` →
`attachment_conflict_remedies[]`:

| source | remedy | proposed_name | name_is_owner_supplied | proposed_dir | dir_is_owner_supplied |
|---|---|---|---|---|---|
| `100 Inbox/Scans/leipzig-plan.png` | `rename` | `leipzig-plan.png` | `true` | `Atlas/296 Karten` | `true` |
| `100 Inbox/Scans/goerlitz-altstadt.png` | `rename` | `goerlitz-altstadt (2).png` | `false` | `100 Inbox/Karten` | `true` |
| `100 Inbox/Fotos/radebeul-weinberg.jpg` | `ignore` | (computed name, irrelevant) | `false` | `Atlas/290 Assets/295 Attachments` | `false` |
| `100 Inbox/Scans/freiberg-dom.png` | `rename` | `freiberg-dom.png` | `true` | `Atlas/290 Assets/295 Attachments` | `false` |

The wire must count as unchanged (markdown path). If Pass 2's output says
`edited wire is authoritative`, something wrote the JSON. Stop and find out what.

**`instructions.json`, actions:**

| Scenario | Expected |
|---|---|
| S1 | `move_asset` `100 Inbox/Scans/leipzig-plan.png` → `Atlas/296 Karten/leipzig-plan.png`. `move_note` for Leipzig's atomic. `delete_source` for `100 Inbox/Leipzig.md` whose `depends_on` holds **both** the `move_note` id **and** the `move_asset` id (F6-AC1) |
| S2 | `move_asset` `100 Inbox/Bilder/pirna-markt.jpg` → `Atlas/290 Assets/295 Attachments/pirna-markt.jpg` (original name, default folder). `delete_source` for `Pirna.md` depends on the note move **and** this asset move |
| S3 | **no** `move_asset` for goerlitz, **no** `move_note` and **no** `delete_source` for `Goerlitz.md`: the note is held (F2-AC4). No move to the default folder either (F2-AC6) |
| S4 | `move_asset` `100 Inbox/Fotos/radebeul-weinberg.jpg` → `Atlas/290 Assets/295 Attachments/radebeul-weinberg.jpg`, sent **unchanged** to the occupied destination (F3-AC4). `delete_source` for `Radebeul.md` with the asset id in `depends_on` |
| E1 | **no** `move_asset` for freiberg, **no** `move_note` and **no** `delete_source` for `Freiberg.md` (F3-AC1) |

`tomo.skipped_assets[]` has exactly **two** entries:
- `kind: "typed_folder_refused"`, `source: "100 Inbox/Scans/goerlitz-altstadt.png"`,
  `destination: null`
- `kind: "vault_occupied"`, `source: "100 Inbox/Scans/freiberg-dom.png"`,
  `destination: "Atlas/290 Assets/295 Attachments/freiberg-dom.png"`

**Rendered atomics (the filed notes' bodies, in `tomo-tmp/rendered/` or the inbox
copies awaiting their move):**

| Scenario | Embed in the filed note |
|---|---|
| S1 | `![[Atlas/296 Karten/leipzig-plan.png]]`: qualified, because the occupier still holds `leipzig-plan.png` (F4-AC2, F1-AC10) |
| S2 | `![[Atlas/290 Assets/295 Attachments/pirna-markt.jpg]]`: qualified, original name in the default folder (F4-AC3). A bare `![[pirna-markt.jpg]]` here is either a census failure or the Kado key not seeing `Atlas/290 Assets/293 Excalidraw/` (A2/R3). Check which before you call it |
| S4 | `![[Atlas/290 Assets/295 Attachments/radebeul-weinberg.jpg]]`: qualified, naming the occupier's path (Rule 4). The files are identical, so this is the right picture even when the move fails |
| S3, E1 | no filed note. Nothing is rewritten for a withheld move (F4-AC8) |

**`instructions.md`: the exact lines (executed).**

S1's move block carries (F2-AC8, F4-AC2):

```
- **New folder:** `Atlas/296 Karten` does not exist yet and will be created on apply
- **Embed written with path:** notes that embed it link to `Atlas/296 Karten/leipzig-plan.png`, because another file has the same name
```

S2's move block carries:

```
- **Embed written with path:** notes that embed it link to `Atlas/290 Assets/295 Attachments/pirna-markt.jpg`, because another file has the same name
```

S4's move block carries the embed line, then the Ignore disclosure (F6-AC8; the
disclosure is a fixed string in `render_md.py`):

```
- **Embed written with path:** notes that embed it link to `Atlas/290 Assets/295 Attachments/radebeul-weinberg.jpg`, because another file has the same name
- ⚠️ **Destination was occupied:** Pass 1 found this name already taken and you chose Ignore, so the move is sent unchanged. If the move fails, the source note that embeds it is kept in the inbox rather than deleted. To resolve it instead, tick Rename or Keep in inbox in the suggestions document, then run `/inbox --pass2 --force`.
```

The sentence "filed either way" must appear **nowhere**. S4 must **not** show up as a
`⚠️ **Conflict remains:**` bullet under `## Skipped`. Since T5.4 an Ignore whose move is
emitted is reported once, at its move (037 C2 narrowing, CON-5).

Under "**Attachments still in the inbox**", exactly these two bullets, character for
character:

S3 (F2-AC5):

```
- ⚠️ **Attachment not filed:** `100 Inbox/Scans/goerlitz-altstadt.png` — typed folder refused: `100 Inbox/Karten` is the inbox folder or inside it, so the next run would read it as inbox material. To fix: correct the folder in the suggestions document and run `/inbox --pass2 --force` before you apply. If you have already applied, the attachment is still in the inbox, and so is every note that embeds it: run `/inbox --recover`. The re-run proposes the default folder for it. If that target is taken, the suggestions document offers the folder again; if it is free, the attachment is filed there.
```

E1 (F3-AC5: names the attachment, the target and what occupies it, in words for an
attachment, never "a note already exists"):

```
- ⚠️ **Attachment not filed:** `100 Inbox/Scans/freiberg-dom.png` — target occupied: the vault already holds a file at the target `Atlas/290 Assets/295 Attachments/freiberg-dom.png`, so the attachment is not filed over it. To fix: free that target in the vault, then run `/inbox --pass2 --force` before you apply. If you have already applied, the attachment is still in the inbox, and so is every note that embeds it: run `/inbox --recover`. If the target is still taken, the suggestions document offers the name again; if you freed it, the attachment is filed there.
```

No `⚠️ **Target not checked:**` line anywhere. Every target folder in this run is
either listed or absent.

Record, without asserting wording: whatever "Not filed" / Source Deletions bullets the
held notes `Goerlitz.md` and `Freiberg.md` get. They must carry the **same** remedy as the
two bullets above (one remedy per kind, T5.4), never a second, different one.

**The shell relay (T4.5 extended by T5.1).** `tomo-tmp/withheld-attachments.md` holds
exactly the two lines above, S3 then E1, byte-identical to the instruction document's
bullets. Its `run_id` sidecar matches this run. The Pass 2 shell report relays **each
line verbatim, one per withheld attachment, and no count**: no "2 attachments withheld",
no summary line standing in for them. The relay is produced by the model at runtime
(`synthesis-conductor.md` Step 4). This run is its only verification. Also record any
lines relayed from `tomo-tmp/withheld-deletes.md`.

**The cost entry (C1-AC1).** `tomo-instance/state/inbox-cost-history.jsonl` gains a
Pass 2 entry with `"action": "render"` and this run's `run_id`, carrying all four of
`folder_listing_calls`, `distinct_destination_folders`, `basename_searches` and
`basename_pages`. Expected:

- `basename_searches`: **3**, one per distinct filed basename (`leipzig-plan.png`,
  `pirna-markt.jpg`, `radebeul-weinberg.jpg`; all ASCII, so NFC equals NFD).
  Withheld sources are never searched. More than 3 is a finding against F3-AC7.
- `basename_pages`: 3 (one page each; no name here comes near the 500-hit page).
- `folder_listing_calls` / `distinct_destination_folders`: record both. Each distinct
  target folder (`295 Attachments`, `296 Karten`) is listed **at most once**, and the
  note folder shares the same lookup. The entry must not show a listing count above its
  distinct-folder count unless pagination explains it.
- The triage entry for the same run still reads `base_kado_calls: 2` (spec 034 T6.4
  baseline).

If the `render` entry is missing, check whether the conductor passed `--cost-history`.
The flag is in its prompt, but the model has to thread it. Look at the container
transcript (`tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance/`,
newest `*.jsonl` and its `subagents/`) for the actual `instruction-render.py`
invocation.

### 1e. Apply via Hashi, then read the vault

Before applying, record the vault state:

```bash
ls "$V/100 Inbox" "$V/100 Inbox/Scans" "$V/100 Inbox/Bilder" "$V/100 Inbox/Fotos"
ls -d "$V/Atlas/296 Karten" 2>&1     # No such file or directory
```

Apply the instruction set in Obsidian with Hashi (instruction-set picker, not the
Suggestions Editor). Then capture the Hashi run log (`100 Inbox/tomo-hashi-run-log_*.md`,
plus the dev-console `[hashi:exec]` lines if debug logging is on).

| Scenario | Expected after apply |
|---|---|
| S1 | `Atlas/296 Karten/` now exists (A3, created by Hashi). `Atlas/296 Karten/leipzig-plan.png` has the **inbox copy's** sha (the `flow-map.png` bytes), **not** the occupier's. The occupier `295 Attachments/leipzig-plan.png` is unchanged. `Leipzig.md` and `Scans/leipzig-plan.png` are gone from the inbox. The filed note's embed resolves in Obsidian to the file in `296 Karten` |
| S2 | `295 Attachments/pirna-markt.jpg` has the inbox copy's sha. The `293 Excalidraw` copy is untouched. The filed note shows the **Pirna** picture, not the other one: the A1 risk, observed and not merely argued |
| S3 | `Goerlitz.md` and `Scans/goerlitz-altstadt.png` still in the inbox. Nothing in `100 Inbox/Karten` (the folder was never created) and nothing new in `295 Attachments` |
| **S4 (F6-AC2)** | Hashi: the `move_asset` for radebeul **failed** (target exists), and the `delete_source` for `Radebeul.md` is **`skipped-dependency (needs I0x)`**, naming that move's id. **`100 Inbox/Radebeul.md` and `100 Inbox/Fotos/radebeul-weinberg.jpg` are both still in the inbox.** The note move itself applied, so a filed Radebeul atomic exists in `Atlas/202 Notes/` and its qualified embed shows the (identical) occupier |
| E1 | `Freiberg.md` and `Scans/freiberg-dom.png` still in the inbox. The occupier `295 Attachments/freiberg-dom.png` keeps the `MiYo.png` sha |

The rest of the run should report **zero failures** apart from S4's single, intended
`move_asset` failure. Any other failure is a finding.

```bash
shasum -a 256 "$V/Atlas/296 Karten/leipzig-plan.png" "$A/leipzig-plan.png" \
  "$A/pirna-markt.jpg" "$V/Atlas/290 Assets/293 Excalidraw/pirna-markt.jpg" \
  "$A/radebeul-weinberg.jpg" "$A/freiberg-dom.png" "$A/goerlitz-altstadt.png"
comm -13 "$SNAP/notes-before.txt" <(ls "$V/Atlas/202 Notes") | tee "$SNAP/notes-filed-cycle1.txt"
comm -13 "$SNAP/attachments-before.txt" <(ls "$V/Atlas/290 Assets/295 Attachments")
ls "$V/100 Inbox"
```

`notes-filed-cycle1.txt` should list three atomics: Leipzig's, Pirna's and Radebeul's.
Their titles come from the classifier, not the source names. Note any rendered atomic
lingering in `100 Inbox/` for the held notes (`Goerlitz`, `Freiberg`) or for Radebeul.
A lingering rendered note would be re-proposed as a fresh source in cycle 2, so it
explains noise there.

**Do not tidy anything before cycle 2.** S5 depends on the vault exactly as this apply
left it.

---

## Cycle 2: S5, `/inbox --recover` after apply (c2)

The held notes `Goerlitz.md` (folder refused) and `Freiberg.md` (target occupied) are
`captured`. Their attachments' targets are still taken: both occupiers are in
`295 Attachments`. That is precisely the after-apply state the T5.4 remedy line tells
the owner to repair with `/inbox --recover`.

```bash
bash scripts/reset-tomo-tmp.sh --pass1 --instance tomo-instance/tomo-tmp
```

```
/inbox --recover
```

`--recover` and not `--pass1 --force`. Measured 2026-10-10: the two-flag form depends
on the agent threading both flags, and once it did not. `--recover` reaches the same
fold through one flag.

**Expect a broader run than cycle 1.** `--recover` re-intakes **every** captured inbox
note: also `Dresden.md` (the 037 `karte.png` conflict reappears), `Bautzen.md`,
`Meissen.md`, `Laufrunde Elbufer.md`, and `Radebeul.md` (kept by S4). That is correct
behaviour, not noise. Do **not** approve this document, and do not run Pass 2: c2 is
Pass 1 only.

### Pass condition

- **Both held notes re-intaken.** The new suggestions document proposes an item for
  `Goerlitz.md` and for `Freiberg.md`.
- **Their conflicts are offered again (c2).** `## Attachment Conflicts` has an entry for
  `100 Inbox/Scans/goerlitz-altstadt.png` and one for
  `100 Inbox/Scans/freiberg-dom.png`. Each has Rename pre-ticked with a computed name
  (expected `goerlitz-altstadt (2).png` and `freiberg-dom (2).png`), and each has its
  `  - Folder: \`Atlas/290 Assets/295 Attachments\`` line. Goerlitz is offered the
  **default** folder again, not `100 Inbox/Karten`: "The re-run proposes the default
  folder for it." This is the promise the S3 remedy line made, now checked.
- **S4's repair path (bonus).** `Radebeul.md` is re-intaken too, with a conflict entry
  for `100 Inbox/Fotos/radebeul-weinberg.jpg` saying "the same file already in the
  vault". This is "a re-run can repair the item" from the PRD's error journey. It will
  also propose a second atomic for a note already filed in cycle 1. Record that, but it
  is not a c2 failure.
- The suggestions JSON is `schema_version: "4"`, with `proposed_dir: null` on every
  conflict, the 037 `karte.png` conflict included.
- The triage entry for this run is in `inbox-cost-history.jsonl` (`base_kado_calls: 2`).

---

## After the runs

- **Capture:** both suggestions documents (`.md` and `.json`), cycle 1's instruction set
  (`.md` and `.json`), `tomo-tmp/parsed-suggestions.json`,
  `tomo-tmp/withheld-attachments.md` (+ sidecar), `tomo-tmp/withheld-deletes.md` if
  present, the Pass 2 shell report as the owner saw it, the Hashi run log, and the last
  three lines of `tomo-instance/state/inbox-cost-history.jsonl`.
- **Cost log:** run `python3 scripts/tomo-session-stats.py --session-latest` and append
  an entry to `docs/evolution/inbox-cost-log.md`, with the agent/script versions from
  the Step 0 table.
- **Fill in the evidence table below**, then the Results section.

## Cleanup: test vault only

Only files this runbook created or the runs produced. Verify every path before
deleting. The atomic titles are not predictable, so the filed notes come from the
`comm` diff, never from a glob.

```bash
V="/Volumes/Moon/Coding/MiYo/temp/Privat-Test"; A="$V/Atlas/290 Assets/295 Attachments"; I="$V/100 Inbox"
SNAP="$HOME/.tomo-spec039-live"

# 1. Fixture notes and inbox attachments still in the inbox (some were moved or deleted by apply)
rm -f "$I/Leipzig.md" "$I/Pirna.md" "$I/Goerlitz.md" "$I/Radebeul.md" "$I/Freiberg.md"
rm -f "$I/Scans/leipzig-plan.png" "$I/Bilder/pirna-markt.jpg" "$I/Scans/goerlitz-altstadt.png" \
      "$I/Fotos/radebeul-weinberg.jpg" "$I/Scans/freiberg-dom.png"

# 2. Occupiers, the elsewhere copy, and what apply filed
rm -f "$A/leipzig-plan.png" "$A/goerlitz-altstadt.png" "$A/radebeul-weinberg.jpg" "$A/freiberg-dom.png" \
      "$A/pirna-markt.jpg" "$V/Atlas/290 Assets/293 Excalidraw/pirna-markt.jpg"
rm -f "$V/Atlas/296 Karten/leipzig-plan.png" && rmdir "$V/Atlas/296 Karten"

# 3. Filed atomics: review the list first, then delete exactly those
comm -13 "$SNAP/notes-before.txt" <(ls "$V/Atlas/202 Notes")
#   for each listed name: rm "$V/Atlas/202 Notes/<name>"

# 4. Anything else new in the attachments folder must now be empty
comm -13 "$SNAP/attachments-before.txt" <(ls "$A")       # expect no output

# 5. Run artefacts in the inbox (suggestions, instructions, run logs, lingering rendered atomics)
comm -13 "$SNAP/inbox-before.txt" <(ls "$I")             # review, then delete each listed file

# 6. Cycle 2 re-stamped the 037 fixture's Dresden.md: put it back
bash scripts/spec037-fixture.sh restore
bash scripts/spec037-fixture.sh status                    # "Vault matches the baseline." (diff Dresden.md before blaming an Updated: line)
```

`spec037-fixture.sh restore` also removes 037-pattern artefacts (`*_suggestions.*`,
`*_instructions.*`, `tomo-hashi-run-log_*`, `20??-??-??_*.md` in `100 Inbox/`, and new
`Atlas/202 Notes/*.md` not in its own baseline). Steps 3 and 5 overlap with it, and that
is fine. Do step 3 by hand anyway: it is the step that proves you know what was filed.

`Bautzen.md`, `Meissen.md` and `Laufrunde Elbufer.md` get a new `run_id` stamp from
cycle 2. That is frontmatter written through Kado, it is benign, and no fixture tracks
it. Do **not** backfill `Calendar/301 Daily/` (the gap after 2026-09-12 is deliberate).
Finally `rm -r "$HOME/.tomo-spec039-live"` once the evidence is recorded.

---

## Evidence table: fill in during the run

| # | Scenario | Criterion | Expected | Observed | Pass/Fail |
|---|---|---|---|---|---|
| 1 | all | F1-AC1 | wire `schema_version "4"`; every conflict `proposed_dir: null` | | |
| 2 | all | F1-AC2 | Folder line under each Rename line, `Atlas/290 Assets/295 Attachments` | | |
| 3 | S1 | F1-AC3 / F1-AC10 | parser: `proposed_dir "Atlas/296 Karten"`, owner-supplied; name `leipzig-plan.png` | | |
| 4 | S1 | F1-AC10 | `move_asset` → `Atlas/296 Karten/leipzig-plan.png` | | |
| 5 | S1 | F2-AC8 | "`Atlas/296 Karten` does not exist yet and will be created on apply" | | |
| 6 | S1 | F4-AC2 | embed `![[Atlas/296 Karten/leipzig-plan.png]]` + "Embed written with path" line | | |
| 7 | S1 | A3 / apply | folder created; file = inbox copy's sha; occupier unchanged | | |
| 8 | S2 | F4-AC3 | embed `![[Atlas/290 Assets/295 Attachments/pirna-markt.jpg]]` | | |
| 9 | S2 | A1 | filed note shows the Pirna image, not the `293 Excalidraw` one | | |
| 10 | S3 | F2-AC3 / F2-AC5 | `typed_folder_refused`; bullet text as executed above | | |
| 11 | S3 | F2-AC4 / F2-AC6 | no move, no default-folder fallback, `Goerlitz.md` held | | |
| 12 | S4 | F3-AC4 | `move_asset` sent unchanged to the occupied destination | | |
| 13 | S4 | F6-AC1 | `Radebeul.md` delete `depends_on` contains the asset move id | | |
| 14 | S4 | F6-AC8 | Ignore disclosure "kept in the inbox rather than deleted"; no "filed either way"; no "Conflict remains" | | |
| 15 | S4 | **F6-AC2** | apply: move failed; delete `skipped-dependency`; `Radebeul.md` + jpg still in inbox | | |
| 16 | S4 | F6-AC7 | Hashi 0.26.1 needed no change: cascade fired on an asset dependency | | |
| 17 | E1 | F3-AC1 | no move; `Freiberg.md` held | | |
| 18 | E1 | F3-AC5 | `vault_occupied` bullet text as executed above | | |
| 19 | S1, S2 | F6-AC1 | Leipzig/Pirna deletes depend on note move **and** asset move; both applied | | |
| 20 | all | F4-AC8 | no embed rewritten for goerlitz/freiberg | | |
| 21 | all | relay (T4.5/T5.1) | `withheld-attachments.md` = the two bullets, byte-identical; shell relays one per item, no count | | |
| 22 | all | F3-AC6 | **not reproduced**: no "Target not checked" line expected or seen | | n/a |
| 23 | all | C1-AC1 | `render` entry with `folder_listing_calls`, `distinct_destination_folders`, `basename_searches` (3), `basename_pages` | | |
| 24 | all | F3-AC7 | each target folder listed at most once; searches ≤ distinct filed basenames | | |
| 25 | all | base cost | triage `base_kado_calls: 2` both cycles | | |
| 26 | S5 | c2 | `Goerlitz.md` and `Freiberg.md` re-intaken by `/inbox --recover` | | |
| 27 | S5 | c2 | both conflicts offered again with computed name + default Folder line | | |
| 28 | S5 | bonus | `Radebeul.md` re-intaken with its conflict ("same file") | | |

## Results

_To be filled in after the run: one subsection per cycle, measured from the artefacts,
in the form of 038's Results._

---

## Optional probes (not owed by T6.3)

- **F3-AC6 live.** Needs a folder whose Kado listing errors with something other than
  `Path not found`, for example a folder the Tomo Kado key is denied. It is **unknown**
  whether Kado answers a denied `listDir` with an error (→ "not checked") or with an
  empty listing (→ "will be created"). If it is the latter, that is a finding against
  Rule 5 in its own right. Doing this means changing the Kado key's permissions. Do it
  only deliberately, in a separate run, and restore the key afterwards.
- **F3-AC2 live.** Between 1c and 1e, copy any file to the default destination of a
  conflict-free attachment (e.g. a `pirna-markt.jpg` into `295 Attachments`), then re-run
  `/inbox --pass2 --force`. Expected: S2 becomes `vault_occupied` and `Pirna.md` is held.
  It costs one more Pass 2, so it is not in the plan.

## Read the output as the owner, not as the author

Spec 037's four defective sentences, and two of 038's documentation defects, were caught
by the owner reading shipped output rather than by review. Read the remedy lines in
particular for whether they can be followed in the order they are written: the S3 line
says to re-run `/inbox --recover` after applying, and cycle 2 is where that promise is
either kept or not.
