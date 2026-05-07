# XDD 014 — Requirements (PRD)

> **Status:** draft (2026-05-07)
> **Spec ID:** 014
> **Title:** MOC-creation skill — proactive `/moc-propose` and `/moc-create`
> **Backlog ref:** F-43 (Must)
> **Roadmap position:** Track #1 in `docs/XDD/roadmap-obsidian-power.md` — next up.
> **Launch gate:** Satisfied 2026-05-07 (commit `053bc4e docs(F-43): mark Hashi launch gate satisfied`).
> **Related specs:** F-34 (XDD 013, accumulation detection — complementary inbox-side trigger); F-35 (placeholder MOC trigger, shipped 2026-05-07); F-44 (garden-audit — depends on a solid MOC primitive); F-13 (legacy `/scan-mocs` — superseded by this).
> **Reference-skill prerequisite:** Import `obsidian-markdown` skill (link/embed/callout syntax) as part of this track.

## 1. User story

> As a Tomo user with an established vault, when I notice a topic area
> getting unwieldy (or want to formalise a budding interest), I run
> `/moc-propose <topic>` to ask Tomo to scan the vault, surface
> candidate clusters, and propose a structured MOC. After I review the
> proposal in a familiar suggestions-doc UI, I run `/moc-create` to
> materialise it: an actual `<Topic> MOC.md` file in `Atlas/200 Maps/`
> with proper sections, bidirectional `up::`/children links, profile-
> aware naming (Dewey for miyo, free thematic for LYT), and tags.
> Today: there is no command for this. The user must hand-craft MOCs in
> Obsidian, manage `up::` markers manually, and remember the
> conventions Tomo otherwise enforces in the inbox flow.

## 2. Problem today

- **Inbox-driven MOC creation only.** F-34 and F-35 fire MOC proposals
  during `/inbox` runs (item-driven). There is no equivalent for the
  "I want to organise this topic NOW, regardless of inbox" workflow.
- **Pre-existing primitives are unused outside the inbox.** The schema
  already defines `create_moc` and `add_relationship` actions
  (`tomo/schemas/instructions.schema.json:43`, `:103`); a `t_moc_tomo`
  template exists; `tier-3/lyt-moc/new-moc-proposal.md` describes the
  intended MOC structure. None of these have a user-facing entry point
  outside the inbox-analyst's emission path.
- **Convention drift in hand-crafted MOCs.** When the user creates
  MOCs by hand in Obsidian, naming conventions, section conventions
  (e.g. `> [!blocks]- Key Concepts`, `> [!connect]- Linked Notes`),
  and `up::`/`down::` markers drift. Later tooling (garden-audit F-44,
  inbox-analyst MOC matching) then has to handle messy edge cases.
- **No reusable MOC structure templating.** Each profile (miyo, LYT)
  has different MOC conventions. There is no profile-aware way to
  materialise a MOC that follows the user's chosen profile correctly.
- **Future tracks are blocked.** Garden-audit (F-44), weekly review
  (F-45), and tag-audit (F-46) all reason about MOCs as first-class
  structures. Building those without a clean creation primitive forces
  each track to re-derive what "a well-formed MOC" means.

## 3. Goals

- **G1 — Two-step UX, proposal-first.** `/moc-propose` discovers and
  proposes; `/moc-create` materialises an approved proposal. Never
  write a MOC to the vault without explicit user approval.
- **G2 — Reuse existing primitives.** Build on the existing
  `create_moc` + `add_relationship` schema actions, the `t_moc_tomo`
  template, and the Hashi executor. No new MCP surface, no new
  schema action types.
- **G3 — Profile-aware naming and structure.** miyo profile applies
  Dewey-aware naming (e.g. `2300 - Health MOC` for major class,
  thematic stems for sub-class); LYT profile uses free thematic stems.
  Section conventions per profile (callout types, headings).
- **G4 — Vault discovery via Kado, no new MCP.** `kado-search byTag`,
  `kado-search byContent`, `listDir`, and frontmatter queries provide
  enough signal to suggest cluster candidates and a starting note set.
  No MCP additions to Kado.
- **G5 — Match the existing 2-pass approval UX.** Proposal surfaces
  in a suggestions-doc-shaped artefact (per `tier-3/inbox/
  suggestions-document.md` conventions), with `[ ] Approved`
  checkboxes per proposal and per-section toggles. The user's mental
  model carries from `/inbox` to MOC-creation unchanged.
