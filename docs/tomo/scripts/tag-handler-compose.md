# WHY: tag-handler-compose.py

> Rationale for decisions in `tomo/scripts/tag-handler-compose.py`.
> The script is a thin orchestration bridge: it reads a payload JSON file written by
> the interpreter skill, calls `target_structure.assemble()`, and prints exactly one JSON
> object to stdout (spec 025 / T4.1a / ADR-3).

## Why this script exists at all (skill→script→lib pattern / ADR-3)

WHY: `target_structure.assemble()` is a pure Python function that must run deterministically
without an LLM. The interpreter is an LLM skill (`tomo/skills/tag-handler-interpreter/`)
— it runs inside a Claude session and cannot call Python library functions directly. To
cross the LLM-boundary cleanly (Constitution L1 Code Quality: deterministic core testable
without AI), the skill writes a payload JSON file and delegates to this script as a
subprocess. The pattern is: skill (LLM context) → tag-handler-compose.py (subprocess) →
`lib/target_structure.py` (pure Python). The script is the glue: it owns the file I/O
boundary, validates the payload shape, calls the library, and formats the result as a
well-typed JSON object on stdout. This keeps `target_structure.py` IO-free and the skill
free of deterministic assembly logic.

## Payload contract (section_lines / output_format / cell_values_per_item / marker)

WHY these four fields and no others:

- `section_lines`: the raw lines of the target note section under the marker heading,
  as read from Kado in Phase 4 by the interpreter skill. The script does not read Kado
  — the skill has already done that and passes the result here. Keeping the Kado read in
  the skill (not here) means this script has no network dependency and can be tested with
  fixture data.
- `output_format`: the handler config's `output_format` object — the structural spec
  (structure/order/granularity/cells). Passed through verbatim to `assemble()`.
- `cell_values_per_item`: one inner list of rendered cell strings per inbox item (for
  `per_item` granularity) or exactly one inner list (for `merged`). The interpreter skill
  synthesizes `synthesize` cells via LLM before calling this script; by the time this
  script runs, all cells are plain strings. The deterministic assembly (row formatting,
  pipe-escape, block construction) happens here.
- `marker`: the handler's marker heading text, used as the heading anchor value when
  `order == "append"` or `structure == "list_item"`. Passed through to `assemble()`.

## Stdout contract (ok / fallback / error)

WHY three status values and not an exit-code-only protocol:

- `{"status": "ok", "composed_block": "...", "resolved_anchor": {...}}` — the happy path.
  The interpreter skill reads `composed_block` and `resolved_anchor` and writes the
  group-result JSON.
- `{"status": "fallback", "reason": "..."}` — `assemble()` returned a `Fallback`
  sentinel. The skill composes a plain prose block and annotates with ⚠️ (FR-19 / ADR-8).
  A non-zero exit would conflate fallback (a normal, expected degradation path) with a
  genuine error; keeping it on stdout with a status field lets the skill branch cleanly.
- `{"status": "error", "message": "..."}` with non-zero exit — bad payload (missing
  field, malformed JSON, file not found). The skill treats this as a hard failure.

Using a JSON envelope on stdout for all three cases means the skill always does the same
`json.loads(stdout)` call and routes on `status` — no stderr parsing, no exit-code
interpretation, no conditional branching on output format.

## Why this script does NOT write the group-result file or compose prose (skill owns step 4)

WHY: The group-result JSON file is a structured output that passes `output_format`,
`composed_block`, and `resolved_anchor` through to the reducer and instruction-render.
Writing that file here would require the script to know the file naming convention
(`tomo-tmp/tag-handler-group-<id>.json`) and the full group-result schema — coupling this
thin bridge to both the grouper and the reducer. The interpreter skill already holds both:
it knows the group id (it called tag-handler-group first) and the schema (it emits the
file as part of its step 4). Similarly, the prose fallback path involves an LLM
composition step — exactly the skill's domain. Keeping this script to its one
responsibility (call the library, return one JSON object) keeps it small, testable, and
decoupled from the rest of the pipeline.

## Why cwd-relative paths — no `_SCRIPT_DIR.parent.parent` (CON-2 instance layout)

WHY: The Docker instance runs in a flattened layout (`tomo-instance/{scripts,config}`).
The `_SCRIPT_DIR.parent.parent` navigation used in some older scripts (e.g.
`tag-handler-resolve.py:44-46`) resolves correctly in the repo but produces the wrong path
in the instance. This script only needs `_SCRIPT_DIR` to wire the `lib/` import path
(`sys.path.insert(0, str(_SCRIPT_DIR))`), which is always correct — `lib/` lives alongside
the calling script in both layouts. The payload file path comes from `argv[0]` (a
cwd-relative path the skill controls), not from any constant in this script.
