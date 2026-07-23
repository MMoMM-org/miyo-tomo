#!/usr/bin/env python3
# version: 0.10.0
"""Pass-2 reader for garden-audit (ADR-4 / spec 030 two-artifact split).

Pure reader: the markdown report (human-facing DECISIONS) + the wire JSON
(machine STRUCTURE, always read) → a ``{"confirmed_items": [...],
"acked_advisories": [...]}`` envelope of SEMANTIC items (not pre-built actions).
instruction-render.py turns confirmed_items into the action list via
render_actions.build_garden_audit_actions (which reuses the shared
_build_edit_note_text_actions builder). acked_advisories ({id, path, check} for
EVERY advisory in the doc — auto-pushback 2026-07-23: approving the report pauses
them all, no per-finding tick) is consumed by ``--stamp-pushback``, which writes
the pushback ledger so the next scan rests those advisories for the configured
window. Triage only routes approved garden-audit docs to Pass-2, so the parser
never stamps an unapproved report.

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
  --stamp-pushback OPTIONAL — Pass-2 apply path only: write acked advisories
                into the pushback ledger (--pushback-ledger; window days from
                --exclusions settings.advisory_pushback_days, default 30).
  result JSON → STDOUT. Wire missing/unreadable → empty confirmed_items (no crash).

confirmed_item shape (per fixable finding the user kept):
  {
    "id", "garden_check", "garden_action",
    "path", "stem",
    # edit_note_text (dead_link fix/remove):
    "match", "replace", "occurrence",
    # remove_up_link (broken_up empty=remove — link-only removal):
    "link",
    # add_relationship (broken_up repoint, filing up::):
    "up_line",
    # file_note (unparented/orphan filing):
    "target_moc", "target_moc_path",
  }

garden_action ∈ {edit_note_text, remove_up_link, add_relationship, file_note}.
Advisory findings (duplicate_stem, stale_moc) never produce a confirmed_item
(but acknowledged ones land in acked_advisories).
"""
import json
import re
import sys

from lib.render_md import (
    bare_stem,
    compute_garden_audit_digest,
    unwrap_list_repr,
    up_line,
)


def _up_link_stem(up_target) -> str:
    """Bare stem of the broken up:: target (str | list | dirty list-repr).

    The wire schema declares up_target as the broken stem (string), but the
    graph cache historically stores up:: as a multi-value list and dirty caches
    carry stringified list-reprs — normalize all shapes to one bare stem for
    the remove_up_link `link` field (no [[ ]]).
    """
    value = unwrap_list_repr(up_target)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    s = str(value or "").strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2].strip()
    return s


# ── Wire load ────────────────────────────────────────────────────────────────

def _wire_is_json_approved(wire: dict) -> bool:
    """True iff the wire carries the top-level JSON-side approve gate (Q1).

    The Tomo-Editor works from the JSON, so it flips a top-level ``approved: true``
    on "ready for /inbox" (parallel to the markdown ``- [x] Approved`` box). When
    set, the JSON channel is authoritative and Pass-2 routes to build_from_wire
    regardless of digest — otherwise an editor-approved run that changed NO apply
    decision (digest still matches emit) would route to build_from_report and read
    an empty markdown, applying nothing (spec 030 edge case).
    """
    return bool(wire.get("approved"))


def _is_wire_edited(wire: dict) -> bool:
    """True iff an already-loaded wire dict is schema-v1 AND the JSON is authoritative.

    Authoritative = the user changed an apply decision (the recomputed garden-audit
    digest over selected/repoint/replace/file_under differs from the stored
    emit_digest, or there is no stored digest) OR the wire is JSON-approved
    (top-level ``approved: true``). Tomo-generated fields (decision.candidates),
    the editor's suggest_requested flag, and the approved gate itself are EXCLUDED
    from the digest — only a real apply-decision change flips it (spec 030). The
    approved gate additionally forces the JSON path so an all-default editor
    approval still applies fixes. Operates on a dict already in memory — no file
    read — so main() decides routing from the single _load_raw_wire result without
    a second open() (TOCTOU-free). Unknown schema version → not authoritative
    (unedited wire supplies structure via build_from_report).
    """
    if wire.get("schema_version") != "1":
        return False
    if _wire_is_json_approved(wire):
        return True
    stored = wire.get("emit_digest")
    return not (stored and compute_garden_audit_digest(wire) == stored)


