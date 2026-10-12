---
title: "Attachment conflict hardening"
status: draft
version: "1.0"
---

# Solution Design Document

> **One decision per attachment, made once.** Today Pass 2 decides an
> attachment's fate in two places that do not talk to each other: the embed
> rewrite inside the render loop, and the move builder after it. That split is
> why a refused name was checked twice (`backlog.md:1917`) and why a withheld
> move still rewrites its note (`backlog.md:1956`). This spec adds three more
> inputs to that decision — a folder, the vault's occupancy, and the vault's
> basename count — and adding them to both sites would make three copies of one
> rule. ADR-1 therefore moves the whole decision in front of the render loop and
> turns both sites into readers of it.

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] Every PRD requirement maps to exactly one owning component
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Every architecture decision is recorded as an ADR and confirmed by the owner
- [x] No component owns another's domain logic
- [x] Runtime view traces both Pass-2 paths, not only the markdown one

### QUALITY CHECKS (Should Pass)

- [x] Existing patterns reused rather than new ones introduced
- [x] Fail direction stated for every new check
- [x] Cost of every new vault interaction accounted for
- [x] The consumer's side of each interface named, with what they must change
- [x] Acceptance criteria traceable 1:1 to the PRD's
- [x] Checked against the MiYo Constitution (no repo-level `Constitution.md`; L1 Privacy — no new data leaves the machine, Kado is the only surface; L1 Testing — CON-5; L2 Architecture — CON-2 is a live pre-implementation obligation)

---

## Output Schema

### SDD Status Report

| Field | Value |
|-------|-------|
| specId | 039-attachment-conflict-hardening |
| status | `COMPLETE` |
| adrsConfirmed | 10 of 10 |
| componentsAdded | 3 (attachment plan, shared folder lookup, basename census) |
| componentsModified | 11 |
| wireVersionMove | suggestions wire `3` → `4`; instructions wire unchanged in shape, `depends_on` values and description widened |

### ArchitectureSummary

| Aspect | Decision |
|--------|----------|
| Where an attachment's fate is decided | Once, in an attachment plan built before the render loop; the embed rewrite and the move builder read it |
| Vault occupancy in Pass 2 | One shared, raw-cached folder lookup for notes and assets; a missing folder and an unanswered folder are distinct states |
| Basename uniqueness | Kado `byName`, once per distinct final basename, exact case-folded match, adjusted to the vault after the run |
| Folder input | Its own markdown line; `proposed_dir` on the wire; refused by a closed set of reasons, never repaired |
| #185 | One new name refusal reason, `breaks_link` |
| #186 | The origin's delete names the `move_asset` ids of its attachments |
| A withheld target | New `skipped_assets` kinds; the existing suppression pass holds the owning notes |
| Embed form | Bare unless ambiguous or unanswered; then the full vault path with extension and the owner's suffix |

### SectionStatus

| Section | Status |
|---------|--------|
| Constraints | `Complete` |
| Implementation Context | `Complete` |
| Solution Strategy | `Complete` |
| Building Block View | `Complete` |
| Runtime View | `Complete` |
| Cross-Cutting Concepts | `Complete` |
| Architecture Decisions | `Complete` — 10 ADRs, all confirmed |
| Acceptance Criteria | `Complete` |
| Risks and Technical Debt | `Complete` |

### ADRStatus

| ADR | Name | Confirmed |
|-----|------|-----------|
| ADR-1 | One attachment plan, decided before the render loop | ✅ owner 2026-10-12 |
| ADR-2 | One raw-cached folder lookup shared by Pass 1 and Pass 2 | ✅ owner 2026-10-12 |
| ADR-3 | Basename uniqueness through `byName`, adjusted to the vault after the run | ✅ owner 2026-10-12 |
| ADR-4 | The folder gets its own markdown line; null means Pass 2's configured asset folder | ✅ owner 2026-10-12 |
| ADR-5 | A typed folder is checked by a closed set of reasons in `typed_name_check` | ✅ owner 2026-10-12 |
| ADR-6 | #185 is one reason, `breaks_link`; the renderer stops defaulting to "blank" | ✅ owner 2026-10-12 |
| ADR-7 | A withheld target is a new `skipped_assets` kind; `ignore` is exempt | ✅ owner 2026-10-12 |
| ADR-8 | An unanswered check emits the move and reports it as unchecked | ✅ owner 2026-10-12 |
| ADR-9 | The embed rewrite covers every filed attachment and matches by path | ✅ owner 2026-10-12 |
| ADR-10 | #186: the origin's delete depends on the plan's `move_asset` ids | ✅ owner 2026-10-12 |

---

## Constraints

