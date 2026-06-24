# Tomo Companion Mode — Charter

> Charter / brainstorm spec for an interactive **companion mode** for Tomo, distinct from the `/inbox` processing pipeline.
> Created: 2026-06-24. Status: **proposal (decision-first, no code)**. Next step: `/xdd` → PRD once scope is accepted.
> Origin: evaluation of [`kepano/obsidian-skills`](https://github.com/kepano/obsidian-skills) (MIT) + analysis of real companion-style usage in the `tomo-privat` session logs.
> Roadmap relation: extends the Obsidian-Power track (epic #16); orthogonal to the `/inbox` 2-pass pipeline.

---

## 1. Goal

Make Tomo usable as an **interactive PKM companion**: the user converses with Tomo to *ask about* their notes, *analyse* them, *enrich* from external sources, and *author / update* notes directly — in-session, outside the `/inbox` batch pipeline.

Today Tomo has one primary mode: `/inbox` — an async, proposal-first pipeline that *manages material the user already captured* (classify → suggest → approve → apply). Companion mode is the complementary half: a synchronous, conversational mode that *produces and interrogates* material on demand.

## 2. Problem It Solves

`/inbox` is reactive and batch-oriented: it waits for captured items, runs a fixed 2-pass flow, and is deliberately constrained (writes only to the inbox folder). Real observed usage wants something `/inbox` cannot provide:

- Answers to ad-hoc questions over the vault's data ("how often X over the last 365 days, what were the gaps?").
- On-demand thematic synthesis ("search the vault for notes about X and write me a summary note").
- Direct authoring/compilation into arbitrary locations ("compile the Elsass-trip daily notes into one note with this format"; "create a Japan-2025 stub like Japan-2024").
- External enrichment woven into notes (historical weather; GitHub project state).

These are conversational, user-directed, and write outside the inbox — none fit the `/inbox` model.

## 3. Observed Usage Patterns (from `tomo-privat` session logs)

Grounding evidence — four recurring patterns, none of which is `/inbox` work:

1. **Vault analytics** *(heaviest)* — read daily-note markers across long spans; compute frequencies, intervals/gaps, monthly time-series, top-N; render as tables. Tomo-native (read via Kado → compute → render).
2. **Thematic search → synthesized note** — "durchsuch den Vault nach X und erstell eine zusammenfassende Notiz".
3. **Direct authoring / compilation** — travel logs from daily notes in a fixed format (`Datum (Orte) / Wetter / Text`); project-update notes; "leg eine neue Datei an"; "update die Notiz".
4. **External enrichment** — fetch historical weather, GitHub state, weave into notes.

Friction signal: the user hit **OFM-correctness bugs** (wikilink rendering with/without backticks) — getting valid Obsidian-Flavored Markdown out is already a pain point.

## 4. Relationship to `kepano/obsidian-skills`

The kepano skills (MIT, by Obsidian's CEO; `obsidian-markdown`, `obsidian-bases`, `json-canvas`, `obsidian-cli`, `defuddle`) bundle **two separable things**:

- **Format knowledge** — how to author valid OFM / `.base` / `.canvas`. **Portable, access-agnostic, conflict-free.**
- **CLI access** — how to read/write vault files directly. **Conflicts with MiYo's Kado-only access model.**

**Decision: adopt the *knowledge*, reject the *access half*.** Do **not** `/plugin install` wholesale. Instead, **adapt the format guidance into Tomo companion skills that write via Kado** (`kado-write` `operation=note` for `.md`; `operation=file` for `.base`/`.canvas`). License is MIT → adaptation is permitted **with attribution** (record the source in the derived skill + a dependency note per Constitution L2 Dependencies).

| kepano skill | Disposition for companion mode |
|---|---|
| `obsidian-markdown` | **Adapt** → OFM-authoring reference skill (fixes the wikilink/format bug class). Highest, lowest-risk value. |
| `obsidian-bases` | **Adapt** → enable analytics output as live `.base` views over tracking data. Strong fit for pattern #1. |
| `json-canvas` | **Defer / optional** → visual maps (relationships, trips, concepts). Situational. |
| `defuddle` | **Defer** → matches the enrichment pattern but needs container network + tool install; evaluate separately. |
| `obsidian-cli` | **Reject** → direct CLI access violates Kado-only (Constitution L2, Privacy & Security). |

## 5. Scope

### In-scope (companion track, phased)

- A **companion entry mode** distinct from `/inbox` (conversational; no fixed pipeline).
- **OFM-authoring reference skill** (adapted from `obsidian-markdown`) — every companion-written note is syntactically correct OFM.
- **Vault-analytics capability** — read daily-note markers/data via Kado, compute summaries/time-series/gaps, render as markdown tables and/or `.base` views.
- **Thematic search → synthesis** — Kado search/read → composed note.
- **Direct authoring/update via Kado**, in-session, with the conversation as the approval gate (see §6 tension).

### Out-of-scope (parking lot)

- Replacing or restructuring `/inbox` (companion is additive, orthogonal).
- `obsidian-cli` adoption (rejected).
- `defuddle` / web-enrichment (deferred — separate evaluation incl. container network policy).
- Autonomous/background companion actions — companion is strictly user-initiated, in-session.

## 6. Architecture & Key Tensions

### 6.1 Kado-only access (settled)
All vault access stays through Kado. CLI is rejected. This is the non-negotiable boundary (Constitution L2).

### 6.2 Execution-boundary tension *(the central decision)*
Tomo's MVP rule (CLAUDE.md): **"Tomo writes only to the inbox folder; user applies everything else"** via the proposal-first 2-pass model. Companion mode the user explicitly asks Tomo to **create/update notes anywhere** ("leg eine Datei an", "update die Notiz") — direct writes outside the inbox. This is a deliberate expansion, and the design must reconcile it:

- **Proposal**: companion direct-writes are legitimate because **the conversational instruction *is* the approval** — synchronous, explicit, per-request, with the user watching. This is a different trust model from `/inbox`'s async batch (where the 2-pass review exists precisely because there is no human in the loop at write time).
- **Implication**: companion needs **broader Kado write scope than inbox-only**. This is a Kado-side ACL/permission change → cross-repo (see §7).
- **Open guardrails**: per-write preview/confirm? scope limits (e.g. never delete, never write to denylisted folders)? a companion-specific Kado key with read-broad + write-broad-but-bounded?

### 6.3 Kado capability needs
- Write `.base` / `.canvas` via `kado-write operation=file` (base64) — verify Kado accepts these extensions.
- Broader read (already largely available) and the broader write scope from §6.2.

### 6.4 Privacy (Constitution L1)
Companion content is among the most sensitive in the vault (the logs include health/sexuality/relationship data). Local-first must hold; **`defuddle`/web-enrichment must not exfiltrate vault content** to resolve external lookups — only the user's explicit external query leaves the machine, never note content. This is why enrichment is deferred to its own evaluation.

## 7. Cross-Repo Implications

- **Kado**: broader companion write scope (§6.2) and `.base`/`.canvas` write confirmation (§6.3) are Kado contract changes → MiYo handoff (`_outbox/for-kado/`) + likely a Kokoro ADR (Constitution L2 Architecture: cross-component interface changes recorded in Kokoro).
- **Kokoro**: the execution-boundary expansion (companion direct-write trust model) is an architecture-level decision → **candidate Kokoro ADR** before implementation.
- **Hashi**: companion writes via Kado directly (synchronous), *not* via Hashi instruction-sets — so no Hashi dependency for v1 (unlike `/inbox`). Worth stating explicitly to avoid scope creep.

## 8. Proposed Phasing

1. **P1 — OFM-authoring foundation**: adapt `obsidian-markdown` into a companion authoring-reference skill; route writes via Kado. Kills the wikilink/format bug class. Smallest, highest-confidence slice.
2. **P2 — Vault analytics**: daily-note marker analytics → markdown tables (Tomo-native; no new Kado capability needed for read).
3. **P3 — Bases output**: render analytics as `.base` views (needs Kado `.base` write confirmation).
4. **P4 — Direct-write scope + guardrails**: the §6.2 trust-model decision + Kado ACL change (gated on Kokoro/Kado).
5. **Deferred**: `json-canvas`, `defuddle`/enrichment.

## 9. Open Questions

- OQ-1: Companion as a new `/companion` (or `/ask`) surface, or ambient (any non-slash prompt in a Tomo session)?
- OQ-2: Direct-write trust model — conversation-as-approval vs. tri-state preview vs. always-to-inbox-then-apply? (§6.2)
- OQ-3: Does Kado need a distinct companion key, or extend the existing Tomo key's write ACL?
- OQ-4: Analytics — generic marker-query engine, or a small set of curated reports? How are markers declared (vault-config)?
- OQ-5: Bases vs. static markdown tables as the default analytics output.

## 10. Risks

- **Boundary erosion**: a broad companion write scope weakens the very guardrail (`/inbox` 2-pass) that makes Tomo safe. Must be bounded and explicit, not a blanket "Tomo can write anywhere".
- **Privacy**: enrichment/web tools risk exfiltration of ultra-sensitive content — deferred and fenced.
- **Scope sprawl**: companion mode can absorb unlimited capability; phasing (P1 first) keeps it shippable.
- **License/attribution**: adapting kepano (MIT) content requires attribution + a dependency note.
