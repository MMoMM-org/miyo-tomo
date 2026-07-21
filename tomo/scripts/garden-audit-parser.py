#!/usr/bin/env python3
# version: 0.5.0
"""Pass-2 reader for garden-audit (ADR-4 / spec 030 two-artifact split).

Pure reader: the markdown report (human-facing DECISIONS) + the wire JSON
(machine STRUCTURE, always read) → a ``{"confirmed_items": [...]}`` envelope of
SEMANTIC items (not pre-built actions). instruction-render.py turns confirmed_items
into the action list via render_actions.build_garden_audit_actions (which reuses
the shared _build_edit_note_text_actions builder).

Two artifacts, joined by the F-id in each ``### F<id>`` heading:
  - MARKDOWN = decisions only: per block, the ``- [x] Apply`` tick and the typed
    ``Repoint to:`` / ``Replace with:`` values. NO HTML comment.
  - WIRE = complete structure per finding: id, check, tier, target.path,
    target.stem, detail (dead_target / up_target / candidate_mocs), decision.

CLI:
  --file <md>   REQUIRED — the human-reviewed markdown report (decisions).
  --wire <json> REQUIRED — the structure source, always read.
                • wire EDITED (digest mismatch) → build_from_wire (Hashi path,
                  wire fully authoritative).
                • wire unedited → build_from_report (wire structure + markdown
                  decisions, joined by F-id).
  result JSON → STDOUT. Wire missing/unreadable → empty confirmed_items (no crash).

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

def _is_wire_edited(wire: dict) -> bool:
    """True iff an already-loaded wire dict is schema-v1 AND Hashi-edited.

    Edited = the recomputed digest over the editable payload differs from the
    stored emit_digest (or there is no stored digest). Operates on a dict already
    in memory — no file read — so main() can decide routing from the single
    _load_raw_wire result without a second open() (TOCTOU-free). Unknown schema
    version → not edited (unedited wire supplies structure via build_from_report).
    """
    if wire.get("schema_version") != "1":
        return False
    stored = wire.get("emit_digest")
    return not (stored and compute_payload_digest(wire) == stored)


def load_changed_wire(path: str | None) -> dict | None:
    """Return the garden-audit wire iff present, parseable, schema_version=="1", AND edited.

    Edited = the recomputed digest over the editable payload differs from the
    stored emit_digest. Unchanged / absent / unreadable / unknown-version → None.
    Mirrors suggestion-parser.load_changed_wire (ADR-026). Thin file-loading
    wrapper over _is_wire_edited for callers that only have a path.
    """
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            wire = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"warning: garden-audit-wire ignored ({exc}); "
            "routing to build_from_report (wire+markdown join)",
            file=sys.stderr,
        )
        return None
    if not isinstance(wire, dict):
        return None
    if wire.get("schema_version") != "1":
        print(
            f"warning: garden-audit-wire schema_version {wire.get('schema_version')!r} "
            "!= '1' — routing to build_from_report (wire+markdown join)",
            file=sys.stderr,
        )
        return None
    if not _is_wire_edited(wire):
        return None  # unchanged — build_from_report joins wire structure + markdown
    return wire


# ── up:: value normalisation (from lib.render_md) ─────────────────────────────

# up_line() reconstructs the `up:: [[a]], [[b]]` frontmatter line from the wire's
# `up_target` (str | list | dirty list-repr); bare_stem() strips a MOC path to its
# stem. Both live in lib.render_md (shared home). The parser reconstructs `match`
# from the wire, so the report no longer needs them (no round-trip comment).


# ── Markdown parse (decisions only) ───────────────────────────────────────────
# The markdown report is human-facing DECISIONS only. STRUCTURE comes from the
# wire, joined by the F-id in each `### F<id>` heading (spec 030 two-artifact
# split). There is NO HTML comment.

RE_FINDING_HEADER = re.compile(r"^###\s+(F\d+)\b")
RE_APPLY_CHECKED = re.compile(r"^\s*-\s+\[x\]\s*Apply\b", re.IGNORECASE | re.MULTILINE)
RE_APPLY_UNCHECKED = re.compile(r"^\s*-\s+\[\s\]\s*Apply\b", re.IGNORECASE | re.MULTILINE)
RE_REPLACE_FIELD = re.compile(
    r"^\s*-?\s*\*\*Replace with:\*\*\s*(.*)", re.IGNORECASE | re.MULTILINE
)
RE_REPOINT_FIELD = re.compile(
    r"^\s*-?\s*\*\*Repoint to:\*\*\s*(.*)", re.IGNORECASE | re.MULTILINE
)
# Structure (unparented/orphan) filing target (Change 2). Semantically distinct
# from Repoint to: — "File under:" reads as filing an orphan under a MOC.
RE_FILEUNDER_FIELD = re.compile(
    r"^\s*-?\s*\*\*File under:\*\*\s*(.*)", re.IGNORECASE | re.MULTILINE
)
# Suggest opt-in (Phase 7): a per-finding box, decoupled from Apply. When ticked,
# `--suggest` computes candidate picks and rewrites the block with a pick list.
RE_SUGGEST_TICKED = re.compile(
    r"^\s*-\s+\[x\]\s+Suggest targets\b", re.IGNORECASE | re.MULTILINE
)
# A ticked pick sub-checkbox: `  - [x] [[Candidate]] (0.92)`. The wikilink stem
# is the chosen Replace/Repoint value (unless the user typed one, which wins).
RE_PICK_TICKED = re.compile(
    r"^\s*-\s+\[x\]\s+\[\[([^\]]*)\]\]\s*\(", re.IGNORECASE | re.MULTILINE
)

# Frontmatter (flat key: value) for run_id / generated / profile.
RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


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


def parse_decision_map(md_text: str) -> dict[str, dict]:
    """Parse the markdown report into ``{F-id → {apply, repoint, replace, suggest}}``.

    The markdown carries DECISIONS only, keyed by the F-id in each ``### F<id>``
    heading (spec 030 two-artifact split). For each block:
      - apply:   True unless a ``- [ ] Apply`` box is present AND unticked.
      - repoint / replace: the RESOLVED target for broken_up / dead_link.
        Precedence (Phase 7, D4): a value TYPED into ``**Repoint to:**`` /
        ``**Replace with:**`` > a ticked ``- [x] [[Candidate]]`` pick sub-checkbox
        > empty (removal). The parser feeds this into the same garden_action
        discrimination as a typed value.
      - file_under: the RESOLVED MOC for an unparented/orphan filing fix. Same
        precedence (typed **File under:** > ticked pick > empty).
      - suggest: True iff the ``- [x] Suggest targets`` opt-in is ticked (so
        ``--suggest`` knows which findings to enrich).
    Findings with no editable field carry apply + empty fields + suggest.
    """
    out: dict[str, dict] = {}
    for fid, lines in _split_finding_blocks(md_text):
        block = "\n".join(lines)
        # Apply gate: a present-but-unticked box → skip; ticked / absent → apply.
        apply = not (
            RE_APPLY_UNCHECKED.search(block) and not RE_APPLY_CHECKED.search(block)
        )
        repoint_raw = _field_value(block, RE_REPOINT_FIELD)
        replace_raw = _field_value(block, RE_REPLACE_FIELD)
        fileunder_raw = _field_value(block, RE_FILEUNDER_FIELD)
        typed_repoint = _wikilink_target(repoint_raw) if repoint_raw is not None else ""
        typed_replace = _wikilink_target(replace_raw) if replace_raw is not None else ""
        typed_fileunder = _wikilink_target(fileunder_raw) if fileunder_raw is not None else ""
        # Precedence: typed field value wins; else a ticked pick sub-checkbox.
        # "Pick one" is the contract — if the user ticked more than one candidate,
        # use the first and warn (the extras are silently dropped otherwise).
        picks = RE_PICK_TICKED.findall(block)
        if len(picks) > 1:
            print(
                f"warning: garden-audit-parser: finding {fid!r} has "
                f"{len(picks)} ticked pick sub-checkboxes — 'Pick one' expected; "
                f"using the first ({picks[0].strip()!r}), ignoring the rest",
                file=sys.stderr,
            )
        pick = picks[0].strip() if picks else ""
        out[fid] = {
            "apply": apply,
            "repoint": typed_repoint or pick,
            "replace": typed_replace or pick,
            "file_under": typed_fileunder or pick,
            "suggest": bool(RE_SUGGEST_TICKED.search(block)),
        }
    return out


def _confirmed_item_from_wire_finding(finding: dict, decision_md: dict) -> dict | None:
    """Build one confirmed_item from a wire finding + the markdown decision.

    STRUCTURE (id, check, path, stem, detail) comes from the wire finding;
    DECISIONS (repoint / replace typed values) come from ``decision_md`` (from
    parse_decision_map). Advisory / non-fixable / unresolvable → None.
    """
    check = finding.get("check", "")
    fid = finding.get("id", "")
    target = finding.get("target") or {}
    path = target.get("path", "")
    stem = target.get("stem") or bare_stem(path)
    detail = finding.get("detail") or {}

    if check == "dead_link":
        replace_target = decision_md.get("replace", "")
        replace = f"[[{replace_target}]]" if replace_target else ""
        dead_target = detail.get("dead_target", "")
        return {
            "id": fid,
            "garden_check": check,
            "garden_action": "edit_note_text",
            "path": path,
            "stem": stem,
            "match": f"[[{dead_target}]]",
            "replace": replace,
            "occurrence": "all",
        }

    if check == "broken_up":
        repoint = decision_md.get("repoint", "")
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
            "match": up_line(detail.get("up_target", "")),
            "replace": "",
            "occurrence": "first",
        }

    if check in ("unparented", "orphan"):
        # file_note target precedence (Change 2): the user's chosen MOC (a typed
        # **File under:** value OR a ticked pick — both resolve into decision
        # file_under) > the scan's candidate_mocs[0] > none (skip + warn). The
        # resolved stem threads into BOTH the link_to_moc bullet and the up:: line
        # in build_garden_audit_actions.
        user_moc = decision_md.get("file_under", "")
        mocs = detail.get("candidate_mocs") or []
        scan_moc_path = mocs[0].get("target_moc", "") if mocs else ""
        if user_moc:
            target_moc = user_moc
            target_moc_path = None  # user-chosen stem; resolver fills the path
        elif scan_moc_path:
            target_moc = bare_stem(scan_moc_path)
            target_moc_path = scan_moc_path
        else:
            print(
                f"warning: garden-audit-parser: finding {fid!r} ({path!r}) is a "
                "filing fix but no MOC resolved (no File-under value, no pick, no "
                "scan candidate) — skipping",
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


def build_from_report(md_text: str, wire: dict) -> dict:
    """Join markdown DECISIONS to wire STRUCTURE → confirmed_items envelope.

    The report is human-facing (Apply ticks + typed Repoint/Replace values); the
    wire is the always-read structure source (path, detail, candidate_mocs). They
    are joined by the F-id in each ``### F<id>`` heading (spec 030 two-artifact
    split). For each wire finding that is fixable AND present-and-ticked in the
    markdown decision map, a confirmed_item is built from the wire's structure +
    the markdown's typed decision. Advisory / unticked / missing → skipped.
    """
    fm = _extract_frontmatter(md_text)
    decision_map = parse_decision_map(md_text)
    confirmed: list[dict] = []

    for finding in (wire or {}).get("findings") or []:
        if not finding.get("fixable"):
            continue  # advisory findings never produce a fix
        fid = finding.get("id", "")
        md_decision = decision_map.get(fid)
        if md_decision is None or not md_decision.get("apply"):
            continue  # id absent from the report, or the user unticked Apply
        item = _confirmed_item_from_wire_finding(finding, md_decision)
        if item is not None:
            confirmed.append(item)

    return {
        "run_id": (wire or {}).get("run_id") or fm.get("run_id", ""),
        "generated": (wire or {}).get("generated") or fm.get("generated", ""),
        "profile": (wire or {}).get("profile") or fm.get("profile") or None,
        "confirmed_items": confirmed,
    }


# ── Wire rebuild (ADR-4 JSON-only override) ───────────────────────────────────

def build_from_wire(wire: dict) -> dict:
    """Reconstruct confirmed_items from an edited garden-audit wire alone.

    ADR-4 JSON-only path: when load_changed_wire returns a wire (Hashi-edited),
    Pass-2 builds the confirmed_items list from the wire alone — the markdown
    decisions are not consulted. Same envelope shape as build_from_report.
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