- **CON-1** — Coordinated release (PRD CON-1). The live suggestions schema and
  its shape manifest move to `"4"`; the vendored consumer copy
  (`tomo/schemas/hashi-suggestions-wire.schema.json`) is first refreshed from
  `"2"` to the `"3"` the consumer actually holds, then moves to `"4"` only after
  the consumer confirms — the same order spec 038's ADR-1 used.
- **CON-2** — **Kokoro handoff before implementation** (PRD CON-2; MiYo
  Constitution L2 Architecture; ADR-029 cadence). ADR-10 changes C1 values and
  C1's prose contract. The handoff is written from this SDD and sent before any
  Phase that touches `depends_on` starts.
- **CON-3** — Additive for untouched runs: a run with no conflict, no typed input
  and only vault-unique basenames produces Pass 2 output byte-identical to today
  (PRD F1-AC7, F4-AC1, F3-AC3).
- **CON-4** — `_asset_dest_join` stays a pure join that never sanitises (038
  CON-4). Every check runs before it.
- **CON-5** — Constitution L1 Testing: every new refusal, the vault check and
  the delete dependency each owe an accepting and a rejecting test.
- **CON-6** — No executor internals and no predictions in rendered text (038
  CON-6). "Will be created" is the executor's documented contract, not a
  prediction about this vault (PRD A3).
- **CON-7** — Kado failures never abort Pass 2. An unanswered lookup degrades to
  the reported, cautious outcome (ADR-8); only `_check_path_shape` keeps its
  whole-run abort, and nothing an owner types can reach it any more (ADR-5).
- **CON-8** — Runtime file discipline (repo CLAUDE.md): rationale goes to the
  `docs/tomo/` mirror of each changed script; runtime agent/skill files change
  only where a CLI contract changes.

## Implementation Context

### Required Context Sources

- `research.md` (this spec) — R1–R4 with file:line facts; this SDD cites it
  rather than repeating it.
- Spec 038 `solution.md` ADR-1 (version-move order), ADR-5 (reject, never
  sanitise), ADR-6 (refused attachment holds its notes), ADR-7 (inventory).
- Spec 037 `solution.md` — the conflict model, the remedy semantics, the folder
  occupancy set.
- Spec 036 `solution.md:519-524` — the four delete emission sites.
- Kokoro `ADR-029-tomo-hashi-boundary-is-a-set-of-channels.md:136-152`.
- Code: `instruction-render.py:380-760`, `render_actions.py` (`_build_move_asset_actions` :723, `make_folder_listing` :991, `validate_destinations` :1261, `suppress_moves_for_unfiled_attachments` :1534, `_build_delete_source_actions` :1969, `build_actions` :2804), `embed_rewrite.py`, `typed_name_check.py`, `suggestions-reducer.py` (`_VaultFolderLookup` :311, `detect_attachment_conflicts` :~690, `render_attachment_conflicts_block` :1438), `suggestion-parser.py` (:245-564, :2252-2546), `kado_client.py`.

### Implementation Boundaries

- **Must preserve:** every 036/037/038 criterion not named in PRD CON-5; the
  three remedies and their markdown labels; Rename pre-ticked; the bare-embed
  default; the 2026-10-02 rename-line rule.
- **Can modify:** Pass 2's internal ordering of attachment decisions; the
  folder-listing cache; refusal sentences; the `depends_on` description.
- **Must not touch:** the consumer's executor; Pass 1's free-name search scope
  (still the asset folder — the owner sees a computed name, not a guarantee);
  `FORBIDDEN_CHARS` and `sanitize_stem`.

### External Interfaces

| Interface | Direction | Change | Consumer must |
|-----------|-----------|--------|---------------|
| Suggestions wire (C3) | Tomo → Hashi → Tomo | `attachment_conflicts[].proposed_dir: string \| null`, required; `schema_version` `"4"` | vendor v4; offer a folder picker; write vault-relative folders without a trailing slash |
| Decision inventory | Tomo → Hashi | Row D26 | vendor; cover D26 in its coverage map |
| Suggestions markdown (C4) | Tomo ↔ owner | Folder line under Rename | — |
| Instructions wire (C1) | Tomo → Hashi | `delete_source.depends_on` may name `move_asset` ids; description updated | nothing (asserted, F6-AC7); vendor the description |
| Kado (`list_dir`, `byName`) | Tomo → Kado | More calls in Pass 2, bounded | — |

### Cross-Component Boundaries

Hashi's executor already honours `depends_on` across kinds and orders
`move_asset` before `delete_source` (`research.md` R1 §2). Hashi's editor
sanitises names and will write `proposed_dir`; Tomo's Pass 2 remains the
independent guard for both (038 F2-AC4).

### Project Commands

