#!/usr/bin/env python3
# version: 0.35.0
"""
suggestion-parser.py — Parse an approved Tomo suggestions document.

Reads a MiYo-Tomo suggestions markdown file (with `[x] Approved` checkbox)
and extracts user-approved items with any modifications they made to fields,
alternatives, and action checkboxes.

Accepts multiple section header formats:
  - Spec format:    ### S01: filename.md    or    ### S01 — Title
  - LLM output:     ### A1. Title    or    ### B1. Title    (A-E groups)

Usage:
    python suggestion-parser.py --file PATH
    cat suggestions.md | python suggestion-parser.py
"""

import argparse
import copy
import itertools
import json
import os
import re
import sys

# H5 (spec 022/023): the supporting_items union is shared with
# instruction-render via lib/supporting_items.py. Ensure the script dir is on
# the path so `lib.supporting_items` resolves both when run as a hyphenated
# top-level script and when loaded via spec_from_file_location in tests.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: E402
from lib.supporting_items import (  # noqa: E402
    union_supporting_items as _union_supporting_items,
)
from lib.item_key import derive as derive_item_key  # noqa: E402
from lib.render_md import compute_payload_digest  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Patterns
# ──────────────────────────────────────────────────────────────────────────────

# Section header: accept both spec format (S01:) and LLM output format (A1., B1., etc.)
#   ### S01: filename.md    ### S01 — Title
#   ### A1. Title           ### B12. Another
RE_SECTION_HEADER = re.compile(r"^#{2,3}\s+([A-Z]\d+)[.:\s—–-]+", re.IGNORECASE)

# MOC proposal-doc section header: ### MOCxx — Title  (F-43 T4.1)
#   ### MOC01 — Shell & Terminal (MOC)
RE_MOC_SECTION_HEADER = re.compile(r"^###\s+(MOC\d+)\s*[—–-]+\s*(.*)", re.IGNORECASE)

# Checkbox lines
RE_CHECKED = re.compile(r"^\s*-\s+\[x\]\s*(.*)", re.IGNORECASE)
RE_UNCHECKED = re.compile(r"^\s*-\s+\[\s\]\s*(.*)", re.IGNORECASE)

# Bold field: **Name:** value
RE_FIELD = re.compile(r"^\s*\*\*([^*]+)\*\*[:\s]*(.*)")

# Wikilink: [[Note Name]]  or  [[Note Name#anchor]]
RE_WIKILINK = re.compile(r"\[\[([^\]#|]+)(?:[#|][^\]]*)?\]\]")

# The same link, with its alias kept: group 1 = target, group 2 = alias or None.
RE_WIKILINK_ALIASED = re.compile(
    r"\[\[([^\]#|]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]"
)

# Source field value: backtick or plain path
RE_SOURCE = re.compile(r"`([^`]+)`|(\S+\.md)")

# Type field: word_word (confidence: 0.85)  or  word_word (confidence 85%)
RE_TYPE = re.compile(r"([a-z_]+)\s*\(confidence[:\s]*([\d.]+%?)\)")

# ── Placement line reverse-parsers (spec 022/023) ──────────────────────────
# Mirror suggestions-reducer.py _placement_line (the SOURCE OF TRUTH for the
# rendered format). Each reverse-parser recovers the structured anchor the
# reducer rendered so a hand-edited Placement line overrides the doc-JSON
# default; an unedited line round-trips to the same anchor.
#   under `## <H>` [(confidence: N%)]            → heading/after
#   new section `## <X>` (before the footer)     → callout/before + new_section
#   new section `## <X>` (at the end of the MOC) → line/after + new_section
#   inside the `> [!name]` callout               → callout (value)
#   inside the `<ref>` callout                   → callout (value)
RE_PLACEMENT_HEADING = re.compile(
    r"\*\*Placement:\*\*\s*under\s+`##\s*([^`]+?)`", re.IGNORECASE
)
RE_PLACEMENT_NEW_SECTION = re.compile(
    r"\*\*Placement:\*\*\s*new section\s+`##\s*([^`]+?)`\s*\((before the footer|at the end of the MOC)\)",
    re.IGNORECASE,
)
RE_PLACEMENT_CALLOUT = re.compile(
    r"\*\*Placement:\*\*\s*inside the\s+`([^`]+?)`\s+callout", re.IGNORECASE
)


def parse_placement_line(line: str) -> dict | None:
    """Reverse-parse a rendered ``**Placement:**`` line into a structured anchor.

    Returns ``None`` for the last-resort "under the note title" tier or any
    unrecognised line, signalling the caller to fall back to the structured
    doc-JSON default anchor (spec 022/023 BOTH design).
    """
    if not line:
        return None
    m = RE_PLACEMENT_NEW_SECTION.search(line)
    if m:
        section = m.group(1).strip()
        if m.group(2).lower().startswith("before the footer"):
            return {
                "type": "callout",
                "value": None,
                "placement": "before",
                "new_section": section,
            }
        return {
            "type": "line",
            "value": None,
            "placement": "after",
            "new_section": section,
        }
    m = RE_PLACEMENT_HEADING.search(line)
    if m:
        return {
            "type": "heading",
            "value": m.group(1).strip(),
            "placement": "after",
        }
    m = RE_PLACEMENT_CALLOUT.search(line)
    if m:
        return {
            "type": "callout",
            "value": m.group(1).strip(),
            "placement": "inside",
        }
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _is_checked(line: str) -> bool:
    return bool(RE_CHECKED.match(line))


def _checkbox_text(line: str) -> str:
    """Return the text after the checkbox marker."""
    m = RE_CHECKED.match(line) or RE_UNCHECKED.match(line)
    return m.group(1).strip() if m else ""


def _extract_wikilink(text: str) -> str | None:
    """Return the first wikilink target found, or None."""
    m = RE_WIKILINK.search(text)
    return m.group(1).strip() if m else None


def _wikilink_display(text: str) -> str | None:
    """Return the first wikilink's DISPLAY text — its alias, else its target.

    A source link is path-qualified with an alias only when two items in the
    run share a filename (spec 034 T5.1): `[[100 Inbox/Places/Dresden|Dresden]]`.
    The path is the vault's way of saying WHICH note; the alias is the bare
    filename the document shows. Identity comes from `item_key`, so the parsed
    display value stays the bare stem on both parser paths (ADR-2) — the wire
    path records `stem` in the same field, and the two must agree.

    An unaliased link is returned verbatim, so every pre-T5.1 document parses
    exactly as it did.
    """
    m = RE_WIKILINK_ALIASED.search(text)
    if not m:
        return None
    alias = m.group(2)
    return alias.strip() if alias and alias.strip() else m.group(1).strip()


def _moc_path_stem(ref: str | None) -> str:
    """Bare lowercase stem of a MOC path/wikilink target for matching.

    `Atlas/200 Maps/Concepts (MOC).md` → `concepts (moc)`
    `Atlas/200 Maps/Concepts (MOC)`    → `concepts (moc)`
    """
    if not ref:
        return ""
    bare = ref.rsplit("/", 1)[-1]
    if bare.endswith(".md"):
        bare = bare[:-3]
    return bare.strip().lower()


def _bind_candidate_anchor(
    result: dict,
    moc_ref: str,
    override: dict | None,
    doc_anchors: dict[str, dict],
) -> None:
    """Append a {path, anchor} entry for a checked MOC (spec 022/023 BOTH design).

    Anchor precedence: the reverse-parsed **Placement:** line (``override``)
    when it parsed to a recognised anchor, else the structured doc-JSON default
    keyed by MOC stem. When neither is available, no candidate is recorded —
    instruction-render falls back to its own resolution.
    """
    anchor = override or doc_anchors.get(_moc_path_stem(moc_ref))
    if anchor is None:
        return
    result["candidate_mocs"].append({"path": moc_ref, "anchor": anchor})


# ── Suggestions wire precedence (ADR-026) ─────────────────────────────────
# The vault-published _suggestions.json sibling carries the editable review
# surface. When it was edited — its embedded emit_digest no longer matches a
# recomputation over the editable payload — the JSON is authoritative for the
# fields it carries (per-note MOC selection/anchors, proposed-MOC
# rename/reparent/decision) and is applied as an override on top of the
# markdown parse. Unchanged / absent / unparseable / unknown-version ⇒ the
# markdown path is used byte-for-byte (Tomo never assumes Hashi is installed).

def load_changed_wire(path: str | None) -> dict | None:
    """Return the wire payload iff present, parseable, v1, AND edited.

    Edited = the recomputed digest differs from the embedded emit_digest.
    Returns None otherwise, so the caller falls back to the markdown parse.
    """
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            wire = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"warning: suggestions-json ignored ({exc}); using markdown",
            file=sys.stderr,
        )
        return None
    if not isinstance(wire, dict):
        return None
    version = wire.get("schema_version")
    if version != "1":
        print(
            f"warning: suggestions-json schema_version {version} != 1 — "
            "ignored, using markdown",
            file=sys.stderr,
        )
        return None
    stored = wire.get("emit_digest")
    if stored and compute_payload_digest(wire) == stored:
        return None  # unchanged — markdown stays authoritative
    return wire


def _wire_moc_ref(path: str) -> str:
    """Wire candidate path (vault path, possibly .md) → parser wikilink ref."""
    return path[:-3] if path.endswith(".md") else path


def _norm_anchor(anchor: dict) -> dict:
    """Normalise a wire anchor to the shape parse_placement_line yields.

    The markdown path recovers a candidate anchor by reverse-parsing the rendered
    **Placement:** line, which keeps only `{type, value, placement}` (+ `new_section`
    for new-section placements). Normalising here keeps the JSON-only output equal
    to the markdown path; the dropped fields (`alt_headings`, `fit_confidence`) are
    advisory and stripped downstream anyway.
    """
    out = {
        "type": anchor.get("type"),
        "value": anchor.get("value"),
        "placement": anchor.get("placement"),
    }
    if anchor.get("new_section"):
        out["new_section"] = anchor.get("new_section")
    return out


def _item_key_of(src: str | None) -> str:
    """Item identity for the Force-Atomic reconciliation join (ADR-1).

    The daily-log path (`source_stem` on a log_entry) and the primary/
    resolve-doc path (`source_path` on a parsed section) both derive
    identity through this one module-level function — the vault-relative
    path verbatim, via `lib.item_key.derive`. No basename extraction, no
    lowercasing: letting the two paths diverge reopens #165 in a form its
    original regression test does not exercise (see
    docs/tomo/scripts/suggestion-parser.md).
    """
    if not src:
        return ""
    return derive_item_key(src)