- **G6 — Bidirectional linking on materialisation.** `/moc-create`
  emits both the new MOC file AND `add_relationship` instructions to
  add `up::<NewMOC>` to each child note. Hashi handles the actual
  vault writes; Tomo emits the instructions.
- **G7 — Standalone but compose-friendly.** Works without F-34
  (accumulation detection) or F-44 (garden-audit), but the same
  output schema makes it easy for those features to feed proposals
  into the same UI.

## 4. Non-goals

- **N1 — Auto-creation.** No "MOC suggested → MOC created" silent
  path. Always 2-pass with explicit user approval.
- **N2 — Bulk MOC migration.** Out of scope: "convert all my Tag
  X notes into a MOC". User picks one MOC at a time.
- **N3 — Splitting / merging existing MOCs.** Refactoring existing
  MOC structure (split a too-big MOC into two; merge two related
  MOCs) is post-MVP. Garden-audit (F-44) is a more natural home.
- **N4 — Topic synthesis from scratch.** `/moc-propose` requires a
  topic argument or a candidate cluster as input. It does not freely
  invent topic areas.
- **N5 — MOC-of-MOCs auto-promotion.** Detecting "you now have 8
  sibling MOCs that should share a parent" is post-MVP. User decides
  the hierarchy explicitly when they pick a `parent_moc`.
- **N6 — Cross-profile migration.** A user does not migrate from miyo
  to LYT (or vice versa) via this feature. Profile is set at install
  time and stays.
- **N7 — Renaming existing MOCs.** Out of scope for `/moc-create`.

## 5. Acceptance criteria

**A1 — `/moc-propose <topic>` discovers candidates.** The command
takes a topic argument (string), queries Kado for notes mentioning the
topic via tag, body, or wikilink, optionally seeds from F-34's
accumulation index when present, and returns ≥1 candidate cluster: a
group of notes that could populate the MOC. Empty results MUST be
surfaced as an explicit "no clusters found" message, not a silent
no-op.

**A2 — Proposal artefact follows suggestions-doc shape.** The
proposal is written to a suggestions-doc-shaped file at a deterministic
path (TBD in SDD — likely `<inbox>/<YYYY-MM-DD_HHMM>_moc-propose-
<slug>.md`). It MUST include: proposed MOC title, proposed file path,
proposed parent MOC (or "root"), proposed sections (header + callout
type + child-note candidates), `[ ] Approved` toggle, per-section
toggles, and a free-text override field for the title.

**A3 — Profile-aware naming.** When the active vault profile is
`miyo`, proposed MOC names follow Dewey conventions (e.g.
`2300 - Health MOC.md` for a class-level MOC). When the active profile
is `lyt`, proposed names follow free thematic conventions (e.g.
`Health MOC.md`). Profile defaults live in
`tomo/profiles/<profile>.yaml`.

**A4 — Profile-aware section structure.** Generated MOCs follow the
profile's MOC template:
- miyo: `> [!blocks]- Key Concepts`, `> [!connect]- Linked Notes`,
  optional H2 sub-sections
- lyt: matches existing LYT conventions in
  `tier-3/profiles/lyt-profile.md`
Child notes are placed under the appropriate section per profile rules.

**A5 — `/moc-create` materialises an approved proposal.** When the
user approves a proposal (toggle `[x] Approved`), running `/moc-create`
parses the doc, emits `instructions.json` containing:
1. one `create_moc` action for the new MOC file with the templated
   body, frontmatter (`up::<parent_moc>` if any), tags, and sections
2. one `add_relationship` action per child note with
   `marker: "up::"` and `target: "<NewMOC>"`
3. cleanup of the proposal doc (move to processed-archive per
   existing inbox-cleanup conventions)
Hashi (or the user via the manual apply path) executes the
instructions.