```
./venv/bin/python -m pytest tests/ -q          # full suite
./venv/bin/python -m ruff check tomo scripts tests
python3 scripts/wire-shape.py --obligations      # preview the v4 manifest delta
python3 scripts/wire-shape.py --regenerate       # write it
```

## Solution Strategy

1. **Decide once.** A new `attachment_plan` component turns the run's confirmed
   items, the owner's remedies and two vault views into one decision per
   attachment source: its final target or the reason it is withheld, and the
   exact embed text for its owning notes. It is built after the remedies are
   loaded and before the first note is rendered (`instruction-render.py` after
   :457), because the render loop is the last point a note body can change.
2. **Read, don't recompute.** The embed rewrite and the move builder become
   projections of the plan. The delete builder reads the plan's owner map for
   #186.
3. **Ask the vault twice, cheaply.** A shared folder lookup (one raw listing per
   folder, reused by the existing note guard) answers occupancy and folder
   existence; a basename census (one `byName` per distinct basename) answers
   uniqueness.
4. **Refuse at the edge.** Folder and name checks run inside the plan, per
   entry, before any join — so a bad folder refuses one item and never reaches
   the whole-run path check.
5. **Reuse the suppression pass.** Every withheld outcome is a `skipped_assets`
   entry; the existing ADR-6 pass holds the owning notes for every kind except
   the owner's own Keep in inbox (`render_actions.py:1587`), so no new holding
   logic is written.

## Building Block View

### Components

| # | Component | Status | Owns | PRD |
|---|-----------|--------|------|-----|
| K1 | `lib/attachment_plan.py` | **new** | One decision per attachment source: target resolution (folder + name), refusal routing, run-local claims, vault occupancy outcome, folder-will-be-created and unchecked flags, embed text, owners per source | F1-AC3/5/6/10/11, F2-AC4/6/7/8, F3-AC1–4/6, F4-AC1–6/8, F6 (owner map) |
| K2 | `lib/vault_folder_lookup.py` | **new** (moved from `suggestions-reducer._VaultFolderLookup`) | One raw `list_dir(folder, depth=1)` per folder per run; views `notes()`, `assets()`, `occupied_by_folder()`; `state(folder)` ∈ {`listed`, `absent`, `unanswered`}; call counter | F3-AC7, F2-AC8, F3-AC6 (state) |
| K3 | `lib/basename_census.py` | **new** | One `byName` per distinct case-folded basename; exact case-folded filter; `count(basename)` or `None` when unanswered; call counter | F4-AC2/4/6, C1-AC1 (counter) |
| K4 | `lib/typed_name_check.py` | modified | Name reasons gain `breaks_link`; new `check_typed_folder` with its own closed reason set | F5-AC1/2/4/6, F2-AC1–3 |
| K5 | `lib/render_actions.py` | modified | `_build_move_asset_actions` projects K1; `_build_delete_source_actions` site 3 adds `move_asset` ids; refusal sentences; `make_folder_listing` becomes a view over K2 | F6-AC1/3/4, F3-AC5, F5-AC3/5, F2-AC5 (sentences) |
| K6 | `lib/embed_rewrite.py` | modified | `rewrite_attachment_embeds(body, attachments, plan)` — writes K1's embed text, matches by resolved path | F4-AC1–3/5/8, F1-AC10 |
| K7 | `instruction-render.py` | modified | Builds K1 before the loop; passes it on; relays new withheld kinds and unchecked targets to the shell; records call counts | F2-AC5 (shell), C1-AC1 |
| K8 | `lib/render_md.py` | modified | Instruction-document bullets for the new kinds, unchecked targets, folders to be created; the revised Ignore disclosure | F2-AC5, F3-AC5/6, F2-AC8, F6-AC8 |
| K9 | `suggestions-reducer.py` | modified | Renders the folder line; conflict records carry `proposed_dir: null`; imports K2 | F1-AC2 |
| K10 | `suggestions-render.py` | modified | Projects `proposed_dir` onto the wire | F1-AC1 |
| K11 | `suggestion-parser.py` | modified | Parses the folder line; joins it to `proposed_dir` + `dir_is_owner_supplied`; `build_from_wire` projects it | F1-AC3/4/8/11 |
| K12 | Schemas | modified | Suggestions wire v4 + shape manifest; vendored copy 2 → 3; both instructions schemas' `depends_on` description; inventory D26 | F1-AC1/9, F6-AC6 |
| K13 | User docs | modified | `docs/usage.md`, `docs/troubleshooting.md` | S1-AC1/2 |
| K14 | Join test (`_propose_asset_name` × `check_typed_name`) | **new test** | Every computed name passes the typed-name rules | F5-AC6 |

