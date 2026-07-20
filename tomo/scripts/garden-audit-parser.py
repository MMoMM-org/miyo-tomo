#!/usr/bin/env python3
# version: 0.1.1
"""Pass-2 rebuild-from-wire for garden-audit (ADR-4 / ADR-026).

Mirrors suggestion-parser.py's wire contract:
  load_changed_wire(path) → wire dict iff present + schema_version=="1" + edited,
                            else None (markdown stays authoritative).
  build_from_wire(wire)   → {"run_id", "generated", "profile", "actions":[...]}

Action mapping (ADR-5):
  unparented / orphan   (selected=True)  → link_to_moc + add_relationship up::
  broken_up repoint     (selected=True, action="add_relationship") → add_relationship up::
  broken_up removal     (selected=True, action="edit_note_text")   → edit_note_text (replace="")
  dead_link             (selected=True)  → edit_note_text
  duplicate_stem        advisory — no action ever
  stale_moc             advisory — no action ever
  selected=False        skipped — no action

Unchanged wire (digest matches) → None; markdown path is byte-authoritative.
Unknown schema_version / unreadable file → None + stderr warning.
"""
import json
import sys

from lib.render_md import compute_payload_digest


# ── Wire load ────────────────────────────────────────────────────────────────

def load_changed_wire(path: str | None) -> dict | None:
    """Return the garden-audit wire iff present, parseable, schema_version=="1", AND edited.

    Edited = the recomputed digest over the editable payload differs from the
    stored emit_digest. Unchanged / absent / unreadable / unknown-version → None.
    Mirrors suggestion-parser.load_changed_wire (ADR-026).
    """
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            wire = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"warning: garden-audit-wire ignored ({exc}); using markdown",
            file=sys.stderr,
        )
        return None
    if not isinstance(wire, dict):
        return None
    version = wire.get("schema_version")
    if version != "1":
        print(
            f"warning: garden-audit-wire schema_version {version!r} != '1' — "
            "ignored, using markdown",
            file=sys.stderr,
        )
        return None
    stored = wire.get("emit_digest")
    if stored and compute_payload_digest(wire) == stored:
        return None  # unchanged — markdown stays authoritative
    return wire


# ── ID counter ───────────────────────────────────────────────────────────────

def _next_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"A{counter[0]:02d}"


# ── Action builders ───────────────────────────────────────────────────────────

def _filing_actions(finding: dict, counter: list[int]) -> list[dict]:
    """Emit link_to_moc + add_relationship up:: for unparented/orphan findings.

    Filing = placing a note under a MOC: one bullet in the MOC (link_to_moc)
    and one up:: line in the note (add_relationship). ADR-5: both actions are
    required together; mirrors emit_up_preservation_actions pattern.
    """
    target = finding["target"]
    path = target["path"]
    stem = target.get("stem") or path.rsplit("/", 1)[-1].removesuffix(".md")
    detail = finding.get("detail", {})
    mocs = detail.get("candidate_mocs") or []
    # Use best candidate (highest score); fall back to empty string if none present.
    best_moc_path = mocs[0]["target_moc"] if mocs else ""
    best_moc_stem = best_moc_path.rsplit("/", 1)[-1].removesuffix(".md") if best_moc_path else ""

    link_action = {
        "id": _next_id(counter),
        "action": "link_to_moc",
        "target_moc": best_moc_stem,
        "target_moc_path": best_moc_path if best_moc_path else None,
        "anchor": {"type": "callout", "value": None},
        "placement": "after",
        "line_to_add": f"- [[{stem}]]",
        "source_note_title": stem,
        "applied": False,
    }
    rel_action = {
        "id": _next_id(counter),
        "action": "add_relationship",
        "target_moc": best_moc_stem,
        "target_moc_path": path,
        "marker": "up::",
        "line": f"up:: [[{best_moc_stem}]]",
        "source_note_title": None,
        "applied": False,
    }
    return [link_action, rel_action]


def _broken_up_repoint_action(finding: dict, counter: list[int]) -> list[dict]:
    """Emit add_relationship up:: for a broken-up repoint (action=add_relationship).

    The wire carries action="add_relationship" when the user wants to repoint the
    broken up:: to a valid MOC (as opposed to removing it). The target MOC stem
    must be derivable from the finding's candidate_mocs or detail. Since a repoint
    requires a live target that the user selects during review, we emit the action
    with the path as the note to modify and a placeholder line; the agent fills the
    MOC stem from the wire context.
    """
    target = finding["target"]
    path = target["path"]
    up_target = finding.get("detail", {}).get("up_target", "")
    # Emit the repair line — the user has selected this, so we set up:: to the
    # target as specified in detail.up_target (the broken old target that needs
    # repointing; the conductor/agent replaces with the correct MOC stem before apply).
    return [{
        "id": _next_id(counter),
        "action": "add_relationship",
        "target_moc": up_target,
        "target_moc_path": path,
        "marker": "up::",
        "line": f"up:: [[{up_target}]]",
        "source_note_title": None,
        "applied": False,
    }]


