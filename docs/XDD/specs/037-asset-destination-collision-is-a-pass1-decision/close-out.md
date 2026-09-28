---
title: "Close-out — 037 an occupied asset destination is a Pass-1 decision"
status: in_progress
---

# Close-out

> **In progress.** Written incrementally as each Phase 4 task lands, not
> retrospectively — because the evidence this document exists to record is
> measured at the moment a task runs and is expensive to reconstruct afterwards.
> Spec 036's close-out was written at the end and its author had to re-run
> checks that had already passed once.

## Standing rule for this document

Every PRD criterion below traces to a test that was **executed**, named by node
id, not to a task that mentions it. That distinction is not pedantry here: spec
037 produced **six named mutations that could not bite** — tests that named a
fault they were structurally incapable of detecting, every one of them passing
happily. In this spec, *"a test exists"* is a materially weaker claim than
usual, so each row says what was run and what turned red.

The check this rule exists for: PRD **S2-AC1** was claimed by T2.4, a parser
task that structurally cannot render anything, was satisfied in T2.2, and was
asserted by **no test at all**. It surfaced only because a plausible-looking
Success line got questioned.

---

## Environment-dependent evidence — recorded here because it is not pinned by a test

These checks cannot live in the suite: they depend on a sibling repo being
checked out and on its `node_modules` being installed, so a hermetic test that
required them would fail anywhere else. They are recorded, with their output,
at the moment they were run.

### T4.1 (a) — the wire schema was not edited

Measured 2026-09-27 on `5ed05c6`:

```
git diff main...HEAD -- tomo/schemas/
→ only suggestions-doc.schema.json
```

`tomo/schemas/hashi-instructions.schema.json` has zero diff lines on this
branch. **This confirms no edit was made. It is not proof of ADR-5** — the file
is untouched by construction, so the check would pass whether or not the design
held. Independently re-derived by the T4.1 compliance review.

### T4.1 (b) — our copy matches the consumer's working tree

Measured 2026-09-27:

```
diff tomo/schemas/hashi-instructions.schema.json \
     /Volumes/Moon/Coding/MiYo/Hashi/src/schema/instructions.schema.json
→ no output, exit 0
```

Byte-identical. **This is the one genuinely new check in T4.1**: the existing
parity tests compare producer to mirror offline and fetch upstream over the
network, but never the sibling working tree. Independently re-derived by the
T4.1 compliance review.

### T4.1 (c) — the consumer's own compiled validator accepts a three-remedy set

Measured 2026-09-27, read-only, from `cd /Volumes/Moon/Coding/MiYo/Hashi`
against their installed `node_modules`, writing nothing under `Hashi/`:

```
node --input-type=module -e "
import Ajv2020 from 'ajv/dist/2020.js';
import fs from 'node:fs';
const schema = JSON.parse(fs.readFileSync('src/schema/instructions.schema.json','utf8'));
const instance = JSON.parse(fs.readFileSync('<rendered three-remedy set>','utf8'));
const ajv = new Ajv2020({allErrors:true, strict:false});
console.log('valid:', ajv.compile(schema)(instance));
"
→ valid: true
```

The instruction set was rendered through production `_build_move_asset_actions`
— a `rename` (`karte.png` → `karte (2).png`), an `ignore` (`foto.jpg`), and a
`keep_in_inbox` (`plan.pdf`). `cd Hashi && git status --porcelain` was empty
afterwards.

**What this does and does not prove.** It adds no coverage beyond T4.1's pytest
assertion — it can only fail on the same stray-key mutation. Its value is proof
**by execution against the consumer's real compiled validator**, where every
other schema check in this repo uses Python `jsonschema` against our own copy.
Recorded once, here, because nothing in the suite can hold it.

### Why ADR-5 held — and why that was design, not luck

