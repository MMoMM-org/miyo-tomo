---
title: "Profile-Agnostic Markers & MOC Suffix"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (seam-map, README Context)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Metrics defined (regression parity + lyt correctness)
- [x] No feature redundancy
- [x] No technical implementation details included (deferred to SDD)
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision
The Tomo pipeline's behavior is defined by the active profile, not by hardcoded LYT conventions — swapping profiles changes markers and MOC naming with zero code edits.

### Problem Statement
Tomo's pipeline hardcodes one vault's conventions in code: the relationship markers `up::` (parent) and `related::` (peer), and the MOC title suffix `" (MOC)"`. These are scattered across at least nine seams in `lib/` and the pipeline scripts. A `lyt.yaml` profile already ships, but the pipeline ignores its differing conventions — an lyt user would get MOC titles with a spurious `" (MOC)"` suffix that their vault does not use. This blocks the 4-layer Knowledge Stack promise (Framework Profiles as pure data) and is a Constitution L3 pattern-consistency debt (Epic #20, backlog F-16 + F-55).

### Value Proposition
Profiles become the single source of truth for vault conventions. Adding or correcting a profile requires no Python changes, the pure-data-profiles architecture rule holds, and the shipped `lyt` profile produces correct output for the first time.

## User Personas

### Primary Persona: Tomo maintainer (Marcus)
- **Demographics:** Single owner/developer, expert, runs Tomo against a personal Obsidian vault via Kado.
- **Goals:** Keep profiles as pure data; add/adjust a profile without editing pipeline code; trust that a profile change is the only thing that changes behavior.
- **Pain Points:** Convention values are duplicated across `lib/up_parse.py`, `lib/render_actions.py`, `lib/topic_clusters.py`, `suggestions-reducer.py`, `shared-ctx-builder.py`, `moc-discovery.py`, `suggestion-parser.py` — a convention change means hunting hardcoded strings and regexes; the `lyt` profile silently produces wrong titles.

### Secondary Personas
Future non-miyo profile author (post-launch) — benefits from F-16 marker configurability even though no current profile diverges on markers. Not a launch driver; recorded so the design does not preclude it.

## User Journey Maps

### Primary User Journey: Switch active profile to lyt
1. **Awareness:** Maintainer selects `lyt` as the active profile in vault config.
2. **Consideration:** Expects the pipeline to honor lyt's conventions (plain MOC titles, lyt markers) without touching code.
3. **Adoption:** Runs the /inbox pipeline.
4. **Usage:** MOC proposals render with plain titles (no `" (MOC)"`); relationship links are parsed and written using the profile's markers.
5. **Retention:** Confidence that profile = behavior; future profile edits need no code change.

### Secondary User Journeys
Regression path — maintainer runs the pipeline under the unchanged `miyo` profile and observes byte-identical output to the pre-change baseline (nothing broke).

## Feature Requirements

### Must Have Features

#### Feature 1: Markers read from profile (F-16 / #34)
- **User Story:** As the maintainer, I want relationship markers read from the active profile so that the pipeline parses and writes `up::`/`related::` (or any profile's markers) without hardcoded strings.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given the active profile defines `relationship_defaults.parent.marker` and `peer.marker`, When the pipeline parses existing relationship links in a note, Then it uses the profile's marker values (not hardcoded `up::`/`related::`).
  - [ ] Given the active profile's markers, When the pipeline emits new `link_to_moc` / up-preservation actions, Then the written marker text matches the profile's `parent`/`peer` marker.
  - [ ] Given the `miyo` profile (markers `up::`/`related::`), When the full pipeline runs, Then reading and writing behavior is unchanged from the pre-change baseline.

#### Feature 2: MOC title suffix read from profile (F-55 / #35)
- **User Story:** As the maintainer, I want the MOC title suffix read from the profile so that lyt produces plain titles while miyo keeps `" (MOC)"`.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given the `miyo` profile with `map_note.name_suffix: " (MOC)"`, When a MOC title is generated or enriched, Then the title ends with `" (MOC)"` exactly as today.
  - [ ] Given the `lyt` profile with `map_note.name_suffix: ""`, When a MOC title is generated or enriched, Then the title has no suffix appended.
  - [ ] Given a profile with a suffix, When titles are normalized/matched (e.g. topic clustering, placeholder MOC detection), Then the suffix is stripped using the profile value, not a hardcoded `" (MOC)"`.

#### Feature 3: Profile key surface (`map_note.name_suffix`)
- **User Story:** As the maintainer, I want a documented profile key for the MOC suffix so both bundled profiles declare their convention as data.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given `miyo.yaml` and `lyt.yaml`, When the pipeline loads a profile, Then a `map_note.name_suffix` value is present and consumed (miyo `" (MOC)"`, lyt `""`).
  - [ ] Given a profile that omits `name_suffix`, When the pipeline loads it, Then a documented default applies (backward-compatible; no crash).

### Should Have Features
- Shared unit-test parameterization proving both profiles' markers and suffix drive behavior from a single test matrix.

### Could Have Features
- Making `FOOTER_CALLOUTS` profile-configurable (deferred; see Won't Have).
- Marker `format` templates (`"up:: {{link}}"`) surfaced for fully custom link rendering.

### Won't Have (This Phase)
- `FOOTER_CALLOUTS` configurability — explicitly out of scope (moc-tree-builder.py's own comment declares it not an F-55 knob).
- Any new profile beyond the bundled `miyo` and `lyt`.
- UI or runtime profile-switching mechanism beyond the existing vault-config profile selection.
- Changes to marker *values* for the miyo profile (must stay `up::`/`related::`).

## Detailed Feature Specifications

### Feature: MOC title suffix read from profile (most divergent today)
**Description:** The MOC title suffix is the only convention that differs between the two shipped profiles today (miyo `" (MOC)"`, lyt `""`). The pipeline must apply it on write and strip it on normalize/match, sourcing the value from the active profile.

**User Flow:**
1. Maintainer sets active profile (miyo or lyt) in vault config.
2. Pipeline generates/enriches a MOC title.
3. System appends the profile's `name_suffix` (possibly empty) exactly once.
4. When later matching/normalizing that title, system strips the profile's `name_suffix`.

**Business Rules:**
- Rule 1: The suffix is applied at most once — a title already ending in the suffix is not double-suffixed.
- Rule 2: An empty suffix (`""`) means no append and a no-op strip.
- Rule 3: Suffix matching on strip is case-insensitive where the current hardcoded behavior is case-insensitive (parity with existing `topic_clusters` / `shared-ctx-builder` regexes).

**Edge Cases:**
- Title already contains the suffix → Expected: not duplicated.
- Profile omits `name_suffix` → Expected: documented default, no crash.
- Empty suffix with a title that coincidentally ends in `"(MOC)"` under lyt → Expected: no stripping (lyt does not define that suffix).

## Success Metrics

### Key Performance Indicators
- **Regression parity:** miyo-profile pipeline output is byte-identical before/after the change (primary success signal).
- **lyt correctness:** lyt-profile MOC titles contain no `" (MOC)"` suffix.
- **Seam elimination:** zero hardcoded `up::`/`related::`/`" (MOC)"` literals remain in the in-scope seams (verified by grep in tests/review).
- **Test coverage:** both profiles' markers and suffix exercised by offline unit tests (happy + strip/no-op cases).

### Tracking Requirements
No runtime telemetry (Constitution: no analytics). Success is validated by the test suite and one final live-test cycle, not by tracked events.

| Event | Properties | Purpose |
|-------|------------|---------|
| N/A (internal dev tooling) | — | No user-facing analytics per MiYo Constitution |

---

## Constraints and Assumptions

### Constraints
- Near-MVP: additive-only on hot paths; no behavior change for the miyo profile.
- Test scope = personal vault (pre-launch); offline unit tests strongly preferred.
- Exactly ONE live-test cycle budgeted, at the very end (minimize live runs against Kado; 429 risk).
- Profiles must remain pure data (YAML); logic stays in scripts (Constitution architecture rule).
- Delivery batched with F-16 + F-55 together so only one live-test cycle is needed.

### Assumptions
- `relationship_defaults.parent.marker`/`peer.marker` already exist in both profiles and hold `up::`/`related::` (verified in seam-map).
- Markers are identical across both current profiles, so F-16 introduces no behavioral change today.
- The SDD will resolve how each of the four core scripts receives marker/suffix values (none currently receive shared-ctx uniformly).

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Writer-path regression in `render_actions.py` changes emitted link text | High | Medium | Byte-identical miyo regression test on rendered actions before/after; unit tests on both marker directions |
| Suffix double-apply or wrong strip breaks MOC matching | High | Medium | Apply-once + strip business rules with explicit unit cases; parity with existing case-insensitive regexes |
| Delivery-channel design balloons scope (per-script plumbing) | Medium | Medium | SDD picks the minimal channel; FOOTER_CALLOUTS explicitly excluded to bound blast radius |
| Missing `name_suffix` in a future profile crashes pipeline | Medium | Low | Documented default when key absent |

## Open Questions
- [ ] (For SDD, not blocking PRD) Which delivery channel carries markers/suffix to each of the four core scripts — extend shared-ctx, pass profile dict, or a small shared loader? Resolved in solution.md.

---

## Supporting Research

### Competitive Analysis
N/A — internal dev-tooling refactor, no competitive dimension.

### User Research
Grounded in the completed seam-map (README Context, 2026-07-01): nine hardcoded seams enumerated with file:line; both shipped profiles inspected; only the suffix diverges today.

### Market Data
N/A — internal to the MiYo/Tomo project.
