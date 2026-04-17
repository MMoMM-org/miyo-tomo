#!/usr/bin/env python3
# suggestions-reducer.py — Phase C: aggregate per-item results into a
# suggestions-doc JSON which the orchestrator renders to markdown.
# version: 0.3.0
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
    """Render a candidate-MOC checkbox line. MOC must be a dict per schema."""
    path = moc.get("path", "")
    link = path[:-3] if path.endswith(".md") else path
    # pre_check is explicit per schema. If omitted, infer from score ≥ 0.5.
    if "pre_check" in moc:
        is_checked = bool(moc.get("pre_check"))
    else:
        is_checked = (moc.get("score") or 0) >= 0.5
    marker = "[x]" if is_checked else "[ ]"
    return f"- {marker} [[{link}]]"


def _template_link(template: str) -> str:
    """Render a template reference as a wikilink (bare name, no .md).

    Accepts either a full filename ('Atomic Note.md'), a bare name
    ('Atomic Note'), or a concept key ('atomic_note'). Emits `[[Atomic Note]]`
    or `[[atomic_note]]` respectively — the user edits if they want.
    """
    name = (template or "").strip()
    if name.endswith(".md"):
        name = name[:-3]
    return f"[[{name}]]" if name else ""


def _location_link(location: str) -> str:
    """Render a folder location. Strip trailing slashes; keep as wikilink
    target so Obsidian opens the folder on click (where supported)."""
    loc = (location or "").strip().rstrip("/")
    return f"[[{loc}/]]" if loc else ""


def render_create_atomic_note(action: dict, stem: str) -> str:
    lines: list[str] = []
    title = (action.get("suggested_title") or "").strip() or stem
    lines.append(f"**Source:** [[{stem}]]")
    lines.append(f"**Suggested name:** {title}")
    template = action.get("template")
    if template:
        lines.append(f"**Template:** {_template_link(template)}    ← change if you want a different template")
    location = action.get("location")
    if location:
        lines.append(f"**Location:** {_location_link(location)}    ← change if you want a different folder")

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
            lines.append(
                f"**Note:** No good thematic MOC matched. A proposed new MOC for this item is "
                f"shown in the **Proposed MOCs** section below (topic: *{topic}*) where you can "
                f"approve creation or edit the name."
            )

    tags = [t for t in (action.get("tags_to_add") or []) if t]
    if tags:
        lines.append("")
        lines.append(f"**New tags to add:** {', '.join(tags)}")

    cls = action.get("classification") or {}
    why_bits = []
    if cls.get("category"):
        why_bits.append(
            f"Classification {cls['category']} ({int((cls.get('confidence') or 0) * 100)}%)"
        )
    top = mocs[0] if mocs else None
    if top and (top.get("pre_check") or (top.get("score") or 0) >= 0.5):
        why_bits.append(
            f"best MOC match {top.get('path','')} ({int((top.get('score') or 0) * 100)}%)"
        )
    if action.get("atomic_note_worthiness") is not None:
        why_bits.append(
            f"atomic-worthiness {int(action['atomic_note_worthiness'] * 100)}%"
        )
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


def _daily_note_stem(path: str) -> str:
    """Extract the bare date-stem from a daily-note path.

    `Calendar/301 Daily/2026-04-15.md` → `2026-04-15`
    `Calendar/301 Daily/ /2026-04-15`  → `2026-04-15`  (defensive)
    `2026-04-15`                       → `2026-04-15`
    """
    if not path:
        return ""
    p = path.strip()
    if p.endswith(".md"):
        p = p[:-3]
    # Use the last non-empty path segment (tolerates stray whitespace and
    # double slashes from mis-joined prefixes).
    segments = [s.strip() for s in p.split("/") if s.strip()]
    return segments[-1] if segments else p


