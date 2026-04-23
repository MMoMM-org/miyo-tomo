# Tomo Roadmap

> Post-MVP priorities derived from XDD-006 spec-vs-IST audit (2026-04-19).
> See [backlog.md](backlog.md) for the full item list with spec references.

## Horizon 1: Live-Validation (now)

Goal: Confirm end-to-end workflow works with real vault data.

- [ ] Test cleanup pass (Pass 3) — vault-executor transitions source items
- [ ] Validate bug fixes (parser re-seen dates, renderer template stems)
- [ ] Second full cycle — fresh items through Pass 1 → Pass 2 → Apply → Cleanup

## Horizon 2: Robustness (next)

Goal: Tomo runs reliably across different vault configurations.

- [ ] F-16: Relationship markers from config (not hardcoded `up::`)
- [ ] F-17: Callout matching by full first line (type + title)
- [ ] F-21: Cache staleness warning at session/run start
- [ ] D-01–D-04: Doc debt cleanup (4 small fixes)

## Horizon 3: UX + Polish

Goal: Reduce manual effort for the user.

- [ ] F-03: Templater rendering by Tomo
- [ ] F-18/F-19/F-20: Cache analysis scripts (frontmatter, tags, orphans)
- [ ] F-13: Standalone MOC density scan (`/scan-mocs`)
- [ ] F-10: Auto-detect applied actions (skip manual checkboxes)

## Horizon 4: Expansion

Goal: Beyond MVP capabilities.

- [ ] F-02: Periodic notes (weekly, monthly, quarterly, yearly)
- [ ] F-01: Tomo Hashi executor (Obsidian plugin reading `instructions.json` via the Obsidian Plugin API; see Kokoro ADR-009 for the charter, 2026-04-23). Contract shipped 2026-04-21 (XDD 008): `instructions.json` + `tomo/schemas/instructions.schema.json`. (Earlier roadmap drafts called this "Seigyo"; Seigyo is now on the backburner and, if ever built, is likely a remote-control plugin rather than an executor.)
