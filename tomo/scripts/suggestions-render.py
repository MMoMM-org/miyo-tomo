#!/usr/bin/env python3
# version: 0.9.0
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
    lines = ["## Proposed MOCs", ""]
    for pm in mocs:
        topic = pm.get("topic", "")
        name = pm.get("name") or f"{topic} (MOC)"
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
            "  - [ ] Skip \u2014 don't create, items stay with their individual MOC matches",
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


def main() -> int:
    p = argparse.ArgumentParser(
        description="Render suggestions-doc.json to final markdown."
    )
    p.add_argument("--input", required=True, help="Path to suggestions-doc.json")
    p.add_argument("--output", required=True, help="Output markdown file path")
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
