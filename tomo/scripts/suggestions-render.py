#!/usr/bin/env python3
# version: 0.16.0
"""Render tomo-tmp/suggestions-doc.json to final suggestions markdown.

Deterministic markdown renderer — no LLM involved. The orchestrator runs
this after the reducer and writes the output to the vault via kado-write.

Input:  suggestions-doc.json (from suggestions-reducer.py)
Output: Final suggestions markdown file (written to --output path)

Section order (strict):
  1. Frontmatter + Approved checkbox + Decision-precedence note + Summary
  2. Daily Notes Updates (when non-empty)
  3. Suggestions (per-item sections)
  4. Proposed MOCs (when non-empty)
  5. Needs Attention (when non-empty)
"""
import json
import re
import sys
import argparse

import yaml

from lib.doc_frontmatter import build_tomo_block
from lib.profile_conventions import ensure_suffix
from lib.render_md import compute_payload_digest


def render_frontmatter(d: dict) -> list[str]:
    # F-47 T2.5: fan-resolve docs carry doc_type='suggestions-fan' so
    # byFrontmatter queries for doc_type=suggestions don't match them.
    doc_type = (
        "suggestions-fan"
        if d.get("doc_variant") == "fan-resolve"
        else "suggestions"
    )
    tomo_block = build_tomo_block(
        doc_type=doc_type,
        state="pending-approval",
        run_id=d["run_id"],
    )
    fm: dict = {
        "type": "tomo-suggestions",
        "generated": d["generated"],
        "tomo_version": "0.1.0",
        "profile": d["profile"],
        "source_items": d["source_items"],
        "run_id": d["run_id"],
        "tomo": tomo_block,
    }
    body = yaml.dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    lines = ["---"] + body.rstrip("\n").splitlines() + ["---"]
    return lines


def render_header(d: dict) -> list[str]:
    date = d["generated"][:10]
    variant = d.get("doc_variant", "primary")
    if variant == "fan-resolve":
        h1 = f"# Inbox Suggestions — Force-Atomic Resolve — {date}"
    else:
        h1 = f"# Inbox Suggestions — {date}"
    lines = [
        "",
        h1,
        "",
        "- [ ] Approved — check this box when you have finished reviewing, then run `/inbox` for Pass 2",
        "",
    ]

    precedence = d.get("decision_precedence_note", "").strip()
    if precedence:
        lines.append(f"> {precedence}")
        lines.append("")

    return lines


def render_summary(d: dict) -> list[str]:
    daily_count = len(d.get("daily_notes_updates") or [])
    th_count = len(d.get("tag_handler_updates") or [])
    lines = [
        "## Summary",
        "",
        f"- Items processed: {d['source_items']}",
        f"- Sections: {len(d['sections'])}",
    ]
    if daily_count:
        lines.append(f"- Daily note updates: {daily_count}")
    if th_count:
        lines.append(f"- Tag-handler updates: {th_count}")
    lines.append(f"- Proposed MOCs: {len(d['proposed_mocs'])}")
    lines.append(f"- Needs attention: {len(d['needs_attention'])}")
    lines.append("")
    return lines


def render_daily_updates(d: dict) -> list[str]:
    md = (d.get("rendered_daily_updates_md") or "").strip()
    if not md:
        return []
    return [md, ""]


def render_tag_handler_updates(d: dict) -> list[str]:
    """Render the ## Tag-Handler Updates block from the pre-rendered reducer output.

    Mirrors render_daily_updates: reads rendered_tag_handler_updates_md verbatim,
    returns [] when absent or empty so the section is omitted cleanly.
    """
    md = (d.get("rendered_tag_handler_updates_md") or "").strip()
    if not md:
        return []
    return [md, ""]


def _extract_atomic_title(rendered_md: str, fallback: str) -> str:
    """Extract 'Suggested name' from rendered_md, strip ← hints, fall back to stem."""
    m = re.search(r"\*\*Suggested name:\*\*\s*([^\n]+)", rendered_md)
    title = m.group(1).strip() if m else fallback
    if "←" in title:
        title = title[:title.index("←")].strip()
    return title


