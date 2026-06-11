# WHY: suggestion-parser.py

> Rationale for decisions in `tomo/scripts/suggestion-parser.py`.
> The script parses an approved Tomo suggestions document (the markdown the user
> ticked `[x] Approved` on) and emits `parsed-suggestions.json` — the list of
> confirmed items + per-action decisions that `instruction-render.py` consumes.
> It also reconciles the Force-Atomic-Note (FAN) resolve doc back into the same
> confirmed-items stream.

## N atomic blocks per source — C3 (F-41, XDD 016, ADR-8)

WHY this matters: F-41 makes one inbox item able to produce N atomic notes (one
per conceptual thread). The reducer renders those N atomics as N independent
Accept blocks under a SINGLE `### SNN` source heading (OQ5 → per-item blocks,
source visible in each). The parser is the first downstream consumer that has to
honour that cardinality, and it had two distinct N=1 traps.

WHY an intra-section split, not just a dict→list change: `split_into_sections`
splits the document only on `### SNN` headings. Because the renderer keeps all N
atomic blocks under ONE heading, a naive `parse_section` would walk every line of
that section and let the LAST `**Suggested name:**` / `**Source:**` pair win —
silently dropping atomics 1..N-1. So the fix is two-layered: the parser must
first split a single section's lines into N per-block items (detected by the
repeated `**Source:**` / `**Suggested name:**` boundary markers the renderer
emits), each carrying the shared `source_path`. A single-block section (the
overwhelming common case) yields exactly one item, byte-identical to pre-F-41
output (CON-2 regression gate).

WHY `sections_by_stem` became `dict[str, list[dict]]`: even after the intra-
section split produces N items, the old `sections_by_stem[stem] = item`
assignment overwrote on the second item sharing a stem — the same silent N-1
loss one level up. Keying the map to a LIST and appending (`setdefault(stem,
[]).append(item)`) is the minimal change that preserves all N. `source_stem`
(ADR-4) is the grouping key: every atomic now carries its origin item's stem
explicitly, so the parser can group N atomics back to one source without
inferring it from the note path (which is ambiguous once N>1).

WHY a stem is lowercased before matching (`_stem_of`): `source_path` and
`source_stem` arrive from different producers (renderer-emitted markdown vs
analyst JSON) with inconsistent casing. Normalising to lowercase before using the
stem as a dict key prevents the same origin splitting into two buckets — which
would re-introduce a partial collapse by the back door.

## FAN resolve doc — N entries per source — C4 (F-41, ADR-8, T4.2)

WHY the same dict→list fix applies to the resolve doc: the Force-Atomic-Note
subflow (XDD 012 / F-33) lets the user tick "Force Atomic Note" on a log_entry
the analyst judged sub-worthy. When that source is multi-thread, the resolve doc
now carries N atomic proposals under one heading — exactly the same layout as the
primary suggestions doc. `resolve_sections_by_stem` had the identical scalar-
overwrite trap (`resolve_sections_by_stem[stem] = item`) and gets the identical
fix: `dict[str, list[dict]]`, append, and the Force-Atomic reconciliation loop
iterates the list rather than reading a single `.get(stem)` scalar.

WHY this is a separate collapse point from C3 (not "fixed for free"): the primary
doc and the resolve doc are parsed by two different code paths over two different
input files. Fixing the primary path leaves the FAN path silently dropping
threads 2..N — exactly the bug the C3/C4 split in the survey caught. Both paths
must promote every not-already-confirmed block per stem, so the
confirmed-items stream can contain multiple entries sharing one `source_path`;
downstream (render) keys per-entry, never per-stem.

## Version 0.10.0

WHY: Bumped for the F-41 C3/C4 cardinality changes (intra-section split,
`sections_by_stem` / `resolve_sections_by_stem` → `dict[str, list[dict]]`, FAN
resolve N-entry parsing). `update-tomo.sh` skips unchanged versions silently —
the bump is required for the edit to ship to the Docker instance.
