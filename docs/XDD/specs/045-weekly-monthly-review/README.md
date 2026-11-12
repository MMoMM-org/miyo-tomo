# Specification: 045-weekly-monthly-review

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-08 |
| **Current Phase** | PLAN |
| **Decomposition tier** | Incremental |
| **Model tier** | frontier |
| **Last Updated** | 2026-11-11 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.3: 8 features, 59 criteria; v1.1 approved 2026-11-11; v1.2 SDD decisions; v1.3 validation findings (definitions, edge cases, KPI scope) |
| solution.md | completed | v1.2 (Phase 2 as-built); v1.1: 19 components, ADR-1..13 confirmed, all 59 PRD criteria traced; validation findings worked in |
| plan/ | completed | v1.1: 6 phases, 34 tasks (28 deliverables + 6 phase validations); PRD traceability table in phase-6.md, checked by script |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

**Model tier**: `routine` | `hard` | `frontier`. The classifier recommends it at the decomposition step and the user confirms it; leave the placeholder until then. `spec.py --read` treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-08 | Spec scaffolded for #31 (F-45) on branch docs/31-weekly-monthly-review | Owner chose #31 as the next P1 item after #182 was closed |
| 2026-11-08 | Start with PRD; research in Agent Team mode (4 researchers: domain, technical, integration, UX/cost) | Owner choice |
| 2026-11-08 | The needed part of F-02 is in this spec: weekly/monthly config, ISO name format, template mapping, date→path resolver, instance config | Owner choice (recommended); quarterly/yearly stay out |
| 2026-11-08 | Periods: the last finished ISO week / calendar month by default, earlier periods on request; no running period | Owner choice (recommended); lets the live walk use March 2026 without writing dailies |
| 2026-11-08 | Output: a section in the existing weekly/monthly note, else a new note from the user's template; delivered through a suggestions doc the user accepts and edits (2-pass, like /inbox), never a black box | Owner: "eine Blackbox wo der Nutzer keine Möglichkeiten hat die Dinge zu ändern … halte ich für falsch" |
| 2026-11-08 | Sources: the whole daily note (trackers/sport, Dayplanner, vault review, 5 Year Journal, Obsidian ToDos, Daily Log, the user's own review text), MOC activity, notes new in the period | Owner choice; must work without Dataview/Quoth for other users while supporting the owner's setup fully |
| 2026-11-08 | Review language = the vault locale | Default; the owner's dailies carry `locale: de` |
| 2026-11-08 | v1 review doc is markdown edited in Obsidian (moc-proposal precedent), parsed by Tomo; no Hashi editor tab, no Hashi handoff | Owner choice (recommended); a Hashi editor view is a later spec |
| 2026-11-08 | Pass 2 is triggered by /review itself, not /inbox | Owner choice (recommended); keeps every eval-gated file untouched |
| 2026-11-11 | Monthly review reads the dailies AND the weekly notes of its weeks; marks what only the weeklies hold and what they left out | Owner: weekly reviews add links and themes in hindsight that no daily holds |
| 2026-11-11 | Rate limit: pace and retry until Kado accepts instead of stopping at a call budget; report retries and suggest raising Kado's limit, slow down further, name what still failed | Owner: a hard budget at 20 calls / 5 s would read almost nothing |
| 2026-11-11 | Arguments name the period by themselves (`W13`, `2026-W13`, `2026-03`, `@`-picked note); `week` word dropped, `month` kept for "last month" | Owner note; the instance's @-picker already offers vault notes via Kado |
| 2026-11-11 | First day of the week is a setup value; `/review setup` reopens the setup | Owner note: not every user starts the week on Monday |
| 2026-11-11 | Readable instructions next to the instruction set for users without Hashi | Owner note; same pattern as /inbox and /note |
| 2026-11-11 | Markdown review document is 80/20; edits it cannot carry safely go to the later Hashi editor spec | Owner note |
| 2026-11-11 | PRD v1.1 approved; phase PRD → SDD | Owner: "passt so" |
| 2026-11-11 | SDD ADR-1..6 confirmed: /note-style shim+skill+scripts; open state in the vault; review section with marker, insert then replace_section; adaptive pacing; vault-config-writer `review` subcommand; applied read from the instruction JSON | Owner confirmed the recommended set |
| 2026-11-11 | PRD v1.2 — week counting: inferred from existing weekly notes, else asked in plain words; never from the Obsidian plugin config | Owner: "Die Obsidian config hat ja nichts damit zu tun wie der user seine Woche definiert" |
| 2026-11-11 | PRD v1.2 — Templater templates: use the Tomo variant when set up; else keep the template and tell the user to run Templater after the move | Owner chose both options |
| 2026-11-11 | SDD ADR-10..12 confirmed: /inbox skips doc_type review by filename suffix " Review" (no extra Kado call); /note's deliver loop extracted into lib/staged_delivery.py; the model writes only proposals.json, scripts compute habits, growth and link differences | Owner confirmed the recommended options |
| 2026-11-11 | Decomposition tier: Incremental | Classifier recommended Incremental (14 new components, 8 features, 59 criteria). Accepted. |
| 2026-11-11 | Model tier: frontier | Classifier recommended frontier (novel_pattern=true: section marker line; high_risks=4; adr_count=12). Accepted with the cost sentence shown. |
| 2026-11-11 | Spec validation (4 validators: consistency, code alignment, coverage/ambiguity, constitution): 9 FAIL, ~30 WARN; all worked in — PRD v1.3, SDD v1.1 (ADR-3/4/11 amended, ADR-13 new: item ids, withdrawal on drop), plan v1.1 (libs split, Kokoro FYI handoff T1.7, error table, write-failure tests) | Owner: "Alle einarbeiten" |
| 2026-11-11 | Command name stays `/review`; Claude Code's built-in is `/code-review`; T5.2 checks the container first, a mod is the fallback | Owner |
| 2026-11-11 | Phase 1 complete: T1.1–T1.7 implemented on fable, each spec- and code-reviewed (T1.1 and T1.2 one FAIL each, fixed); full suite 8294 passed, 1 known unrelated failure (test_install_smoke_ide_bridge_block_exists); drift check closed in 7bfbc2a6 | Coordinator |
| 2026-11-11 | Process: commit 1acbfe03 carries T1.1 and T1.4 under T1.1's subject (parallel agents shared the index); one fable commit used its own Co-Authored-By line. Not rewritten (no amend/rebase); both disappear in the squash merge. Rule tightened: `git commit -F … -- <paths>` and the attribution copied verbatim | Coordinator |
| 2026-11-11 | Phase 2 complete: T2.1–T2.3 on fable, each spec- and code-reviewed (T2.1 one spec FAIL + one code FAIL, T2.2 one spec FAIL + one code FAIL, T2.3 one code FAIL — all fixed); new libs review_vault, week_rule_inference, vault_config_edit; full suite 8488 passed, 1 known unrelated failure; drift closed in 38a5733e (SDD v1.2) | Coordinator |
| 2026-11-11 | Phase 2 decisions: review heading ≤ level 5 so groups stay ≤ 6; config rule beats inferred rule; --first-day/--min-days only together; no kado-none signal for an empty open-review search; duplicate stem → flat folder is the target (T4.1); place-too-deep preview problem (T4.1/T4.2); T4.3 probes the set JSON only for approved documents | Coordinator |
| 2026-11-11 | PRD v1.2 — F7-AC2 cleanup promise replaced by documentation of where content rests (transcripts, working folders, inbox) and a recommendation to protect the instance like the vault | Owner: content stays on the machine anyway; a cleanup script is overkill and inflexible |
| 2026-11-11 | Highest reachable rung: T3.2 BLOCKED on fable | Trigger: second review FAIL in a row (code review 34877879 → b9595c2a FAIL: two untested paths — digit-boundary rule inside is_navigation, cut_at_rule for other-day sections of linked notes); run halted for the owner |
| 2026-11-11 | Stop overridden: T3.2 gets one more fable round for the two test gaps only, then one last code review | Owner chose "one more round"; the behaviour defects were already fixed, the open findings are tests that cannot fail |
| 2026-11-11 | Highest reachable rung: T3.3 BLOCKED on fable | Trigger: second review FAIL in a row (code review ebcf6657 → fbdc7524 FAIL: result.not_read snapshotted before weekly notes read after a recovered listing — a failed weekly note is missing from it); run halted for the owner |
| 2026-11-11 | Stop overridden: T3.3 gets one more fable round (not_read snapshot fix, per-prefix cache-key tests, test-file split), then one last code review | Owner chose "one more round" |
| 2026-11-11 | Phase 3 complete: T3.1–T3.7 on fable, each spec- and code-reviewed (T3.2 and T3.3 reached the top rung's second FAIL, owner overrode both stops; T3.5/T3.6/T3.7 three fix rounds each); new libs review_pacer, review_day, review_md, review_period, review_reader, review_weekly, review_habits, review_doc, review_doc_parse; scripts review-read.py, review-doc.py (write/parse/replace); full suite 8887 passed, 1 known unrelated failure deselected; ruff clean; fixtures hold template structure only; drift closed in 74a5f8e6 (SDD v1.3) | Coordinator |
| 2026-11-11 | Highest reachable rung: T4.1 BLOCKED on fable | Trigger: second spec-review FAIL in a row (76e17fff: the Python mirror of Hashi's heading regex reads CRLF headings Hashi cannot see; JS vs Python whitespace classes; collision/place-missing refusals do not report the found heading); run halted for the owner |
| 2026-11-12 | T4.1 done (spec + code review after the owner-approved round); open follow-up: a lone `%%` that a user types into an item lands verbatim and opens an Obsidian comment that hides the rest of the target note — review_doc's escape set (T3.6) does not cover it; to be filed as an issue at close-out | Coordinator |
| 2026-11-12 | T4.2 done (spec PASS; code review FAIL once → fix 54292aae → PASS): doc-mark conflict read from Kado's `code: CONFLICT` (write_note never raises KadoConcurrencyError; the open-dirty-editor refusal is CONFLICT too, both are doc-changed); `drop` withdraws once any step began, naming a lone note; resume after `doc-changed` does not re-check the set against the edited document (SDD:1007, accepted); T4.3 reads a begun delivery without `failed_step` as `failed-delivery` | Coordinator |
| 2026-11-12 | T4.3 done (spec PASS; code review FAIL once → fix 2735358f → PASS): withdrawn is tested before the begun-delivery reading; `stem_state` is the one probe-and-classify step for `start` and `status`; set probe only for approved docs, step-5/6 probes only for a waiting set, absent only on NotFound; `start` writes `applied_reported`, a failed write keeps the listing with `notices: [applied-not-recorded]` (SDD `start` shape to be updated in T4.4); a reported applied review still costs one set read per start (vault stays the source of truth, coordinator) | Coordinator |
| 2026-11-12 | Stop overridden: T4.1 gets one more fable round (JS-exact heading regex incl. CRLF, JS whitespace classes, refused replaces report the found heading), then a last spec review and the code review | Owner chose "one more round" |
| 2026-11-11 | Phase 3 decisions: the reader owns the yesterday shift and reads the day after the period; time averages are circular; a bare `-` is missing for every tracker; a rule `---` ends a section only before navigation; exact digit-bounded day tokens; plain dailies read whole under `text`; empty growth is not an access problem; a recovered folder listing rereads the period, an unread daily listing stops the run; write never overwrites (review-exists), replace --confirm/--abort; links only from resolved period sources, structural markers escaped; edited is structural (pass1_links, nothing text-derived in meta); the parse result stays in-process; one stem guard | Coordinator |

## Context

Issue #31 (part of #16, backlog F-45): a weekly / monthly review that rolls up the past N daily notes (completed work, open threads, MOCs that gained content, recurring themes) into a periodic note. The roadmap (`docs/XDD/roadmap-obsidian-power.md` §3) names F-02 (periodic-notes rendering; config present) as a hard prerequisite and orders it after the garden audit (#30, closed). Spec 044 (`/note`) already creates filled notes from vault templates. `tomo/profiles/miyo.yaml` enables weekly (`Calendar/302 Weekly/`) and monthly (`Calendar/303 Monthly/`); `tomo/config/vault-example.yaml` carries their name formats and templates.

---
*This file is managed by the xdd-meta skill.*
