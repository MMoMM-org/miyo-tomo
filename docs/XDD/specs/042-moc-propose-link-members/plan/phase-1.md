---
title: "Phase 1: Budgeted lookups and node eligibility"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Budgeted lookups and node eligibility

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Internal API Changes]` — `KadoClient` additions, `lib/link_members.py` interfaces
- `[ref: SDD/Implementation Examples; link-member qualification (traced), budget gate across retries]`
- `[ref: SDD/ADR-1, ADR-3, ADR-4]`
- `tomo/scripts/lib/kado_client.py:668` (`_call_tool`), `:689-717` (retry loop), `:793-813` (`_retry_delay`)
- `tomo/scripts/lib/moc_scan.py:133` (`_is_excluded`), `tomo/scripts/lib/moc_tags.py:27`, `tomo/profiles/miyo.yaml:42-51`, `tomo/scripts/moc-discovery.py:396, :535` (atomic paths)

**Key Decisions**:
- Pure library work: no change to `moc-discovery.py`, the reducer or any prose yet.
- Budget unit is the HTTP **attempt**, retries included. `call_count` keeps its current meaning.
- Eligibility never calls Kado and never logs a node path.

**Dependencies**: none.

---

## Tasks

Establishes the two building blocks every later phase uses: a Kado client that can be held to a per-run attempt budget with pacing, and a library that decides member eligibility and computes link members.

- [x] **T1.1 KadoClient attempt budget and pacing** `[activity: backend-api]` `[component: KadoClient]`

  1. Prime: WHY doc first — `docs/tomo/scripts/lib/kado_client.md` (new): attempts vs calls, the gate, pacing, why retries count (owner: backoff support) `[ref: SDD/ADR-4]`
  2. Test: `tests/test_kado_client_attempts.py` (RED): a fake transport answering 429 `Retry-After: 0` twice then 200 → `attempt_count == 3`, `call_count == 1`; `attempt_gate` returning False before the second attempt raises `KadoBudgetExhausted` and makes no further send; `min_interval=0.3` with a fake monotonic clock sleeps the difference between sends; defaults (`gate=None`, `min_interval=0`) leave every existing test unchanged
  3. Implement: `attempt_count`, `attempt_gate`, `min_interval`, `KadoBudgetExhausted` in `tomo/scripts/lib/kado_client.py` (bump `# version:`); the gate is consulted before **every** send including retries
  4. Validate: new tests green; `tests/test_kado_client_retry.py` and `tests/test_kado_client_graph.py` unchanged and green; ruff clean
  5. Success: retries are counted and stoppable `[ref: PRD/F5-AC3]`; pacing ≥ 0.3 s available to callers `[ref: PRD/F5-AC2]`

- [x] **T1.2 NodeEligibility** `[activity: domain-modeling]` `[component: NodeEligibility]` `[parallel: true]`

  1. Prime: WHY doc first — `docs/tomo/scripts/lib/link_members.md` (new): the eligibility rule, why offline, why periodic notes and MOCs are neither members nor bridges, why uncached nodes are skipped; `[ref: SDD/ADR-3; Implementation Gotchas]`
  2. Test: `tests/test_link_members.py::TestEligibility` (RED), each rule falsified on its own: non-`.md` path; outside atomic-note paths; inbox path; periodic (profile `calendar.base_path` + every `granularities.*.path`, vault-config `concepts.calendar.*` incl. the trailing-space value `"Calendar/301 Daily/ "`, and `exclude_paths`); MOC (cache `kind == "moc"`, `map_notes`, `name_suffix`); cached tag `exclude/note`; uncached path → ineligible with reason `uncached`; an eligible cached atomic note → True. Reasons are returned, never printed.
  3. Implement: `NodeEligibility` in `tomo/scripts/lib/link_members.py` (new, `# version: 0.1.0`, header docstring per repo convention)
  4. Validate: tests green; ruff clean; a grep shows no `print`/`logging` of a path in the module
  5. Success: `[ref: PRD/F6-AC1, F6-AC2, F6-AC4]`

- [x] **T1.3 LinkLookup and link-member qualification** `[activity: domain-modeling]` `[component: LinkLookup, augment_clusters]`

  1. Prime: `[ref: SDD/Implementation Examples; traced example; Complex Logic]`; T1.1 and T1.2 deliverables
  2. Test: `tests/test_link_members.py::TestLookup` and `::TestAugment` (RED), with a graph fake copied from `tests/test_instruction_render_up_preservation.py`:
     - memoisation: two clusters sharing member A → one `neighbors(A)` call;
     - the traced example verbatim (X and Y qualify; Daily and MOC Z never counted);
     - a node in exactly 1 member list is not added `[ref: PRD/F1-AC2]`; a node that is already a member is not added `[ref: PRD/F1-AC3]`; a node qualifying in two clusters is returned for both `[ref: PRD/F1-AC4]`;
     - hub rule: a periodic note linking A and B never raises another node's count `[ref: PRD/F6-AC3]`;
     - budget: a cluster whose uncached lookups exceed `remaining()` → `skipped_budget`, no call made, and a later smaller cluster still runs `[ref: PRD/F5-AC1]`;
     - failure: a lookup raising `KadoError` → that cluster `failed`, others unaffected `[ref: PRD/F5-AC4]`;
     - `limit` is never passed to `graph()`.
  3. Implement: `LinkLookup` (budget 60, pacing 0.3 s, installs the client gate) and `augment_clusters` in `lib/link_members.py`; `LinkMember` with `linked_with` sorted and up state taken from the cache entry
  4. Validate: tests green; mutation check in a `git archive` copy — drop the `>= threshold` comparison to `>= 1` and the F1-AC2 test must fail; drop the eligibility check inside the hit loop and the hub test must fail
  5. Success: `[ref: PRD/F1-AC1…AC4, F5-AC1, F5-AC4, F6-AC3]`

- [x] **T1.4 Phase Validation** `[activity: validate]`

  - Run `./venv/bin/python -m pytest -q tests/test_link_members.py tests/test_kado_client_*.py`, then the full suite; ruff clean. Confirm both WHY docs exist and were committed before their code.