def build_from_wire(wire: dict, moc_template: str) -> dict:
    """Build the complete parsed-suggestions output from an edited wire alone.

    ADR-026 JSON-only path: when `load_changed_wire` returns a wire (the user
    edited it), Pass-2 reconstructs its ENTIRE output from the wire and never
    re-reads the markdown. Output shape matches `suggestion-parser`'s markdown
    path (verified by the golden test against parse(render(doc))).
    """
    confirmed_items: list[dict] = []
    skipped_items: list[dict] = []
    pending_fan_resolutions: list[dict] = []
    # id → item_key (ADR-1), not id → stem: proposed-MOC member_ids resolve
    # through this map, and a bare stem binds a member to whichever same-named
    # note was written into the join dict last.
    id_to_item_key: dict[str, str] = {}

    for w in wire.get("suggestions", []):
        stem = w.get("stem")
        item_key = w.get("item_key") or stem
        id_to_item_key[w.get("id")] = item_key
        # Suppressed light block promoted via Force Atomic → resolve subflow (#88).
        # Mirror the section-level pending_fan_resolutions shape (stem is the
        # lowercased source stem; Pass 2 verifies via kado-search).
        if w.get("suppressed") and w.get("force_atomic"):
            summary = (w.get("title") or "").strip()
            if len(summary) > 140:
                summary = summary[:137] + "…"
            pending_fan_resolutions.append({
                "stem": (stem or "").lower(),
                "source_path": stem or "",
                "log_entry_summary": summary,
            })
            continue
        if w.get("decision") == "approve":
            parent_mocs: list[str] = []
            candidate_mocs: list[dict] = []
            for c in w.get("candidate_mocs", []):
                if not c.get("selected"):
                    continue
                ref = _wire_moc_ref(c.get("path", ""))
                if not ref:
                    continue
                parent_mocs.append(ref)
                anchor = c.get("anchor")
                if anchor:
                    candidate_mocs.append({"path": ref, "anchor": _norm_anchor(anchor)})
            template = w.get("template") or ""
            if template.endswith(".md"):
                template = template[:-3]
            confirmed_items.append({
                "id": w.get("id"),
                # source_path stays the bare display stem (ADR-2); item_key is
                # the identity downstream joins key on (ADR-1).
                "source_path": stem,
                "item_key": item_key,
                "audio_peer": w.get("audio_peer"),
                "attachments": list(w.get("attachments") or []),
                "type": None,
                "approved": True,
                "delete_source": bool(w.get("delete_source")),
                "keep_source": bool(w.get("keep_source")),
                "action": None,
                "title": w.get("title"),
                "tags": list(w.get("tags") or []),
                "parent_moc": parent_mocs[0] if parent_mocs else None,
                "parent_mocs": parent_mocs,
                "candidate_mocs": candidate_mocs,
                "destination": w.get("location"),
                "template": template,
                "summary": None,
                "classification": None,
            })
        else:
            skipped_items.append({
                "id": w.get("id"),
                # source_path stays the bare display stem (ADR-2); item_key is
                # what Pass 2 addresses the note by when it emits a skip or a
                # user-requested delete for it (ADR-1).
                "source_path": stem,
                "item_key": item_key,
                "disposition": "delete_source" if w.get("delete_source") else "skip",
            })

    total_sections = len(wire.get("suggestions", []))

    # Proposed MOCs (approve) → create_moc confirmed items; member_ids resolve to
    # source stems via id_to_stem, then to confirmed ids in the binding pass below.
    wire_mocs: list[dict] = []
    for idx, pm in enumerate(wire.get("proposed_mocs", []), start=1):
        if pm.get("decision") != "approve":
            continue
        name = (pm.get("name") or "").strip()
        if not name:
            continue
        parent = pm.get("parent", "")
        member_stems = [
            id_to_item_key[mid]
            for mid in pm.get("member_ids", [])
            if mid in id_to_item_key
        ]
        wire_mocs.append({
            "id": f"MOC{idx:02d}",
            "source_path": None,
            "type": "moc",
            "approved": True,
            "delete_source": False,
            "action": "create_moc",
            "title": name,
            "tags": list(pm.get("tags") or []),
            "parent_moc": parent,
            "parent_mocs": [parent] if parent else [],
            "destination": "Atlas/200 Maps/",
            "template": moc_template,
            "summary": None,
            "classification": None,
            "supporting_items": "",
            "topic": pm.get("topic", ""),
            "member_stems": member_stems,
        })
    confirmed_items.extend(_merge_proposed_mocs_by_name(wire_mocs))

    # Bind member_stems → supporting_items ids (mirrors the markdown path's final
    # pass), then strip the internal helper fields.
    key_to_id = {
        _item_key_of(c.get("item_key") or c.get("source_path")): c.get("id")
        for c in confirmed_items
        if (c.get("item_key") or c.get("source_path")) and c.get("id")
    }
    for c in confirmed_items:
        if c.get("action") == "create_moc":
            ids = [
                key_to_id[_item_key_of(s)]
                for s in (c.get("member_stems") or [])
                if _item_key_of(s) in key_to_id
            ]
            if ids:
                c["supporting_items"] = ", ".join(ids)
        c.pop("member_stems", None)
        c.pop("topic", None)
    # Lifted at the same site the other internal fields are stripped: the
    # carrier must not reach a confirmed item, and the record must reach the
    # output dict below.
    merged_moc_proposals = _lift_merged_moc_records(confirmed_items)

    tag_groups = wire.get("tag_handler_groups", [])
    return {
        "confirmed_items": confirmed_items,
        # spec 034 T6.0c: what the by-Name merge absorbed, so instructions.md
        # can say that one MOC was created where more than one was approved
        # (CON-2). Empty list when nothing merged.
        "merged_moc_proposals": merged_moc_proposals,
        # Daily updates are carried in the wire in the parser's own output shape
        # (mirrored at emit), so they pass through verbatim.
        "daily_updates": wire.get("daily_updates", []),
        "skipped": skipped_items,
        "pending_fan_resolutions": pending_fan_resolutions,
        "approved_tag_handler_group_ids": [
            g["group_id"] for g in tag_groups if g.get("approved")
        ],
        "tag_handler_keep_source_group_ids": [
            g["group_id"] for g in tag_groups if g.get("keep_source")
        ],
        "total_sections": total_sections,
        "total_approved": len(confirmed_items),
        "total_skipped": len(skipped_items),
    }


def build_from_wire_companion(
    primary_wire: dict, fan_wire: dict, moc_template: str
) -> dict:
    """Companion merge from two EDITED wires (ADR-026 JSON-only), no markdown.

    The markdown companion defers the primary's force-atomic'd items and resolves
    them in a fan doc, then merges both. Under JSON-only we do the same by COMBINING
    the two wires into one and running build_from_wire once — so all of its member
    binding + proposed-MOC same-name merge logic is reused over the union, with no
    id collisions or cross-wire membership gaps:

    - The fan's ids are re-namespaced (S## → F-S##, M## → F-M##; member_ids fixed)
      so they never clash with the primary's.
    - The primary's deferred suggestions (the force-atomic'd stems the fan resolves)
      are DROPPED and replaced by the fan's resolved (un-suppressed) versions — so
      there are no leftover pending_fan_resolutions.
    - proposed_mocs are concatenated (build_from_wire merges same-name across both);
      daily_updates + tag_handler_groups come from the primary (the fan has none).
    """
    fan = copy.deepcopy(fan_wire)
    id_map: dict[str, str] = {}
    for s in fan.get("suggestions") or []:
        old = s.get("id")
        if old:
            id_map[old] = f"F-{old}"
            s["id"] = id_map[old]
    for pm in fan.get("proposed_mocs") or []:
        if pm.get("id"):
            pm["id"] = f"F-{pm['id']}"
        pm["member_ids"] = [id_map.get(m, m) for m in (pm.get("member_ids") or [])]

    fan_stems = {s.get("stem") for s in (fan.get("suggestions") or [])}
    combined = copy.deepcopy(primary_wire)
    combined["suggestions"] = [
        s for s in (combined.get("suggestions") or [])
        if s.get("stem") not in fan_stems
    ] + (fan.get("suggestions") or [])
    combined["proposed_mocs"] = (
        (combined.get("proposed_mocs") or []) + (fan.get("proposed_mocs") or [])
    )
    return build_from_wire(combined, moc_template)


def _load_moc_template() -> str:
    """MOC template path from config/vault-config.yaml (empty on any error)."""
    import os
    try:
        config_path = os.path.join(os.getcwd(), "config", "vault-config.yaml")
        if not os.path.isfile(config_path):
            return ""
        import yaml
        with open(config_path, encoding="utf-8") as cf:
            cfg = yaml.safe_load(cf) or {}
        return cfg.get("templates", {}).get("mapping", {}).get("map_note", "")
    except Exception:  # noqa: BLE001
        return ""


def _parse_tags(value: str) -> list[str]:
    """
    Parse tags from a variety of formats:
      - Comma-separated:   topic/knowledge, type/note/normal
      - Hash-prefixed:     #topic/knowledge, #type/note/normal
      - YAML list:         ['topic/knowledge', 'type/note/normal']
      - Space-separated hash tags on one line
    Returns a list of clean tag strings (no leading #).
    """
    # Strip surrounding brackets/quotes that look like YAML inline list
    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]

    # Split on commas or spaces (if comma-separated, prefer comma)
    if "," in stripped:
        parts = [p.strip().strip("'\"") for p in stripped.split(",")]
    else:
        parts = [p.strip().strip("'\"") for p in stripped.split()]

    # Remove leading # and empty strings
    tags = [p.lstrip("#") for p in parts if p and p != "#"]
    return tags


def _parse_attachments(value: str) -> list[str]:
    """Parse the **Attachments:** line's backtick-delimited paths.

    e.g. "`100 Inbox/Images/karte.jpg`, `100 Inbox/scan.pdf`" ->
    ["100 Inbox/Images/karte.jpg", "100 Inbox/scan.pdf"].

    Extracts backtick-delimited segments rather than splitting on "," — the
    comma between entries is incidental, not the delimiter, so a comma
    inside a filename (e.g. "photo, cropped.jpg") must not fragment it.
    A literal backtick in a filename is unsupported by this line format
    (the render side has the same limitation: paths are wrapped in a single
    unescaped backtick pair).
    """
    return [p for p in re.findall(r"`([^`]*)`", value) if p]


# ──────────────────────────────────────────────────────────────────────────────
# Section parser
# ──────────────────────────────────────────────────────────────────────────────

