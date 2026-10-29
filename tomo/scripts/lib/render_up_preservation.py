# version: 0.1.0
"""render_up_preservation.py — Rule 4.x up::/related:: preservation actions.

Split out of render_actions.py (#216, Constitution L2 file size). Owns the
add_relationship actions that keep a child note's existing parent link when a
new MOC claims it (Rule 4.x, F-43 T4.2), and the Tomo-side aggregation of
peer-marker (related::) lines per target note. Reads the vault through the
Kado client passed in; builds no other action kind.
"""
from __future__ import annotations

import functools
import re
import sys

from lib.kado_client import KadoError
from lib.render_emit import _next_id
from lib.up_parse import up_marker_re as _up_marker_re
from lib.supporting_items import parse_supporting_items as _parse_supporting_items


# Matches the first ``<peer_marker>`` line in a note body (Rule 4.x). MULTILINE
# so ``^`` anchors to each line start. The marker literal is injected from the
# active profile (spec 028 T3.2); the default builders below preserve the
# historical ``related::`` pattern. The ``<parent_marker> [[Target]]`` counterpart
# is imported as ``_up_marker_re`` from lib.up_parse (SSoT).
@functools.lru_cache(maxsize=None)
def _related_marker_re(peer_marker: str) -> re.Pattern:
    return re.compile(rf"^[\s>\-]*{re.escape(peer_marker)}\s*(.*)", re.MULTILINE)


_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _extract_existing_related(content: str, peer_marker: str = "related::") -> list[str]:
    """Extract existing peer-marker wikilink targets from note content."""
    m = _related_marker_re(peer_marker).search(content)
    if not m:
        return []
    return [wl.group(1).strip() for wl in _WIKILINK_RE.finditer(m.group(1))]


def _aggregate_related_actions(
    actions: list[dict], kado_client, peer_marker: str = "related::",
) -> list[dict]:
    """Merge peer-marker actions per target note with existing vault values.

    Per contract (docs/instructions-json.md §882-886), Tomo reads the
    existing peer-marker line and emits one combined action per target.
    """
    if kado_client is None:
        return actions

    # Collect peer-marker actions grouped by target_moc_path
    related_by_target: dict[str, list[dict]] = {}
    non_related: list[dict] = []
    for a in actions:
        if a.get("action") == "add_relationship" and a.get("marker") == peer_marker:
            path = a["target_moc_path"]
            related_by_target.setdefault(path, []).append(a)
        else:
            non_related.append(a)

    if not related_by_target:
        return actions

    merged: list[dict] = []
    for path, rel_actions in related_by_target.items():
        # Read existing peer-marker line from vault
        try:
            note = kado_client.read_note(path)
            content = note.get("content", "") if isinstance(note, dict) else ""
            existing = _extract_existing_related(content, peer_marker)
        except Exception:
            existing = []

        # Collect new stems from actions
        new_stems = []
        for a in rel_actions:
            for wl in _WIKILINK_RE.finditer(a.get("line", "")):
                stem = wl.group(1).strip()
                if stem and stem not in existing and stem not in new_stems:
                    new_stems.append(stem)

        all_stems = existing + new_stems
        if not all_stems:
            continue

        combined_line = f"{peer_marker} " + ", ".join(f"[[{s}]]" for s in all_stems)
        # Keep the first action as template, update line
        merged_action = dict(rel_actions[0])
        merged_action["line"] = combined_line
        merged.append(merged_action)

    # Reassemble: non-related actions + merged related actions (in original order)
    result = []
    seen_targets: set[str] = set()
    for a in actions:
        if a.get("action") == "add_relationship" and a.get("marker") == peer_marker:
            path = a["target_moc_path"]
            if path not in seen_targets:
                seen_targets.add(path)
                # Find the merged action for this target
                for m in merged:
                    if m["target_moc_path"] == path:
                        result.append(m)
                        break
        else:
            result.append(a)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Rule 4.x: per-child existing-up:: preservation (F-43 T4.2)
# ──────────────────────────────────────────────────────────────────────────────


def extract_first_up_marker(content: str, parent_marker: str = "up::") -> str | None:
    """Return the first ``<parent_marker> [[Target]]`` target from note content, or None.

    Searches the note body (frontmatter stripped) for the first line that
    matches the up:: wikilink pattern.  Frontmatter is excluded to prevent
    false positives when a user's YAML frontmatter contains an ``up::`` key.

    Stripping logic: if content begins with ``---\n`` and contains a closing
    ``---`` on its own line, the body starts after that closing fence.
    Otherwise the full content is searched.

    This is a self-contained inline-only `up::` extractor for the renderer.
    NOTE (spec 021 T2.2): moc-discovery and moc-tree-builder migrated their
    `up` resolution to lib/up_parse.parse_up_from_content (dual-up: inline +
    frontmatter). instruction-render was intentionally NOT retrofitted in spec
    021 — it deliberately strips frontmatter and matches inline `up::` ONLY
    (see test_extract_first_up_marker_ignores_frontmatter_up). Migrating it to
    the dual-up SSoT is a separate change, out of T2.2 scope.

    Multiple ``up::`` lines on the same note → only the first is returned;
    callers are responsible for warning when that case is detected.
    """
    if not content:
        return None
    # Strip YAML frontmatter before regex search to avoid false positives.
    body = content
    if content.startswith("---\n"):
        closing = content.find("\n---", 4)
        if closing != -1:
            body = content[closing + 4:]  # skip past closing ---\n
    match = _up_marker_re(parent_marker).search(body)
    if not match:
        return None
    target = match.group(1).strip()
    return target or None