F4-AC7 (a qualified embed is still recognised) is owned by the existing
`attachment_index.extract_attachment_embeds` and needs only a test — R1 §5
verified the regex accepts it. F6-AC2/F6-AC7 are owned by the consumer's
executor and are asserted, not built.

### Directory Map

```
tomo/scripts/
  instruction-render.py            MODIFY  build the plan after :457; relay; counters
  suggestion-parser.py             MODIFY  folder line, join, wire projection
  suggestions-reducer.py           MODIFY  folder line render; proposed_dir: null; use K2
  suggestions-render.py            MODIFY  proposed_dir on the wire
  lib/attachment_plan.py           NEW
  lib/vault_folder_lookup.py       NEW     (moved from suggestions-reducer.py)
  lib/basename_census.py           NEW
  lib/typed_name_check.py          MODIFY  breaks_link; check_typed_folder
  lib/render_actions.py            MODIFY
  lib/embed_rewrite.py             MODIFY
  lib/render_md.py                 MODIFY
tomo/schemas/
  suggestions-wire.schema.json               MODIFY  v4, proposed_dir
  shapes/suggestions-wire.shape.json         REGENERATE
  hashi-suggestions-wire.schema.json         MODIFY  2 → 3 now; → 4 after consumer confirms
  instructions.schema.json                   MODIFY  depends_on description
  hashi-instructions.schema.json             MODIFY  depends_on description
  suggestions-decision-inventory.json        MODIFY  D26
docs/usage.md, docs/troubleshooting.md       MODIFY
docs/tomo/scripts/**                          MODIFY  WHY mirrors for every changed script
tests/test_039_*.py                           NEW
```

### Interface Specifications

#### Data Storage Changes

None. No persistent store changes; the plan lives for one Pass 2 run.

#### Internal API Changes

**K1 — attachment plan** (signatures are illustrative; names are binding):

```python
@dataclass(frozen=True)
class AttachmentDecision:
    source: str                    # resolved inbox path — the key everywhere
    owners: tuple[str, ...]        # every owning origin key, in confirmed order
    target: str | None             # final vault path, None when withheld
    withheld: dict | None          # a skipped_assets entry when withheld
    embed: str | None              # exact embed target to write (bare name or full path); None = leave embeds untouched
    folder_created: bool           # target folder absent in the vault
    unchecked: bool                # occupancy could not be established
    qualified_reason: str | None   # "ambiguous" | "unanswered" | None

def build_attachment_plan(confirmed, remedies_by_source, *, asset_folder,
                          inbox_path, folder_lookup, census) -> AttachmentPlan
```