def render_update_daily(action: dict, stem: str, field_sections: dict[str, str] | None = None) -> str:
    field_sections = field_sections or {}
    lines: list[str] = []
    daily_stem = _daily_note_stem(action.get("daily_note_path", ""))
    # Wikilinks use the note-name only — never the path. Obsidian resolves by name.
    lines.append(f"**Daily update:** [[{daily_stem}]]")

    # Only render tracker updates here — log_entry and log_link are rendered
    # in the aggregated Daily Notes Updates block, not per-item.
    updates = action.get("updates") or []
    trackers = [u for u in updates if u.get("kind") == "tracker"]

    grouped: dict[str, list[dict]] = {}
    for u in trackers:
        field = u.get("field", "")
        section = field_sections.get(field) or u.get("section") or "<unknown section>"
        grouped.setdefault(section, []).append(u)

    for section, group in grouped.items():
        lines.append("")
        lines.append(f"Under `## {section}` (create it if missing):")
        for u in group:
            field = u.get("field", "")
            value = u.get("value", "")
            syntax = u.get("syntax", "inline_field")
            if syntax == "inline_field":
                value_str = "true" if value is True else ("false" if value is False else str(value))
                lines.append(f"- Add `{field}:: {value_str}`")
            elif syntax == "callout_body":
                lines.append(f"- Under the `{field}` entry, append: {value}")
            elif syntax == "checkbox":
                mark = "[x]" if value in (True, "true", 1, "1") else "[ ]"
                lines.append(f"- Check `{field}`: `- {mark} {field}`")
            else:
                lines.append(f"- `{field}` = {value}")

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


def render_daily_notes_updates_block(daily_notes_updates: list[dict]) -> str:
    """Render the ## Daily Notes Updates section from daily_notes_updates[]."""
    if not daily_notes_updates:
        return ""
    lines: list[str] = ["## Daily Notes Updates", ""]
    for entry in daily_notes_updates:
        stem = entry["daily_note_stem"]
        lines.append(f"### [[{stem}]]")
        lines.append("")
        if not entry.get("exists", True):
            lines.append(f"- [ ] Create daily note [[{stem}]] first")
            lines.append("")

        trackers = entry.get("trackers") or []
        if trackers:
            lines.append("**Possible Trackers:**")
            for t in trackers:
                value_str = "true" if t["value"] is True else ("false" if t["value"] is False else str(t["value"]))
                lines.append(f"- **{t['field']}** → `{value_str}`")
                lines.append(f"  - Reason: {t['reason']}")
                lines.append(f"  - Source: [[{t['source_stem']}]] ({t['source_section']})")
                lines.append("  - [ ] Accept")
            lines.append("")

        log_entries = entry.get("log_entries") or []
        if log_entries:
            lines.append("**Possible Log Entries (inline text):**")
            for le in log_entries:
                time_str = le.get("time") or "end of day"
                lines.append(f"- {time_str} — {le['content']}")
                lines.append(f"  - Reason: {le['reason']}")
                lines.append(f"  - Source: [[{le['source_stem']}]]")
                lines.append("  - [ ] Accept")
            lines.append("")

        log_links = entry.get("log_links") or []
        if log_links:
            lines.append("**Possible Log Links (reference substantive notes):**")
            for ll in log_links:
                time_str = ll.get("time") or "end of day"
                lines.append(f"- [[{ll['target_stem']}]]")
                lines.append(f"  - Time: {time_str}")
                lines.append(f"  - Reason: {ll['reason']}")
                lines.append("  - [ ] Accept")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_log_link_mirror(log_links_for_stem: list[dict]) -> str:
    """Render per-item Material für block for items that produced log_links."""
    if not log_links_for_stem:
        return ""
    lines: list[str] = []
    for ll in log_links_for_stem:
        daily_stem = ll["daily_note_stem"]
        time_str = ll.get("time") or "end of day"
        lines.append(f"**Material für [[{daily_stem}]]:**")
        lines.append(f"- Reason: {ll['reason']}")
        lines.append(f"- Time: {time_str}")
        lines.append("- [ ] Accept (add link from daily log)")
    return "\n".join(lines)


RENDERERS = {
    "create_atomic_note": render_create_atomic_note,
    "update_daily": render_update_daily,
    "link_to_moc": render_link_to_moc,
    "create_moc": render_create_moc,
    "modify_note": render_modify_note,
}


