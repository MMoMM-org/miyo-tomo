#!/usr/bin/env python3
# suggestions-reducer.py — Phase C: aggregate per-item results into a
# suggestions-doc JSON which the orchestrator renders to markdown.
# version: 0.2.0
"""
Inputs (CLI):
  --state      tomo-tmp/inbox-state.jsonl
  --items-dir  tomo-tmp/items/
  --run-id     Run identifier
  --profile    Active profile name (e.g. "miyo")
  --output     tomo-tmp/suggestions-doc.json
  --threshold  Minimum cluster size for Proposed MOC (default 3)

Outputs:
  JSON file matching schemas/suggestions-doc.schema.json. Each section carries
  a list of `actions`, each with a pre-rendered markdown block the orchestrator
  concatenates under the section's SNN heading.

Rendering rules (replicated from the retired suggestion-builder format):
  - `### SNN — <suggested title>` heading (in orchestrator render step)
  - `**Source:** [[<stem>]]`
  - `**New tags to add:** <csv>` (omitted when empty)
  - `**Link to MOC:**` with pre-checked boxes
  - `**Why:**` 1-2 sentences (from classification signals)
  - `**Decision:**` tri-state Approve | Skip | Delete source (per action)
  - Multi-action items emit each action's block under the same section
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def last_state_per_stem(state_path: Path) -> dict[str, dict]:
    """Return {stem: last_entry} by replaying the append-only JSONL."""
    out: dict[str, dict] = {}
    if not state_path.exists():
        return out
    with state_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            stem = obj.get("stem")
            if stem:
                out[stem] = obj
    return out


def normalise_topic(topic: str) -> str:
    """Lowercase, strip punctuation, naive plural fold."""
    if not topic:
        return ""
    t = topic.strip().lower()
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Naive pluralisation fold (English):
    #  - "ies" → "y" (e.g. "stories" → "story")
    #  - sibilant-"es" → strip "es" (buses, boxes, buzzes, churches, dishes)
    #  - trailing "s" → strip (tools → tool, routines → routine)
    if t.endswith("ies") and len(t) > 3:
        t = t[:-3] + "y"
    elif len(t) > 3 and t.endswith(("ses", "xes", "zes", "ches", "shes")):
        t = t[:-2]
    elif t.endswith("s") and not t.endswith("ss") and len(t) > 3:
        t = t[:-1]
    return t


# ── Rendering ────────────────────────────────────────────────────────────────

def moc_link_line(moc: dict) -> str:
    path = moc.get("path", "")
    link = path
    if link.endswith(".md"):
        link = link[:-3]
    marker = "[x]" if moc.get("pre_check") else "[ ]"
    return f"- {marker} [[{link}]]"


def render_create_atomic_note(action: dict, stem: str) -> str:
    lines: list[str] = []
    title = action.get("suggested_title", "").strip() or stem
    lines.append(f"**Source:** [[{stem}]]")
    lines.append(f"**Suggested name:** {title}")
    dest = action.get("destination_concept")
    if dest:
        lines.append(f"**Destination:** {dest}")

    mocs = action.get("candidate_mocs") or []
    if mocs:
        lines.append("")
        lines.append("**Link to MOC:**")
        for moc in mocs:
            lines.append(moc_link_line(moc))

    if action.get("needs_new_moc"):
        topic = action.get("proposed_moc_topic") or ""
        if topic:
            lines.append("")
            parent = ""
            cls = action.get("classification") or {}
            if cls.get("category"):
                parent = f" under [[{cls['category']}]]"
            lines.append(f"**Propose new MOC:** {topic} (MOC){parent}")

    tags = [t for t in (action.get("tags_to_add") or []) if t]
    if tags:
        lines.append("")
        lines.append(f"**New tags to add:** {', '.join(tags)}")

    cls = action.get("classification") or {}
    why_bits = []
    if cls.get("category"):
        why_bits.append(f"Classification {cls['category']} ({int((cls.get('confidence') or 0) * 100)}%)")
    if mocs and mocs[0].get("pre_check"):
        why_bits.append(f"best MOC match {mocs[0].get('path','')} ({int((mocs[0].get('score') or 0) * 100)}%)")
    if action.get("atomic_note_worthiness") is not None:
        why_bits.append(f"atomic-worthiness {int(action['atomic_note_worthiness'] * 100)}%")
    if why_bits:
        lines.append("")
        lines.append("**Why:** " + "; ".join(why_bits) + ".")

    alternatives = action.get("alternatives") or []
    if alternatives:
        lines.append("")
        lines.append("**Alternatives:**")
        for alt in alternatives:
            lines.append(f"- [ ] {alt.get('kind', 'alternative')} — {alt.get('reason', '')}")

    lines.append("")
    lines.append("**Decision (atomic note):**")
    lines.append("- [x] Approve")
    lines.append("- [ ] Skip (keep in inbox)")
    lines.append("- [ ] Delete source")
    return "\n".join(lines)


def render_update_daily(action: dict, stem: str) -> str:
    lines: list[str] = []
    daily_path = action.get("daily_note_path", "")
    link = daily_path[:-3] if daily_path.endswith(".md") else daily_path
    lines.append(f"**Daily update:** [[{link}]]")
    updates = action.get("updates") or []
    if updates:
        lines.append("- Apply to the daily note:")
        for u in updates:
            field = u.get("field", "")
            value = u.get("value", "")
            syntax = u.get("syntax", "inline_field")
            if syntax == "inline_field":
                lines.append(f"  - Add `{field}:: {value}`")
            elif syntax == "callout_body":
                lines.append(f"  - Append to `{field}` section: {value}")
            elif syntax == "checkbox":
                mark = "[x]" if value in (True, "true", 1, "1") else "[ ]"
                lines.append(f"  - Check `{field}`: {mark}")
            else:
                lines.append(f"  - `{field}` = {value}")
    lines.append("")
    lines.append("**Decision (daily update):**")
    lines.append("- [x] Approve")
    lines.append("- [ ] Skip")
    return "\n".join(lines)


def render_link_to_moc(action: dict, stem: str) -> str:
    target = action.get("target_moc", "")
    section = action.get("section_name", "")
    return (
        f"**Source:** [[{stem}]]\n"
        f"**Link to existing MOC:** [[{target}#{section}]]\n"
        "\n**Decision (link to MOC):**\n- [x] Approve\n- [ ] Skip"
    )


def render_create_moc(action: dict, stem: str) -> str:
    moc_title = action.get("moc_title", "")
    parent = action.get("parent_moc", "")
    return (
        f"**Source:** [[{stem}]]\n"
        f"**Create new MOC:** {moc_title}\n"
        f"**Parent MOC:** [[{parent}]]\n"
        "\n**Decision (create MOC):**\n- [x] Approve\n- [ ] Skip"
    )


def render_modify_note(action: dict, stem: str) -> str:
    target = action.get("target_path", "")
    desc = action.get("diff_description", "")
    link = target[:-3] if target.endswith(".md") else target
    return (
        f"**Source:** [[{stem}]]\n"
        f"**Modify note:** [[{link}]]\n"
        f"**Change:** {desc}\n"
        "\n**Decision (modify note):**\n- [x] Approve\n- [ ] Skip"
    )


RENDERERS = {
    "create_atomic_note": render_create_atomic_note,
    "update_daily": render_update_daily,
    "link_to_moc": render_link_to_moc,
    "create_moc": render_create_moc,
    "modify_note": render_modify_note,
}


# ── Main ─────────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Reduce per-item result JSONs into a single suggestions-doc JSON."
    )
    p.add_argument("--state", required=True)
    p.add_argument("--items-dir", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--threshold", type=int, default=3,
                   help="Minimum cluster size to emit a Proposed MOC (default 3)")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    state_path = Path(args.state)
    items_dir = Path(args.items_dir)
    out_path = Path(args.output)

    state = last_state_per_stem(state_path)
    done_stems = sorted(s for s, e in state.items() if e.get("status") == "done")
    failed_entries = sorted(
        ((s, e) for s, e in state.items() if e.get("status") == "failed"),
        key=lambda kv: kv[0],
    )

    sections: list[dict] = []
    topic_clusters: dict[str, list[tuple[str, str, str]]] = {}  # norm_topic -> [(section_id, display, parent)]

    for idx, stem in enumerate(done_stems, start=1):
        result_path = items_dir / f"{stem}.result.json"
        if not result_path.exists():
            # Subagent reported done but file is missing — skip gracefully
            continue
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        section_id = f"S{idx:02d}"
        rendered_actions: list[dict] = []
        for action in result.get("actions", []):
            kind = action.get("kind")
            renderer = RENDERERS.get(kind)
            if not renderer:
                continue
            rendered = renderer(action, stem)
            rendered_actions.append({"kind": kind, "rendered_md": rendered})

            # Cluster Proposed MOCs from atomic-note actions
            if kind == "create_atomic_note" and action.get("needs_new_moc"):
                topic_raw = (action.get("proposed_moc_topic") or "").strip()
                if topic_raw:
                    norm = normalise_topic(topic_raw)
                    parent = ""
                    cls = action.get("classification") or {}
                    if cls.get("category"):
                        parent = cls["category"]
                    topic_clusters.setdefault(norm, []).append(
                        (section_id, topic_raw, parent)
                    )

        if rendered_actions:
            sections.append({
                "id": section_id,
                "stem": stem,
                "actions": rendered_actions,
            })

    proposed_mocs: list[dict] = []
    for norm, hits in topic_clusters.items():
        if len(hits) < args.threshold:
            continue
        display_topic = hits[0][1]  # first occurrence's original casing
        # Parent: mode across hits
        parents = [h[2] for h in hits if h[2]]
        parent = max(set(parents), key=parents.count) if parents else ""
        proposed_mocs.append({
            "topic": display_topic,
            "items": [h[0] for h in hits],
            "parent": parent,
        })

    needs_attention: list[dict] = []
    for stem, entry in failed_entries:
        err = entry.get("error") or {}
        needs_attention.append({
            "stem": stem,
            "error": f"{err.get('kind', 'unknown')}: {err.get('message', '')}".strip(": "),
        })

    doc = {
        "schema_version": "1",
        "generated": now_iso(),
        "run_id": args.run_id,
        "profile": args.profile,
        "source_items": len(done_stems) + len(failed_entries),
        "sections": sections,
        "proposed_mocs": proposed_mocs,
        "needs_attention": needs_attention,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"suggestions-reducer: done={len(done_stems)} failed={len(failed_entries)} "
        f"sections={len(sections)} proposed_mocs={len(proposed_mocs)} "
        f"out={out_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
