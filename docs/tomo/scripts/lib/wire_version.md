# WHY: lib/wire_version.py

> Rationale for decisions in `tomo/scripts/lib/wire_version.py`.
> Makes F3's failure impossible instead of merely detected.

## WHY This Module Exists (spec 035 F3, ADR-5)

Before this task each of the three wire renderers (`suggestions-render.py`,
`instruction-render.py`, `garden-audit-render.py`) wrote its `schema_version`
as a free string literal at its emission site. Nothing tied that literal to
the schema it claims to conform to, so a schema bump could land without the
renderer following, or a renderer's literal could drift without the schema
moving — either direction, undetected until a consumer rejected the
document. `wire_schema_version()` reads the `const` the schema itself
declares, so the two cannot diverge: there is only one number, and the
renderer reads it instead of asserting it. CON-8 established that schemas
ship to the instance (`scripts/install-tomo.sh:1262-1264`) and
`garden-audit-configure.py:49` already resolves one at runtime, so the file
is reachable from a running renderer.

## WHY the Schemas Directory Is Resolved Per Call, Not at Import Time

`doc_frontmatter.py` — the cited precedent — resolves and loads its schema
at module import time and raises `FileNotFoundError` from the module body.
Copying that shape here would have made the missing-schema and
scratch-schema tests very hard to write: an import-time raise cannot be
redirected per test, and by the time a test could monkeypatch anything the
import has already succeeded or already failed for the whole process.
`_default_schemas_dir()` is a function precisely so it runs at call time —
tests point it at a scratch directory (or an empty one, for the
missing-schema case) via `monkeypatch.setattr`, and each renderer's own
production call site is unaffected, because it never passes an override.

## WHY No `schemas_dir` Parameter on `wire_schema_version()`

`lib/wire_gate.py`'s `gate_one_wire`/`run_wire_gate` take explicit
`schemas_dir`/`shapes_dir` parameters — but that module is itself a
standalone script invoked with explicit directories; there is no single
"real" schemas dir it defaults to. A renderer's call to
`wire_schema_version("suggestions-wire.schema.json")` has exactly one
correct directory in production — the instance's `schemas/` — so adding an
unused parameter whose only caller would ever be a test is speculative
surface, not flexibility. Redirecting `_default_schemas_dir` for tests keeps
the renderers' call sites identical to the SDD's own worked example
(`solution.md:455-471`): a bare `wire_schema_version("<schema>.json")`, no
second argument.

## WHY the Error Message Shape Matches `doc_frontmatter.py`, Not Its Timing

The SDD (ADR-5) asks for "a missing schema raises with an explicit message,
matching `doc_frontmatter.py:80`'s existing treatment of the same failure."
That is a claim about message content — name the file, name the resolved
path, say what to do — not about when the check runs. Matching the message
shape while moving the check inside the function satisfies the SDD's actual
intent (a maintainer sees the same kind of error either way) without
inheriting the import-time raise that would have made this module
untestable.

## WHY `const` Is Type-Checked Before It's Returned

`schema["properties"]["schema_version"]["const"]` returns whatever JSON value
sits there — code review (2026-09-11) pointed out that nothing stopped a
schema declaring `"const": 2` or `"const": null` from flowing straight into
a renderer's wire payload with no exception, despite the function's own
docstring and `-> str` annotation. This cannot happen against any schema
committed under `tomo/schemas/` today (every `const` there is a string), but
the consequence if it ever did is specific rather than cosmetic: Hashi's
validator enforces `schema_version` as a string const, so an integer or null
on the wire is rejected at apply for the whole instruction set — the exact
cross-repo divergence this spec exists to prevent, one layer below where the
rest of spec 035 is looking. `wire_schema_version()` raises `TypeError`
rather than coercing with `str(const)`: coercion would silently manufacture
a value nobody declared and mask the schema authoring error instead of
surfacing it.

## WHY Malformed JSON Is Caught and Re-Raised, Not Left Bare

A schema file that exists but isn't valid JSON used to raise a bare
`json.JSONDecodeError` — a real exception, so nothing crashed silently, but
its message (`"Expecting value: line 1 column 1 (char 0)"`) never names
`schema_path`. Both of this function's other two failure modes (missing
file, missing `properties.schema_version.const`) are caught and re-raised
naming the resolved path; the JSON-decode step was the one link in the
chain that didn't meet the module's own standard. Caught explicitly and
re-raised as `ValueError` naming the schema filename and the resolved path,
matching the others — a maintainer debugging a broken schema file sees the
same kind of message regardless of which of the three ways it broke.

## WHY the Regression Guard Is a Source Scan, Not a Value Comparison

An earlier test plan asserted "each renderer's emitted value equals its
schema's declared value" — that assertion was rejected at the test-plan
gate because it passes today, against the literal-emitting code, since both
sides already happen to read `"1"`/`"2"`/`"1"`. It falsifies nothing. The
real coverage is `tests/test_035_wire_version.py`'s per-renderer tests,
which drive each renderer's own emission path against a scratch schema
whose declared version is deliberately NOT today's value — those fail
against the literal-emitting code and pass once it reads
`wire_schema_version()`. `test_no_renderer_hardcodes_schema_version` in
`tests/test_035_wire_shape.py` is a second, different check: once the
literal is gone, "the renderer's own code bumps schema_version
independently of its schema" is no longer a state the renderer's source can
even be in, so no runtime assertion can exercise that failure — there is
nothing left to run. Scanning the renderer source files for a reintroduced
`"schema_version": "..."` literal is the only thing left that a regression
in this direction can still trip. It is a guard against reintroduction, not
evidence the property holds today.