**A6 — Bidirectional linking is enforced.** Every child note in the
approved proposal gets an `up::<NewMOC>` marker added (frontmatter or
content position per `vault-config.relationships`), AND the MOC body
contains a wikilink to the child under the appropriate section. The
two halves of the link are emitted as paired instructions; Hashi
applies them transactionally (per Hashi's existing semantics).

**A7 — Reference-skill prerequisite shipped.** Before `/moc-create`
ships, `tomo/skills/obsidian-markdown/` is imported as a `user-
invocable: false` reference skill, so the MOC-architect agent can
load it lazily for link/embed/callout syntax checks. Source: aitmpl.com
or equivalent (per roadmap §3 reference-skill table).

**A8 — Empty-vault / no-MOC-yet bootstrap.** A vault with no existing
MOCs MUST work: `/moc-propose` against an empty MOC tree creates the
first root MOC with `parent_moc: null`. This is the "bootstrap" case
for users adopting Tomo into a flat vault.

**A9 — No vault writes from `/moc-propose`.** The propose command
writes only to the inbox (proposal artefact). All vault writes happen
via `/moc-create` → Hashi, going through the existing approval +
instruction-render + Hashi-executor pipeline.

**A10 — Tests cover the happy path and the edge cases.**
- Topic with 0 candidates → "no clusters found" message
- Topic with 1 candidate cluster → single proposal
- Topic with multiple disjoint clusters → multiple proposals in one
  doc, user approves a subset
- miyo profile vs LYT profile → correct naming + sections
- Bootstrap (empty MOC tree) → root MOC, no parent
- Profile-mismatch (LYT vault but miyo conventions in user override)
  → user's free-text override wins
- Existing MOC with same name → conflict detection, suggest disambiguation

**A11 — Documentation.** New entries in `docs/XDD/README.md` index
(currently lists 001-006 only — see backlog item D-05 below) and
backlog F-43 marked code-complete. Tier-3 specs cross-referenced.

## 6. Out of scope (noted)

- **Cluster scoring / ranking.** First cut surfaces all candidates
  ordered by cluster size; user picks. Future: confidence score per
  cluster, topical-fit score per child note.
- **Section auto-population from existing structure.** First cut
  proposes empty `> [!blocks]- Key Concepts` and `> [!connect]-
  Linked Notes` callouts; user fills in the section names that fit
  their MOC. Future: infer section names from child-note H2 patterns.
- **Auto-removal of conflicting links.** If a child note already has
  an `up::OtherMOC`, `/moc-create` does NOT remove it — the user must
  decide whether to keep both, replace, or split. First-cut emits a
  warning.
- **MOC-template per topic-area.** All generated MOCs use the same
  per-profile template. Future: domain-specific templates (e.g.
  "Project MOC" template with status/timeline sections).
- **Reading existing MOC structure to suggest sections.** If a
  related MOC already exists, the proposed MOC could borrow its
  section layout — out of scope for MVP.

## 7. Success signals

- The user can take a vault with 5 unrelated boardgames notes (no
  MOC) and run `/moc-propose Boardgames` to get a proposal with
  those 5 notes pre-populated under sections, then `/moc-create` to
  ship a clean MOC with bidirectional links — without leaving Claude
  Code or hand-editing files in Obsidian.
- Every MOC created via `/moc-create` passes garden-audit (F-44,
  when shipped) with zero violations on naming / section structure /
  `up::` linking.
- F-44, F-45, F-46 build on top of `/moc-create`'s schema for their
  own propose/materialise flows without re-implementing the
  primitive.
- The `/scan-mocs` legacy backlog item (F-13) can be marked
  superseded — `/moc-propose` covers the same vault-wide scan use
  case in a more user-controllable form.

## 8. Open questions

> Answer before SDD locks the surface.

- **OQ1 — Where does the proposal artefact live?**
  (a) `<inbox>/` like FAN resolve docs (XDD 012); pro: one place for
  all 2-pass artefacts; con: clutters inbox with non-inbox content.
  (b) `+/moc-proposals/` (new subfolder); pro: clean separation;
  con: new convention to teach.
  **Lean:** (a) for MVP — reuse existing inbox cleanup pipeline.

- **OQ2 — Naming conventions on collision.** If `Health MOC.md`
  already exists and user runs `/moc-propose Health`:
  (a) abort with "MOC already exists, use `/moc-extend` (post-MVP)";
  (b) propose under a disambiguated stem (`Health MOC (proposed).md`).
  **Lean:** (a) — explicit failure beats silent file-creation collisions.

- **OQ3 — Argument shape for `/moc-propose`.** Single string topic, or
  multi-keyword (e.g. `/moc-propose health fitness exercise`)?
  **Lean:** single string for MVP; keywords are split internally on
  whitespace and OR-combined in the Kado search.

- **OQ4 — How is parent MOC selected?** Auto-suggest based on
  candidate-children's `up::` consensus? Always default to root
  (no parent)? Always ask user?
  **Lean:** auto-suggest based on cluster's existing `up::` patterns,
  but show a free-text override field in the proposal doc.

- **OQ5 — Profile schema extensions for MOC conventions.** Where does
  the "callout types per section" + "max children per section" live?
  - (a) New top-level `moc_creation:` block in
    `tomo/profiles/<profile>.yaml`
  - (b) Inline in existing `lyt:` / `miyo:` profile sections
  **Lean:** (a) — clear separation, easier to schema-validate.

- **OQ6 — Subfolder for new MOCs.** Per profile config, MOCs go to
  `Atlas/200 Maps/`. Should `/moc-create` auto-derive a subfolder
  (e.g. `Atlas/200 Maps/2300/Health MOC.md` for Dewey 2300)?
  **Lean:** flat `Atlas/200 Maps/<MOC>.md` for MVP; nested subfolders
  per Dewey class is post-MVP.

- **OQ7 — Reference-skill source.** `obsidian-markdown` skill source —
  aitmpl.com community, or hand-author? Per the 2026-05-06 decision
  (`docs/ai/memory/decisions.md`), only Kado-MCP-compatible community
  skills can be absorbed. obsidian-markdown is reference-only (no
  filesystem access), so importable. SDD must validate this before
  locking.
  **Lean:** import via `tcs-helper:skill-import` with
  `user-invocable: false` flag, lazy-loaded by the MOC-architect agent.

- **OQ8 — Agent vs script split.** The roadmap mentions a new agent
  `moc-architect.md` plus scripts `moc-propose.py` / `moc-render.py`.
  Where is the boundary?
  **Lean:** scripts handle deterministic work (Kado searches, frontmatter
  templating, instructions emission). Agent (sonnet, like
  inbox-analyst) handles classification (cluster shape, section
  proposals, naming suggestions). Same pattern as inbox-analyst /
  shared-ctx-builder.

## 9. Constraints

- **C1 — Constitution L1 (privacy / Kado-only).** All vault access
  through Kado MCP. No direct filesystem reads of vault content.
- **C2 — Proposal-first principle.** No vault writes without explicit
  approval (the same principle that governs inbox flow).
- **C3 — Reuse existing schema actions.** `create_moc` and
  `add_relationship` already exist; no new schema additions needed
  except optional new fields if SDD discovers gaps.
- **C4 — Profile-aware everything.** miyo and LYT must be supported
  on day one; the abstraction has to support a third profile being
  added without changing core code.
- **C5 — Reference-skill compatibility (memory:
  `decisions.md` 2026-05-06).** Imported skills must be Kado-MCP-
  compatible (no direct filesystem access). `obsidian-markdown` from
  aitmpl.com qualifies as a reference-only skill.
- **C6 — "Additive only on hot paths" memo
  (`feedback_near_mvp_no_breakage.md`).** This feature adds NEW
  commands and a NEW agent — it does not modify existing inbox-flow
  hot paths. Safe.
- **C7 — Branch + commit discipline.** Implementation lands on
  `feat/f-43-moc-creation-skill`; no direct commits to main.

## 10. Definition of done

- All A1–A11 acceptance criteria pass.
- All OQ1–OQ8 open questions are answered in the SDD.
- `obsidian-markdown` reference skill imported and lazy-loaded.
- Tier-3 specs (`new-moc-proposal.md`, `moc-matching.md`)
  cross-reference XDD 014.
- Backlog F-43 marked code-complete; live-validation result attached.
- F-13 (`/scan-mocs`) marked superseded.
- A real user-flow run: take a topic-area in Marcus's vault that
  currently has 3-5 unclassified atomic notes, run
  `/moc-propose <topic>` → review → `/moc-create` → see a proper
  miyo-style MOC in `Atlas/200 Maps/` with bidirectional links to
  the children. End-to-end without manual editing.

## 11. Validation hooks (for SDD/PLAN phases)

- Empty-vault bootstrap test: zero MOCs, run `/moc-propose Health`
  → proposal with `parent_moc: null`.
- Profile-aware test: run twice (miyo + lyt) against the same topic
  → confirm correct naming and section structure per profile.
- Bidirectional linking test: confirm child notes get `up::<NewMOC>`
  and the MOC body contains wikilinks to children.
- Conflict-detection test: pre-existing `Health MOC.md`, run
  `/moc-propose Health` → confirm correct error/disambiguation
  behaviour (per OQ2 resolution).
- Cluster-size scaling test: topic with 1, 5, 20 candidate notes
  → confirm proposal doc remains readable; section layout adapts.
- Reference-skill load: confirm `obsidian-markdown` is loaded only
  when `moc-architect` is invoked, not on every Tomo session.

## 12. Doc-debt note (separate backlog item)

- **D-05 (new) — XDD index lag:** `docs/XDD/README.md` lists only
  specs 001–006. Specs 007–014 are not in the index. Should be
  refreshed as part of this XDD's documentation pass (A11).
