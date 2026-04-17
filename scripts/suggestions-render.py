#!/usr/bin/env python3
# version: 0.2.0
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


def render_frontmatter(d: dict) -> list[str]:
    lines = [
        "---",
        "type: tomo-suggestions",
        f"generated: {d['generated']}",
        'tomo_version: "0.1.0"',
        f"profile: {d['profile']}",
        f"source_items: {d['source_items']}",
        f"run_id: {d['run_id']}",
        "---",
    ]
    return lines


def render_header(d: dict) -> list[str]:
    date = d["generated"][:10]
    lines = [
        "",
        f"# Inbox Suggestions — {date}",
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
    lines = [
        "## Summary",
        "",
        f"- Items processed: {d['source_items']}",
        f"- Sections: {len(d['sections'])}",
    ]
    if daily_count:
        lines.append(f"- Daily note updates: {daily_count}")
    lines.append(f"- Proposed MOCs: {len(d['proposed_mocs'])}")
    lines.append(f"- Needs attention: {len(d['needs_attention'])}")
    lines.append("")
    return lines


def render_daily_updates(d: dict) -> list[str]:
    md = (d.get("rendered_daily_updates_md") or "").strip()
    if not md:
        return []
    return [md, ""]


def render_suggestions(d: dict) -> list[str]:
    if not d["sections"]:
        return []
    lines = ["## Suggestions", ""]
    for s in d["sections"]:
        # Extract title from first action's "Suggested name" field, or fall back to stem
        first_md = s["actions"][0]["rendered_md"] if s["actions"] else ""
        m = re.search(r"\*\*Suggested name:\*\*\s*([^\n]+)", first_md)
        title = m.group(1).strip() if m else s["stem"]
        # Strip trailing comment hints like "← change if you want..."
        if "←" in title:
            title = title[:title.index("←")].strip()

        lines.append(f"### {s['id']} — {title}")
        for a in s["actions"]:
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
        items = ", ".join(pm.get("items", []))
        parent = pm.get("parent", "")
        lines.extend([
            f"### Proposed MOC: {topic}",
            f"- **Name:** {topic} (MOC)    \u2190 edit this to rename the MOC before approving",
            f"- **Parent:** [[{parent}]]    \u2190 change parent MOC if needed",
            f"- **Supporting items:** {items}",
            "- **Decision:**",
            "  - [ ] Approve (create this MOC with the Name above)",
            "  - [ ] Skip \u2014 don't create, items stay with their individual MOC matches",
            "",
        ])
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
    parts.extend(render_suggestions(d))
    parts.extend(render_proposed_mocs(d))
    parts.extend(render_needs_attention(d))

    content = "\n".join(parts)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(content)

    section_count = len(d.get("sections", []))
    daily_count = len(d.get("daily_notes_updates") or [])
    moc_count = len(d.get("proposed_mocs") or [])
    print(
        f"suggestions-render: sections={section_count} daily={daily_count} "
        f"mocs={moc_count} out={args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