def render_suggestions(d: dict) -> list[str]:
    if not d["sections"]:
        return []
    lines = ["## Suggestions", ""]
    for s in d["sections"]:
        for a in s["actions"]:
            if a.get("kind") == "create_atomic_note":
                sid = a.get("suggestion_id") or s["id"]
                title = _extract_atomic_title(a["rendered_md"], s["stem"])
                lines.append(f"### {sid} — {title}")
            lines.append(a["rendered_md"])
            lines.append("")
    return lines


def render_proposed_mocs(d: dict) -> list[str]:
    mocs = d.get("proposed_mocs") or []
    if not mocs:
        return []
    moc_suffix = (d.get("conventions") or {}).get("moc_suffix", "")
    lines = ["## Proposed MOCs", ""]
    for pm in mocs:
        topic = pm.get("topic", "")
        name = pm.get("name") or ensure_suffix(topic, moc_suffix)
        note_titles = pm.get("note_titles")
        if note_titles:
            supporting = ", ".join(note_titles)
        else:
            supporting = ", ".join(pm.get("items", []))
        parent = pm.get("parent", "")
        tags = ", ".join(pm.get("tags", []))
        tag_line = f"- **Suggested tags:** {tags}" if tags else ""
        reason = pm.get("reason", "")

        entry = [
            f"### Proposed MOC: {topic}",
            f"- **Name:** {name}    \u2190 edit this to rename the MOC before approving",
            f"- **Parent:** [[{parent}]]    \u2190 change parent MOC if needed",
            f"- **Supporting notes:** {supporting}",
        ]
        if reason:
            entry.append(f"- **Why:** {reason}")
        if tag_line:
            entry.append(tag_line)
        entry.extend([
            "- **Decision:**",
            "  - [ ] Approve (create this MOC with the Name above)",
            "",
        ])
        lines.extend(entry)
    return lines


def render_needs_attention(d: dict) -> list[str]:
    items = d.get("needs_attention") or []
    if not items:
        return []
    lines = ["## Needs Attention", ""]
    for n in items:
        lines.extend([
            f"### {n.get('stem', '')}",
            f"**Error:** {n.get('error', '')}",
            "",
        ])
    return lines


# ── Suggestions wire (ADR-026) ───────────────────────────────────────────
# A structured, vault-published sibling of _suggestions.md that the Hashi
# Suggestions Editor reads/edits. Projected from the same suggestions-doc.json
# the markdown is rendered from; render-intermediate fields (rendered_md, …) are
# dropped. Conforms to schemas/suggestions-wire.schema.json.


def _wire_selected(moc: dict) -> bool:
    """Pre-checked state for a candidate MOC — mirrors reducer.moc_link_line."""
    if "pre_check" in moc:
        return bool(moc.get("pre_check"))
    return (moc.get("score") or 0) >= 0.5


def _wire_anchor(anchor: dict | None) -> dict | None:
    """Project a suggestions-doc anchor to the wire anchor shape (same keys).

    Guard (ADR-026): `inside` is executable only on callout anchors — the
    executor hard-fails `inside` on heading/line. Coerce it to `after` here so
    the wire can never carry an unexecutable placement.
    """
    if not anchor:
        return None
    placement = anchor.get("placement")
    if placement == "inside" and anchor.get("type") != "callout":
        placement = "after"
    return {
        "type": anchor.get("type"),
        "value": anchor.get("value"),
        "placement": placement,
        "new_section": anchor.get("new_section"),
        "alt_headings": [h for h in (anchor.get("alt_headings") or []) if h],
        "fit_confidence": anchor.get("fit_confidence"),
    }


_PARSER_MOD = None
_THG_MOD = None


