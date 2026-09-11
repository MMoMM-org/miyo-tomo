# version: 0.1.0
"""wire_snapshot_parity.py — The snapshot-vs-upstream REPORT for a vendored
consumer copy (spec 035 T2.4, generalised for T4.2's three vendored copies).

ADR-7 names two DIFFERENT comparisons between a published wire schema and a
consumer's copy of it — conflating them produces a permanently flaky test
(see docs/tomo/scripts/lib/wire_snapshot_parity.md):

  - OUR schema <-> the COMMITTED vendored copy (`tomo/schemas/hashi-*`):
    "does the consumer accept what we emit?" Offline, hermetic,
    deterministic — the committed copy never moves on its own.
  - the COMMITTED vendored copy <-> LIVE upstream: "is our copy stale?"
    Needs the network, and skips (never fails) when it is unreachable.

`snapshot_parity_delta` runs EITHER comparison — it is symmetric in what it
is handed, not in which direction its caller reads the result (see its own
docstring for the `recorded`/`observed` convention). `render_snapshot_
parity_report` renders the result of one or many such comparisons. Neither
function is a gate: this module is a REPORT (ADR-7) — a vendored copy is
*supposed* to lag ours between a cross-repo handoff and the consumer's
confirmation, so nothing here may fail a build over a delta.

Moved out of `tests/test_instruction_render_wire_hygiene.py` (T2.4 built it
there — correct for a single caller and a single document) into this
module (T4.2 code-quality carry-forward, 2026-09-10): three documents,
three callers, and production code must never import from a test module.
See `wire_gate.py`'s own module docstring for the identical move it made
one phase earlier, for the identical reason.
"""
from __future__ import annotations

from lib.wire_shape import describe_shape, diff_shapes

__all__ = ["snapshot_parity_delta", "render_snapshot_parity_report"]


def snapshot_parity_delta(recorded_schema: dict, observed_schema: dict) -> list:
    """The full-depth structural delta between two schema documents, via
    `describe_shape` + `diff_shapes`.

    `recorded_schema` / `observed_schema` follow `diff_shapes`'s own
    direction convention: `recorded` is the baseline, `observed` is the
    schema being compared against it. Both ADR-7 comparisons this module
    serves hold the COMMITTED VENDORED COPY as `recorded` — our own live
    schema is `observed` when checking "does the consumer accept what we
    emit", and a freshly fetched live document is `observed` when checking
    "is our copy stale". Keeping `recorded` fixed to the vendored copy in
    both calls means an `added_property` always reads as "present on the
    other side, not (yet) in the committed copy" regardless of which
    comparison produced it — do not swap the arguments at a call site.

    Deliberately UNCLASSIFIED: this never calls `classify`, so every
    returned `ShapeChange` carries `consumer_affecting: False` (see
    `wire_shape.py`'s `_change`). That is correct for BOTH comparisons —
    a vendored copy lagging ours between a handoff and confirmation
    obliges nobody, and ADR-7 is the reason this is a report at all, not a
    gate. Keep it unclassified if this function is ever touched again: a
    reader "fixing" the missing affecting/not-affecting marker would
    quietly re-introduce a gate's semantics into what ADR-7 requires to
    stay a report.
    """
    return diff_shapes(describe_shape(recorded_schema), describe_shape(observed_schema))


def render_snapshot_parity_report(results: list) -> str:
    """Human text for one or many `snapshot_parity_delta` results — a
    REPORT, never a gate (ADR-7): no caller may fail on this output, so it
    follows the same display-only contract `wire_gate.py`'s
    `render_wire_gate_report` and `wire_shape.py`'s `detail` field already
    carry — nothing parses this back.

    `results` is a list of `{"document": <name>, "changes": <ShapeChange
    list from snapshot_parity_delta>}` — the multi-document form of the
    single-document renderer T2.4 built (moved and generalised here for
    T4.2's three vendored copies), matching the reporting signature
    `wire_gate.py`'s `render_wire_gate_report(results)` already uses for
    the gate side rather than carrying two renderers that differ only in
    arity.

    A document with an empty `changes` list contributes nothing — an
    all-in-sync run renders to `""`, the same "pass silently" contract
    `render_wire_gate_report` uses for a passing wire.

    Two cosmetic fixes made while this rendering was being touched
    (neither is a defect, both were harder to read than necessary):
    a root-level change (`pointer == ""`) now renders as `(root)` instead
    of bare leading whitespace with no marker, and the line no longer
    repeats `kind` before `detail` — `detail` already names the kind in
    prose (e.g. "added property: up_source", "node removed: /$defs/x"), so
    printing both produced lines like "node_removed: node removed: /$defs/x".
    """
    lines = []
    for result in results:
        changes = result["changes"]
        if not changes:
            continue
        document = result["document"]
        lines.append(
            f"{document}: snapshot vs upstream delta "
            f"({len(changes)} change(s), report only — ADR-7)"
        )
        for change in changes:
            pointer = change["pointer"] if change["pointer"] else "(root)"
            lines.append(f"  {pointer} {change['detail']}")
    return "\n".join(lines)
