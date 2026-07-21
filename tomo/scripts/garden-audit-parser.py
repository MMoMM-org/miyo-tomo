#!/usr/bin/env python3
# version: 0.2.2
"""Pass-2 reader for garden-audit (ADR-4 / ADR-026).

Pure reader: markdown report (authoritative) + optional wire override → a
``{"confirmed_items": [...]}`` envelope of SEMANTIC items (not pre-built
actions). instruction-render.py turns confirmed_items into the action list via
render_actions.build_garden_audit_actions (which reuses the shared
_build_edit_note_text_actions builder). This mirrors suggestion-parser.py.

CLI (mirrors suggestion-parser.py):
  --file <md>   REQUIRED — the human-reviewed markdown report (byte-authoritative)
  --wire <json> OPTIONAL — vault-published wire sibling; when present AND edited
                (embedded emit_digest no longer matches), it overrides the
                markdown decisions (build_from_wire). Unchanged/absent/unreadable
                → markdown stays authoritative.
  result JSON → STDOUT.

confirmed_item shape (per fixable finding the user kept):
  {
    "id", "garden_check", "garden_action",
    "path", "stem",
    # edit_note_text (dead_link fix/remove, broken_up removal):
    "match", "replace", "occurrence",
    # add_relationship (broken_up repoint, filing up::):
    "up_line",
    # file_note (unparented/orphan filing):
    "target_moc", "target_moc_path",
  }

garden_action ∈ {edit_note_text, add_relationship, file_note}.
Advisory findings (duplicate_stem, stale_moc) never produce a confirmed_item.
"""
import json
import re
import sys

from lib.render_md import bare_stem, compute_payload_digest, up_line


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


# ── up:: value normalisation (shared by markdown + wire paths) ────────────────

# up_line() / bare_stem() are the load-bearing round-trip contract shared with
# garden-audit-render; both import them from lib.render_md so they cannot diverge.


# ── Markdown parse (authoritative) ────────────────────────────────────────────

# Per-finding structural comment the renderer emits, e.g.:
#   <!-- garden-audit id="F01" check="dead_link" path="Notes/N.md"
#        match="[[Old]]" occurrence="all" target_moc="Writing MOC"
#        target_moc_path="MOCs/Writing MOC.md" -->
RE_FINDING_HEADER = re.compile(r"^###\s+(F\d+)\b")
RE_GA_COMMENT = re.compile(r"<!--\s*garden-audit\s+(.*?)\s*-->", re.DOTALL)
RE_GA_COMMENT_ATTR = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')
RE_APPLY_CHECKED = re.compile(r"^\s*-\s+\[x\]\s*Apply\b", re.IGNORECASE | re.MULTILINE)
RE_APPLY_UNCHECKED = re.compile(r"^\s*-\s+\[\s\]\s*Apply\b", re.IGNORECASE | re.MULTILINE)
RE_REPLACE_FIELD = re.compile(
    r"^\s*-?\s*\*\*Replace with:\*\*\s*(.*)", re.IGNORECASE | re.MULTILINE
)
RE_REPOINT_FIELD = re.compile(
    r"^\s*-?\s*\*\*Repoint to:\*\*\s*(.*)", re.IGNORECASE | re.MULTILINE
)

# Frontmatter (flat key: value) for run_id / generated / profile.
RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_ga_comment(text: str) -> dict[str, str]:
    """Extract the ``garden-audit`` structural comment attributes from a block."""
    m = RE_GA_COMMENT.search(text)
    if not m:
        return {}
    return {k: v.replace('\\"', '"') for k, v in RE_GA_COMMENT_ATTR.findall(m.group(1))}


def _field_value(text: str, regex: re.Pattern) -> str | None:
    """Return the value of a `**Field:**` line (hint stripped), or None if absent."""
    m = regex.search(text)
    if not m:
        return None
    val = m.group(1)
    # Drop the trailing "← ..." editor hint if present.
    if "←" in val:
        val = val.split("←", 1)[0]
    return val.strip()


def _wikilink_target(val: str) -> str:
    """Bare target from a possibly-wikilinked user value: `[[X]]` / `X` → `X`.

    An empty `[[]]` (the pre-filled placeholder the user left untouched) or a
    blank string both yield "".
    """
    s = (val or "").strip()
    if not s:
        return ""
    m = re.search(r"\[\[([^\]]*)\]\]", s)
    if m is not None:
        return m.group(1).strip()
    return s


