---
title: "Close-out — 037 an occupied asset destination is a Pass-1 decision"
status: complete
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

> **What this evidence is and is not** (added 2026-09-29 after Hashi's reply).
> The validator is theirs; the machine, the generated set and the run were ours.
> That makes it a real check and **not** something the consumer can verify — we
> sent the claim without the artifact. Hashi said so plainly: *"your validator
> claim rests on your run, not our check."* Fair. Attach the instruction set to
> the handoff next time, the way the 2026-09-18 schema pair was attached.

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

### T4.4 (a) — keep-in-inbox

Run 2026-09-28. Metadata only.

**Behaviour, first attempt:** Pass 1 raised the conflict again
(`worthiness: 0.7`, not suppressed — the repaired fixture is stable across
runs), `base_kado_calls` **2**, `folder_listing_calls` 1 → 2. A read-only dry
run of the parser against the ticked document returned `remedy:
"keep_in_inbox"` — worth recording because the owner's checkbox plugin appends
`✅ 2026-09-28` to a ticked line, and the label match survived it. Pass 2
emitted **zero `move_asset` actions**.

**Then the rendered text was read, and four defects were in it** — in shipped
output, with the suite green. They are described in
`docs/tomo/scripts/lib/render_md.md` and fixed in `b82f70d`; in short: the
section heading claimed *"the owner chose otherwise"*, which is the exact claim
T4.2 made the bullet passive to avoid and which is false for a degraded rename;
every remedy opened a sentence in lower case after a full stop; the skipped path
rendered twice on one line in two quoting styles, in all three skip kinds; and
the block heading was the bullet's own label verbatim.

None of these removes an expected substring, which is why every existing
assertion stayed true. `tests/test_037_t4_4_rendered_text.py` pins them with
five mutations, each **measured** on 2026-09-28: every one turns red exactly the
test that names it, and only that test.

**Re-run after the fix**, instance at `render_md` 0.25.0 / `render_actions`
0.26.7. The live document matched the offline preview exactly, and a sweep of
the whole instruction document found no lowercase sentence start, no repr-quoted
path, and no path named twice in a bullet.

**Hashi apply — 5 of 5 actions applied, `failed: 0`.**

| Path | sha256 (12) | Verdict |
|---|---|---|
| `100 Inbox/Scans/karte.png` | `fa86a6e447ff` | held in the inbox, as instructed |
| `Atlas/290 Assets/295 Attachments/karte.png` | `0fb588dae23c` | untouched |
| `100 Inbox/Dresden.md` | absent | source consumed — the note WAS filed |

The note being filed while its attachment stays put is the owner's ruling of
2026-09-27 (requirements.md:374-382): keep-in-inbox names the attachment, not
the note.

**The consequence of that ruling, measured rather than assumed.** The filed note
embeds `![[100 Inbox/Scans/karte.png]]` — unrewritten, because keep-in-inbox
triggers no rename and therefore no embed rewrite. The reference resolves, since
the file is still there. This is the same *shape* as the 2026-09-15 damage — an
Atlas note reaching back into the inbox — and it is not the same defect: on
2026-09-15 nobody chose it, a move was emitted and refused, and the document
reported nothing. Here the owner chose it, and both blocks of the instruction
document say so in their own words. Recorded because the shape alone will look
like a regression to anyone who meets it without this note.

---

### T4.4 (b) — ignore, the run that was supposed to fail

Run 2026-09-29. Metadata only.

**It failed, exactly once, in the same words as 2026-09-15.** Hashi's run log:

| Action | Result |
|---|---|
| `I02` `move_asset` `100 Inbox/Scans/karte.png` → `Atlas/290 Assets/295 Attachments/karte.png` | **failed** — `Inconsistent state — both source and destination present` |

`applied: 6, failed: 1`. The refusal text is **verbatim** the one the
2026-09-15 incident recorded. **ADR-5 is therefore proven rather than
assumed**: Tomo emits no wire field and relies on Hashi's own final check, and
that check exists, fires, and reads identically a fortnight later.

| Check | Measured |
|---|---|
| Failures | exactly 1, naming the attachment move |
| `Atlas/290 Assets/295 Attachments/karte.png` | `0fb588dae23c` — untouched by the refused move |
| `100 Inbox/Scans/karte.png` | `fa86a6e447ff` — still in the inbox |
| Summary blocks | "Conflict remains" only; "Attachment not filed" correctly absent, since `ignore` never reaches `skipped_assets` |
| Action annotation | rendered on `I02` itself, different sentence from the summary bullet |

**Three rendered-text corrections were made between the keep-in-inbox run and
this one**, two of them caught by the owner reading shipped output: the Pass-1
`Ignore` label and the Pass-2 bullet both promised an outcome nothing re-checks
("will fail", "will be refused"); the new action annotation named its steps in
an order nobody can follow ("Re-run `/inbox` and pick ..." — the remedy is
ticked in the suggestions document *first*); and the held remedy named only the
route for after applying. All four are described in
`docs/tomo/scripts/lib/render_md.md` with measured mutations.

### The open finding this run produced: a delete that outlives a refused move

`I03 delete_source` applied although `I02` failed. `Dresden.md` is gone,
`karte.png` sits in the inbox with no note referencing it, and the filed Atlas
note embeds `![[100 Inbox/Scans/karte.png]]` — reaching backwards into the
inbox. **That is the end state of 2026-09-15, reproduced.**

Two mechanisms, both working as written:

1. `delete_source` declares `depends_on: ["I01"]` — the note move. Spec 036's
   contract covers four delete sources (checked "Delete source", daily-only,
   move_note origins, tag-handler groups) and an attachment move is none of
   them. By 036's own logic the delete IS justified: the note's content was
   captured by the atomic.
2. ADR-6's residue rule (`render_actions.py:1410`) cannot fire here at all —
   not because `ignore` was excluded, but because it keys on `skipped_assets`
   and an `ignore`d conflict never produces an entry there. The exclusion that
   IS explicit covers `vault_collision_held`, per the owner's 2026-09-27
   ruling.

So for all three remedies the note is filed and its source deleted. Under
`rename` that is correct and complete. Under the other two the filed note points
back into the inbox — a reference that still resolves, because the file is
genuinely still there, but that no longer has an owning note in the inbox to
bring it forward.

**What the document does not say.** It states that the move goes out unchanged
and will be refused unless the name was freed. It does not state that the note
is filed and its source note deleted regardless. An owner ticking `ignore` is
told what happens to the attachment and not what happens to the note.

Recorded as a finding, not fixed in flight: closing it means either widening
ADR-6 to a case that produces no `skipped_assets` entry, or adding a sentence to
the disclosure, and the first is a design change to a rule the owner ruled on
two days earlier.

---

## PRD criteria — every one traced to a test that was RUN

All 22 acceptance criteria in F1-F3, S1-S2, C1-C2. The node ids below were
**executed together on 2026-09-29** — one `pytest` invocation naming exactly
these tests, `30 passed` — not collected, not inferred from a task that mentions
the criterion. That distinction is the point of this table: spec 037 produced
**nine tests whose named mutation could not bite**, so "a test exists" is a
materially weaker claim here than usual.

Test ids are given without the `tests/test_037_` prefix.

### F1 — Tomo learns whether the destination is already taken

| Criterion | Executed test |
|---|---|
| Free destination → no conflict, run unchanged | `t1_2_attachment_vault_collision.py::test_a_free_destination_leaves_the_emitted_document_unchanged` |
| Occupied → conflict names incoming file and destination | `t1_2_attachment_vault_collision.py::test_an_occupied_destination_names_source_destination_and_owner` |
| Vault consulted once per folder, not per attachment | `t1_1_folder_cache_serves_attachments.py::test_a_folder_primed_by_notes_serves_the_attachment_caller_from_one_listing` + `::test_the_attachment_caller_first_also_serves_the_note_caller_from_one_listing` |
| Case-differing name counts as occupied (CON-6) | `t1_1_folder_cache_serves_attachments.py::test_a_name_differing_only_in_case_is_found` + `t1_2_attachment_vault_collision.py::test_unit_dedup_by_destination_case_folded` |
| Vault unreachable → check degrades, does not block | `t1_2_attachment_vault_collision.py::test_no_kado_client_produces_no_conflicts_and_no_error` + `::test_a_listing_that_raises_produces_no_conflicts_and_no_error` |

### F2 — The conflict is a decision, with rename as the default

| Criterion | Executed test |
|---|---|
| Entry names file, occupied destination, every embedding note | `t2_2_render_conflicts.py::test_owner_link_matches_same_notes_own_section_link` |
| Exactly three remedies, rename ticked | `t2_2_render_conflicts.py::test_exactly_three_remedies_with_rename_ticked` |
| Several owners → one entry, one tick settles all | `t2_2_render_conflicts.py::test_one_block_per_conflict_not_per_owner` + `t1_5_one_entry_one_file.py::test_one_attachment_three_owners_still_one_entry` |
| No conflicts → no section at all | `t2_2_render_conflicts.py::test_one_conflict_renders_section_zero_conflicts_render_nothing` |
| Rename unticked, nothing else ticked → read back as `ignore` | `t2_4_parse_remedy.py::test_rename_cleared_nothing_else_ticked_yields_ignore` |

### F3 — Pass 2 honours the chosen remedy

| Criterion | Executed test |
|---|---|
| Rename → move to a free name, every owning embed names it | `t3_1_remedy_outcomes.py::test_rename_emits_move_to_the_proposed_basename` + `t3_3_embed_rewrite.py::test_end_to_end_written_file_agrees_with_the_emitted_move_asset` |
| Keep-in-inbox → no move, nothing fails at apply | `t3_1_remedy_outcomes.py::test_keep_in_inbox_emits_no_move_and_records_vault_collision_held` |
| Ignore → move emitted unchanged, **so Hashi refuses and reports it** | `t3_1_remedy_outcomes.py::test_ignore_emits_the_move_unchanged_and_skips_nothing` — **first half only**; see below |
| No action overwrites the occupying file | `t3_1_remedy_outcomes.py::test_a_remedys_destination_still_goes_through_the_claimed_check` + `t2_1_proposed_name.py::test_an_occupied_proposal_advances` |
| Coverage audit agrees on a run containing conflicts | `t3_2_audit_needs_no_new_arithmetic.py::test_mixing_every_remedy_in_one_run_passes_the_audit` |

**The one criterion no Tomo test can close.** F3's ignore criterion is two
claims joined by *so*: Tomo emits the move unchanged, **and Hashi refuses it**.
The first is ours and is tested. The second is the consumer's behaviour and is
structurally outside this repo — the same shape as spec 036's two consumer-owned
criteria, which that close-out left OPEN pending Hashi's reply.

This one is **not** left open, because it was measured end to end in T4.4's live
run on 2026-09-29: Hashi refused with `Inconsistent state — both source and
destination present`, **verbatim the 2026-09-15 text**, exactly one failure in a
seven-action set. That is stronger evidence than a Tomo-side test could ever
be — a test would assert our belief about Hashi, while the run observed Hashi.

### S1 — The document says whether it is the same file

| Criterion | Executed test |
|---|---|
| Byte-identical → says so, warns of a second copy | `t2_3_same_file_wording.py::test_same_file_true_renders_second_copy_warning` + `t1_3_same_file.py::test_byte_identical_files_set_same_file_true` |
| Differs → says a different file holds the name | `t2_3_same_file_wording.py::test_same_file_false_renders_different_file_statement` |
| Cannot compare → says so, remedies unchanged | `t2_3_same_file_wording.py::test_same_file_null_renders_could_not_compare` + `::test_remedies_unchanged_from_t2_2_baseline` |

### S2 — An unresolved conflict is called out

| Criterion | Executed test |
|---|---|
| Rename not ticked → entry states the conflict remains and what follows | `t4_2_unresolved_summary.py::test_unresolved_report_names_the_two_non_rename_sources_verbatim` + `::test_degraded_rename_is_reported_despite_its_remedy_field_saying_rename` |

The second test is the load-bearing one. A degraded rename's own `remedy` field
still reads `"rename"`, so filtering on `remedy != "rename"` drops it — which is
why this report is built from two source lists rather than one filter.

### C1 / C2 — Could-have features, both shipped

| Criterion | Executed test |
|---|---|
| C1 — the rename remedy names the destination it would use | `t2_2_render_conflicts.py::test_rename_remedy_names_fully_composed_destination` |
| C1 — an occupied proposal advances to the next free variant | `t2_1_proposed_name.py::test_an_occupied_proposal_advances` |
| C2 — the summary names each unresolved conflict rather than counting | `t4_2_unresolved_summary.py::test_no_sentence_counts_the_conflicts` |

---

## What this spec cost, and what it is worth recording

**Nine tests named a mutation they could not detect.** Every one passed happily;
every one was found by running the mutation it named rather than by reading it.
The ninth was found in this phase, in a test written *for* this phase's own
lesson. A which-test-catches-what claim is measurable, and in this spec it was
wrong often enough that measuring it is no longer optional.

**Presence-only assertions hid two defects a fixture already rendered.** T4.2's
duplication defect and T4.4's duplicated path both sat in output an existing
test was rendering. Every assertion checked that expected strings were present;
none counted. Count assertions found both.

**Four owner-facing sentences asserted more than the renderer knows**, two of
them caught by the owner reading shipped output rather than by review:
"the owner chose otherwise" (false for a degraded rename), "will fail" and "it
will be refused" (nothing re-checks the destination between Pass 1 and the
apply), and an instruction whose steps could not be followed in the order given.
Sweeping every instructional line of a rendered document offline — one
`render_instructions_md` call — found the fifth before it shipped.

**The live runs found what no test did.** The first T4.3 attempt produced no
conflict at all: the fixture note's own body asked the classifier not to act,
and the runbook had called that text "harmless". Three of this spec's findings —
the force-atomic gap, the ignore disclosure, and the delete that outlives a
refused move — came from running it against a real vault.

## Open, recorded rather than closed

- **Force Atomic Note bypasses conflict detection** (`docs/XDD/backlog.md`).
  Detection skips suppressed items by design; the tick un-suppresses one in
  Pass 2, after detection has run. Traced in code, not yet measured.
- **A delete outlives a refused attachment move.** T4.4's ignore run filed the
  note and deleted its source while the move failed. Both mechanisms behave as
  written; the disclosure was the gap, and it was closed in `render_md` 0.30.0.
- **The embed rewrite cannot disambiguate a shared basename**
  (`docs/XDD/backlog.md`), accepted at T3.3.
- **For byte-identical files, the pre-ticked Rename creates a second copy.** The
  comparison sentence warns; the default does not. Documented for the owner in
  `docs/usage.md`; whether the pre-tick should differ for that case is a design
  question this spec did not open.