`AttachmentPlan` exposes `decisions` (ordered by first appearance in
`confirmed`), `by_source`, `move_ids_by_origin` (filled by K5's projection),
and the two call counters.

**K2 — folder lookup:** `state(folder) -> Literal["listed","absent","unanswered"]`;
`assets(folder) -> dict[str, str]` (case-folded joined path → vault spelling);
`notes(folder)`; `occupied_by_folder(folder)`; `calls: int`. `absent` is Kado's
`NOT_FOUND` on `listDir` (Kado `search-adapter.ts:271`); every other error is
`unanswered`.

**K3 — basename census:** `count(basename) -> int | None` — the number of vault
files whose name case-folds equal to `basename`, or `None` when Kado did not
answer; `calls: int`.

**K4 — typed-name check:**

```python
REFUSAL_REASONS = frozenset({"separator_present", "forbidden_character",
                             "blank", "breaks_link"})
FOLDER_REFUSAL_REASONS = frozenset({"blank", "escapes_vault", "empty_segment",
                                    "edge_whitespace", "trailing_separator",
                                    "forbidden_character", "breaks_link",
                                    "inside_inbox"})
def check_typed_folder(folder: str, *, inbox_path: str) -> TypedNameVerdict
```

**K6:** `rewrite_attachment_embeds(body, attachments, plan) -> str` replaces
`rewrite_renamed_embeds`.

**K5:** `build_actions(..., attachment_plan=plan)` replaces the
`attachment_conflict_remedies` argument; `_build_move_asset_actions(manifest, plan)`
returns `(moves, skipped_assets, move_ids_by_origin)`.

#### Application Data Models

Remedy record (parser output, both paths):

```
{source, remedy, proposed_name, name_is_owner_supplied,
 proposed_dir, dir_is_owner_supplied}        # two new keys
```

New `skipped_assets` kinds (all carry `source`, `destination`, `reason`,
`kind`, `owner_source_items`):

| kind | Set when | Holds owning notes |
|------|----------|--------------------|
| `typed_folder_refused` | K4 refuses an owner-typed folder (+ `refusal_reason`) | yes |
| `vault_occupied` | K2 lists the target folder and the target is taken | yes |

Existing kinds unchanged: `vault_collision_held` (does not hold), `typed_name_refused`, `collision`, `no_basename` (hold).

Suggestions wire, per conflict: `proposed_dir: string | null` — description
begins "Editable — " (inventory join contract).

#### Integration Points

- K1 is built from K2 + K3 + remedies + `confirmed`; K6 and K5 read K1; K5's
  `validate_destinations` receives `make_folder_listing` as a view of the **same**
  K2 instance, so a folder listed for an asset is not listed again for a note.
- K7 relays K1's withheld entries through the existing
  `tomo-tmp/withheld-attachments.md` (038 T4.5) and adds unchecked targets to it.

### Implementation Examples

#### Example: the plan for one source (complex logic)

```
input  source=100 Inbox/Scans/karte.png, owners=[100 Inbox/Dresden.md]
       remedy=rename, name="karte.png" (owner), dir="Atlas/296 Maps" (owner)
1  folder check   check_typed_folder("Atlas/296 Maps")  -> ok
2  name check     check_typed_name("karte.png")          -> ok
3  target         _asset_dest_join("Atlas/296 Maps","karte.png")
4  run claim      not claimed this run                    -> claim it
5  occupancy      K2.state("Atlas/296 Maps") = listed; assets() has no karte.png -> free
6  census         K3.count("karte.png") = 2  (occupier in 295 Attachments + inbox copy)
                  - inbox sources this run moves with that basename: 1
                  + other in-run targets with that basename: 0
                  = 1 other file after the run  -> ambiguous
7  embed          "Atlas/296 Maps/karte.png"
output target=Atlas/296 Maps/karte.png, embed=full path, qualified_reason=ambiguous
```

Same input with `dir` null and name `karte (2).png` (computed): step 5 lists the
asset folder (one call per Pass 2 run, shared with the note guard), step 6
counts `karte (2).png` = 0 → embed bare `karte (2).png` — byte-identical to
today.

#### Test Examples as Interface Documentation

- `test_039_plan_*` — table-driven over the outcomes in the Runtime View's
  decision table, against fake K2/K3.
- `test_039_delete_waits_for_assets` — site 3 `depends_on` equals note ids +
  asset ids; a withheld asset id never appears.
- `test_039_wire_and_markdown_converge_on_folder` — 038 T4.4's convergence test
  extended with a typed folder.

## Runtime View

### Primary Flow — Pass 1

1. `detect_attachment_conflicts` (unchanged search) emits conflict records with
   `proposed_dir: None`.
2. `render_attachment_conflicts_block` renders the Rename line as today, then a
   sub-line `  - Folder: \`<dirname(destination)>\``, in both the ordinary and
   the "no free name available" variant.
3. `suggestions-render` projects `proposed_dir: null` onto the v4 wire.

### Primary Flow — Pass 2, markdown path

1. `_walk_attachment_conflicts` reads the Rename line (unchanged) and the Folder
   sub-line (new, non-checkbox branch).
2. `_join_attachment_conflict_remedies` sets `proposed_dir`: `None` when the
   folder text equals the record's `dirname(destination)` after trailing-slash
   normalisation, else the text verbatim with `dir_is_owner_supplied: True`.
3. K7 builds K1 → render loop (K6 per note) → `build_actions` (K5 projects K1) →
   `validate_destinations` (K2 view) → `suppress_moves_for_unfiled_attachments`
   (holds notes for the new kinds) → `withdraw_unjustified_deletes`.

### Primary Flow — Pass 2, wire path

1. `build_from_wire` projects `proposed_dir` with `dir_is_owner_supplied: True`
   (same rule as names, 038 T2.5); a value equal to `dirname(destination)` is
   normalised to `None` in K1 rather than in the parser, so both paths share
   one equality rule.
2. Steps 3 onward as above — the paths converge at K1.

### Decision table (K1, per source, first match wins)

| # | Condition | Outcome | Embed |
|---|-----------|---------|-------|
| 1 | No basename | withheld `no_basename` | untouched |
| 2 | Remedy Keep in inbox | withheld `vault_collision_held` | untouched |
| 3 | Rename, folder owner-typed and refused | withheld `typed_folder_refused` | untouched |
| 4 | Rename, name empty and folder owner-typed (F1-AC11) | withheld `typed_name_refused` / `blank` | untouched |
| 5 | Rename, name empty, folder not typed | withheld `vault_collision_held` (today's degrade) | untouched |
| 6 | Rename, name owner-typed and refused | withheld `typed_name_refused` | untouched |
| 7 | Target already claimed this run | withheld `collision` | untouched |
| 8 | Not Ignore, K2 `listed`, target taken | withheld `vault_occupied` | untouched |
| 9 | K2 `unanswered` | move, `unchecked` | per census |
| 10 | K2 `absent` | move, `folder_created` | per census |
| 11 | otherwise (incl. Ignore) | move | per census |

Census, for rows 9–11: `None` → full path (`unanswered`); `others ≥ 1` → full
path (`ambiguous`); `0` → bare final name if it differs from the name the note
wrote, else untouched.

### Error Handling

| Failure | Behaviour | Reported |
|---------|-----------|----------|
| Kado `listDir` error other than NOT_FOUND | row 9 | instruction doc + shell: "not checked" |
| Kado `byName` error | qualified embed | instruction doc: embed written with path |
| Folder refused | row 3, notes held | instruction doc + shell, with the reason |
| Path-shape backstop (`_check_path_shape`) | whole-run abort, unchanged | — (unreachable from typed input after K4) |
| Move fails at apply | delete skipped by executor (ADR-10) | executor's own report |

## Deployment View

Single application; no deployment change. Release order (CON-1, CON-2):
Kokoro handoff → implementation → vendored copy 2 → 3 → consumer handoff with
v4 schema, inventory, #185 ruling → consumer confirms → vendored copy → 4.

## Cross-Cutting Concepts

### Cost

Pass 2 Kado calls added: one `list_dir` per distinct target folder not already
listed (usually 1–2), one `byName` per distinct final basename (≈ number of
filed attachments). Zero for a run that files no attachment (F3-AC7). Counted in
K2/K3 and recorded with the run's existing call counts (C1).

### Fail direction

| Check | Unanswered → |
|-------|--------------|
| Occupancy | move emitted, reported unchecked (ADR-8) |
| Folder existence | indistinguishable from occupancy failure → unchecked |
| Basename uniqueness | qualified embed |
| Typed folder / name | n/a — pure, no I/O |

### Security and privacy

`check_typed_folder` refuses `..`, absolute and home-relative paths before any
join (CON-4), so an owner-typed or consumer-written folder cannot address a path
outside the vault. Kado's scope still bounds what is listed. No content is read;
only names and paths.

## Architecture Decisions

### ADR-1 — One attachment plan, decided before the render loop

- **Choice:** New K1, built after remedies load and before the first note
  renders; K5 and K6 read it.
- **Rationale:** The render loop is the last point a body can change, and the
  embed now depends on vault data and on every other attachment's target. A
  single decision site satisfies PRD Rule 6, closes `backlog.md:1917` (refusal
  decided twice) and `:1956` (withheld move still rewrites).
- **Trade-offs:** Largest change in the spec — `_build_move_asset_actions`
  (~250 lines) becomes a projection. Attachments of an item that later fails to
  render are planned too; they emit nothing (the projection filters by the
  manifest, as today) but their targets count for uniqueness — at worst one
  needless qualification.
- **Rejected:** moving the rewrite after `build_actions` and re-writing staged
  files (two writes per note, and the decision would still live in the move
  builder while the embed lives elsewhere); adding the checks to both existing
  sites (three copies of one rule).

### ADR-2 — One raw-cached folder lookup shared by Pass 1 and Pass 2

- **Choice:** Move `_VaultFolderLookup` to `lib/vault_folder_lookup.py`; add
  `state()`; re-base `make_folder_listing` on it.
- **Rationale:** Pass 2's listing keeps only `.md` and caches the filtered map
  (R1 §1); widening it would double the calls. The Pass 1 class already caches
  raw entries and derives both views. `NOT_FOUND` vs other errors gives the
  absent/unanswered split F2-AC8 and F3-AC6 need.
- **Trade-offs:** Touches the Pass 1 reducer's import; no behaviour change there.

### ADR-3 — Basename uniqueness through `byName`, adjusted to the vault after the run

- **Choice:** K3, one `byName` per distinct case-folded basename, exact
  case-folded equality filter; K1 subtracts this run's moved inbox sources with
  that basename and adds this run's other targets with it.
- **Rationale:** `byName` searches every file type vault-wide (R3 §1); one call
  per basename beats a full listing below ~15 basenames per run. The adjustment
  is mandatory: without it every filed attachment counts its own inbox copy.
- **Trade-offs:** A key scoped to part of the vault under-counts (PRD A2, R3).
  Index lag after outside changes is accepted.

### ADR-4 — The folder gets its own markdown line; null means Pass 2's configured asset folder

- **Choice:** A non-checkbox sub-line `  - Folder: \`…\`` under the Rename line,
  pre-filled with `dirname(destination)`. On both paths a folder equal to that
  value is `null`; `null` resolves to Pass 2's `concepts.asset`, exactly as
  today.
- **Rationale:** Owner ruling 2026-10-11 (own line, keeps 2026-10-02). Resolving
  null to the configured folder keeps F1-AC5's "exactly what it is today" even
  if the config changed between passes.
- **Trade-offs:** The default markdown gains one line per conflict, so 038's
  `test_ordinary_conflict_renders_byte_identically_to_today` is retargeted
  (Gotchas). The parser gains one literal, carried by D26's `parser_label`.

### ADR-5 — A typed folder is checked by a closed set of reasons in `typed_name_check`

- **Choice:** `check_typed_folder` beside `check_typed_name`, own closed set
  (`blank`, `escapes_vault`, `empty_segment`, `edge_whitespace`,
  `trailing_separator`, `forbidden_character`, `breaks_link`, `inside_inbox`);
  K1 calls it only when `dir_is_owner_supplied`; refusal kind
  `typed_folder_refused`.
- **Rationale:** One module owns "what an owner may type"; a separate kind keeps
  the instruction document's sentence accurate ("the folder you typed …").
  `breaks_link` applies to folders too, because a folder becomes part of a
  qualified embed. Running inside K1 means `_check_path_shape`'s whole-run abort
  is never reached by typed input (F2-AC7).
- **Trade-offs:** Eight reasons, each owing a sentence and a test.

### ADR-6 — #185 is one reason, `breaks_link`; the renderer stops defaulting to "blank"

- **Choice:** `breaks_link` covers edge whitespace and `# ^ [ ]` in names;
  `_typed_name_refusal_reason` gets an explicit `blank` branch and raises on an
  unknown reason (caught by tests, never by an owner).
- **Rationale:** Owner ruling (one reason). The fall-through is `backlog.md:1757`
  and fires the moment a fourth reason exists (R1 §4).
- **Trade-offs:** `FORBIDDEN_CHARS` untouched — the new characters live in a
  set local to `typed_name_check.py` (PRD F5-AC4).

### ADR-7 — A withheld target is a new `skipped_assets` kind; `ignore` is exempt

- **Choice:** `vault_occupied` for rows 8; Ignore skips row 8.
- **Rationale:** `suppress_moves_for_unfiled_attachments` already holds notes for
  every kind but `vault_collision_held` (`render_actions.py:1587`), so the owner
  ruling "hold the notes" costs no new holding logic. Ignore exempt per owner.
- **Trade-offs:** The occupancy check is not added to `validate_destinations`
  (which stays note-only); asset and note checks live in different passes but
  share K2's data.

### ADR-8 — An unanswered check emits the move and reports it as unchecked

- **Choice:** Row 9; embed qualified when the census is also unanswered.
- **Rationale:** Owner ruling (cautious). ADR-10 makes a failed move safe for the
  origin, so emitting is not destructive; reporting makes it visible.
- **Trade-offs:** Supersedes 037 F1-AC5's silence (PRD CON-5).

### ADR-9 — The embed rewrite covers every filed attachment and matches by path

- **Choice:** K6 writes K1's `embed` for every embed of a moved attachment whose
  current text differs; a written target with a folder component matches only
  the attachment whose resolved path ends with it; a bare one matches by
  basename (today's rule). The owner's `|…` and `#…` suffix is kept; the
  extension is never dropped; no alias is added.
- **Rationale:** F4-AC3 extends qualification beyond renames; R1 §3 measured
  that basename-only matching rewrites a qualified embed pointing elsewhere.
- **Trade-offs:** Notes whose attachments were never renamed can now change —
  only when ambiguous (CON-3 holds for unique basenames).

### ADR-10 — #186: the origin's delete depends on the plan's `move_asset` ids

- **Choice:** K5's projection returns `move_ids_by_origin` built from K1's full
  owner list (not the first owner only); site 3 appends those ids to the origin's
  and its audio peer's `depends_on`, notes first. Both instructions schemas'
  `depends_on` descriptions name `move_asset`.
- **Rationale:** Owner ruling (option 1). The executor cascade does the rest
  (R1 §2). Withheld moves never get an id, so F6-AC4 holds by construction;
  later withdrawals go through `withdraw_unjustified_deletes`, which is
  kind-agnostic.
- **Trade-offs:** A shared attachment couples two origins' deletes (F6-AC3,
  accepted). A C1 change → CON-2.

## Quality Requirements

- Untouched-run byte identity (CON-3) — golden comparison.
- Every K1 decision-table row has an accepting and a rejecting test (CON-5).
- Added Kado calls bounded as in Cost, asserted with counting fakes.
- `ruff` clean; full suite green in one invocation before close-out.

## Acceptance Criteria

Every PRD criterion maps to one owning component (Components table); the
system-level counterpart is the K1 decision-table row or the component's named
behaviour:

| PRD | Owner | System behaviour |
|-----|-------|------------------|
| F1-AC1 | K10, K12 | wire carries `proposed_dir: null`, version `"4"` |
| F1-AC2 | K9 | folder sub-line, pre-filled |
| F1-AC3, F1-AC10 | K1 | target = folder + name (rows 11) |
| F1-AC4 | K11 → K1 | paths converge at K1 |
| F1-AC5 | K1 | null / equal folder → `concepts.asset` |
| F1-AC6 | K1 | folder read only under Rename |
| F1-AC7 | K1, K5, K6 | CON-3 golden |
| F1-AC8 | K11 | rename-line rule unchanged |
| F1-AC9 | K12 | D26; count 26 |
| F1-AC11 | K1 | row 4 |
| F2-AC1–3 | K4 | folder reasons |
| F2-AC4, F2-AC6 | K1 | row 3, no fallback |
| F2-AC5 | K8, K7 | sentence + shell relay |
| F2-AC7 | K1 | per-entry, before joins |
| F2-AC8 | K1, K8 | row 10, "will be created" |
| F3-AC1, F3-AC2 | K1 | row 8 (every non-Ignore target) |
| F3-AC3 | K1 | row 11 |
| F3-AC4 | K1 | Ignore skips row 8 |
| F3-AC5 | K8 | attachment wording |
| F3-AC6 | K1, K8 | row 9 |
| F3-AC7 | K2, K3 | call bounds |
| F4-AC1–6, F4-AC8 | K1, K6 | census rule; untouched for withheld |
| F4-AC7 | `attachment_index` | test only |
| F5-AC1–3 | K4, K5 | `breaks_link` + sentence |
| F5-AC4 | K4 | `FORBIDDEN_CHARS` untouched |
| F5-AC5 | K5 | no default-to-blank |
| F5-AC6 | K14 | join test |
| F6-AC1, F6-AC3, F6-AC4 | K5 | site 3 |
| F6-AC5 | K5 | no move → unchanged |
| F6-AC6 | K12 | both descriptions |
| F6-AC7 | executor | asserted against its planner |
| F6-AC8 | K8 | Ignore disclosure |
| S1-AC1/2 | K13 | docs |
| C1-AC1 | K2, K3, K7 | counters |

## Risks and Technical Debt

### Known Technical Issues

- The vendored consumer suggestions schema is at v2 (spec 038 Phase 5 gap) —
  fixed first (CON-1).
- `build_from_wire_companion` drops the fan wire's conflicts — backlogged.
- An empty typed name degrades instead of refusing (`backlog.md:1839`) — only the
  folder-typed case is fixed (row 4).

### Technical Debt

- `_walk_attachment_conflicts` declares per-entry fields in three places
  (`backlog.md:1894`); the folder is the seventh. Consolidate in the same task
  that adds it.
- Pass 1's free-name search still reads only the asset folder; a computed name
  may be non-unique vault-wide — now caught by the census, not prevented.

### Implementation Gotchas

- **The vendored copy must move 2 → 3 before the v4 change**, or
  `test_wire_snapshot_parity.py`'s pinned delta mixes two versions.
- **Two "3"s.** The instructions wire is also `schema_version` `"3"`; only
  suggestions-wire literals move (R2 §1 lists both kinds of hit).
- **038 golden for the conflict render** gains the folder line — retarget the
  test to assert the new shape, don't delete it.
- **`test_a_different_folder_typed_is_refused_separator_present` must stay
  green** — it is F1-AC8.
- **Inventory note text** may not contain a bare 3–4 digit number
  (`_IDENTIFIER_RE`) — no "296 Maps" in D26's note.
- **The census sees the inbox copy.** Subtract every moved inbox source, or every
  attachment reads as ambiguous.
- **Owners are first-only today** for emitted moves (`render_actions.py:820-829`);
  K1 must collect all of them or F6-AC3 fails silently.
- **`refusal_reason` is not projected to the instructions JSON**
  (`instruction-render.py:1039-1046`); keep it that way — the prose carries it.

## Glossary

### Domain Terms

| Term | Meaning |
|------|---------|
| Origin | The inbox note an item came from; what `delete_source` removes |
| Occupier | The vault file already at an attachment's target |
| Qualified embed | `![[Folder/name.ext]]` — a path, not a bare basename |

### Technical Terms

| Term | Meaning |
|------|---------|
| Attachment plan | K1's per-source decision table output |
| Census | K3's case-folded basename count |
| Unanswered | Kado returned an error other than NOT_FOUND |

### API/Interface Terms

| Term | Meaning |
|------|---------|
| `proposed_dir` | Editable wire field, vault-relative folder or null |
| C1/C3/C4/C10 | Kokoro ADR-029 channels: instructions wire, suggestions wire, suggestions markdown, executor behaviour |