def _broken_up_removal_action(finding: dict, counter: list[int]) -> list[dict]:
    """Emit edit_note_text to remove a broken up:: line (action=edit_note_text).

    match = the full "up:: [[Broken Stem]]" line; replace="" removes it and
    the now-empty line (per edit_note_text semantics). ADR-3 / ADR-5 Rule 7.
    """
    target = finding["target"]
    path = target["path"]
    up_target = finding.get("detail", {}).get("up_target", "")
    return [{
        "id": _next_id(counter),
        "action": "edit_note_text",
        "path": path,
        "match": f"up:: [[{up_target}]]",
        "replace": "",
        "occurrence": "first",
        "applied": False,
    }]


def _dead_link_action(finding: dict, counter: list[int]) -> list[dict]:
    """Emit edit_note_text for a dead wikilink (fix or remove). ADR-3.

    match = [[dead_target]] — dead_target is the raw wikilink stem from graph_audit;
    we wrap it in [[ ]] to match the wikilink as it appears in the note body.
    replace = decision.get("replace", "") — the user sets this in the wire to
    specify a replacement target (e.g. "[[New Note]]"). Empty string = remove intent.
    occurrence = "all" removes every instance (dead links are typically repeated).
    """
    target = finding["target"]
    path = target["path"]
    detail = finding.get("detail", {})
    decision = finding.get("decision", {})
    dead_target = detail.get("dead_target", "")
    replace_target = decision.get("replace", "")
    return [{
        "id": _next_id(counter),
        "action": "edit_note_text",
        "path": path,
        "match": f"[[{dead_target}]]",
        "replace": replace_target,
        "occurrence": "all",
        "applied": False,
    }]


# ── Core rebuild ─────────────────────────────────────────────────────────────

def build_from_wire(wire: dict) -> dict:
    """Reconstruct confirmed-fix actions from an edited garden-audit wire alone.

    ADR-4 JSON-only path: when load_changed_wire returns a wire, Pass-2 builds
    the full action list from the wire without re-reading the markdown report.

    Returns:
        {
            "run_id": str,
            "generated": str,
            "profile": str | None,
            "actions": [...]   # ordered action list, IDs A01, A02, …
        }
    """
    counter = [0]
    actions: list[dict] = []

    for finding in wire.get("findings") or []:
        # Advisory findings (fixable=False) never produce actions.
        if not finding.get("fixable"):
            continue

        decision = finding.get("decision") or {}
        if not decision.get("selected"):
            continue  # user deselected — skip

        check = finding.get("check")
        action_name = decision.get("action")

        if check in ("unparented", "orphan"):
            # Filing: link_to_moc + add_relationship up::
            actions.extend(_filing_actions(finding, counter))

        elif check == "broken_up":
            if action_name == "add_relationship":
                actions.extend(_broken_up_repoint_action(finding, counter))
            elif action_name == "edit_note_text":
                actions.extend(_broken_up_removal_action(finding, counter))
            # Unknown action name → skip silently (forward-compat)

        elif check == "dead_link":
            actions.extend(_dead_link_action(finding, counter))

        # duplicate_stem / stale_moc and anything else → advisory, no action

    return {
        "run_id": wire.get("run_id", ""),
        "generated": wire.get("generated", ""),
        "profile": wire.get("profile"),
        "actions": actions,
    }


# ── Main (passthrough invocation) ────────────────────────────────────────────

def main() -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Rebuild garden-audit confirmed-fix actions from an edited wire."
    )
    p.add_argument("--wire", required=True, help="Path to garden-audit-wire.json")
    p.add_argument("--output", required=True, help="Output JSON path for confirmed actions")
    args = p.parse_args()

    wire = load_changed_wire(args.wire)
    if wire is None:
        print(
            "garden-audit-parser: wire unchanged or unreadable — "
            "markdown path is authoritative; no action output written.",
            file=sys.stderr,
        )
        return 0

    result = build_from_wire(wire)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(
        f"garden-audit-parser: {len(result['actions'])} actions → {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