def _group_id_fn():
    """Lazily load the tag-handler-group module's stable group_id() (ADR-026
    Hashi flag 3) so the wire can join descriptive fields to each group by id."""
    global _THG_MOD
    if _THG_MOD is None:
        import importlib.util
        import pathlib

        path = pathlib.Path(__file__).resolve().parent / "tag-handler-group.py"
        spec = importlib.util.spec_from_file_location("_thg_for_wire", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _THG_MOD = mod
    return _THG_MOD.group_id


def _parser_mod():
    """Lazily load suggestion-parser.py to reuse its section parsers.

    The daily-note and tag-handler sections are mirrored into the wire by parsing
    our OWN freshly-rendered markdown with the parser's own functions — so the
    wire carries the exact parse-output shape and build_from_wire reproduces it
    (parity by construction). Reusing the parser avoids a second, divergent
    implementation of those intricate sub-parsers.
    """
    global _PARSER_MOD
    if _PARSER_MOD is None:
        import importlib.util
        import pathlib

        path = pathlib.Path(__file__).resolve().parent / "suggestion-parser.py"
        spec = importlib.util.spec_from_file_location("_suggestion_parser_for_wire", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _PARSER_MOD = mod
    return _PARSER_MOD


def _wire_note(section: dict, action: dict) -> dict:
    """Project one create_atomic_note action to a full-mirror wire suggestion."""
    item = action.get("item") or {}
    sid = action.get("suggestion_id") or section["id"]
    worthiness = item.get("worthiness")
    # Mirror the Approve pre-check: checked (⇒ approve) when worthiness >= 0.5.
    decision = "approve" if (worthiness is not None and worthiness >= 0.5) else "skip"
    candidate_mocs = [
        {
            "path": moc["path"],
            "selected": _wire_selected(moc),
            "anchor": _wire_anchor(moc.get("anchor")),
            "source": "tomo",
        }
        for moc in (action.get("candidate_mocs") or [])
        if moc.get("path")
    ]
    return {
        "id": sid,
        "stem": section["stem"],
        "title": item.get("title") or section["stem"],
        "summary": item.get("summary"),
        "template": item.get("template", ""),
        "location": item.get("location", ""),
        "tags": list(item.get("tags") or []),
        "audio_peer": item.get("audio_peer"),
        "attachments": list(item.get("attachments") or []),
        "decision": decision,
        "keep_source": False,
        "delete_source": False,
        "force_atomic": bool(item.get("force_atomic")),
        "suppressed": bool(item.get("suppressed")),
        "worthiness": worthiness,
        "candidate_mocs": candidate_mocs,
    }


def build_wire_payload(d: dict) -> dict:
    """Project suggestions-doc.json to the full-mirror suggestions-wire + emit_digest.

    ADR-026: the wire is a complete, structured serialization of the review
    surface. When Hashi edits it, Pass-2 rebuilds its entire output from the wire
    alone (build_from_wire) — never re-reading the markdown — so every editable
    decision the markdown offers is carried here.
    """
    moc_suffix = (d.get("conventions") or {}).get("moc_suffix", "")

    suggestions = [
        _wire_note(s, a)
        for s in d.get("sections", [])
        for a in s.get("actions", [])
        if a.get("kind") == "create_atomic_note"
    ]

    # proposed_mocs.items are keyed in the reducer's per-SOURCE section_id space
    # (atomic_key = section_id, or section_id#idx for F-41 multi-atomic sources),
    # but each wire suggestion is keyed by its flat per-ATOMIC suggestion_id. The
    # two spaces diverge whenever a daily-only source sits between atomics (its
    # source index is consumed but it emits no atomic), so copying items verbatim
    # made member_ids point at the wrong suggestion. Map atomic_key → the flat id
    # (mirroring the reducer's `_atomic_id` keying) and remap below so member_ids
    # reference the wire's own suggestions.
    atomic_key_to_sid: dict[str, str] = {}
    for s in d.get("sections", []):
        atom_idx = 0
        for a in s.get("actions", []):
            if a.get("kind") != "create_atomic_note":
                continue
            key = s["id"] if atom_idx == 0 else f"{s['id']}#{atom_idx}"
            atomic_key_to_sid[key] = a.get("suggestion_id") or s["id"]
            atom_idx += 1

    proposed_mocs: list[dict] = []
    for i, pm in enumerate(d.get("proposed_mocs") or [], start=1):
        topic = pm.get("topic", "")
        proposed_mocs.append(
            {
                "id": f"M{i:02d}",
                "topic": topic,
                "name": pm.get("name") or ensure_suffix(topic, moc_suffix),
                "parent": pm.get("parent", ""),
                "member_ids": [
                    atomic_key_to_sid.get(it, it) for it in (pm.get("items") or [])
                ],
                "tags": list(pm.get("tags") or []),
                "reason": pm.get("reason", ""),
                # Mirror the markdown default (Approve un-ticked ⇒ not created;
                # un-approving IS skipping). Hashi flips this to "approve" to create.
                "decision": "skip",
            }
        )

    # Daily + tag-handler: mirror the exact parse-output by parsing our own
    # rendered markdown, so build_from_wire reproduces them verbatim (parity).
    pm = _parser_mod()
    daily_updates = pm.parse_daily_updates(d.get("rendered_daily_updates_md") or "")
    # Tag-handler: decisions (approved/keep_source) come from parsing our own
    # rendered markdown; descriptive context (Hashi flag 3) is joined from the
    # doc's tag_handler_updates by the stable group_id so the editor card can
    # show what's being approved, not a bare id.
    gid_fn = _group_id_fn()
    doc_groups = {gid_fn(g): g for g in (d.get("tag_handler_updates") or [])}
    tag_handler_groups = []
    for gid, approved, keep_source in pm._walk_tag_handler_decisions(
        d.get("rendered_tag_handler_updates_md") or ""
    ):
        g = doc_groups.get(gid, {})
        tag_handler_groups.append({
            "group_id": gid,
            "approved": approved,
            "keep_source": keep_source,
            "handler": g.get("handler", ""),
            "target_path": g.get("target_path"),
            "marker": g.get("marker", ""),
            "source_paths": list(g.get("source_paths") or []),
            "preview": g.get("composed_block", ""),
        })

    payload = {
        "schema_version": "1",
        "generated": d["generated"],
        "run_id": d["run_id"],
        "profile": d["profile"],
        "source_items": d["source_items"],
        "suggestions": suggestions,
        "proposed_mocs": proposed_mocs,
        "daily_updates": daily_updates,
        "tag_handler_groups": tag_handler_groups,
    }
    payload["emit_digest"] = compute_payload_digest(payload)
    return payload


def main() -> int:
    p = argparse.ArgumentParser(
        description="Render suggestions-doc.json to final markdown."
    )
    p.add_argument("--input", required=True, help="Path to suggestions-doc.json")
    p.add_argument("--output", required=True, help="Output markdown file path")
    p.add_argument(
        "--json-output",
        help="Optional path for the structured suggestions-wire JSON (ADR-026).",
    )
    args = p.parse_args()

    with open(args.input, encoding="utf-8") as f:
        d = json.load(f)

    parts: list[str] = []
    parts.extend(render_frontmatter(d))
    parts.extend(render_header(d))
    parts.extend(render_summary(d))
    parts.extend(render_daily_updates(d))
    parts.extend(render_tag_handler_updates(d))
    parts.extend(render_suggestions(d))
    parts.extend(render_proposed_mocs(d))
    parts.extend(render_needs_attention(d))

    content = "\n".join(parts)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(content)

    if args.json_output:
        wire = build_wire_payload(d)
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(wire, f, ensure_ascii=False, indent=2)

    section_count = len(d.get("sections", []))
    daily_count = len(d.get("daily_notes_updates") or [])
    th_count = len(d.get("tag_handler_updates") or [])
    moc_count = len(d.get("proposed_mocs") or [])
    print(
        f"suggestions-render: sections={section_count} daily={daily_count} "
        f"tag_handler={th_count} mocs={moc_count} out={args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