def _load_raw_wire(path: str) -> dict | None:
    """Load the wire JSON regardless of digest, or None (+warn) on any failure.

    Used for the STRUCTURE source (build_from_report always reads the wire). The
    digest-gated edit check is a separate concern handled by load_changed_wire.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            wire = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"warning: garden-audit-parser: wire unreadable ({exc}) — "
            "emitting empty confirmed_items",
            file=sys.stderr,
        )
        return None
    if not isinstance(wire, dict):
        print(
            "warning: garden-audit-parser: wire is not an object — "
            "emitting empty confirmed_items",
            file=sys.stderr,
        )
        return None
    return wire


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(
        description=(
            "Join a garden-audit report's DECISIONS to the wire's STRUCTURE → "
            "confirmed_items JSON (stdout)."
        )
    )
    p.add_argument(
        "--file", required=True, metavar="PATH",
        help="Path to the garden-audit markdown report (human-facing decisions).",
    )
    p.add_argument(
        "--wire", required=True, metavar="PATH",
        help="Path to garden-audit-wire.json — the STRUCTURE source, always read. "
             "When it is Hashi-edited (digest mismatch), it is fully authoritative "
             "(build_from_wire); otherwise its structure is joined to the markdown "
             "decisions by F-id (build_from_report).",
    )
    args = p.parse_args()

    try:
        with open(args.file, encoding="utf-8") as fh:
            md_text = fh.read()
    except OSError as exc:
        print(f"error: cannot read report: {exc}", file=sys.stderr)
        return 1

    raw_wire = _load_raw_wire(args.wire)
    if raw_wire is None:
        # Degrade gracefully — no structure source means no fixes to emit.
        print(json.dumps({
            "run_id": "", "generated": "", "profile": None, "confirmed_items": [],
        }, ensure_ascii=False, indent=2))
        return 0

    # Digest check on the ALREADY-LOADED wire (no second file read — TOCTOU-free):
    # an edited wire is the Hashi-authored path (wire fully authoritative); an
    # unedited wire supplies structure to the markdown decisions.
    if _is_wire_edited(raw_wire):
        result = build_from_wire(raw_wire)
        print(
            "garden-audit-parser: edited wire is authoritative (JSON-only path)",
            file=sys.stderr,
        )
    else:
        result = build_from_report(md_text, raw_wire)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        f"garden-audit-parser: {len(result['confirmed_items'])} confirmed item(s)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