def _make_add_rel(
    counter: list[int],
    target_note_path: str,
    marker: str,
    target_stem: str,
) -> dict:
    """Build a single add_relationship action dict.

    ``target_moc_path`` holds the child note's vault path (the note being
    modified).  ``marker`` is the dataview field (``up::`` or ``related::``).
    ``line`` is the pre-formatted replacement line that Hashi will write.
    """
    return {
        "id": _next_id(counter),
        "action": "add_relationship",
        "target_moc_path": target_note_path,
        "marker": marker,
        "line": f"{marker} [[{target_stem}]]",
        "source_note_title": None,
        "applied": None,
    }


def emit_up_preservation_actions(
    child_stem: str,
    new_moc_stem: str,
    override_flag: bool,
    kado_client,
    counter: list[int],
    parent_marker: str = "up::",
    peer_marker: str = "related::",
) -> list[dict]:
    """For one child, emit 1 or 2 add_relationship actions per Rule 4.x.

    Implements SDD Example 1 verbatim.  Called once per accepted child of a
    ConfirmedMOCProposal.  ``override_flag`` is the group-level up::-handling
    override toggle from the proposal doc.

    Rules:
      4.1 / 4.4 — no existing up:: → up:: <newMOC> (Override is a no-op here)
      4.2        — unchecked Override + valid existing up:: <X> →
                   up:: <newMOC> + related:: <X>
      4.5        — checked Override + valid existing up:: <X> →
                   related:: <newMOC> (existing up:: kept, not touched)
      4.3        — retired: an existing up:: whose target is not a MOC or
                   does not exist follows 4.2 / 4.5 like a valid one

    Edge cases:
      - Self-link: if existing_up_target == new_moc_stem → no actions emitted.
      - Child missing: KadoError(NOT_FOUND) on resolve → one action with
        applied=False and error="child-missing"; does NOT raise.
      - Multiple up:: lines: extract_first_up_marker returns the first; callers
        may log a warning for multi-up:: notes.
    """
    try:
        child_path = kado_client.resolve_stem_to_path(child_stem)
    except KadoError:
        child_path = None

    if child_path is None:
        return [{
            "id": _next_id(counter),
            "action": "add_relationship",
            "target_moc_path": child_stem,
            "marker": parent_marker,
            "line": f"{parent_marker} [[{new_moc_stem}]]",
            "applied": False,
            "error": "child-missing",
        }]

    if not child_path.endswith(".md"):
        print(
            f"  [warn] {child_stem!r} resolved to non-markdown: {child_path} — skipping",
            file=sys.stderr,
        )
        return [{
            "id": _next_id(counter),
            "action": "add_relationship",
            "target_moc_path": child_path,
            "marker": parent_marker,
            "line": f"{parent_marker} [[{new_moc_stem}]]",
            "applied": False,
            "error": "non-markdown-asset",
        }]

    note = kado_client.read_note(child_path)
    content = note.get("content", "") if isinstance(note, dict) else ""
    existing_up_target = extract_first_up_marker(content, parent_marker)

    actions: list[dict] = []

    if existing_up_target is None:
        if override_flag:
            # Override checked + no existing parent link → peer marker (user chose peer for this MOC)
            actions.append(_make_add_rel(counter, child_path, peer_marker, new_moc_stem))
        else:
            # No existing parent link + no override → parent marker (new MOC becomes primary parent)
            actions.append(_make_add_rel(counter, child_path, parent_marker, new_moc_stem))
    elif existing_up_target == new_moc_stem:
        # Self-link guard: existing parent link already points to the new MOC → no-op
        pass
    elif override_flag:
        # Rule 4.5 — keep existing parent link, new MOC becomes peer
        actions.append(_make_add_rel(counter, child_path, peer_marker, new_moc_stem))
    else:
        # Rule 4.2 — new MOC becomes parent, existing target moves to peer
        actions.append(_make_add_rel(counter, child_path, parent_marker, new_moc_stem))
        actions.append(_make_add_rel(counter, child_path, peer_marker, existing_up_target))

    return actions


def _build_up_preservation_actions(
    manifest: list[dict],
    kado_client,
    counter: list[int],
    parent_marker: str = "up::",
    peer_marker: str = "related::",
) -> list[dict]:
    """Emit add_relationship actions for existing-up:: preservation on MOC children.

    Iterates create_moc manifest items that originate from a ConfirmedMOCProposal.
    The conservative gate: the item must carry BOTH ``supporting_items`` (the
    accepted-children stems, comma-joined) AND ``override_preserve_existing_up``
    (presence flag — value may be True or False).  Items that lack either field
    were produced by the regular inbox flow and are skipped.

    For each qualifying create_moc item, dispatches to
    ``emit_up_preservation_actions`` once per child stem parsed from
    ``supporting_items``.  Returned actions are appended in child order.

    Called by ``build_actions`` after create_moc but before link_to_moc so
    the up:: actions on the children are present in the ordered output.
    """
    if kado_client is None:
        return []
    out: list[dict] = []
    for m in manifest:
        if m.get("action") != "create_moc":
            continue
        if not m.get("supporting_items"):
            continue
        if "override_preserve_existing_up" not in m:
            # Inbox-flow create_moc items lack this field → skip preservation.
            continue
        new_moc_stem = m.get("title", "")
        override_flag = bool(m.get("override_preserve_existing_up", False))
        for child_stem in _parse_supporting_items(m.get("supporting_items")):
            out.extend(
                emit_up_preservation_actions(
                    child_stem, new_moc_stem, override_flag, kado_client, counter,
                    parent_marker=parent_marker, peer_marker=peer_marker,
                )
            )
    return out