def load_field_sections(shared_ctx_path: Path) -> dict[str, str]:
    """Build a {field_name: section} map from shared-ctx.json."""
    if not shared_ctx_path or not shared_ctx_path.exists():
        return {}
    try:
        ctx = json.loads(shared_ctx_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, str] = {}
    for f in (ctx.get("daily_notes") or {}).get("tracker_fields", []) or []:
        name = f.get("name")
        section = f.get("section")
        if name and section:
            out[name] = section
    return out


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
    p.add_argument("--shared-ctx", default="tomo-tmp/shared-ctx.json",
                   help="Path to shared-ctx.json (for field→section lookup)")
    p.add_argument("--threshold", type=int, default=1,
                   help="Minimum cluster size to emit a Proposed MOC section (default 1 — "
                        "every needs_new_moc surfaces; cluster size shown in heading)")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    state_path = Path(args.state)
    items_dir = Path(args.items_dir)
    out_path = Path(args.output)
    field_sections = load_field_sections(Path(args.shared_ctx))

    state = last_state_per_stem(state_path)
    done_stems = sorted(s for s, e in state.items() if e.get("status") == "done")
    failed_entries = sorted(
        ((s, e) for s, e in state.items() if e.get("status") == "failed"),
        key=lambda kv: kv[0],
    )

    sections: list[dict] = []
    topic_clusters: dict[str, list[tuple[str, str, str]]] = {}  # norm_topic -> [(section_id, display, parent)]
    # daily_note_stem -> {trackers, log_entries, log_links}
    daily_groups: dict[str, dict] = {}
    # stem -> [(daily_note_stem, time, reason)] for Material für mirror
    stem_log_links: dict[str, list[dict]] = {}

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
            if kind == "update_daily":
                rendered = renderer(action, stem, field_sections)
                # Collect daily_notes_updates entries
                daily_stem = _daily_note_stem(action.get("daily_note_path", "") or action.get("date", ""))
                if daily_stem:
                    if daily_stem not in daily_groups:
                        daily_groups[daily_stem] = {
                            "daily_note_stem": daily_stem,
                            "exists": True,
                            "trackers": [],
                            "log_entries": [],
                            "log_links": [],
                        }
                    for u in action.get("updates") or []:
                        ukind = u.get("kind")
                        if ukind == "tracker":
                            daily_groups[daily_stem]["trackers"].append({
                                "field": u.get("field", ""),
                                "value": u.get("value"),
                                "reason": u.get("reason", ""),
                                "source_stem": stem,
                                "source_section": section_id,
                            })
                        elif ukind == "log_entry":
                            daily_groups[daily_stem]["log_entries"].append({
                                "time": u.get("time"),
                                "time_source": u.get("time_source"),
                                "content": u.get("content", ""),
                                "reason": u.get("reason", ""),
                                "source_stem": stem,
                                "source_section": section_id,
                            })
                        elif ukind == "log_link":
                            target = u.get("target_stem", stem)
                            daily_groups[daily_stem]["log_links"].append({
                                "target_stem": target,
                                "time": u.get("time"),
                                "time_source": u.get("time_source"),
                                "reason": u.get("reason", ""),
                                "source_stem": stem,
                                "source_section": section_id,
                            })
                            # Record for per-item Material für mirror
                            stem_log_links.setdefault(stem, []).append({
                                "daily_note_stem": daily_stem,
                                "time": u.get("time"),
                                "reason": u.get("reason", ""),
                            })
            else:
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

        # Append Material für mirror blocks to per-item rendered actions
        if stem in stem_log_links:
            material_md = render_log_link_mirror(stem_log_links[stem])
            if material_md:
                # Append to the last create_atomic_note action if present, else last action
                target_action = None
                for ra in rendered_actions:
                    if ra["kind"] == "create_atomic_note":
                        target_action = ra
                if target_action is None and rendered_actions:
                    target_action = rendered_actions[-1]
                if target_action is not None:
                    target_action["rendered_md"] = target_action["rendered_md"] + "\n\n" + material_md

        # Items that ONLY have update_daily actions are fully represented in the
        # aggregated Daily Notes Updates block — skip per-item section to avoid
        # duplication. Items that mix update_daily with other actions (e.g.
        # create_atomic_note + update_daily) still get a per-item section.
        has_non_daily = any(a["kind"] != "update_daily" for a in rendered_actions)
        if rendered_actions and has_non_daily:
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

    daily_notes_updates = sorted(daily_groups.values(), key=lambda d: d["daily_note_stem"])
    daily_notes_updates_sorted = daily_notes_updates
    rendered_daily_updates_md = render_daily_notes_updates_block(daily_notes_updates_sorted)

    doc = {
        "schema_version": "1",
        "generated": now_iso(),
        "run_id": args.run_id,
        "profile": args.profile,
        "source_items": len(done_stems) + len(failed_entries),
        "sections": sections,
        "daily_notes_updates": daily_notes_updates,
        "rendered_daily_updates_md": rendered_daily_updates_md,
        "decision_precedence_note": (
            "If you Accept in either the Daily Notes Updates block or the per-item Material block, "
            "the decision is captured once. Top-of-doc block takes precedence if both are checked."
        ),
        "proposed_mocs": proposed_mocs,
        "needs_attention": needs_attention,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"suggestions-reducer: done={len(done_stems)} failed={len(failed_entries)} "
        f"sections={len(sections)} daily_notes_updates={len(daily_notes_updates)} "
        f"proposed_mocs={len(proposed_mocs)} out={out_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