`skipped_assets`, the field carrying spec 037's new `kind:
vault_collision_held`, is not a named property in the instruction schema. It
sits under `properties.tomo`, which deliberately carries **no**
`additionalProperties: false` (`hashi-instructions.schema.json:35` — *"kept
permissive so Tomo can evolve the block without a coordinated round-trip"*), and
`tests/test_wire_snapshot_parity.py`'s `SANCTIONED_ASYMMETRIES` excludes
`/properties/tomo` by name.

The two remedies that touch the **strict** part of the schema — `rename` and
`ignore` — cross it by falling through to the *existing, unmodified* `move_asset`
shape. They change which `destination` string goes in; they never change the
dict. The one remedy needing genuinely new data was routed to the one block left
unlocked.

So ADR-5 could be written as "no wire field" **because** the permissive seam was
already there. T4.1's mutation is the counterfactual, executed: append any stray
key to the `move_asset` dict (`render_actions.py:839-844`) and the consumer's
`additionalProperties: false` (`:105-116`) rejects the set. That is what
"anywhere else" would have cost.

---

### T4.3 — the 2026-09-15 case, reproduced and resolved live

Run 2026-09-28, instance `tomo-instance`, vault `temp/Privat-Test`.
Metadata only — no vault content is recorded here (Constitution L2, and this
repo is public).

**The fixture had to be repaired first, and that is itself a finding.** The
first attempt produced no `attachment_conflicts` at all. Not a code defect:
`Dresden.md` scored `worthiness: 0.2, suppressed: true`, and
`detect_attachment_conflicts` deliberately skips suppressed items
(`suggestions-reducer.py:596-600`) because a sub-worthy atomic stays in the
inbox and its attachments claim no destination. The cause was the note body —
*"Erwartung: als `ambiguous` gemeldet, keine Aktion"* — which the runbook had
called "stale ... harmless". It was the thing producing the 20% score. Body
rewritten, baseline retaken; see `live-runbook.md`.

**Pass 1** (`/inbox --pass1 --force`, run `2026-09-28T10-55-48Z-9f0c4d`):

| Check | Measured |
|---|---|
| `attachment_conflicts` entries | exactly 1, source `100 Inbox/Scans/karte.png` |
| `same_file` | `false` — the byte comparison distinguished the two 69-byte PNGs |
| `proposed_name` | `karte (2).png` — a basename |
| Rename pre-ticked | yes |
| `owner_source_items` | `100 Inbox/Dresden.md`, rendered `[[Dresden]]` |
| `base_kado_calls` | **2** — the spec 034 T6.4 baseline, unchanged |
| `folder_listing_calls` | 1 → 2, a rise of exactly one |

**The parser join, verified on live data rather than reasoned about.** The
rendered remedy line displays a full path (`Atlas/290 Assets/295
Attachments/karte (2).png`) while `proposed_name` must remain a basename. A
read-only dry run of `suggestion-parser.py` against the vault document returned
`{"source": "100 Inbox/Scans/karte.png", "remedy": "rename", "proposed_name":
"karte (2).png"}` — a basename. The full path in the markdown cannot leak into
the field, because `_join_attachment_conflict_remedies` joins on `source`
against the structured doc and never reads the rendered text. Worth pinning:
the vault-side `*_suggestions.json` is the **wire**, whose `attachment_conflicts`
is `null`; the join resolves to `tomo-tmp/suggestions-doc.json` through
`_default_doc_path`'s fallback, since no sibling `suggestions-doc.json` exists
next to the markdown.

**Pass 2** (`2026-09-28_1106_instructions.json`): `I03 move_asset`, source
`100 Inbox/Scans/karte.png`, destination `Atlas/290 Assets/295 Attachments/karte
(2).png`. The dict carried `{id, action, source, destination}` and no internal
fields. The rendered note's embed was rewritten from the path-prefixed
`![[100 Inbox/Scans/karte.png]]` to the bare basename `![[karte (2).png]]` —
T3.3's path-prefix branch, exercised live. No `⚠️` entry was rendered for this
attachment, correctly: it was resolved, not withheld.

**Hashi apply — 10 of 10 actions applied, `error: None` on every one.**

| Path | sha256 (12) | Verdict |
|---|---|---|
| `Atlas/290 Assets/295 Attachments/karte (2).png` | `fa86a6e447ff` | the inbox file, filed under the new name |
| `Atlas/290 Assets/295 Attachments/karte.png` | `0fb588dae23c` | pre-existing vault file, **untouched** |
| `100 Inbox/Scans/karte.png` | absent | inbox drained |
| `100 Inbox/Dresden.md` | absent | source consumed |

The filed note embeds `![[karte (2).png]]`, which resolves to the renamed asset
and does **not** reach back into the inbox. **Zero `move_asset` failures** — the
row that was red on 2026-09-15 is green, end to end, through the same vault
shape that produced the original defect.

**Carried into T4.4.** `I05 delete_source` for `Dresden.md` declares
`depends_on: ["I01"]` — the note move — and **not** `I03`, the asset move. Under
the `rename` remedy this is immaterial, since the move succeeds. Under `ignore`,
where the move is expected to fail, the source deletion is not gated on it. To
be measured in T4.4 step 4 rather than asserted here.

---

## PRD criteria — filled in as Phase 4 completes

_(F1, F2, F3, S1, S2, C1, C2 traced by node id once T4.2-T4.4 land.)_