def load_changed_wire(path: str | None) -> dict | None:
    """Return the garden-audit wire iff present, parseable, schema_version=="1", AND authoritative.

    Authoritative = an apply decision changed (garden-audit digest mismatch over
    selected/repoint/replace/file_under) OR the wire is JSON-approved. Unchanged /
    absent / unreadable / unknown-version → None. Mirrors
    suggestion-parser.load_changed_wire (ADR-026). Thin file-loading wrapper over
    _is_wire_edited for callers that only have a path.
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
        dead_target = detail.get("dead_target", "")
        # Non-empty target → repoint to the new wikilink. Empty (remove intent) →
        # UNLINK: drop the [[ ]] brackets but KEEP the text (`[[X]]` → `X`), not a
        # full deletion of link+text. dead_target is the inner text of the match.
        replace = f"[[{replace_target}]]" if replace_target else dead_target
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
        # Empty / absent Repoint → remove ONLY the broken link from the up:: line
        # (remove_up_link, link-only semantics — user decision 2026-07-23). The
        # earlier whole-line edit_note_text match silently no-opped on multi-link
        # up:: lines; Hashi edits the real line with body access instead.
        return {
            "id": fid,
            "garden_check": check,
            "garden_action": "remove_up_link",
            "path": path,
            "stem": stem,
            "link": _up_link_stem(detail.get("up_target", "")),
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


def _acked_advisory(finding: dict) -> dict:
    """Project an acknowledged advisory finding to a pushback-ledger item."""
    target = finding.get("target") or {}
    return {
        "id": finding.get("id", ""),
        "path": target.get("path", ""),
        "check": finding.get("check", ""),
    }


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
    acked: list[dict] = []

    for finding in (wire or {}).get("findings") or []:
        fid = finding.get("id", "")
        md_decision = decision_map.get(fid)
        if not finding.get("fixable"):
            # Advisory findings never produce a fix. Auto-pushback (2026-07-23):
            # approving the report pauses EVERY advisory it lists — no per-finding
            # tick. --stamp-pushback (Pass-2 apply, approval-gated by triage) writes
            # them; a non-stamp parse just carries the list harmlessly.
            acked.append(_acked_advisory(finding))
            continue
        if md_decision is None or not md_decision.get("apply"):
            continue  # id absent from the report, or the user left Apply unticked
        item = _confirmed_item_from_wire_finding(finding, md_decision)
        if item is not None:
            confirmed.append(item)

    return {
        "run_id": (wire or {}).get("run_id") or fm.get("run_id", ""),
        "generated": (wire or {}).get("generated") or fm.get("generated", ""),
        "profile": (wire or {}).get("profile") or fm.get("profile") or None,
        "confirmed_items": confirmed,
        "acked_advisories": acked,
    }


# ── Wire rebuild (ADR-4 JSON-only override) ───────────────────────────────────

def build_from_wire(wire: dict) -> dict:
    """Reconstruct confirmed_items from an edited garden-audit wire alone.

    ADR-4 JSON-only path: when load_changed_wire returns a wire (Hashi-edited),
    Pass-2 builds the confirmed_items list from the wire alone — the markdown
    decisions are not consulted. Same envelope shape as build_from_report.
    """
    confirmed: list[dict] = []
    acked: list[dict] = []

    for finding in wire.get("findings") or []:
        # Advisory checks (duplicate_stem, stale_moc) never produce a fix. Auto-
        # pushback (2026-07-23): an approved/edited wire pauses every advisory it
        # lists (the wire is only authoritative post-approval).
        if not finding.get("fixable"):
            acked.append(_acked_advisory(finding))
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
            # file_note target precedence (Q2): an explicit decision.file_under
            # value ALWAYS wins > the scan's candidate_mocs[0] > skip. The wire's
            # decision.candidates is DISPLAY-ONLY (the editor renders it for the
            # user to pick from) and is NEVER auto-applied — only the value the
            # editor commits into file_under is read here.
            user_moc = _wikilink_target(decision.get("file_under", ""))
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
                    f"warning: garden-audit-parser: finding {fid!r} ({path!r}) "
                    "selected for filing but has no file_under value and no "
                    "candidate_mocs — skipping",
                    file=sys.stderr,
                )
                continue
            confirmed.append({
                "id": fid,
                "garden_check": check,
                "garden_action": "file_note",
                "path": path,
                "stem": stem,
                "target_moc": target_moc,
                "target_moc_path": target_moc_path,
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
                # Wire remove intent (decision.action stays "edit_note_text" —
                # Hashi contract unchanged) → link-only removal, same semantics
                # as the report path.
                confirmed.append({
                    "id": fid,
                    "garden_check": check,
                    "garden_action": "remove_up_link",
                    "path": path,
                    "stem": stem,
                    "link": _up_link_stem(up_target),
                })
            # Unknown action name → skip (forward-compat)

        elif check == "dead_link":
            dead_target = detail.get("dead_target", "")
            replace_target = decision.get("replace", "")
            # Non-empty (repoint) → the wikilink the editor wrote (e.g. '[[New]]').
            # Empty (remove intent) → UNLINK: drop the [[ ]] but KEEP the text
            # (`[[X]]` → `X`), NOT a full deletion. Same rule as build_from_report.
            replace = replace_target if replace_target else dead_target
            confirmed.append({
                "id": fid,
                "garden_check": check,
                "garden_action": "edit_note_text",
                "path": path,
                "stem": stem,
                "match": f"[[{dead_target}]]",
                "replace": replace,
                "occurrence": "all",
            })
        # duplicate_stem / stale_moc and anything else → advisory, no item

    return {
        "run_id": wire.get("run_id", ""),
        "generated": wire.get("generated", ""),
        "profile": wire.get("profile"),
        "confirmed_items": confirmed,
        "acked_advisories": acked,
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
    p.add_argument(
        "--stamp-pushback",
        action="store_true",
        help="Write acknowledged advisories into the pushback ledger so the next "
             "scan suppresses them for the configured rest window. Pass this on "
             "the Pass-2 apply path only — never on read-only parses.",
    )
    p.add_argument(
        "--pushback-ledger", default="config/garden-audit-pushback.yaml",
        metavar="PATH", help="Ledger path for --stamp-pushback.",
    )
    p.add_argument(
        "--exclusions", default="config/garden-audit-exclusions.yaml",
        metavar="PATH",
        help="Exclusions YAML — read only for settings.advisory_pushback_days "
             "when stamping (missing file = default window).",
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
            "run_id": "", "generated": "", "profile": None,
            "confirmed_items": [], "acked_advisories": [],
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

    acked = result.get("acked_advisories") or []
    if args.stamp_pushback and acked:
        from pathlib import Path

        from lib.garden_exclusions import GardenExclusions, stamp_pushback

        days = GardenExclusions.from_path(Path(args.exclusions)).advisory_pushback_days
        stamp_pushback(Path(args.pushback_ledger), acked, days)
        print(
            f"garden-audit-parser: stamped {len(acked)} acknowledged advisory(ies) "
            f"into {args.pushback_ledger} (rest {days} days)",
            file=sys.stderr,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        f"garden-audit-parser: {len(result['confirmed_items'])} confirmed item(s), "
        f"{len(acked)} acknowledged advisory(ies)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
