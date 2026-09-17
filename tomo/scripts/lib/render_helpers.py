# version: 0.3.1
"""render_helpers.py — pure, cross-module primitives for instruction rendering.

Extracted from instruction-render.py (#42, D-07 Constitution L2 split). Holds the
tiny stem helpers used by every render submodule (render_actions, render_md,
render_resolve) and the orchestrator. Pure string ops — no Kado, no I/O, no
dependency on any other render module (keeps the module graph a DAG).
"""
from __future__ import annotations


def _stem(path: str | None) -> str:
    """Extract the bare note stem from a path (no folder, no .md)."""
    if not path:
        return ""
    p = path.rsplit("/", 1)[-1]
    if p.endswith(".md"):
        p = p[:-3]
    return p


def _moc_stem(name: str | None) -> str:
    """Normalise a MOC reference to its bare stem."""
    return _stem(name)


def resolve_source_path(
    item_key: str | None, source_path: str | None, inbox_path: str
) -> str:
    """The vault-relative path of an inbox item's source note.

    `item_key` IS that path, verbatim (spec 034 ADR-1), so when it is present
    there is nothing to derive. `source_path` is display text (ADR-2) — a bare
    filename — and reconstructing a path from it can only assume the inbox
    root. That assumption held while discovery was `depth=1`; once discovery
    became recursive it stopped holding, which is why the key exists.

    The reconstruction remains as the fallback so a suggestions document
    produced before spec 034 (every item of which did sit at the inbox root)
    still renders. It is a fallback, never a preference.

    Returns "" when there is nothing to address.
    """
    if item_key:
        return item_key
    if not source_path:
        return ""
    if "/" in source_path:
        return source_path
    return f"{(inbox_path or '').rstrip('/')}/{source_path}"


def resolve_sibling_path(
    item_key: str | None, basename: str | None, inbox_path: str
) -> str:
    """The vault-relative path of a file sitting beside an item's source note.

    Used for the audio peer of a voice transcript. Triage pairs audio to a note
    by containing folder plus stem (`inbox-triage.check_audio`), so the peer is
    a sibling of the note by construction — its folder is the note's folder,
    not the inbox root.

    Falls back to the inbox root only when no key is available, matching
    `resolve_source_path`.
    """
    if not basename:
        return ""
    if "/" in basename:
        return basename
    folder = inbox_path
    if item_key and "/" in item_key:
        folder = item_key.rsplit("/", 1)[0]
    return f"{(folder or '').rstrip('/')}/{basename}"


# ── Withdrawal cause attribution (spec 036 T4.3) ─────────────────────────────
# Grouped here as a cohesion choice, not because the DAG forces it for all
# three functions: render_actions.py imports FROM render_md.py (`bare_stem`,
# one-directional), and render_md.py imports nothing from render_actions.py.
# The one real cycle constraint is narrower — `describe_withdrawal_cause` is
# the only one of the three render_md.py itself calls (its markdown "##
# Skipped" section), so it cannot live in render_actions.py: render_md.py
# would then have to import it back from render_actions.py, completing the
# cycle render_md -> render_actions -> render_md. `attribute_withdrawal_
# causes` and `build_delete_withdrawal_reports` are consumed solely by
# instruction-render.py, which already imports from both render_actions.py
# and render_md.py without cycle risk, so either of them could equally live
# in render_actions.py next to `withdraw_unjustified_deletes`. Keeping all
# three together here is a cohesion choice — one module owns the whole
# withdrawal-cause join — not an unavoidable one; see
# docs/tomo/scripts/lib/render_helpers.md for the full rationale.

WITHDRAWAL_GUARDS = (
    "validate_destinations",
    "suppress_moves_for_unfiled_attachments",
    "filter_unresolvable_moc_links",
    "filter_missing_daily_notes",
    "filter_unappliable_relationships",
)


def attribute_withdrawal_causes(
    withdrawal: dict, drop_sources: dict[str, list[str]]
) -> list[dict]:
    """Join one `withdraw_unjustified_deletes` record to the guard(s) that
    dropped its missing id(s) (spec 036 T4.3, PRD F2-AC4 / F6-AC1).

    `drop_sources` maps each of the five action-dropping guards' name (see
    `WITHDRAWAL_GUARDS`) to the ids it removed this run. The five are
    structurally disjoint — each governs its own action kind (SDD ADR-2), so
    an id dropped by one guard is never also dropped by another; this
    function does not need to detect or resolve a collision.

    Returns one "cause" dict per missing id, `{"missing_id": ..., "guard":
    ...}`:

    - `depends_on_declared is False` -> a single cause `{"missing_id": None,
      "guard": None}`. The delete never named a justification, so there is
      nothing to join on — distinct wording from an unresolved join below,
      which DID name something.
    - a missing id present in exactly one guard's dropped-id list -> `guard`
      names that guard.
    - a missing id present in NO guard's list -> `guard: "unattributed"`.
      Structurally unreachable today: `withdraw_unjustified_deletes` runs
      after all five guards (SDD ADR-2), so every id it can name either was
      dropped by one of them or never existed in the set at all. Kept as a
      tripwire against a future sixth drop site that removes an action
      without reporting what it removed — a withdrawal must never go
      silently unexplained.
    """
    if not withdrawal.get("depends_on_declared", True):
        return [{"missing_id": None, "guard": None}]
    id_to_guard: dict[str, str] = {}
    for guard, ids in drop_sources.items():
        for dropped_id in ids:
            id_to_guard.setdefault(dropped_id, guard)
    return [
        {
            "missing_id": missing_id,
            "guard": id_to_guard.get(missing_id, "unattributed"),
        }
        for missing_id in withdrawal.get("missing_dependencies") or []
    ]


def describe_withdrawal_cause(cause: dict) -> str:
    """Render one `attribute_withdrawal_causes` entry as a metadata-only phrase.

    Shared by stderr (instruction-render.py) and markdown (render_md.py) so
    the two surfaces never drift into different wording for the same cause
    (spec 036 T4.3, PRD F6-AC1). Reads only the id and guard name this module
    already carries — never note content (Constitution L2).
    """
    guard = cause.get("guard")
    if guard is None:
        return "no dependency was ever declared (depends_on missing)"
    if guard == "unattributed":
        return (
            f"missing id {cause.get('missing_id')} (cause unattributed — no "
            "guard reported dropping it)"
        )
    return f"missing id {cause.get('missing_id')} (dropped by {guard})"


def build_delete_withdrawal_reports(
    withdrawn_deletes: list[dict], drop_sources: dict[str, list[str]]
) -> list[dict]:
    """Shape `withdraw_unjustified_deletes`' output for the three report
    surfaces — stderr, the `tomo` block, markdown (spec 036 T4.3).

    One record per withdrawal: id, action kind, source_path, the builder's
    own reason template (never re-derived or re-worded — Constitution L2 /
    PRD F6-AC1), and `causes` from `attribute_withdrawal_causes`.
    """
    return [
        {
            "id": w.get("id"),
            "action": "delete_source",
            "source_path": w.get("source_path"),
            "reason": w.get("reason"),
            "causes": attribute_withdrawal_causes(w, drop_sources),
        }
        for w in withdrawn_deletes
    ]
