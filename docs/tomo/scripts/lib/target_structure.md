# WHY: lib/target_structure.py

> Rationale for decisions in `tomo/scripts/lib/target_structure.py`.
> The module is a pure, IO-free target-section parser and row/item assembler: it takes
> raw section lines and an `output_format` config dict, and returns either a composed
> `(block, anchor)` tuple or a `Fallback` sentinel (spec 025, T2.1–T2.3).

## Why a pure deterministic helper with no IO (ADR-3 / Constitution L1 Code Quality / CON-3)

WHY: Structure detection and row assembly are deterministic, composable operations — they
require only raw strings and a config dict, never a Kado read or an LLM call. Making
them IO-free means they are unit-testable without a vault, a running Kado server, or a
live model. This mirrors the purity contract established by `moc_structure.py` for
the MOC-side parsing: Constitution L1 requires domain behaviour to be testable without an AI
in the loop, and a deterministic library that only touches `synthesize` cells at the
call-site of the interpreter skill satisfies that constraint. Any IO that crept into this
module would force all tests to mock network or filesystem, increasing fragility and
coupling the structural logic to infrastructure concerns.

## Why first-matching-structure-under-marker wins (ADR-9)

WHY: A target section may contain introductory prose before the actual table or list —
a short paragraph explaining the section's purpose, a callout, or a blank line. Scanning
only for the first valid structure (header+separator pair for tables; first list item for
lists) and skipping prose means `parse_section` is robust to any reasonable preamble
without requiring a perfectly clean section. Stopping at the next heading (any `#` level)
ensures the scan never bleeds into an adjacent section. This "first-match, skip-prose"
rule is the ADR-9 parse contract; callers that need a different selection strategy must
pre-filter the lines they hand to `parse_section`.

## Why the block anchor carries RAW header+separator bytes (byte-exact Hashi contract)

WHY: `assemble()` returns an anchor of `{type: "block", value: header_line + "\n" +
separator_line, placement: "after"}` for `table_row + newest_first`. The value is the
RAW bytes from the live vault section — only trailing whitespace is stripped. If the
anchor were re-pretty-printed (e.g. normalised pipe spacing, added trailing space), Hashi's
`resolveBlock` would perform a byte-level substring search against the live file content
and silently fail to find it — the table row would never be inserted. The "trailing-trim
only; no reformatting" rule is the sole reason `parse_section` preserves the exact
characters the section carried, and it must stay that way for any future structure type
that uses a block anchor. Instruction-render passes this resolved anchor verbatim to
Hashi (SDD Boundary 1 — the Phase 4→5 contract).

## Why single-line + pipe-escape sanitisation (`_sanitize`)

WHY: A table cell must be a single-line string and must not contain a literal `|`
character (which would break Markdown table parsing). Cell values that come from
frontmatter fields or LLM synthesis may legitimately contain newlines (a multi-sentence
synthesis response) or pipe characters (paths, URLs). `_sanitize` collapses newlines to
a space and replaces `|` with `\|` (the escaped form). The list-item variant
(`_sanitize_line`) only collapses newlines because a bullet list cell does not need pipe
escaping — the pipe character is not meaningful there. FR-18 is the requirement: never
emit a malformed table row.

## Why a typed `Fallback` sentinel instead of raising (ADR-8)

WHY: The caller (tag-handler-compose.py, and through it the interpreter skill) needs to
distinguish between "structure not found" and "cells don't match columns" to emit the
right ⚠️ label in the suggestions doc. Raising an exception would either require the
caller to catch different exception subclasses (brittle — the caller is partly an LLM
skill) or lose the reason code in a single catch block. A typed `Fallback(reason)` lets
the caller do a single `isinstance(result, Fallback)` check and read `result.reason` for
a reason string that maps directly to the `_FALLBACK_REASON_LABELS` dict in the reducer.
Degrading to prose + ⚠️ is the correct behaviour (ADR-8 / FR-19): the user approves a
safe prose fallback, the feature never silently no-ops by raising.

## Why cwd-relative paths — no `_SCRIPT_DIR.parent.parent` (CON-2 instance layout)

WHY: The Docker instance uses a flattened layout: `tomo-instance/{scripts,config}` rather
than the repo's `tomo/{scripts,config}`. Scripts that navigate up via
`_SCRIPT_DIR.parent.parent` to reach sibling directories resolve correctly in the repo
but break inside the instance. `target_structure.py` is a pure library with no filesystem
access of its own, so it has no paths to resolve. Sibling scripts that call it
(`tag-handler-compose.py`) use `_SCRIPT_DIR` only to wire the import path
(`sys.path.insert(0, str(_SCRIPT_DIR))`), which is always correct regardless of layout —
the lib lives alongside the calling script in both the repo and the instance.