def load_doc_anchor_map(doc_path: str) -> dict[str, dict[str, dict]]:
    """Build ``{section_id → {moc_stem → anchor}}`` from a suggestions-doc JSON.

    The reducer persists ``candidate_mocs: [{path, anchor}]`` on each
    create_atomic_note action (spec 022/023). This map is the structured
    apply-time DEFAULT anchor, indexed by section id (S##) and MOC stem so
    parse_section can look up the anchor for each checked MOC. Returns an empty
    map when the doc is absent or unreadable (backward-compatible — Pass-2 then
    relies on the rendered **Placement:** line alone).
    """
    try:
        with open(doc_path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return anchor_map_from_doc(doc)


def anchor_map_from_doc(doc: dict) -> dict[str, dict[str, dict]]:
    """``load_doc_anchor_map`` over an ALREADY-loaded doc (spec 034 T6.4a).

    The companion resolve document is read once for its members, its identity
    keys and its anchors; splitting the load from the mapping keeps that one
    read instead of three.
    """
    out: dict[str, dict[str, dict]] = {}
    for section in (doc or {}).get("sections") or []:
        sec_id = section.get("id")
        if not sec_id:
            continue
        per_moc: dict[str, dict] = {}
        for action in section.get("actions") or []:
            for cand in action.get("candidate_mocs") or []:
                anchor = cand.get("anchor")
                path = cand.get("path")
                if anchor and path:
                    per_moc[_moc_path_stem(path)] = anchor
        if per_moc:
            out[sec_id] = per_moc
    return out


# spec 034 T6.4a: each rendered document type is rendered FROM its own
# structured document, and identity is joined back from that one. Every type in
# use is listed, INCLUDING the ones whose answer is the primary doc, so that an
# absent entry means "nobody decided" and can be reported rather than guessed.
_PRIMARY_STRUCTURED_DOC = "suggestions-doc.json"
_STRUCTURED_DOC_BY_TYPE = {
    "suggestions": _PRIMARY_STRUCTURED_DOC,
    "suggestions-fan": "suggestions-fan-doc.json",
    "moc-proposal": _PRIMARY_STRUCTURED_DOC,  # reads the conventions block only
}


def _structured_doc_basename(doc_text: str) -> str:
    """Name the structured document a rendered document was rendered from.

    An unlisted type still resolves to the primary doc — the pre-fan behaviour,
    and a safe answer — but says so, because binding a document against the
    primary map when it has its own is exactly the T6.4a defect.
    """
    doc_type = _extract_tomo_doc_type(doc_text)
    if not doc_type:  # legacy document, no provenance — the primary IS correct
        return _PRIMARY_STRUCTURED_DOC
    basename = _STRUCTURED_DOC_BY_TYPE.get(doc_type)
    if basename is None:
        print(
            f"[warn] unrecognised tomo.doc_type {doc_type!r} — joining identity "
            f"from {_PRIMARY_STRUCTURED_DOC}; add it to "
            f"_STRUCTURED_DOC_BY_TYPE if it has its own structured document",
            file=sys.stderr,
        )
        return _PRIMARY_STRUCTURED_DOC
    return basename


def _default_doc_path(markdown_path: str, doc_text: str = "") -> str:
    """Derive the structured JSON path for a rendered markdown document.

    The pipeline writes each structured doc under ``tomo-tmp/`` (relative to
    the instance cwd). Prefer a sibling file next to the markdown; fall back to
    the canonical tomo-tmp path. Which basename is looked for follows the
    document's own ``tomo.doc_type``: a fan document is rendered from
    ``suggestions-fan-doc.json``, not from the primary ``suggestions-doc.json``,
    and binding it against the primary map leaves every key unset.
    """
    basename = _structured_doc_basename(doc_text)
    if markdown_path:
        sibling = os.path.join(os.path.dirname(markdown_path), basename)
        if os.path.isfile(sibling):
            return sibling
    fallback = os.path.join("tomo-tmp", basename)
    exists = "exists" if os.path.isfile(fallback) else "does NOT exist"
    print(
        f"note: no sibling {basename}; falling back to "
        f"cwd-relative {fallback} ({exists})",
        file=sys.stderr,
    )
    return fallback


def parse_section(
    section_id: str,
    lines: list[str],
    doc_anchors: dict[str, dict] | None = None,
) -> dict | None:
    """
    Parse one section and return a structured dict, or None on fatal error.

    Flat format (LLM output from suggestion-builder v0.6.0+):

        ### A1. Ausdaueraufbau (Endurance Training)
        - **Source:** `202301031251.md`
        - **Suggested name:** Ausdaueraufbau
        - **Type:** #type/note/normal
        - **Destination:** Atlas/202 Notes/
        - **Link to MOC:** [[2200 - Mind-Body Connection]]
        - **Template:** t_note_tomo
        - **Tags:** #topic/exercise
        - **Summary:** ...
        - **Why:** reasoning here
        - [x] Accept
        - [ ] Skip (keep in inbox)
        - [ ] Delete source

    Field aliases handled:
      - "Suggested name" / "Title"       → title
      - "Link to MOC" / "Parent MOC"     → parent_moc
      - "Destination"                    → destination
      - "Template"                       → template
      - "Summary"                        → summary
      - "Type"                           → type (strips leading # and backticks)
      - "Tags" / "Tag"                   → tags list

    Approval checkboxes:
      - "Accept" or "Approve" checked    → approved = true
      - "Delete source" checked          → delete_source = true
      - "Skip" checked (and not Accept)  → approved = false
    """
    result: dict = {
        "id": section_id,
        "source_path": None,
        "audio_peer": None,
        "attachments": [],
        "type": None,
        "approved": False,
        "delete_source": False,
        "keep_source": False,
        "action": None,
        "title": None,
        "tags": [],
        "parent_moc": None,
        "parent_mocs": [],  # all checked MOCs from Link to MOC checkboxes
        # spec 022/023: [{path, anchor}] for each CHECKED MOC. The anchor is the
        # apply-time placement: the reverse-parsed **Placement:** line (override)
        # when recognised, else the structured doc-JSON default (doc_anchors).
        "candidate_mocs": [],
        "destination": None,
        "template": None,
        "summary": None,
        "classification": None,
        # #88: per-item "Force Atomic Note" checkbox on a suppressed low-worthiness
        # light block. When ticked, reconcile routes the stem to the resolve
        # subflow (the light block lacks template/location/MOC, so the atomic is
        # rebuilt from source) rather than promoting the incomplete section.
        "force_atomic": False,
    }
    doc_anchors = doc_anchors or {}

    # State: when we see "Link to MOC:" header, subsequent checkboxes are
    # MOC selections (not approve/skip). Reset when we hit a Decision header
    # or another field.
    in_moc_list = False
    # The MOC checkbox most recently seen while in_moc_list — its following
    # **Placement:** line (if any) binds to it for anchor override.
    pending_moc: str | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # ── Placement line (spec 022/023) — binds to the most recent checked
        # MOC. Handled before generic field parsing so it does NOT reset the
        # MOC-list state (multiple MOC checkboxes can each carry a Placement).
        if in_moc_list and pending_moc and stripped.startswith("**Placement:**"):
            override = parse_placement_line(stripped)
            _bind_candidate_anchor(result, pending_moc, override, doc_anchors)
            pending_moc = None
            continue

        # ── Checkbox lines ────────────────────────────────────────
        cb_checked = RE_CHECKED.match(stripped)
        cb_unchecked = RE_UNCHECKED.match(stripped)
        if cb_checked or cb_unchecked:
            text = _checkbox_text(stripped)

            # MOC selection checkboxes (under "Link to MOC:" header)
            if in_moc_list:
                wl = _extract_wikilink(text)
                # Flush any prior checked MOC that had no Placement line — it
                # falls back to its structured doc-JSON default.
                if pending_moc:
                    _bind_candidate_anchor(result, pending_moc, None, doc_anchors)
                    pending_moc = None
                if wl and cb_checked:
                    result["parent_mocs"].append(wl)
                    pending_moc = wl
                continue

            # Decision checkboxes (force-atomic/approve/skip/delete/keep-source)
            text_lower = text.lower()
            if "force atomic" in text_lower:
                result["force_atomic"] = bool(cb_checked)
            elif "accept" in text_lower or "approve" in text_lower:
                result["approved"] = bool(cb_checked)
            elif "keep source" in text_lower:
                result["keep_source"] = bool(cb_checked)
            elif "delete source" in text_lower or text_lower.startswith("delete"):
                result["delete_source"] = bool(cb_checked)
            # "Skip" is the implicit inverse of Accept — no extra handling needed
            continue

        # ── Field lines: - **Field:** value  OR  **Field:** value ─
        # Strip leading "- " if present so RE_FIELD matches both forms.
        # Reject lines with leading whitespace that isn't a list marker: they
        # are body/continuation text, not structural fields (W1 guard).
        if line != line.lstrip() and not stripped.startswith("- "):
            continue
        field_line = stripped
        if field_line.startswith("- "):
            field_line = field_line[2:].strip()

        m = RE_FIELD.match(field_line)
        if not m:
            continue

        # Key may include trailing colon when written as **Field:** (colon inside
        # bold markers). Strip it and any whitespace before comparing.
        key = m.group(1).strip().rstrip(":").strip().lower()
        val = m.group(2).strip()

        # `**Placement:**` and `**Other sections in this MOC:**` are part of a
        # MOC block — they must NOT close the checkbox region (otherwise the
        # next `- [x] [[MOC]]` checkbox is misread as a Decision box). Skip them
        # here; Placement is handled above, Other-sections is display-only.
        if key in ("placement", "other sections in this moc"):
            continue

        # Any new field header ends the MOC checkbox region. Flush a still-
        # pending checked MOC to its structured doc-JSON default anchor.
        if pending_moc:
            _bind_candidate_anchor(result, pending_moc, None, doc_anchors)
            pending_moc = None
        in_moc_list = False

        if key == "source":
            src = RE_SOURCE.search(val)
            if src:
                result["source_path"] = src.group(1) or src.group(2)
            else:
                # Voice source set: "[[stem]] + [[audio.m4a]]" → stem + peer.
                # findall captures ALL wikilinks; index 0 is the transcript
                # stem, index 1 (when present) is the audio peer basename.
                # The DISPLAY text is taken, not the target: a path-qualified
                # source link (spec 034 T5.1) carries the bare stem as its
                # alias, and `source_path` stays that bare stem (ADR-2).
                wikilinks = [
                    (alias.strip() if alias and alias.strip() else target.strip())
                    for target, alias in RE_WIKILINK_ALIASED.findall(val)
                ]
                result["source_path"] = wikilinks[0] if wikilinks else val
                result["audio_peer"] = wikilinks[1] if len(wikilinks) >= 2 else None

        elif key == "type":
            # "#type/note/normal" or "fleeting_note (confidence: 0.85)"
            tm = RE_TYPE.match(val)
            if tm:
                result["type"] = tm.group(1)
            else:
                # Strip backticks, leading #, take first token
                cleaned = val.strip("`").lstrip("#").strip()
                result["type"] = cleaned.split()[0] if cleaned else None

        elif key in ("title", "suggested name", "suggested title", "name"):
            # Strip trailing edit hints like "← change if you want..."
            clean_val = val.split("←")[0].strip() if "←" in val else val
            result["title"] = clean_val

        elif key in ("tags", "tag", "new tags to add", "new tags"):
            result["tags"] = _parse_tags(val)

        elif key == "attachments":
            result["attachments"] = _parse_attachments(val)

        elif key in ("parent moc", "parent_moc", "parentmoc", "link to moc", "moc"):
            in_moc_list = True  # subsequent checkboxes are MOC selections
            wl = _extract_wikilink(val)
            if wl:
                result["parent_moc"] = wl

        elif key in ("destination", "location", "move to"):
            # Strip wrapping backticks/brackets/wikilinks and edit hints
            cleaned = val.split("←")[0].strip().strip("`").strip()
            wl = _extract_wikilink(cleaned)
            result["destination"] = wl or cleaned

        elif key == "template":
            cleaned = val.split("←")[0].strip().strip("`").strip()
            wl = _extract_wikilink(cleaned)
            result["template"] = wl or cleaned

        elif key == "summary":
            result["summary"] = val

        elif key == "classification":
            result["classification"] = val

    # Flush a checked MOC still pending at end-of-section (no Placement line,
    # no trailing field) to its structured doc-JSON default anchor.
    if pending_moc:
        _bind_candidate_anchor(result, pending_moc, None, doc_anchors)

    # ── MOC consolidation ──────────────────────────────────────
    # If parent_moc was not set directly but parent_mocs has checked items,
    # use the first checked MOC as the primary parent_moc.
    if not result["parent_moc"] and result["parent_mocs"]:
        result["parent_moc"] = result["parent_mocs"][0]

    # ── Delete semantics ─────────────────────────────────────────
    # If Accept is checked, Delete is irrelevant — we keep the source.
    if result["approved"]:
        result["delete_source"] = False

    return result


def _is_source_field_line(line: str) -> bool:
    """True when a section line is a `**Source:**` field (block boundary).

    Mirrors parse_section's field detection: strip a leading "- ", match
    RE_FIELD, normalise the key the same way, and compare to "source".

    The renderer always emits **Source:** flush-left (column 0). Any line
    with leading whitespace is body/continuation text, not a field boundary.
    """
    if line != line.lstrip():
        return False
    stripped = line.strip()
    if not stripped:
        return False
    field_line = stripped[2:].strip() if stripped.startswith("- ") else stripped
    m = RE_FIELD.match(field_line)
    if not m:
        return False
    key = m.group(1).strip().rstrip(":").strip().lower()
    return key == "source"


def split_section_into_blocks(
    section_id: str, lines: list[str]
) -> list[tuple[str, list[str]]]:
    """Split one section's lines into per-atomic-block (block_id, lines) groups.

    A new block begins at each `**Source:**` field line (the first line the
    renderer emits per atomic block). Sections with zero or one Source line
    yield a single group whose id == section_id, so single-block output stays
    byte-identical to the pre-split behaviour. Lines preceding the first
    Source line (heading-level decision boxes, blanks) are attached to the
    first block.
    """
    boundaries = [i for i, ln in enumerate(lines) if _is_source_field_line(ln)]
    if len(boundaries) < 2:
        return [(section_id, lines)]

    groups: list[tuple[str, list[str]]] = []
    for n, start in enumerate(boundaries):
        end = boundaries[n + 1] if n + 1 < len(boundaries) else len(lines)
        if n == 0:
            # Attach any preamble (lines before the first Source) to block 0.
            block_lines = lines[:end]
            block_id = section_id
        else:
            block_lines = lines[start:end]
            block_id = f"{section_id}#{n}"
        groups.append((block_id, block_lines))
    return groups


# ──────────────────────────────────────────────────────────────────────────────
# Document splitter
# ──────────────────────────────────────────────────────────────────────────────

def split_into_sections(text: str) -> list[tuple[str, list[str]]]:
    """
    Split the document into (section_id, lines) tuples for each S## section.
    Lines before the first S## header are ignored (document header/preamble).
    """
    sections: list[tuple[str, list[str]]] = []
    current_id: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        m = RE_SECTION_HEADER.match(line)
        if m:
            if current_id is not None:
                sections.append((current_id, current_lines))
            current_id = m.group(1).upper()
            current_lines = []
        elif current_id is not None:
            # A level-2 header that isn't an S## section ends the current section.
            # This prevents "## Proposed MOCs", "## Needs Attention", etc. from
            # bleeding into the last S## item.
            if line.startswith("## ") and not RE_SECTION_HEADER.match(line):
                sections.append((current_id, current_lines))
                current_id = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_id is not None:
        sections.append((current_id, current_lines))

    return sections


# ──────────────────────────────────────────────────────────────────────────────
# Proposed MOCs parser
# ──────────────────────────────────────────────────────────────────────────────

RE_PROPOSED_MOC_HEADER = re.compile(r"^###\s+Proposed MOC:\s*(.*)", re.IGNORECASE)


def _load_json_doc(path: str) -> dict:
    """Load a structured suggestions-doc JSON, or {} on any error."""
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _parent_marker_from_doc(path: str) -> str:
    """Resolve the active profile's parent marker from a suggestions-doc JSON.

    The reducer writes an additive ``conventions`` block (spec 028 T2.3). Older
    artifacts without that block — and any read/parse error — fall back to the
    default ``up::`` (spec 028 ADR-3), keeping byte-identical behaviour.
    """
    conv = _load_json_doc(path).get("conventions")
    if isinstance(conv, dict):
        marker = conv.get("parent_marker")
        if isinstance(marker, str) and marker:
            return marker
    return "up::"


def _topic_member_stems(doc: dict) -> dict[str, list[str]]:
    """Map proposed-MOC topic → member source-stems from a structured doc.

    The reducer records each proposed MOC's member SNN ids in ``items``; the
    markdown render drops them (only ``note_titles`` survive). Recover them by
    resolving each ``items`` SNN id to its section ``stem``.
    """
    id_to_stem: dict[str, str] = {}
    for sec in doc.get("sections") or []:
        sid, stem = sec.get("id"), sec.get("stem")
        if sid and stem:
            id_to_stem[sid] = stem
    out: dict[str, list[str]] = {}
    for pm in doc.get("proposed_mocs") or []:
        topic = (pm.get("topic") or "").strip()
        stems = [id_to_stem[i] for i in (pm.get("items") or []) if i in id_to_stem]
        if topic and stems:
            out[topic] = stems
    return out


def parse_proposed_mocs(
    text: str, config_template: str = "", topic_members: dict | None = None
) -> list[dict]:
    """Parse the ## Proposed MOCs section and return approved MOC items.

    Each approved Proposed MOC becomes a confirmed_item with action=create_moc.

    ``topic_members`` (topic → member source-stems, from the structured doc)
    enriches each block's ``member_stems`` BEFORE the same-name merge, so a name
    merged from multiple topics keeps every topic's members.
    """
    topic_members = topic_members or {}
    mocs: list[dict] = []

    # Find the ## Proposed MOCs section
    lines = text.splitlines()
    in_section = False
    moc_blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        if line.startswith("## Proposed MOCs"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            # Next top-level section ends Proposed MOCs
            break
        if not in_section:
            continue

        m = RE_PROPOSED_MOC_HEADER.match(line)
        if m:
            if current_block:
                moc_blocks.append(current_block)
            current_block = [line]
        elif current_block:
            current_block.append(line)

    if current_block:
        moc_blocks.append(current_block)

    for idx, block in enumerate(moc_blocks, start=1):
        name = ""
        parent = ""
        items_str = ""
        approved = False
        tags: list[str] = []
        # The block's first line is the "### Proposed MOC: <topic>" header. The
        # markdown render drops the SNN members (only note_titles survive), so
        # the topic is the key used to recover members from the structured
        # suggestions-doc JSON (see _topic_member_stems / the binding pass).
        thm = RE_PROPOSED_MOC_HEADER.match(block[0]) if block else None
        topic = thm.group(1).strip() if thm else ""

        for line in block:
            stripped = line.strip()

            # Check for approve/skip checkboxes — only the checked one matters
            cb_checked = RE_CHECKED.match(stripped)
            cb_unchecked = RE_UNCHECKED.match(stripped)
            if cb_checked:
                cb_text = cb_checked.group(1).lower()
                if "approve" in cb_text:
                    approved = True
            elif cb_unchecked:
                # Only unchecked approve line can revoke approval
                cb_text = cb_unchecked.group(1).lower()
                if "approve" in cb_text:
                    approved = False

            # Parse fields
            field_line = stripped
            if field_line.startswith("- "):
                field_line = field_line[2:].strip()
            m = RE_FIELD.match(field_line)
            if m:
                key = m.group(1).strip().rstrip(":").strip().lower()
                val = m.group(2).strip()
                # Strip edit hints
                if "←" in val:
                    val = val[:val.index("←")].strip()
                if key == "name":
                    name = val
                elif key == "parent":
                    wl = _extract_wikilink(val)
                    parent = wl or val
                elif key in ("supporting items", "items"):
                    items_str = val
                elif key in ("tags", "tag", "new tags", "suggested tags"):
                    tags = _parse_tags(val)

        if not approved or not name:
            continue

        # Derive MOC destination from parent path or default to Maps folder
        parent_stem = parent.rsplit("/", 1)[-1] if parent else ""
        if parent_stem.endswith(".md"):
            parent_stem = parent_stem[:-3]

        moc_id = f"MOC{idx:02d}"
        mocs.append({
            "id": moc_id,
            "source_path": None,
            "type": "moc",
            "approved": True,
            "delete_source": False,
            "action": "create_moc",
            "title": name,
            "tags": tags,
            "parent_moc": parent,
            "parent_mocs": [parent] if parent else [],
            "destination": "Atlas/200 Maps/",
            "template": config_template,
            "summary": None,
            "classification": None,
            "supporting_items": items_str,
            # Internal (stripped before output by the binding pass): the topic
            # keys structured-doc member recovery; member_stems holds the
            # recovered source-stems until they're mapped to confirmed ids.
            "topic": topic,
            "member_stems": list(topic_members.get(topic, [])),
        })

    return _merge_proposed_mocs_by_name(mocs)


def _merge_proposed_mocs_by_name(mocs: list[dict]) -> list[dict]:
    """Collapse approved Proposed MOCs that resolve to the same final Name into a
    single create_moc whose supporting_items and tags are the UNION of the group
    (#67). Decision 2026-06-17: merge on Name only — same-name proposals collapse
    regardless of parent; the first occurrence's parent is kept. Without this, two
    proposals renamed to one Name emit two create_moc at the same destination and
    the second overwrites the first on apply, silently dropping children.

    Names are compared case-folded (CON-6, spec 034 T6.0c): `Travel (MOC)` and
    `travel (MOC)` are one file on this filesystem, so they are one proposal.
    `casefold()`, not `.lower()` — `ß` folds to `ss` and these are German notes.
    The key folds; the survivor keeps the spelling its author wrote. Folding
    here removes the case-only pair upstream of every consumer, so the
    downstream `by_dest` fold is the defence-in-depth its comment claims and
    `derive_expected` counts what is actually emitted.
    """
    merged: dict[str, dict] = {}
    order: list[str] = []
    for moc in mocs:
        name = moc.get("title", "").casefold()
        head = merged.get(name)
        if head is None:
            merged[name] = moc
            order.append(name)
            continue
        head["supporting_items"] = _union_supporting_items(
            head.get("supporting_items"), moc.get("supporting_items")
        )
        for tag in moc.get("tags") or []:
            if tag not in head["tags"]:
                head["tags"].append(tag)
        # Union recovered members so a name merged from multiple topics
        # (e.g. "Gesellschaftsspiele" + "Games" → "Board Games (MOC)") keeps
        # every member's stem for the down-link binding pass.
        head_ms = head.setdefault("member_stems", [])
        for s in moc.get("member_stems") or []:
            if s not in head_ms:
                head_ms.append(s)
        # Record what was absorbed, so the run can say what it did (CON-2).
        # Internal field, same lifecycle as `member_stems` and `topic`: it rides
        # on the SURVIVOR across repeated merge calls and is lifted out at the
        # same two strip sites. The markdown path merges twice and the second
        # call has no memory of the first, so a record built per call would
        # emit a second entry for a survivor already merged in stage 1.
        # Appended, never a set: the absorbed list's order is asserted, and a
        # set would make it implementation-defined.
        head_absorbed = head.setdefault("absorbed_names", [])
        head_absorbed.append(moc.get("title", ""))
        head_absorbed.extend(moc.get("absorbed_names") or [])
    return [merged[name] for name in order]


# The merge's sibling wording lives in `render_actions._CASE_NOTE`, which says
# the same thing about a destination clash. Restated rather than imported: the
# parser has no dependency on the action builder, and buying one for a sentence
# would be the worse trade.
_MERGE_CASE_NOTE = (
    "The names differ only in case — the filesystem may treat them as one file."
)


def _lift_merged_moc_records(items: list[dict]) -> list[dict]:
    """Pop the internal absorbed-spellings carrier and return user-facing records.

    One record per SURVIVING name carrying the group it absorbed — the shape
    `validate_destinations`' clash record already uses (`dropped: [...]` inside
    one record rather than one record per claimant). A pairwise record would
    emit two entries for a three-way collapse.

    Called at the same sites that strip `member_stems` and `topic`; items that
    absorbed nothing carry no field and produce no record.
    """
    records: list[dict] = []
    for item in items:
        absorbed = item.pop("absorbed_names", None)
        if not absorbed:
            continue
        name = item.get("title", "")
        # Every absorbed spelling is casefold-equal to the survivor's by
        # construction, so an unequal one differed only in case.
        case_only = any(a != name for a in absorbed)
        count = len(absorbed) + 1
        reason = (
            f"{count} approved proposals resolve to this Name — one MOC was "
            f"created, with every proposal's tags and supporting items combined"
        )
        records.append({
            "name": name,
            "case_only": case_only,
            "absorbed": list(absorbed),
            "reason": f"{reason}. {_MERGE_CASE_NOTE}" if case_only else f"{reason}.",
        })
    return records


# ──────────────────────────────────────────────────────────────────────────────
# MOC proposal-doc parser  (F-43 T4.1)
# ──────────────────────────────────────────────────────────────────────────────

# Frontmatter YAML block extractor
RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _extract_frontmatter(text: str) -> dict[str, str]:
    """Extract key→value pairs from a YAML frontmatter block.

    Returns a flat dict of string values.  No full YAML parse — just
    simple `key: value` lines (sufficient for frontmatter dispatch).
    """
    m = RE_FRONTMATTER.match(text)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def _parse_children_list(section_text: str) -> list[str]:
    """Return all `[x]`-ticked wikilink stems from a Children section.

    Handles lines like:
        - [x] `[[note-stem]]` (annotation text)
        - [x] [[note-stem]]

    Only checked items are extracted; unchecked `[ ]` lines are ignored.
    """
    stems: list[str] = []
    for line in section_text.splitlines():
        if not RE_CHECKED.match(line.strip()):
            continue
        wl = RE_WIKILINK.search(line)
        if wl:
            stems.append(wl.group(1).strip())
    return stems


def _extract_tomo_doc_type(text: str) -> str | None:
    """Return the value of ``tomo.doc_type`` from a nested YAML frontmatter block.

    The ``tomo:`` key introduces an indented sub-block; standard flat-key
    parsing misses nested values.  This helper scans within the frontmatter
    for a ``tomo:`` section and reads the first ``doc_type:`` line indented
    under it.
    """
    m = RE_FRONTMATTER.match(text)
    if not m:
        return None
    in_tomo = False
    for line in m.group(1).splitlines():
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if not in_tomo:
            if stripped.startswith("tomo:"):
                in_tomo = True
            continue
        # Inside the tomo: sub-block — exit when a non-indented key appears
        if indent == 0 and stripped and not stripped.startswith("#"):
            break
        if stripped.startswith("doc_type:"):
            _, _, v = stripped.partition(":")
            return v.strip()
    return None


def _is_moc_proposal_doc(text: str, filename: str = "") -> bool:
    """Return True when the document is a MOC proposal-doc.

    Dispatch criteria (first match wins, in priority order):
    1. (PRIMARY) frontmatter ``tomo.doc_type: moc-proposal``
    2. (FALLBACK) filename matches either of the two known patterns:
       - new: ``<YYYY-MM-DD>_<HHMM>_moc-proposal-<slug>.md``
       - old: ``tomo-moc-proposal-<YYYYMMDD>-<HHMM>-<slug>.md``
       Both are accepted so that files produced before the convention
       alignment (suggestions-reducer.py L558-561) still match.
    3. (FALLBACK) frontmatter ``type: tomo-proposal``
    """
    if _extract_tomo_doc_type(text) == "moc-proposal":
        return True
    basename = os.path.basename(filename)
    if basename.startswith("tomo-moc-proposal-"):  # old pattern
        return True
    if "_moc-proposal-" in basename and basename.endswith(".md"):  # new pattern
        return True
    fm = _extract_frontmatter(text)
    return fm.get("type") == "tomo-proposal"


# RE for the Cluster field:  **Cluster:** N Notes — kw1, kw2, kw3
RE_CLUSTER_LINE = re.compile(
    r"\*\*Cluster:\*\*\s*\d+\s+Notes\s*[—–-]+\s*(.*)", re.IGNORECASE
)

# RE for children wikilinks: - [x] `[[stem]]` or - [ ] `[[stem]]`
RE_CHILD_WIKILINK = re.compile(r"`?\[\[([^\]]+)\]\]`?")


def _split_moc_blocks(lines: list[str]) -> list[tuple[str, str, list[str]]]:
    """Split document lines into ``### MOCxx`` blocks.

    Returns a list of ``(moc_id, title, block_lines)`` tuples — one per
    ``### MOCxx — Title`` header found.  A block ends when the next MOC header
    or an h1/h2 section boundary is encountered.
    """
    moc_blocks: list[tuple[str, str, list[str]]] = []
    current_moc_id: str | None = None
    current_moc_title: str = ""
    current_moc_lines: list[str] = []

    for line in lines:
        m = RE_MOC_SECTION_HEADER.match(line)
        if m:
            if current_moc_id is not None:
                moc_blocks.append((current_moc_id, current_moc_title, current_moc_lines))
            current_moc_id = m.group(1).upper()
            current_moc_title = m.group(2).strip()
            current_moc_lines = []
        elif current_moc_id is not None:
            if line.startswith("## ") or line.startswith("# "):
                moc_blocks.append((current_moc_id, current_moc_title, current_moc_lines))
                current_moc_id = None
                current_moc_lines = []
            else:
                current_moc_lines.append(line)

    if current_moc_id is not None:
        moc_blocks.append((current_moc_id, current_moc_title, current_moc_lines))

    return moc_blocks


def enumerate_all_moc_sections(
    content: str,
) -> list[tuple[str, str, list[str], list[str]]]:
    """Return ALL ``### MOCxx`` sections from a proposal-doc, accepted or not.

    Each tuple is ``(moc_id, title, candidate_stems, topic_keywords)`` extracted
    from the rendered body.  Used by the squelch-persist helper (T5.2) to identify
    rejected clusters (enumerate_all − accepted).

    Extraction strategy:
    - ``candidate_stems``  — wikilinks from ``#### Children`` items
    - ``topic_keywords``   — comma-separated list from ``**Cluster:** N Notes — kw1, kw2``
    """
    lines = content.splitlines()
    results: list[tuple[str, str, list[str], list[str]]] = []

    moc_blocks = _split_moc_blocks(lines)

    # ── Extract stems + keywords from each block ─────────────────────────────
    for moc_id, title, block_lines in moc_blocks:
        topic_keywords: list[str] = []
        candidate_stems: list[str] = []
        in_children_section = False

        for bl in block_lines:
            stripped = bl.strip()

            # **Cluster:** N Notes — kw1, kw2, kw3
            cm = RE_CLUSTER_LINE.search(stripped)
            if cm:
                raw_kws = cm.group(1).strip()
                topic_keywords = [k.strip() for k in raw_kws.split(",") if k.strip()]
                continue

            # #### Children section
            if re.match(r"^####\s+Children", stripped, re.IGNORECASE):
                in_children_section = True
                continue
            if in_children_section and stripped.startswith("####"):
                in_children_section = False
                continue
            if in_children_section:
                wl = RE_CHILD_WIKILINK.search(bl)
                if wl:
                    candidate_stems.append(wl.group(1).strip())

        results.append((moc_id, title, candidate_stems, topic_keywords))

    return results


def enumerate_moc_sections_split(
    content: str,
) -> tuple[list[dict], list[dict]]:
    """Split a proposal-doc's MOC sections into ticked and unticked clusters.

    Each returned cluster dict contains:
        moc_id          — e.g. "MOC01"
        title           — heading title string
        children        — list of wikilink stem strings from #### Children
        candidate_stems — same list (alias for topic_signature computation)
        topic_keywords  — list from **Cluster:** N Notes — kw1, kw2 line
        topic_signature — 16-char hex from topic_signature.compute_topic_signature

    Returns ``(ticked, unticked)`` where each element is a list of such dicts.
    A cluster is ticked when its block contains ``- [x] Accept`` (case-insensitive).

    Used by the F-47 MOC-consumption branch to dispatch instruction-builder
    and persist unticked clusters to squelch (AC-5.2).
    """
    # Lazy-import to avoid mandatory dependency for callers that don't need it.
    try:
        from lib.topic_signature import compute_topic_signature
    except ImportError:
        # Fallback for direct-module-load outside the scripts/ sys.path context.
        import sys as _sys
        import os as _os
        _lib_path = _os.path.join(_os.path.dirname(__file__), "lib")
        _sys.path.insert(0, _lib_path)
        from topic_signature import compute_topic_signature  # type: ignore[no-redef]

    lines = content.splitlines()
    moc_blocks = _split_moc_blocks(lines)

    ticked: list[dict] = []
    unticked: list[dict] = []

    for moc_id, title, block_lines in moc_blocks:
        # ── Accept check ─────────────────────────────────────────────────────
        is_ticked = any(
            RE_CHECKED.match(bl.strip()) and
            RE_CHECKED.match(bl.strip()).group(1).strip().lower() == "accept"
            for bl in block_lines
        )

        # ── Extract topic_keywords ────────────────────────────────────────────
        topic_keywords: list[str] = []
        for bl in block_lines:
            cm = RE_CLUSTER_LINE.search(bl.strip())
            if cm:
                raw_kws = cm.group(1).strip()
                topic_keywords = [k.strip() for k in raw_kws.split(",") if k.strip()]
                break

        # ── Extract children from #### Children section ───────────────────────
        children: list[str] = []
        in_children = False
        for bl in block_lines:
            stripped = bl.strip()
            if re.match(r"^####\s+Children", stripped, re.IGNORECASE):
                in_children = True
                continue
            if in_children and stripped.startswith("####"):
                break
            if in_children:
                wl = RE_CHILD_WIKILINK.search(bl)
                if wl:
                    children.append(wl.group(1).strip())

        # ── Build cluster dict ────────────────────────────────────────────────
        cluster: dict = {
            "moc_id": moc_id,
            "title": title,
            "children": children,
            "candidate_stems": children,  # children ARE the candidate stems here
            "topic_keywords": topic_keywords,
        }
        cluster["topic_signature"] = compute_topic_signature(cluster)

        if is_ticked:
            ticked.append(cluster)
        else:
            unticked.append(cluster)

    return ticked, unticked


def parse_moc_proposal_doc(
    content: str, filename: str = "", parent_marker: str = "up::"
) -> list[dict]:
    """Parse a MOC proposal-doc and return a list of ConfirmedMOCProposal dicts.

    Each accepted cluster (``- [x] Accept``) produces one entry:
    {
        "moc_id":                       str,   # e.g. "MOC01"
        "title":                        str,
        "location":                     str,
        "template":                     str,
        "parent":                       str | None,
        "children":                     list[str],
        "override_preserve_existing_up": bool,
    }

    Skips clusters whose ``- [ ] Accept`` is unchecked.
    Returns [] when no clusters are accepted.
    """
    lines = content.splitlines()
    proposals: list[dict] = []

    # ── Split into ### MOCxx sections ────────────────────────────────────────
    moc_blocks = _split_moc_blocks(lines)

    # parent_marker is constant for the call — compile the override header regex
    # once here rather than per block.
    _override_header_re = re.compile(
        rf"^####\s+{re.escape(parent_marker)}.*Override", re.IGNORECASE
    )

    # ── Parse each block ────────────────────────────────────────────────────
    for moc_id, heading_title, block_lines in moc_blocks:
        # ── Accept gate ──────────────────────────────────────────────────────
        accepted = False
        for bl in block_lines:
            cb = RE_CHECKED.match(bl.strip())
            if cb and cb.group(1).strip().lower() == "accept":
                accepted = True
                break
        if not accepted:
            continue

        # ── Title field (may be edited inline) ───────────────────────────────
        title = heading_title  # fallback
        for bl in block_lines:
            stripped = bl.strip()
            field_line = stripped[2:].strip() if stripped.startswith("- ") else stripped
            fm = RE_FIELD.match(field_line)
            if fm:
                key = fm.group(1).strip().rstrip(":").strip().lower()
                val = fm.group(2).strip()
                if key == "title":
                    # Strip backticks
                    title = val.strip("`")
                    break

        # ── Location field ────────────────────────────────────────────────────
        location: str = "Atlas/200 Maps/"
        for bl in block_lines:
            stripped = bl.strip()
            field_line = stripped[2:].strip() if stripped.startswith("- ") else stripped
            fm = RE_FIELD.match(field_line)
            if fm:
                key = fm.group(1).strip().rstrip(":").strip().lower()
                val = fm.group(2).strip()
                if key in ("location", "destination"):
                    location = val.strip("`")
                    break

        # ── Template field ────────────────────────────────────────────────────
        template: str = ""
        for bl in block_lines:
            stripped = bl.strip()
            field_line = stripped[2:].strip() if stripped.startswith("- ") else stripped
            fm = RE_FIELD.match(field_line)
            if fm:
                key = fm.group(1).strip().rstrip(":").strip().lower()
                val = fm.group(2).strip()
                if key == "template":
                    # Strip wikilink brackets and backticks
                    wl = _extract_wikilink(val)
                    template = (wl or val).strip("`").strip()
                    break

        # ── Parent section (#### Parent) — first [x] wins ────────────────────
        parent: str | None = None
        in_parent_section = False
        for bl in block_lines:
            stripped = bl.strip()
            if stripped.startswith("#### Parent"):
                in_parent_section = True
                continue
            if in_parent_section and stripped.startswith("####"):
                # Next sub-section ends Parent block
                in_parent_section = False
                continue
            if in_parent_section:
                cb = RE_CHECKED.match(stripped)
                if cb:
                    cb_text = cb.group(1).strip()
                    # Skip "kein parent" option
                    if "kein parent" not in cb_text.lower():
                        wl = RE_WIKILINK.search(cb_text)
                        if wl:
                            parent = wl.group(1).strip()
                        else:
                            # up:: `[[stem]]` pattern: extract from backtick wikilink
                            bk = re.search(r"`\[\[([^\]]+)\]\]`", cb_text)
                            if bk:
                                parent = bk.group(1).strip()
                        if parent:
                            break  # first checked wins

        # ── Children section (#### Children) — all [x] ───────────────────────
        children: list[str] = []
        in_children_section = False
        children_lines: list[str] = []
        for bl in block_lines:
            stripped = bl.strip()
            if re.match(r"^####\s+Children", stripped, re.IGNORECASE):
                in_children_section = True
                continue
            if in_children_section and stripped.startswith("####"):
                in_children_section = False
                continue
            if in_children_section:
                children_lines.append(bl)
        children = _parse_children_list("\n".join(children_lines))

        # ── Override toggle (#### <parent_marker>-Handling Override) ──────────
        override_preserve = False
        in_override_section = False
        for bl in block_lines:
            stripped = bl.strip()
            if _override_header_re.match(stripped):
                in_override_section = True
                continue
            if in_override_section and stripped.startswith("####"):
                in_override_section = False
                continue
            if in_override_section:
                cb = RE_CHECKED.match(stripped)
                if cb:
                    cb_text = cb.group(1).lower()
                    if ("behalten" in cb_text or "keep" in cb_text
                            or "preserve" in cb_text or "related" in cb_text):
                        override_preserve = True
                        break

        proposals.append({
            "moc_id": moc_id,
            "title": title,
            "location": location,
            "template": template,
            "parent": parent,
            "children": children,
            "override_preserve_existing_up": override_preserve,
        })

    return proposals


# ──────────────────────────────────────────────────────────────────────────────
# Daily Notes Updates parser
# ──────────────────────────────────────────────────────────────────────────────

RE_DAILY_DATE_HEADER = re.compile(r"^###\s+\[\[([^\]]+)\]\]")
RE_DAILY_TRACKER_LINE = re.compile(r"^\s*-\s+\*\*([^*]+)\*\*\s*→\s*`?([^`\n]+)`?")
RE_DAILY_LOG_LINE = re.compile(r"^\s*-\s+(.+?)\s+—\s+(.*)")
RE_TIME_HH_MM = re.compile(r"^\d{1,2}:\d{2}$")

POSITION_TOKENS = {"after_last_line", "before_first_line"}


def _parse_time_position(raw: str) -> tuple[str | None, str]:
    """Parse a time/position string into (time, position).

    Returns:
        (time, position) where:
        - "10:00" → ("10:00", "at_time")
        - "after_last_line" → (None, "after_last_line")
        - "before_first_line" → (None, "before_first_line")
        - "end of day" (legacy) → (None, "after_last_line")
        - anything else → (None, "after_last_line")
    """
    if RE_TIME_HH_MM.match(raw):
        return raw, "at_time"
    if raw in POSITION_TOKENS:
        return None, raw
    # Legacy fallback: "end of day" or any unrecognized string
    return None, "after_last_line"


def parse_daily_updates(text: str) -> list[dict]:
    """Parse the ## Daily Notes Updates section.

    Returns a list of daily update entries:
    [{date, trackers: [{field, value, reason, source_stem, accepted}],
      log_entries: [{time, content, reason, source_stem, accepted}]}]
    """
    lines = text.splitlines()
    in_section = False
    entries: list[dict] = []
    current_date: str | None = None
    current_entry: dict | None = None
    block_type: str | None = None  # "trackers", "log_entries", "log_links"
    pending_item: dict | None = None

    def _flush_pending():
        nonlocal pending_item
        if pending_item and current_entry:
            if block_type and block_type in current_entry:
                current_entry[block_type].append(pending_item)
        pending_item = None

    for line in lines:
        stripped = line.strip()

        if stripped == "## Daily Notes Updates":
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            _flush_pending()
            break
        if not in_section:
            continue

        # Date header: ### [[2026-03-26]]
        dm = RE_DAILY_DATE_HEADER.match(stripped)
        if dm:
            _flush_pending()
            current_date = dm.group(1)
            # Reuse existing entry for this date (same date can appear
            # with trackers first, then log entries in a later block)
            existing = next((e for e in entries if e["date"] == current_date), None)
            if existing:
                current_entry = existing
            else:
                current_entry = {
                    "date": current_date,
                    "trackers": [],
                    "log_entries": [],
                    "log_links": [],
                }
                entries.append(current_entry)
            block_type = None
            continue

        if not current_entry:
            continue

        # Block type headers
        if stripped.startswith("**Possible Trackers:**"):
            _flush_pending()
            block_type = "trackers"
            continue
        if stripped.startswith("**Possible Log Entries"):
            _flush_pending()
            block_type = "log_entries"
            continue
        if stripped.startswith("**Possible Log Links"):
            _flush_pending()
            block_type = "log_links"
            continue

        # Accept checkbox for the current pending item
        cb = RE_CHECKED.match(stripped)
        if cb and "accept" in cb.group(1).lower():
            if pending_item:
                pending_item["accepted"] = True
            continue
        cb_un = RE_UNCHECKED.match(stripped)
        if cb_un and "accept" in cb_un.group(1).lower():
            if pending_item:
                pending_item["accepted"] = False
            continue

        # Force Atomic Note checkbox — log_entry only. When checked, the
        # source note gets promoted to a confirmed create_atomic_note even
        # if the per-item section's own Approve box is empty. Captured
        # here as a hint; the main() function reconciles against the
        # per-item sections at the end.
        if cb and "force atomic note" in cb.group(1).lower():
            if pending_item and block_type == "log_entries":
                pending_item["force_atomic_note"] = True
            continue
        if cb_un and "force atomic note" in cb_un.group(1).lower():
            if pending_item and block_type == "log_entries":
                pending_item["force_atomic_note"] = False
            continue

        # Sub-fields: Reason, Source, Time
        if stripped.startswith("- Reason:") and pending_item:
            pending_item["reason"] = stripped.split(":", 1)[1].strip()
            continue
        if stripped.startswith("- Source:") and pending_item:
            wl = _wikilink_display(stripped)
            if wl:
                pending_item["source_stem"] = wl
            continue
        if stripped.startswith("- Time:") and pending_item:
            pending_item["time"] = stripped.split(":", 1)[1].strip()
            continue

        # Tracker line: - **Sport** → `true`
        if block_type == "trackers":
            tm = RE_DAILY_TRACKER_LINE.match(stripped)
            if tm:
                _flush_pending()
                pending_item = {
                    "field": tm.group(1).strip(),
                    "value": tm.group(2).strip(),
                    "reason": "",
                    "source_stem": "",
                    "accepted": False,
                }
                continue

        # Log entry line: - after_last_line — content  OR  - 10:00 — content
        if block_type in ("log_entries", "log_links"):
            lm = RE_DAILY_LOG_LINE.match(stripped)
            if lm:
                _flush_pending()
                raw_time = lm.group(1).strip()
                time_val, position_val = _parse_time_position(raw_time)
                if block_type == "log_entries":
                    pending_item = {
                        "time": time_val,
                        "position": position_val,
                        "content": lm.group(2).strip(),
                        "reason": "",
                        "source_stem": "",
                        "accepted": False,
                        # Populated when the user ticks the per-entry
                        # "Force Atomic Note" checkbox — default off.
                        "force_atomic_note": False,
                    }
                elif block_type == "log_links":
                    wl = _extract_wikilink(stripped)
                    pending_item = {
                        "target_stem": wl or raw_time,
                        "time": time_val,
                        "position": position_val,
                        "reason": "",
                        "accepted": False,
                    }
                continue

    _flush_pending()
    return entries


# ──────────────────────────────────────────────────────────────────────────────
# Tag-Handler Updates parser  (spec 024 T4.1)
# ──────────────────────────────────────────────────────────────────────────────

# Group-id field line:  **Group:** `th-<handler>-<target-slug>`
RE_TAG_HANDLER_GROUP_ID = re.compile(
    r"\*\*Group:\*\*\s*`([^`]+)`", re.IGNORECASE
)


def item_keys_by_section_id(doc: dict) -> dict[str, tuple[str, str] | None]:
    """Map each rendered section id to (item_key, display stem) from the doc.

    The rendered markdown carries only a bare display stem, but the markdown
    PATH is never just the markdown: `synthesis-conductor.md` passes
    `--suggestions-doc`, and that document holds `sections[].item_key` keyed by
    the same id the heading shows (`### S01 — …`). So identity is recoverable
    without changing a byte of what the user reads.

    Both the section id and each action's flat `suggestion_id` are registered:
    F-41 gives a multi-atomic source several headings from one section, and the
    heading shows the suggestion_id. Every atomic of one source shares that
    source's key, so the two id spaces cannot disagree about the key.

    An id that maps to two different keys is recorded as None — ambiguous, and
    never guessed.
    """
    lookup: dict[str, tuple[str, str] | None] = {}

    def _register(sid: str | None, value: tuple[str, str]) -> None:
        if not sid:
            return
        if sid in lookup and lookup[sid] != value:
            lookup[sid] = None
            return
        lookup.setdefault(sid, value)

    for section in (doc or {}).get("sections") or []:
        key = section.get("item_key")
        if not key:
            continue
        value = (key, section.get("stem") or "")
        _register(section.get("id"), value)
        for action in section.get("actions") or []:
            _register(action.get("suggestion_id"), value)
    return lookup


def bind_section_item_key(
    item: dict, lookup: dict[str, tuple[str, str] | None]
) -> None:
    """Attach `item_key` to a parsed section, or leave it unset (ADR-1/ADR-2).

    The id match alone is not evidence: the user owns this document and may
    have retyped the Source line. The display stem is therefore cross-checked
    against the one the doc recorded before binding — on a mismatch the key is
    left unset, so the item falls back to the reconstruction. A wrong key names
    a specific wrong note, which is strictly worse than a fallback that may
    simply find nothing.

    Compared on the basename so a path-qualified source link still binds
    (spec 034 T5.1 qualifies links for same-filename groups).
    """
    entry = lookup.get(item.get("id"))
    if not entry:
        return
    key, doc_stem = entry
    parsed = (item.get("source_path") or "").rsplit("/", 1)[-1]
    if parsed.endswith(".md"):
        parsed = parsed[:-3]
    if doc_stem and parsed and parsed != doc_stem:
        return
    item["item_key"] = key


_DAILY_DISCRIMINATOR = {
    "trackers": "field",
    "log_entries": "content",
    "log_links": "target_stem",
}


def enrich_daily_updates_with_item_keys(entries: list[dict], doc: dict) -> None:
    """Restore each daily entry's `source_item_key` from the structured doc.

    A daily-only item — one whose content is fully captured in a daily note —
    gets no per-item section, so the rendered document is the only place it
    appears, and there it carries a bare display stem. Pass 2 nonetheless emits
    a `delete_source` for it (`render_actions._build_delete_source_actions`),
    which is why its identity has to survive the round trip through markdown.

    The structured `daily_notes_updates` block the markdown was rendered from
    still holds `source_item_key`, so the key is recovered by matching on the
    daily-note stem, the bucket, and the entry's own discriminating field
    (tracker name / log content / link target). A discriminator that maps to
    more than one distinct key is ambiguous and is left unset rather than
    guessed — an absent key falls back to the inbox-root reconstruction, a
    wrong one names the wrong note.

    Mutates `entries` in place. A document without the field is untouched.
    """
    if not entries or not isinstance(doc, dict):
        return
    lookup: dict[tuple[str, str, str], str | None] = {}
    for day in doc.get("daily_notes_updates") or []:
        day_stem = day.get("daily_note_stem") or ""
        for bucket, field in _DAILY_DISCRIMINATOR.items():
            for entry in day.get(bucket) or []:
                key = entry.get("source_item_key")
                if not key:
                    continue
                lookup_key = (day_stem, bucket, str(entry.get(field, "")))
                if lookup_key in lookup and lookup[lookup_key] != key:
                    lookup[lookup_key] = None  # ambiguous — never guess
                else:
                    lookup.setdefault(lookup_key, key)

    if not lookup:
        return
    for day in entries:
        day_stem = day.get("date") or ""
        for bucket, field in _DAILY_DISCRIMINATOR.items():
            for entry in day.get(bucket) or []:
                key = lookup.get((day_stem, bucket, str(entry.get(field, ""))))
                if key:
                    entry["source_item_key"] = key


def _restore_daily_item_keys(
    parsed: dict,
    suggestions_doc: str | None,
    markdown_path: str,
    doc_text: str = "",
) -> None:
    """Re-attach daily-entry item keys to a wire-built output (ADR-026 path).

    The wire deliberately does NOT carry `source_item_key`: its schema is
    `additionalProperties: false` and it is the Hashi Suggestions Editor's
    contract, so widening it is a coordinated cross-repo change. The key is
    instead recovered here from the Tomo-owned suggestions doc — the same
    source the markdown path uses — which keeps both parser paths on one
    recovery mechanism and leaves the wire untouched.
    """
    doc_path = suggestions_doc or _default_doc_path(markdown_path, doc_text)
    enrich_daily_updates_with_item_keys(
        parsed.get("daily_updates") or [], _load_json_doc(doc_path)
    )


def _walk_tag_handler_decisions(text: str) -> list[tuple[str, bool, bool]]:
    """Walk the ## Tag-Handler Updates section, one record per group block.

    The reducer renders one block per (handler, target_path) group, each carrying
    a ``**Group:** `<group_id>` `` field line and the decision:
        - [x] Approve
        - [ ] Keep source files (leave the captured inbox notes in place)
        - [ ] Skip
    Group blocks are delimited by the ``**Group:**`` line — a new id starts a new
    block, and the most recent checkbox state seen after that line decides it.

    Returns ``[(group_id, approved, keep_source), ...]`` in document order. Empty
    when the section is absent. Shared by the two public extractors below so the
    section is parsed identically for both decisions.
    """
    lines = text.splitlines()
    in_section = False
    records: list[tuple[str, bool, bool]] = []
    current_id: str | None = None
    current_approved: bool = False
    current_keep_source: bool = False

    def _flush() -> None:
        nonlocal current_id, current_approved, current_keep_source
        if current_id is not None:
            records.append((current_id, current_approved, current_keep_source))
        current_id = None
        current_approved = False
        current_keep_source = False

    for line in lines:
        stripped = line.strip()

        if stripped == "## Tag-Handler Updates":
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            # Next top-level section ends Tag-Handler Updates.
            _flush()
            break
        if not in_section:
            continue

        gm = RE_TAG_HANDLER_GROUP_ID.search(stripped)
        if gm:
            # New group block — flush the previous one first.
            _flush()
            current_id = gm.group(1).strip()
            continue

        if current_id is None:
            continue

        # Decision checkboxes: Approve toggles inclusion; Keep source files suppresses
        # source deletion; Skip leaves the group out.
        cb = RE_CHECKED.match(stripped)
        if cb:
            label = cb.group(1).lower()
            if "keep source" in label:
                current_keep_source = True
                continue
            if "approve" in label:
                current_approved = True
                continue
        cb_un = RE_UNCHECKED.match(stripped)
        if cb_un:
            label = cb_un.group(1).lower()
            if "keep source" in label:
                current_keep_source = False
                continue
            if "approve" in label:
                current_approved = False
                continue

    _flush()
    return records


def parse_tag_handler_groups(text: str) -> list[str]:
    """Return the group ids the user APPROVED in ## Tag-Handler Updates.

    A group whose Approve box is checked is included; a ``[x] Skip`` (or an
    un-ticked Approve) group is NOT. Returns ids in document order, empty when
    the section is absent or no group is approved.
    """
    return [gid for gid, approved, _ in _walk_tag_handler_decisions(text) if approved]


def parse_tag_handler_keep_source(text: str) -> list[str]:
    """Return the group ids whose "Keep source files" box is checked.

    A checked Keep source files box opts the group out of having its consolidated
    inbox sources deleted (instruction-render suppresses the paired
    delete_source). Reported independently of approval — only an approved group
    has a delete to suppress, so a stray keep-source on a skipped group is
    harmless downstream. Returns ids in document order.
    """
    return [gid for gid, _, keep in _walk_tag_handler_decisions(text) if keep]


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Parse a confirmed Tomo suggestions document and output approved "
            "items as JSON."
        )
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        help="Path to the suggestions markdown file (defaults to stdin)",
    )
    parser.add_argument(
        "--fan-resolve-file",
        metavar="PATH",
        help=(
            "Optional companion fan-resolve suggestions doc. When provided, "
            "its approved per-item atomic sections are merged into the "
            "primary doc's FAN log_entries by stem (XDD 012)."
        ),
    )
    parser.add_argument(
        "--fan-resolve-json",
        metavar="PATH",
        help=(
            "Optional vault-published _suggestions-fan.json wire sibling (ADR-026). "
            "When BOTH this and --suggestions-json are edited, the companion merge "
            "is done entirely from the two wires (build_from_wire), never the "
            "markdown — the JSON flow behaves exactly like the markdown companion."
        ),
    )
    parser.add_argument(
        "--suggestions-doc",
        metavar="PATH",
        help=(
            "Optional structured suggestions-doc JSON (reducer output). Supplies "
            "the Pass-1 placement anchor as the apply-time default per checked "
            "MOC (spec 022/023) and the item_key identity join (spec 034). "
            "Defaults to the sibling / tomo-tmp copy of the structured doc the "
            "input markdown was rendered from, chosen by its own tomo.doc_type "
            "(suggestions-fan-doc.json for a fan document, suggestions-doc.json "
            "otherwise); absent → Placement-line parsing only."
        ),
    )
    parser.add_argument(
        "--suggestions-json",
        metavar="PATH",
        help=(
            "Optional vault-published _suggestions.json sibling (ADR-026). When "
            "edited (embedded emit_digest no longer matches), the JSON is "
            "authoritative for MOC selection/anchors and proposed-MOC "
            "rename/decision; otherwise the markdown path is used unchanged."
        ),
    )
    args = parser.parse_args()

    # ── Read input ────────────────────────────────────────────────
    try:
        if args.file:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read()
        else:
            text = sys.stdin.read()
    except OSError as exc:
        print(f"error: cannot read input: {exc}", file=sys.stderr)
        return 1

    if not text.strip():
        print("error: input is empty", file=sys.stderr)
        return 1

    # ── Pre-parse dispatch: MOC proposal-doc (F-43 T4.1) ─────────
    filename = args.file or ""
    if _is_moc_proposal_doc(text, filename=filename):
        # spec 028 T3.4: the override-header marker follows the active profile's
        # parent marker, carried in the suggestions-doc conventions block; absent
        # block → default up::.
        _doc_path = args.suggestions_doc or _default_doc_path(filename, text)
        _parent_marker = _parent_marker_from_doc(_doc_path)
        proposals = parse_moc_proposal_doc(
            text, filename=filename, parent_marker=_parent_marker
        )
        print(json.dumps(proposals, ensure_ascii=False, indent=2))
        return 0

    # ── ADR-026: JSON-only precedence ─────────────────────────────
    # When the vault _suggestions.json sibling was edited (its emit_digest no
    # longer matches a recomputation), it is the SOLE authoritative source:
    # rebuild the entire output from the wire and never read the markdown. No
    # mixing.
    if not args.fan_resolve_file:
        # Primary flow (no companion): edited primary wire → JSON-only.
        _wire = load_changed_wire(args.suggestions_json)
        if _wire is not None:
            _out = build_from_wire(_wire, _load_moc_template())
            _restore_daily_item_keys(_out, args.suggestions_doc, filename, text)
            print(json.dumps(_out, indent=2, ensure_ascii=False))
            print(
                "suggestions-json: edited wire is authoritative (JSON-only path)",
                file=sys.stderr,
            )
            return 0
    else:
        # Companion flow: when BOTH the primary and the fan wire were edited, the
        # merge is done entirely from the two wires — the fan-resolve flow now has
        # JSON-only parity with the primary. Mixed/neither edited → markdown below.
        _p = load_changed_wire(args.suggestions_json)
        _f = load_changed_wire(args.fan_resolve_json)
        if _p is not None and _f is not None:
            _out = build_from_wire_companion(_p, _f, _load_moc_template())
            _restore_daily_item_keys(_out, args.suggestions_doc, filename, text)
            print(json.dumps(_out, indent=2, ensure_ascii=False))
            print(
                "companion: both wires edited — JSON-only merge (build_from_wire_companion)",
                file=sys.stderr,
            )
            return 0
        if _p is not None or _f is not None:
            print(
                "warning: companion has only ONE edited wire — falling back to the "
                "markdown merge (mixed markdown/JSON authority is not supported)",
                file=sys.stderr,
            )

    # ── Split and parse ───────────────────────────────────────────
    raw_sections = split_into_sections(text)

    if not raw_sections:
        print("warning: no S## sections found in document", file=sys.stderr)

    confirmed_items: list[dict] = []
    skipped_items: list[dict] = []
    total_sections = len(raw_sections)

    # Keep parsed sections by item key (`_item_key_of`, module-level) so the
    # Force-Atomic reconciliation pass can promote unapproved items later. A
    # single rendered section can carry N atomic blocks (F-41), so the map is
    # item_key → list of per-block items.
    parsed_sections: list[dict] = []
    sections_by_stem: dict[str, list[dict]] = {}

    # spec 022/023: load the structured Pass-1 anchor map (section id → moc
    # stem → anchor) from the structured doc this markdown was rendered from
    # (spec 034 T6.4a — a fan document resolves its OWN doc). Supplies the
    # apply-time DEFAULT anchor per checked MOC; the rendered **Placement:**
    # line overrides it when hand-edited. Absent doc → empty map (back-compat).
    _own_doc_path = args.suggestions_doc or _default_doc_path(filename, text)
    doc_anchor_map = load_doc_anchor_map(_own_doc_path)
    # spec 034: the rendered document carries a display stem only, so identity
    # is joined back from the structured doc it was rendered from. Empty when
    # no doc is reachable — every item then falls back to the reconstruction,
    # exactly as before this existed.
    doc_item_keys = item_keys_by_section_id(_load_json_doc(_own_doc_path))

    # F-41: split each rendered section into per-atomic-block groups on
    # **Source:** boundaries. Sections with ≤1 Source line yield one group
    # whose id == section_id, keeping single-block output byte-identical.
    for section_id, lines in itertools.chain.from_iterable(
        split_section_into_blocks(sid, lns) for sid, lns in raw_sections
    ):
        try:
            # Per-block ids carry a "#N" suffix (F-41); the anchor map is keyed
            # by the base section id.
            base_id = section_id.split("#", 1)[0]
            item = parse_section(section_id, lines, doc_anchor_map.get(base_id))
        except Exception as exc:  # noqa: BLE001
            print(
                f"warning: skipping {section_id} — parse error: {exc}",
                file=sys.stderr,
            )
            skipped_items.append({"id": section_id, "disposition": "error"})
            continue

        if item is None:
            print(
                f"warning: skipping {section_id} — returned None",
                file=sys.stderr,
            )
            skipped_items.append({"id": section_id, "disposition": "error"})
            continue

        bind_section_item_key(item, doc_item_keys)
        parsed_sections.append(item)
        stem_key = _item_key_of(item.get("source_path"))
        if stem_key:
            sections_by_stem.setdefault(stem_key, []).append(item)

        if item["approved"]:
            confirmed_items.append({
                "id": item["id"],
                # source_path stays the display stem (ADR-2); item_key is the
                # identity Pass 2 addresses the note by (ADR-1).
                "source_path": item["source_path"],
                "item_key": item.get("item_key"),
                "audio_peer": item.get("audio_peer"),
                "attachments": item.get("attachments") or [],
                "type": item["type"],
                "approved": item["approved"],
                "delete_source": item["delete_source"],
                "keep_source": item["keep_source"],
                "action": item["action"],
                "title": item["title"],
                "tags": item["tags"],
                "parent_moc": item["parent_moc"],
                "parent_mocs": item["parent_mocs"],
                "candidate_mocs": item.get("candidate_mocs", []),
                "destination": item["destination"],
                "template": item["template"],
                "summary": item["summary"],
                "classification": item["classification"],
            })
        else:
            disposition = "delete_source" if item["delete_source"] else "skip"
            skipped_items.append({
                "id": section_id,
                "source_path": item["source_path"],
                "item_key": item.get("item_key"),
                "disposition": disposition,
            })

    # ── Parse Proposed MOCs ────────────────────────────────────
    moc_template = _load_moc_template()

    # Read the companion fan-resolve doc up-front (if any) so its proposed
    # MOCs merge by-name with the primary's: a fanned force-atomic item can
    # have no thematic match and propose a new MOC that joins the same-named
    # primary proposal (#67). resolve_text is reused by the atomic-section
    # reconciliation pass below.
    resolve_text = ""
    if args.fan_resolve_file:
        try:
            with open(args.fan_resolve_file, encoding="utf-8") as fh:
                resolve_text = fh.read()
        except OSError as exc:
            print(
                f"warning: cannot read --fan-resolve-file "
                f"{args.fan_resolve_file}: {exc}",
                file=sys.stderr,
            )
            resolve_text = ""

    # spec 034 T6.4a: the resolve document is a document in its own right —
    # rendered from its own structured doc, with its own section-id namespace.
    # Its identity keys, placement anchors and proposed-MOC members are joined
    # back from THAT doc, resolved by its own tomo.doc_type exactly as the
    # input markdown's are. Unreadable resolve markdown → no doc, and every
    # consumer below is already gated on `resolve_text`.
    _resolve_doc = (
        _load_json_doc(_default_doc_path(args.fan_resolve_file, resolve_text))
        if args.fan_resolve_file and resolve_text.strip() else {}
    )
    resolve_item_keys = item_keys_by_section_id(_resolve_doc)
    resolve_anchor_map = anchor_map_from_doc(_resolve_doc)

    # Recover proposed-MOC members from the structured docs (the render drops
    # the SNN members; we resolve topic → source-stems and bind them to the
    # create_moc below so the new MOC gets its child down-links).
    primary_members = _topic_member_stems(_load_json_doc(_own_doc_path))
    fan_members = _topic_member_stems(_resolve_doc)
    # Enrich member_stems INSIDE parse (before its internal same-name merge) so
    # a name merged from multiple topics keeps every topic's members.
    primary_pmocs = parse_proposed_mocs(
        text, config_template=moc_template, topic_members=primary_members
    )
    fan_pmocs = (
        parse_proposed_mocs(
            resolve_text, config_template=moc_template, topic_members=fan_members
        )
        if resolve_text.strip() else []
    )
    proposed_mocs = _merge_proposed_mocs_by_name(primary_pmocs + fan_pmocs)
    if proposed_mocs:
        confirmed_items.extend(proposed_mocs)
        print(
            f"proposed_mocs: {len(proposed_mocs)} approved"
            + (f" ({len(fan_pmocs)} from fan-resolve)" if fan_pmocs else ""),
            file=sys.stderr,
        )

    # ── Parse Tag-Handler Updates (spec 024 T4.1) ─────────────
    approved_tag_handler_group_ids = parse_tag_handler_groups(text)
    tag_handler_keep_source_group_ids = parse_tag_handler_keep_source(text)
    if approved_tag_handler_group_ids:
        print(
            f"tag_handler_groups: {len(approved_tag_handler_group_ids)} approved, "
            f"{len(tag_handler_keep_source_group_ids)} keep-source",
            file=sys.stderr,
        )

    # ── Parse Daily Notes Updates ─────────────────────────────
    daily_updates = parse_daily_updates(text)
    # The rendered daily block carries only a display stem, so the identity of
    # each entry's source note is recovered from the structured doc it was
    # rendered from — Pass 2 emits a delete_source for daily-only items.
    enrich_daily_updates_with_item_keys(
        daily_updates, _load_json_doc(_own_doc_path)
    )
    if daily_updates:
        accepted_count = sum(
            1 for d in daily_updates
            for lst in (d.get("trackers", []), d.get("log_entries", []), d.get("log_links", []))
            for item in lst if item.get("accepted")
        )
        print(
            f"daily_updates: {len(daily_updates)} dates, {accepted_count} accepted items",
            file=sys.stderr,
        )

    # ── Parse companion FAN-resolve doc (XDD 012) ───────────────
    # When the user approved a <date>_suggestions-fan.md in addition to
    # the primary doc, its approved atomic sections carry the proposals
    # generated by the force_atomic=true Pass-2 subflow. Parse them into
    # a {stem → section} map so the reconciliation pass below can pick
    # them up for FAN log_entries that had no primary-doc section.
    # F-41 (T4.2): resolve-doc is list-valued — a single SNN heading can carry
    # N atomic blocks (same multi-block render layout as the primary doc).
    resolve_sections_by_stem: dict[str, list[dict]] = {}
    if args.fan_resolve_file and resolve_text.strip():
        for section_id, lines in itertools.chain.from_iterable(
            split_section_into_blocks(sid, lns)
            for sid, lns in split_into_sections(resolve_text)
        ):
            try:
                # Per-block ids carry a "#N" suffix (F-41); both maps are keyed
                # by the base section id.
                base_id = section_id.split("#", 1)[0]
                item = parse_section(
                    section_id, lines, resolve_anchor_map.get(base_id)
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"warning: resolve-doc {section_id} parse error: {exc}",
                    file=sys.stderr,
                )
                continue
            if item is None:
                continue
            # spec 034 T6.4a: `_promote_entry` reads `item_key` off this
            # section, so a resolve atomic that never binds one addresses its
            # note by display stem and a subfolder note cannot be filed.
            bind_section_item_key(item, resolve_item_keys)
            # Only approved atomic sections count. Unchecked = user
            # hasn't accepted the proposal yet.
            if not item.get("approved"):
                continue
            stem_key = _item_key_of(item.get("source_path"))
            if stem_key:
                resolve_sections_by_stem.setdefault(stem_key, []).append(item)

    # ── Reconcile Force Atomic Note promotions ─────────────────
    # When the user ticks [x] Force Atomic Note on a log_entry, they're
    # saying "also create a standalone note for this source," even if
    # the per-item section's own Approve box is empty. Three-way lookup:
    #   (a) primary-doc per-item section (legacy promote path, commit 2665f81)
    #   (b) resolve-doc atomic section (XDD 012 new path)
    #   (c) neither → pending_fan_resolutions[] (Pass 2 will trigger the
    #       resolve subflow to generate (b) for next run)
    force_atomic_stems: list[tuple[str, dict]] = []  # preserve order + log_entry ref
    for d in daily_updates:
        for le in d.get("log_entries", []):
            if le.get("force_atomic_note"):
                stem = _item_key_of(le.get("source_stem"))
                if stem:
                    force_atomic_stems.append((stem, le))

    promoted = 0
    from_resolve = 0
    pending_fan_resolutions: list[dict] = []
    already_in = {_item_key_of(c.get("source_path")) for c in confirmed_items}
    # Track per-block confirmations by id so a stem with N atomic blocks can
    # have some user-approved and the rest FAN-promoted without duplication.
    confirmed_ids = {c.get("id") for c in confirmed_items}
    seen_pending: set[str] = set()
    # The resolve doc has its OWN S01.. id namespace that collides with the
    # primary doc's, so resolve atomics are de-duped against ids promoted FROM
    # the resolve doc (not the primary confirmed_ids) and re-numbered to a
    # collision-free SNN — otherwise a colliding id both drops the atomic here
    # AND corrupts instruction-render's id_index (same id, two items).
    resolve_promoted_ids: set[str] = set()
    _used_nums = {
        int(m.group(1)) for m in (re.match(r"S0*(\d+)", c or "") for c in confirmed_ids) if m
    }
    _id_counter = [max(_used_nums, default=0)]

    def _alloc_resolve_id() -> str:
        _id_counter[0] += 1
        return f"S{_id_counter[0]:02d}"

    def _promote_entry(sec: dict, from_resolve: bool) -> dict:
        sec["approved"] = True
        sec["delete_source"] = False
        entry = {
            "id": sec["id"],
            "source_path": sec["source_path"],
            "item_key": sec.get("item_key"),
            # Both fields belong to the canonical confirmed-item shape built
            # above; omitting them here filed the note and left its audio peer
            # and attachments behind in the inbox (#161).
            "audio_peer": sec.get("audio_peer"),
            "attachments": sec.get("attachments") or [],
            "type": sec["type"],
            "approved": True,
            "delete_source": False,
            "keep_source": bool(sec.get("keep_source", False)),
            "action": sec.get("action"),
            "title": sec["title"],
            "tags": sec["tags"],
            "parent_moc": sec["parent_moc"],
            "parent_mocs": sec["parent_mocs"],
            "candidate_mocs": sec.get("candidate_mocs", []),
            "destination": sec["destination"],
            "template": sec["template"],
            "summary": sec["summary"],
            "classification": sec["classification"],
            "force_atomic": True,  # trace marker for instruction-render logs
        }
        if from_resolve:
            entry["from_resolve"] = True
        return entry

    for stem, log_entry in force_atomic_stems:
        # Branch (a): primary-doc per-item section(s). A stem may carry N
        # atomic blocks (F-41) — promote every block not already confirmed.
        primary_secs = [
            s for s in sections_by_stem.get(stem, [])
            if s.get("id") not in confirmed_ids
        ]
        if primary_secs:
            for sec in primary_secs:
                entry = _promote_entry(sec, from_resolve=False)
                confirmed_items.append(entry)
                confirmed_ids.add(entry["id"])
                promoted += 1
            already_in.add(stem)
            skipped_items[:] = [
                s for s in skipped_items
                if _item_key_of(s.get("source_path")) != stem
            ]
            continue

        if stem in already_in:
            continue  # user already checked per-item Approve — Force is a no-op

        # Branch (b): resolve-doc atomic section(s). A stem may carry N
        # blocks (F-41 T4.2) — promote every block not already confirmed.
        resolve_secs = [
            s for s in resolve_sections_by_stem.get(stem, [])
            if s.get("id") not in resolve_promoted_ids
        ]
        if resolve_secs:
            for sec in resolve_secs:
                resolve_promoted_ids.add(sec.get("id"))
                entry = _promote_entry(sec, from_resolve=True)
                entry["id"] = _alloc_resolve_id()
                from_resolve += 1
                confirmed_items.append(entry)
                confirmed_ids.add(entry["id"])
            already_in.add(stem)
            # Drop the matching skipped entry (if any) so counts stay clean.
            skipped_items[:] = [
                s for s in skipped_items
                if _item_key_of(s.get("source_path")) != stem
            ]
        else:
            # Branch (c): no matching section anywhere. Record the item so
            # Pass 2 can trigger the resolve subflow next.
            if stem in seen_pending:
                continue
            seen_pending.add(stem)
            # Pull a short summary from the log entry content (first 140
            # chars) for the resolve-doc writer to display.
            summary = (log_entry.get("content") or "").strip()
            if len(summary) > 140:
                summary = summary[:137] + "…"
            pending_fan_resolutions.append({
                "stem": stem,
                # Reconstruct a best-effort source_path; log_entry may only
                # carry source_stem. Pass 2 will verify via kado-search.
                "source_path": log_entry.get("source_path") or f"{stem}.md",
                "log_entry_summary": summary,
            })

    # ── Section-level Force Atomic (suppressed low-worthiness blocks, #88) ──
    # A suppressed light block has no Approve box (→ it landed in skipped_items)
    # and carries no template/location/MOC. Ticking its "Force Atomic Note" box
    # routes the stem to the resolve subflow — Pass 2 rebuilds the full atomic
    # from source. Runs AFTER the daily-driven loop so already_in /
    # seen_pending de-dup against it.
    #
    # Carries the same (b)/(c) split as the daily-driven loop above: consume an
    # approved resolve-doc proposal when one exists, park only when none does.
    # Without (b) this loop parked unconditionally, so the proposal the user
    # had just approved was re-parked on every run and the subflow could never
    # complete — a livelock reported as "you left its Approve box unticked"
    # while the box was ticked (#165).
    for sec in parsed_sections:
        if not sec.get("force_atomic"):
            continue
        stem = _item_key_of(sec.get("source_path"))
        if not stem or stem in already_in or stem in seen_pending:
            continue

        # (b) resolve-doc atomic section(s) — a stem may carry N blocks (F-41).
        resolve_secs = [
            s for s in resolve_sections_by_stem.get(stem, [])
            if s.get("id") not in resolve_promoted_ids
        ]
        if resolve_secs:
            for rsec in resolve_secs:
                resolve_promoted_ids.add(rsec.get("id"))
                entry = _promote_entry(rsec, from_resolve=True)
                entry["id"] = _alloc_resolve_id()
                from_resolve += 1
                confirmed_items.append(entry)
                confirmed_ids.add(entry["id"])
            already_in.add(stem)
            skipped_items[:] = [
                s for s in skipped_items
                if _item_key_of(s.get("source_path")) != stem
            ]
            continue

        # (c) no proposal yet — park so Pass 2 generates one.
        seen_pending.add(stem)
        summary = (sec.get("summary") or sec.get("title") or "").strip()
        if len(summary) > 140:
            summary = summary[:137] + "…"
        pending_fan_resolutions.append({
            "stem": stem,
            "source_path": sec.get("source_path") or f"{stem}.md",
            "log_entry_summary": summary,
        })
        # Remove from skipped (it's being force-atomic'd, not skipped).
        skipped_items[:] = [
            s for s in skipped_items if _item_key_of(s.get("source_path")) != stem
        ]

    if promoted:
        print(
            f"force_atomic: promoted {promoted} per-item section(s) to confirmed",
            file=sys.stderr,
        )
    if from_resolve:
        print(
            f"force_atomic: merged {from_resolve} atomic(s) from resolve doc",
            file=sys.stderr,
        )
    if pending_fan_resolutions:
        print(
            f"force_atomic: {len(pending_fan_resolutions)} log entries have "
            "Force Atomic Note but no atomic proposal — resolve subflow will "
            "be triggered by Pass 2.",
            file=sys.stderr,
        )

    # Bind proposed-MOC members → supporting_items (down-links). Runs AFTER fan
    # reconciliation so a fan-promoted member (re-numbered id) is resolvable.
    # member_stems were recovered from the structured docs; map them to the
    # FINAL confirmed-item ids so _build_link_to_moc_actions emits the child
    # links into the new MOC. Strip the internal helper fields afterwards.
    _stem_to_id = {
        _item_key_of(c.get("source_path")): c.get("id")
        for c in confirmed_items
        if c.get("source_path") and c.get("id")
    }
    for c in confirmed_items:
        if c.get("action") == "create_moc":
            ids = [
                _stem_to_id[_item_key_of(s)]
                for s in (c.get("member_stems") or [])
                if _item_key_of(s) in _stem_to_id
            ]
            if ids:
                c["supporting_items"] = ", ".join(ids)
        c.pop("member_stems", None)
        c.pop("topic", None)
    # Lifted at the same site the other internal fields are stripped: the
    # carrier must not reach a confirmed item, and the record must reach the
    # output dict below.
    merged_moc_proposals = _lift_merged_moc_records(confirmed_items)

    output = {
        "confirmed_items": confirmed_items,
        # spec 034 T6.0c — see the wire path's note. Same record, same shape;
        # this path merges twice, so the carrier is reentrant across both.
        "merged_moc_proposals": merged_moc_proposals,
        "daily_updates": daily_updates,
        "skipped": skipped_items,
        # XDD 012: items with FAN-without-section that Pass 2 must
        # resolve via a follow-up subflow. Empty list when nothing pending.
        "pending_fan_resolutions": pending_fan_resolutions,
        # spec 024 T4.1: group ids the user approved in ## Tag-Handler Updates.
        # instruction-render maps each to its group-result JSON and emits one
        # insert_under_marker. Empty list when no group approved.
        "approved_tag_handler_group_ids": approved_tag_handler_group_ids,
        # Group ids the user opted out of source-deletion via "Keep source files".
        # instruction-render suppresses the paired delete_source for these.
        "tag_handler_keep_source_group_ids": tag_handler_keep_source_group_ids,
        "total_sections": total_sections,
        "total_approved": len(confirmed_items),
        "total_skipped": len(skipped_items),
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