def _extract_frontmatter(md_text: str) -> dict[str, str]:
    """Flat key→value from a leading YAML frontmatter block (no full YAML parse)."""
    m = RE_FRONTMATTER.match(md_text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def _split_finding_blocks(md_text: str) -> list[tuple[str, list[str]]]:
    """Split the report into ``(finding_id, block_lines)`` per `### Fxx` header."""
    blocks: list[tuple[str, list[str]]] = []
    cur_id: str | None = None
    cur_lines: list[str] = []
    for line in md_text.splitlines():
        m = RE_FINDING_HEADER.match(line)
        if m:
            if cur_id is not None:
                blocks.append((cur_id, cur_lines))
            cur_id = m.group(1)
            cur_lines = [line]
        elif cur_id is not None:
            cur_lines.append(line)
    if cur_id is not None:
        blocks.append((cur_id, cur_lines))
    return blocks


def _confirmed_item_from_block(fid: str, block: str) -> dict | None:
    """Build one confirmed_item from a `### Fxx` block, or None to skip.

    Skips when: no structural comment (advisory / non-fixable finding), or the
    Apply checkbox is unticked (user opted out).
    """
    attrs = _parse_ga_comment(block)
    if not attrs:
        return None  # advisory / read-only finding — no fix

    # Apply gate: ticked → include, unticked → skip. A finding with a structural
    # comment but no Apply line at all defaults to included (fixable + present).
    if RE_APPLY_UNCHECKED.search(block) and not RE_APPLY_CHECKED.search(block):
        return None

    check = attrs.get("check", "")
    path = attrs.get("path", "")
    stem = attrs.get("stem") or bare_stem(path)

    if check == "dead_link":
        replace_raw = _field_value(block, RE_REPLACE_FIELD)
        target = _wikilink_target(replace_raw) if replace_raw is not None else ""
        replace = f"[[{target}]]" if target else ""
        return {
            "id": fid,
            "garden_check": check,
            "garden_action": "edit_note_text",
            "path": path,
            "stem": stem,
            "match": attrs.get("match", ""),
            "replace": replace,
            "occurrence": attrs.get("occurrence", "all"),
        }

    if check == "broken_up":
        repoint_raw = _field_value(block, RE_REPOINT_FIELD)
        repoint = _wikilink_target(repoint_raw) if repoint_raw is not None else ""
        if repoint:
            # Non-empty Repoint target → repair the up:: to the chosen MOC.
            return {
                "id": fid,
                "garden_check": check,
                "garden_action": "add_relationship",
                "path": path,
                "stem": stem,
                "up_line": up_line(repoint),
            }
        # Empty / absent Repoint → remove the broken up:: line (edit_note_text).
        return {
            "id": fid,
            "garden_check": check,
            "garden_action": "edit_note_text",
            "path": path,
            "stem": stem,
            "match": attrs.get("match", ""),
            "replace": "",
            "occurrence": attrs.get("occurrence", "first"),
        }

    if check in ("unparented", "orphan"):
        target_moc = attrs.get("target_moc", "")
        target_moc_path = attrs.get("target_moc_path") or None
        if not target_moc:
            print(
                f"warning: garden-audit-parser: finding {fid!r} ({path!r}) is a "
                "filing fix but carries no target_moc — skipping (no MOC resolved)",
                file=sys.stderr,
            )
            return None
        return {
            "id": fid,
            "garden_check": check,
            "garden_action": "file_note",
            "path": path,
            "stem": stem,
            "target_moc": target_moc,
            "target_moc_path": target_moc_path,
        }

    return None  # unknown check — forward-compatible skip


def build_from_markdown(md_text: str) -> dict:
    """Read the human-reviewed markdown report → confirmed_items envelope.

    Markdown is byte-authoritative (Tomo never assumes Hashi is installed). Each
    ``### Fxx`` block carries a structural HTML comment (invisible in Obsidian
    reading view) describing the fix; the visible checkbox + Replace/Repoint
    fields carry the user's decision. Advisory findings have no comment → no item.
    """
    fm = _extract_frontmatter(md_text)
    confirmed: list[dict] = []
    for fid, lines in _split_finding_blocks(md_text):
        item = _confirmed_item_from_block(fid, "\n".join(lines))
        if item is not None:
            confirmed.append(item)
    return {
        "run_id": fm.get("run_id", ""),
        "generated": fm.get("generated", ""),
        "profile": fm.get("profile") or None,
        "confirmed_items": confirmed,
    }


# ── Wire rebuild (ADR-4 JSON-only override) ───────────────────────────────────

def build_from_wire(wire: dict) -> dict:
    """Reconstruct confirmed_items from an edited garden-audit wire alone.

    ADR-4 JSON-only path: when load_changed_wire returns a wire, Pass-2 builds
    the confirmed_items list from the wire without re-reading the markdown. Same
    envelope shape as build_from_markdown.
    """
    confirmed: list[dict] = []

    for finding in wire.get("findings") or []:
        # Advisory checks (duplicate_stem, stale_moc) never produce a fix.
        if not finding.get("fixable"):
            continue
        decision = finding.get("decision") or {}
        if not decision.get("selected"):
            continue  # user deselected — skip

        check = finding.get("check")
        fid = finding.get("id", "")
        target = finding.get("target") or {}
        path = target.get("path", "")
        stem = target.get("stem") or bare_stem(path)
        detail = finding.get("detail") or {}

        if check in ("unparented", "orphan"):
            mocs = detail.get("candidate_mocs") or []
            if not mocs:
                print(
                    f"warning: garden-audit-parser: finding {fid!r} ({path!r}) "
                    "selected for filing but has no candidate_mocs — skipping",
                    file=sys.stderr,
                )
                continue
            best = mocs[0].get("target_moc", "")
            confirmed.append({
                "id": fid,
                "garden_check": check,
                "garden_action": "file_note",
                "path": path,
                "stem": stem,
                "target_moc": bare_stem(best),
                "target_moc_path": best or None,
            })

        elif check == "broken_up":
            action_name = decision.get("action")
            up_target = detail.get("up_target", "")
            if action_name == "add_relationship":
                # Wire parity with the markdown "Repoint to:" field: a non-empty
                # decision.repoint is the user's chosen MOC — point up:: there,
                # NOT at the broken original. Empty → fall back to up_target.
                repoint = decision.get("repoint", "")
                target = repoint if repoint else up_target
                confirmed.append({
                    "id": fid,
                    "garden_check": check,
                    "garden_action": "add_relationship",
                    "path": path,
                    "stem": stem,
                    "up_line": up_line(target),
                })
            elif action_name == "edit_note_text":
                confirmed.append({
                    "id": fid,
                    "garden_check": check,
                    "garden_action": "edit_note_text",
                    "path": path,
                    "stem": stem,
                    "match": up_line(up_target),
                    "replace": "",
                    "occurrence": "first",
                })
            # Unknown action name → skip (forward-compat)

        elif check == "dead_link":
            dead_target = detail.get("dead_target", "")
            replace_target = decision.get("replace", "")
            confirmed.append({
                "id": fid,
                "garden_check": check,
                "garden_action": "edit_note_text",
                "path": path,
                "stem": stem,
                "match": f"[[{dead_target}]]",
                "replace": replace_target,
                "occurrence": "all",
            })
        # duplicate_stem / stale_moc and anything else → advisory, no item

    return {
        "run_id": wire.get("run_id", ""),
        "generated": wire.get("generated", ""),
        "profile": wire.get("profile"),
        "confirmed_items": confirmed,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse

    p = argparse.ArgumentParser(
        description=(
            "Read an approved garden-audit report → confirmed_items JSON (stdout)."
        )
    )
    p.add_argument(
        "--file", required=True, metavar="PATH",
        help="Path to the garden-audit markdown report (authoritative).",
    )
    p.add_argument(
        "--wire", metavar="PATH",
        help="Optional garden-audit-wire.json sibling. When edited, overrides "
             "the markdown decisions (ADR-4 / ADR-026 JSON-only path).",
    )
    args = p.parse_args()

    try:
        with open(args.file, encoding="utf-8") as fh:
            md_text = fh.read()
    except OSError as exc:
        print(f"error: cannot read report: {exc}", file=sys.stderr)
        return 1

    wire = load_changed_wire(args.wire)
    if wire is not None:
        result = build_from_wire(wire)
        print(
            "garden-audit-parser: edited wire is authoritative (JSON-only path)",
            file=sys.stderr,
        )
    else:
        result = build_from_markdown(md_text)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        f"garden-audit-parser: {len(result['confirmed_items'])} confirmed item(s)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
