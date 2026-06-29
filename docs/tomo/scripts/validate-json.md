# WHY: validate-json.py (script)

> Rationale for decisions in `tomo/scripts/validate-json.py`.
> Spec 026, T1.1 — Companion Mode P1 Deterministic Safety Scripts.

## Parse-Gate Before Every .base/.canvas Write (ADR-4)

WHY: Obsidian `.base` and `.canvas` artefacts are JSON files composed by the
inbox-author skill and written to the vault via `kado-write-file.py
operation=file`.  A malformed file reaching the vault silently corrupts the
user's canvas or base — Obsidian parses them on open and shows an empty or
broken view with no clear error.  `validate-json.py` intercepts the artefact
BEFORE the write: `json.loads` either succeeds (exit 0, write proceeds) or
raises (exit 1, write is aborted, vault is never touched).

## Safety Logic Must Be Deterministic, Not LLM-Judged (ADR-9)

WHY: The question "is this JSON valid?" must not be answered by asking the LLM
to inspect the content.  An LLM can hallucinate "looks fine" on malformed
output, and its judgment drifts between runs and between model versions — the
same artefact could be accepted one run and rejected the next.  A deterministic
`json.loads` call is stable, auditable, and testable in both directions (valid
→ exit 0; malformed → exit 1), satisfying the MiYo Constitution L1 requirement
that safety properties (here: no malformed JSON ever enters the vault) be
covered by automated tests.

## Read-Only by Design

WHY: A gate that writes side-effect files as part of validation would be
dangerous in a pipeline (it could create artefacts even when the gate rejects,
leaving partial state).  `validate-json.py` is strictly read-only: it reads the
target file, calls `json.loads`, and exits.  It never creates, modifies, or
deletes any file.  This is enforced by the unit test suite
(`test_validator_writes_nothing_for_valid_input` and
`test_validator_writes_nothing_for_invalid_input`).

## Stderr for Errors, No Stdout Noise

WHY: The script is designed to sit in a shell pipeline where stdout carries
structured data and stderr carries diagnostics.  All error messages go to
stderr; stdout is intentionally empty on both success and failure.  Callers can
capture stdout without polluting it with error text.
