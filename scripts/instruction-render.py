#!/usr/bin/env python3
# version: 0.4.1
"""instruction-render.py — Deterministic Pass-2 rendering.

Reads parsed suggestions (from suggestion-parser.py) and produces three outputs
in --output-dir:

  1. Rendered note files (one markdown file per note that has a template).
  2. `instructions.json` — the canonical, machine-readable instruction set
     consumed by Tomo Hashi. Contains every action derived from the suggestions.
  3. `instructions.md` — human-readable view, rendered deterministically from
     the JSON. No LLM assembly is involved.

`manifest.json` is also written (the list of rendered files) for backwards
compatibility with callers that expect it.

Usage:
  python3 scripts/instruction-render.py \\
    --suggestions tomo-tmp/parsed-suggestions.json \\
    --output-dir tomo-tmp/rendered \\
    --config config/vault-config.yaml

Exit codes:
  0 — all items rendered successfully
  1 — one or more items failed (partial output, both JSON+MD still written)
  2 — fatal error (no output)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.kado_client import KadoClient, KadoError  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Config loading (T1.5 — one load, all fields resolved up front)
# ──────────────────────────────────────────────────────────────────────────────

CONFIG_DEFAULTS = {
    "concepts.inbox": "100 Inbox/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": None,
}


def _get_dotted(data: dict, dotted: str):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def load_config(config_path: str) -> dict:
    """Load all config fields needed by instruction-render in a single read.

    Returns a flat dict with the fields listed in CONFIG_DEFAULTS. Missing
    fields fall back to defaults. Paths are trimmed of stray whitespace.
    """
    resolved = dict(CONFIG_DEFAULTS)
    path = Path(config_path)
    if not path.exists():
        return resolved
    try:
        import yaml
        with path.open(encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] Could not parse {config_path}: {exc}", file=sys.stderr)
        return resolved

    for key in list(resolved):
        val = _get_dotted(cfg, key)
        if val is None:
            continue
        # strip stray trailing whitespace on path-like values
        if isinstance(val, str) and key.endswith(("path", "inbox")):
            val = val.strip()
        resolved[key] = val

    # Coerce heading_level to int
    try:
        resolved["daily_log.heading_level"] = int(resolved["daily_log.heading_level"])
    except (TypeError, ValueError):
        resolved["daily_log.heading_level"] = 2
    return resolved


def slugify(text: str) -> str:
    """Convert a title to a filename-safe slug."""
    s = text.lower()
    s = re.sub(r"[äÄ]", "ae", s)
    s = re.sub(r"[öÖ]", "oe", s)
    s = re.sub(r"[üÜ]", "ue", s)
    s = re.sub(r"ß", "ss", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:80]  # cap length


def read_note_body(client: KadoClient, path: str) -> str:
    """Read a note via Kado and extract body (content after frontmatter)."""
    try:
        result = client.read_note(path)
        content = result.get("content", "")
    except KadoError as exc:
        print(f"  [warn] Could not read source {path}: {exc}", file=sys.stderr)
        return ""

    # Strip frontmatter (--- ... ---)
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            body = content[end + 3:].strip()
            return body
    return content.strip()


def read_template(client: KadoClient, template_path: str) -> str | None:
    """Read a template file from the vault via Kado.

    Handles both full vault-relative paths (e.g. "Atlas/900 Templates/t_note_tomo.md")
    and bare stems (e.g. "t_note_tomo"). Bare stems are resolved via kado-search byName.
    """
    # Ensure .md extension
    if not template_path.endswith(".md"):
        template_path += ".md"
    # If bare stem (no path separator), resolve via search
    if "/" not in template_path:
        try:
            results = client.search_by_name(template_path)
            if results:
                template_path = results[0].get("path", template_path)
                print(f"  [template] Resolved bare stem to: {template_path}", file=sys.stderr)
            else:
                print(f"  [error] Template not found by name: {template_path}", file=sys.stderr)
                return None
        except KadoError as exc:
            print(f"  [error] Could not search for template {template_path}: {exc}", file=sys.stderr)
            return None
    try:
        result = client.read_note(template_path)
        return result.get("content", "")
    except KadoError as exc:
        print(f"  [error] Could not read template {template_path}: {exc}", file=sys.stderr)
        return None


def render_via_script(template_path: str, tokens_path: str, config_path: str) -> str | None:
    """Call token-render.py and return stdout, or None on error."""
    cmd = [
        sys.executable, str(SCRIPT_DIR / "token-render.py"),
        "--template", template_path,
        "--tokens", tokens_path,
        "--config", config_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"  [error] token-render.py failed: {result.stderr.strip()}", file=sys.stderr)
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        print("  [error] token-render.py timed out", file=sys.stderr)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Action building (T1.1)
# ──────────────────────────────────────────────────────────────────────────────

def _stem(path: str | None) -> str:
    """Extract the bare note stem from a path (no folder, no .md)."""
    if not path:
        return ""
    p = path.rsplit("/", 1)[-1]
    if p.endswith(".md"):
        p = p[:-3]
    return p


def _moc_stem(name: str | None) -> str:
    """Normalise a MOC reference to its bare stem."""
    return _stem(name)


def _next_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"I{counter[0]:02d}"


def _inbox_join(inbox: str, basename: str) -> str:
    """Join inbox path + basename, normalising the trailing slash."""
    return f"{(inbox or '').rstrip('/')}/{basename}"


def _dest_join(folder: str, title: str) -> str:
    """Join destination folder + sanitised title as filename (with .md)."""
    if not folder:
        folder = ""
    folder = folder.rstrip("/") + "/"
    # Obsidian allows Umlauts, em-dash etc. — no slug; just add .md.
    filename = title if title.endswith(".md") else f"{title}.md"
    return f"{folder}{filename}"


def _build_create_moc_actions(
    manifest: list[dict],
    inbox_path: str,
    counter: list[int],
) -> list[dict]:
    """Emit create_moc actions for rendered MOCs. MUST run before move_note and
    link_to_moc so IDs for new MOCs precede anything that links into them.
    """
    out: list[dict] = []
    for m in manifest:
        if m.get("action") != "create_moc":
            continue
        title = m.get("title", "")
        rendered = m.get("rendered_file", "")
        out.append({
            "id": _next_id(counter),
            "action": "create_moc",
            "source": _inbox_join(inbox_path, rendered) if rendered else "",
            "destination": _dest_join(m.get("destination", ""), title),
            "title": title,
            "rendered_file": rendered,
            "parent_moc": _moc_stem(m.get("parent_moc")) or None,
            "template": m.get("template") or None,
            "tags": m.get("tags", []) or [],
            "supporting_items": m.get("supporting_items") or None,
        })
    return out


def _build_move_note_actions(
    manifest: list[dict],
    inbox_path: str,
    counter: list[int],
) -> list[dict]:
    """Emit move_note actions for rendered atomic notes. Runs after create_moc."""
    out: list[dict] = []
    for m in manifest:
        if m.get("action") == "create_moc":
            continue
        title = m.get("title", "")
        rendered = m.get("rendered_file", "")
        origin_basename = m.get("source_path") or ""
        if origin_basename and "/" not in origin_basename:
            origin = _inbox_join(inbox_path, origin_basename)
        elif origin_basename:
            origin = origin_basename
        else:
            origin = None
        # Ensure origin has .md when present
        if origin and not origin.endswith(".md"):
            origin = origin + ".md"
        out.append({
            "id": _next_id(counter),
            "action": "move_note",
            "source": _inbox_join(inbox_path, rendered) if rendered else "",
            "destination": _dest_join(m.get("destination", ""), title),
            "title": title,
            "rendered_file": rendered,
            "origin_inbox_item": origin,
            "parent_mocs": [_moc_stem(x) for x in (m.get("parent_mocs") or []) if x],
            "tags": m.get("tags", []) or [],
        })
    return out


def _parse_supporting_items(raw: str | None) -> list[str]:
    """Parse 'S02, S06, S12' (or 'S02 S06 S12', or with brackets) → ['S02','S06','S12']."""
    if not raw:
        return []
    s = raw.strip().strip("[](){}").replace(",", " ")
    out: list[str] = []
    for tok in s.split():
        tok = tok.strip().strip("[]()").lstrip("#")
        if tok:
            out.append(tok)
    return out


def _build_link_to_moc_actions(confirmed: list[dict], counter: list[int]) -> list[dict]:
    """Emit link_to_moc actions from two sources:

    1. Each confirmed item's parent_mocs[] — the up-links user checked on the
       item (regular atomic notes) or on the proposed MOC block (for
       create_moc items, these are the new MOC's parents).
    2. Each create_moc item's supporting_items — down-links FROM the new MOC
       TO each confirmed atomic note referenced by ID. Fills the gap where
       the suggestions doc cannot offer a future-MOC as a parent option when
       reviewing atomic items.

    Dedup by (target_moc, line_to_add) so a parent_moc that happens to also
    appear in supporting_items isn't double-emitted.
    """
    id_index: dict[str, dict] = {it.get("id"): it for it in confirmed if it.get("id")}
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _emit(target_moc: str, source_title: str) -> None:
        key = (target_moc, source_title)
        if not target_moc or not source_title or key in seen:
            return
        seen.add(key)
        out.append({
            "id": _next_id(counter),
            "action": "link_to_moc",
            "target_moc": target_moc,
            "target_moc_path": None,
            "section_name": None,
            "line_to_add": f"- [[{source_title}]]",
            "source_note_title": source_title,
        })

    # Pass 1 — parent_mocs up-links from every confirmed item.
    for item in confirmed:
        parents = item.get("parent_mocs") or []
        if not parents and item.get("parent_moc"):
            parents = [item["parent_moc"]]
        if not parents:
            continue
        # For a create_moc item, the "source" of the up-link is the NEW MOC title.
        # For a regular atomic note, the source is the note title.
        if item.get("action") == "create_moc":
            source_title = item.get("title", "")
        else:
            source_title = item.get("title") or _stem(item.get("source_path"))
        for parent in parents:
            _emit(_moc_stem(parent), source_title)

    # Pass 2 — supporting_items down-links: each new MOC pulls its approved
    # supporting atomic notes as children. Required because the suggestions
    # doc cannot offer a not-yet-created MOC as a parent option at review time.
    for item in confirmed:
        if item.get("action") != "create_moc":
            continue
        new_moc_title = item.get("title", "")
        if not new_moc_title:
            continue
        for sid in _parse_supporting_items(item.get("supporting_items")):
            sup = id_index.get(sid)
            if not sup or sup.get("action") == "create_moc":
                continue  # supporting ID not confirmed, or references another MOC
            sup_title = sup.get("title") or _stem(sup.get("source_path"))
            if not sup_title:
                continue
            _emit(new_moc_title, sup_title)
    return out


def _resolve_daily_path(daily_path_cfg: str, date: str, daily_note_path: str | None) -> str:
    """Return a vault-relative path for a daily note.

    Prefer the path given by the classifier/parser (`daily_note_path`); fall
    back to `<daily_path_cfg>/<date>.md`.
    """
    if daily_note_path:
        p = daily_note_path.strip()
        if p and not p.endswith(".md"):
            p += ".md"
        return p
    base = (daily_path_cfg or "Calendar/301 Daily/").rstrip("/")
    return f"{base}/{date}.md"


def _build_daily_update_actions(
    daily_updates: list[dict],
    cfg: dict,
    counter: list[int],
) -> list[dict]:
    """Emit tracker / log_entry / log_link actions for accepted daily updates."""
    daily_path_cfg = cfg["concepts.calendar.granularities.daily.path"]
    heading = cfg["daily_log.heading"]
    heading_level = cfg["daily_log.heading_level"]
    out: list[dict] = []
    for day in daily_updates:
        date = day.get("date", "")
        note_path = _resolve_daily_path(daily_path_cfg, date, day.get("daily_note_path"))
        for tr in day.get("trackers", []) or []:
            if not tr.get("accepted"):
                continue
            out.append({
                "id": _next_id(counter),
                "action": "update_tracker",
                "daily_note_path": note_path,
                "date": date,
                "field": tr.get("field", ""),
                "value": tr.get("value", ""),
                "syntax": tr.get("syntax") or "inline_field",
                "section": tr.get("section") or None,
                "source_stem": _stem(tr.get("source_stem")) or None,
                "reason": tr.get("reason") or None,
            })
        for le in day.get("log_entries", []) or []:
            if not le.get("accepted"):
                continue
            out.append({
                "id": _next_id(counter),
                "action": "update_log_entry",
                "daily_note_path": note_path,
                "date": date,
                "section": heading,
                "heading_level": heading_level,
                "position": le.get("position") or "after_last_line",
                "time": le.get("time") or None,
                "content": le.get("content", ""),
                "source_stem": _stem(le.get("source_stem")) or None,
                "reason": le.get("reason") or None,
            })
        for ll in day.get("log_links", []) or []:
            if not ll.get("accepted"):
                continue
            out.append({
                "id": _next_id(counter),
                "action": "update_log_link",
                "daily_note_path": note_path,
                "date": date,
                "section": heading,
                "heading_level": heading_level,
                "position": ll.get("position") or "after_last_line",
                "time": ll.get("time") or None,
                "target_stem": _stem(ll.get("target_stem")) or "",
                "reason": ll.get("reason") or None,
            })
    return out


def _build_delete_source_actions(
    confirmed: list[dict],
    daily_updates: list[dict],
    skipped: list[dict],
    inbox_path: str,
    counter: list[int],
) -> list[dict]:
    """Emit delete_source actions from two sources:

    1. `skipped[]` entries where the user explicitly checked "Delete source"
       (disposition == "delete_source").
    2. Daily-only items — source_stems that appear in accepted daily_updates
       but have no matching confirmed_item (content fully captured in the
       daily note, no atomic note will be created).
    """
    out: list[dict] = []
    confirmed_stems: set[str] = set()
    for item in confirmed:
        sp = item.get("source_path")
        if sp:
            confirmed_stems.add(_stem(sp))

    inbox = inbox_path.rstrip("/") + "/"

    # (1) Explicit user "Delete source" on skipped items
    for sk in skipped:
        if sk.get("disposition") != "delete_source":
            continue
        sp = sk.get("source_path") or ""
        if not sp:
            continue
        full = sp if "/" in sp else f"{inbox}{sp}"
        if not full.endswith(".md"):
            full += ".md"
        out.append({
            "id": _next_id(counter),
            "action": "delete_source",
            "source_path": full,
            "reason": "User marked source for deletion (no atomic note created).",
        })

    # (2) Daily-only source stems
    seen: set[str] = set()
    for day in daily_updates:
        for bucket in ("trackers", "log_entries", "log_links"):
            for entry in day.get(bucket, []) or []:
                if not entry.get("accepted"):
                    continue
                stem = _stem(entry.get("source_stem"))
                if not stem or stem in confirmed_stems or stem in seen:
                    continue
                seen.add(stem)
                out.append({
                    "id": _next_id(counter),
                    "action": "delete_source",
                    "source_path": f"{inbox}{stem}.md",
                    "reason": "Content fully captured in daily note.",
                })
    return out


def _build_skip_actions(skipped: list[dict], inbox_path: str, counter: list[int]) -> list[dict]:
    out: list[dict] = []
    inbox = inbox_path.rstrip("/") + "/"
    for sk in skipped:
        if sk.get("disposition") != "skip":
            continue
        sp = sk.get("source_path") or None
        if sp and "/" not in sp:
            sp = f"{inbox}{sp}"
        if sp and not sp.endswith(".md"):
            sp += ".md"
        out.append({
            "id": _next_id(counter),
            "action": "skip",
            "source_path": sp,
            "reason": "Skipped by user (kept in inbox).",
        })
    return out


def build_actions(
    manifest: list[dict],
    confirmed: list[dict],
    daily_updates: list[dict],
    skipped: list[dict],
    cfg: dict,
) -> list[dict]:
    """Assemble the full ordered action list.

    Execution order matters: create_moc comes first because subsequent
    link_to_moc actions may target the newly-created MOCs (via supporting_items
    expansion). move_note follows, then all links (parent_mocs + supporting
    items), then daily updates, deletions, and skips.

    Emitted order:
      1. create_moc   — new MOCs must exist before anything links into them
      2. move_note    — atomic notes
      3. link_to_moc  — parent_mocs up-links + supporting_items down-links
      4. update_tracker / update_log_entry / update_log_link
      5. delete_source
      6. skip
    """
    counter = [0]
    inbox_path = cfg["concepts.inbox"]
    out: list[dict] = []
    out.extend(_build_create_moc_actions(manifest, inbox_path, counter))
    out.extend(_build_move_note_actions(manifest, inbox_path, counter))
    out.extend(_build_link_to_moc_actions(confirmed, counter))
    out.extend(_build_daily_update_actions(daily_updates, cfg, counter))
    out.extend(_build_delete_source_actions(
        confirmed, daily_updates, skipped, inbox_path, counter,
    ))
    out.extend(_build_skip_actions(skipped, inbox_path, counter))
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Markdown rendering (T1.4 — deterministic, matches the format the LLM used)
# ──────────────────────────────────────────────────────────────────────────────

SECTION_TITLES = [
    ("new_files", "New Files"),
    ("moc_links", "MOC Links"),
    ("daily_updates", "Daily Updates"),
    ("deletions", "Source Deletions"),
    ("skips", "Skips"),
]


def _md_section_for(action: dict) -> str:
    kind = action["action"]
    if kind in ("move_note", "create_moc"):
        return "new_files"
    if kind == "link_to_moc":
        return "moc_links"
    if kind in ("update_tracker", "update_log_entry", "update_log_link"):
        return "daily_updates"
    if kind == "delete_source":
        return "deletions"
    if kind == "skip":
        return "skips"
    return "new_files"


def _render_action_md(action: dict, cfg: dict) -> str:
    """Render a single action as an H3 block with a checkbox + structured fields."""
    aid = action["id"]
    kind = action["action"]
    heading_prefix = f"### {aid} — "

    if kind == "move_note":
        title = action.get("title") or "(untitled)"
        rendered = action.get("rendered_file", "")
        lines = [f"{heading_prefix}Move note: {title}", "- [ ] Applied"]
        if rendered:
            lines.append(f"- **Rendered file:** [[{_stem(rendered)}]]")
        if action.get("source"):
            lines.append(f"- **From:** `{action['source']}`")
        if action.get("destination"):
            lines.append(f"- **To:** `{action['destination']}`")
        if action.get("origin_inbox_item"):
            lines.append(f"- **Origin (reference):** [[{_stem(action['origin_inbox_item'])}]]")
        lines.append("- **After moving:** run `Templater: Replace Templates in Active File` via Cmd+P")
        return "\n".join(lines)

    if kind == "create_moc":
        title = action.get("title") or "(untitled)"
        lines = [f"{heading_prefix}Create MOC: {title}", "- [ ] Applied"]
        rendered = action.get("rendered_file")
        if rendered:
            lines.append(f"- **Rendered file:** [[{_stem(rendered)}]]")
        if action.get("source"):
            lines.append(f"- **From:** `{action['source']}`")
        if action.get("destination"):
            lines.append(f"- **To:** `{action['destination']}`")
        if action.get("parent_moc"):
            lines.append(f"- **Parent MOC:** [[{action['parent_moc']}]]")
        if action.get("supporting_items"):
            lines.append(f"- **Supporting items:** {action['supporting_items']} (each one will get a separate link_to_moc action below)")
        return "\n".join(lines)

    if kind == "link_to_moc":
        moc = action.get("target_moc", "")
        src = action.get("source_note_title", "")
        lines = [f"{heading_prefix}Add link to [[{moc}]] — {src}", "- [ ] Applied"]
        lines.append(f"- **Target:** [[{moc}]]")
        lines.append("- **Open the MOC**, find the first editable callout (e.g. `> [!blocks]`) or the matching section.")
        lines.append(f"- **Add this line:** `{action.get('line_to_add', '')}`")
        return "\n".join(lines)

    if kind == "update_tracker":
        date = action.get("date", "")
        daily_stem = date or _stem(action.get("daily_note_path"))
        lines = [f"{heading_prefix}Daily update: [[{daily_stem}]]", "- [ ] Applied"]
        lines.append(f"- **Open:** [[{daily_stem}]]")
        value = action.get("value", "")
        lines.append("- **Add to tracker section:**")
        lines.append(f"  `{action.get('field', '')}:: {value}`")
        return "\n".join(lines)

    if kind == "update_log_entry":
        date = action.get("date", "")
        daily_stem = date or _stem(action.get("daily_note_path"))
        section = action.get("section") or cfg.get("daily_log.heading", "Daily Log")
        level = action.get("heading_level") or cfg.get("daily_log.heading_level", 2)
        hashes = "#" * int(level)
        pos = action.get("position", "after_last_line")
        if pos == "at_time" and action.get("time"):
            pos_desc = f"Add at {action['time']} in section {hashes} {section} (chronological order)"
        elif pos == "before_first_line":
            pos_desc = f"Add before the first line in section {hashes} {section}"
        else:
            pos_desc = f"Add after the last line in section {hashes} {section}"
        lines = [f"{heading_prefix}Add log entry to [[{daily_stem}]]", "- [ ] Applied"]
        lines.append(f"- **Daily note:** [[{daily_stem}]]")
        lines.append(f"- **Section:** `{hashes} {section}`")
        lines.append(f"- **Position:** {pos_desc}")
        lines.append("- **Content to add:**")
        lines.append(f"  > {action.get('content', '')}")
        lines.append("- **If daily note doesn't exist:** Create it first, then add the entry.")
        return "\n".join(lines)

    if kind == "update_log_link":
        date = action.get("date", "")
        daily_stem = date or _stem(action.get("daily_note_path"))
        section = action.get("section") or cfg.get("daily_log.heading", "Daily Log")
        level = action.get("heading_level") or cfg.get("daily_log.heading_level", 2)
        hashes = "#" * int(level)
        pos = action.get("position", "after_last_line")
        if pos == "at_time" and action.get("time"):
            pos_desc = f"Add at {action['time']} in section {hashes} {section} (chronological order)"
        elif pos == "before_first_line":
            pos_desc = f"Add before the first line in section {hashes} {section}"
        else:
            pos_desc = f"Add after the last line in section {hashes} {section}"
        target = action.get("target_stem", "")
        lines = [f"{heading_prefix}Add log link to [[{daily_stem}]] → [[{target}]]", "- [ ] Applied"]
        lines.append(f"- **Daily note:** [[{daily_stem}]]")
        lines.append(f"- **Section:** `{hashes} {section}`")
        lines.append(f"- **Position:** {pos_desc}")
        lines.append(f"- **Link to add:** `- [[{target}]]`")
        return "\n".join(lines)

    if kind == "delete_source":
        src = action.get("source_path", "")
        lines = [f"{heading_prefix}Delete source note (content captured in daily note)", "- [ ] Applied"]
        if src:
            lines.append(f"- **Source:** [[{_stem(src)}]]")
        lines.append(f"- **Action:** Delete the note from the inbox — {action.get('reason', '')}")
        return "\n".join(lines)

    if kind == "skip":
        src = action.get("source_path")
        lines = [f"{heading_prefix}Skip — {_stem(src) if src else 'unknown source'}", "- [ ] Applied"]
        if src:
            lines.append(f"- **Source:** [[{_stem(src)}]]")
        lines.append(f"- **Reason:** {action.get('reason', 'Skipped by user.')}")
        return "\n".join(lines)

    # Fallback — unknown action type
    return f"{heading_prefix}(unknown action: {kind})\n- [ ] Applied"


def render_instructions_md(actions: list[dict], metadata: dict, cfg: dict) -> str:
    """Produce the full human-readable instruction set markdown."""
    fm_lines = ["---"]
    fm_lines.append("type: tomo-instructions")
    if metadata.get("source_suggestions"):
        fm_lines.append(f"source_suggestions: {metadata['source_suggestions']}")
    fm_lines.append(f"generated: {metadata['generated']}")
    if metadata.get("profile"):
        fm_lines.append(f"profile: {metadata['profile']}")
    if metadata.get("tomo_version"):
        fm_lines.append(f"tomo_version: \"{metadata['tomo_version']}\"")
    fm_lines.append(f"action_count: {len(actions)}")
    fm_lines.append("---")
    fm = "\n".join(fm_lines)

    # Group actions by section (preserving order within each section)
    by_section: dict[str, list[dict]] = {key: [] for key, _ in SECTION_TITLES}
    for a in actions:
        by_section.setdefault(_md_section_for(a), []).append(a)

    body_parts: list[str] = [fm, "", "# Instructions", ""]
    for key, title in SECTION_TITLES:
        bucket = by_section.get(key) or []
        if not bucket:
            continue
        body_parts.append(f"## {title}")
        body_parts.append("")
        for a in bucket:
            body_parts.append(_render_action_md(a, cfg))
            body_parts.append("")
    return "\n".join(body_parts).rstrip() + "\n"


def backfill_supporting_items_parents(confirmed: list[dict]) -> None:
    """Prepend each create_moc's title into its supporting items' parent_mocs.

    The suggestions doc cannot offer a not-yet-existing MOC as a parent option
    at review time, so supporting_items on the Proposed MOC block is the only
    way atomic notes get linked under a new MOC. This back-fill makes the
    relationship explicit BEFORE the rendering loop runs, so:

      - Rendered atomic notes pick up `up:: [[<new MOC>]]` via the {{up}} token
        (which reads parent_moc — the primary/first parent).
      - `build_actions` emits the link_to_moc down-links naturally via parent_mocs;
        the supporting_items expansion path deduplicates against it.

    Mutates `confirmed` in place. Safe to call multiple times (idempotent).
    """
    id_index = {it.get("id"): it for it in confirmed if it.get("id")}
    for item in confirmed:
        if item.get("action") != "create_moc":
            continue
        new_moc_title = item.get("title", "")
        if not new_moc_title:
            continue
        for sid in _parse_supporting_items(item.get("supporting_items")):
            sup = id_index.get(sid)
            if not sup or sup.get("action") == "create_moc":
                continue
            parents = sup.get("parent_mocs") or []
            # Normalise: strip to bare stems for comparison; prepend the new MOC
            # only if not already present under any naming convention.
            already = any(_moc_stem(p) == _moc_stem(new_moc_title) for p in parents)
            if not already:
                sup["parent_mocs"] = [new_moc_title] + list(parents)
            # Set primary parent_moc if empty — this is the field the rendering
            # loop reads to populate {{up}}.
            if not sup.get("parent_moc"):
                sup["parent_moc"] = new_moc_title


def resolve_target_moc_paths(actions: list[dict], client) -> int:
    """Best-effort: resolve `target_moc_path` on link_to_moc actions.

    Two-tier resolution:
      1. In-set lookup — if the target_moc matches a `create_moc` action in
         THIS instruction set, use its `destination` directly. The MOC doesn't
         exist in the vault yet, so Kado can't find it; but we know where it
         WILL be after Tomo Hashi applies I01.
      2. Kado `search_by_name` — for MOCs that already exist in the vault.

    Actions that can't be resolved by either route keep their
    `target_moc_path: null`. Returns the number of resolutions populated.
    """
    # Tier 1 — index create_moc actions by stem of their title so we can
    # resolve links that target a new MOC in the same instruction set.
    in_set: dict[str, str] = {}
    for a in actions:
        if a.get("action") == "create_moc":
            title = a.get("title") or ""
            dest = a.get("destination")
            if title and dest:
                in_set[_moc_stem(title)] = dest

    cache: dict[str, str | None] = {}
    def _resolve(stem: str) -> str | None:
        if stem in cache:
            return cache[stem]
        # Tier 1: in-set create_moc lookup (no Kado call, no I/O)
        if stem in in_set:
            cache[stem] = in_set[stem]
            return in_set[stem]
        # Tier 2: Kado byName search, cached per unique stem
        if client is None:
            cache[stem] = None
            return None
        try:
            hits = client.search_by_name(stem)
        except Exception:  # noqa: BLE001
            cache[stem] = None
            return None
        if not hits:
            cache[stem] = None
            return None
        # Prefer a hit whose filename stem matches exactly (not a substring).
        exact = [h for h in hits if _stem(h.get("path", "")) == stem]
        chosen = (exact or hits)[0]
        path = chosen.get("path") or None
        cache[stem] = path
        return path

    resolved = 0
    for a in actions:
        if a.get("action") != "link_to_moc":
            continue
        target = a.get("target_moc")
        if not target:
            continue
        path = _resolve(_moc_stem(target))
        if path:
            a["target_moc_path"] = path
            resolved += 1
    return resolved


def main() -> int:
    p = argparse.ArgumentParser(description="Render approved suggestions into note files.")
    p.add_argument("--suggestions", required=True, help="Path to parsed suggestions JSON")
    p.add_argument("--output-dir", required=True, help="Directory for rendered files")
    p.add_argument("--config", default="config/vault-config.yaml", help="vault-config.yaml path")
    args = p.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.suggestions, encoding="utf-8") as f:
        suggestions = json.load(f)

    confirmed = suggestions.get("confirmed_items", [])
    daily_updates = suggestions.get("daily_updates", [])
    skipped = suggestions.get("skipped", [])

    cfg = load_config(args.config)
    inbox_path = cfg["concepts.inbox"]
    daily_path = cfg["concepts.calendar.granularities.daily.path"]
    daily_heading = cfg["daily_log.heading"]
    daily_level = cfg["daily_log.heading_level"]
    profile_name = cfg["profile"]

    # No confirmed items AND no daily updates AND no skipped items → nothing to do.
    if not confirmed and not daily_updates and not skipped:
        print("instruction-render: no confirmed items, daily updates, or skips", file=sys.stderr)
        return 0

    client: KadoClient | None = None
    if confirmed:
        try:
            client = KadoClient()
        except KadoError as exc:
            print(f"FATAL: Cannot connect to Kado: {exc}", file=sys.stderr)
            return 2

    # Back-fill parent_mocs on supporting items of create_moc items — BEFORE
    # the rendering loop reads parent_moc to compute {{up}}. Ensures atomic
    # notes that justify a new MOC actually get `up:: [[<new MOC>]]` written.
    backfill_supporting_items_parents(confirmed)

    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%Y-%m-%d_%H%M")

    manifest: list[dict] = []
    errors = 0

    for item in confirmed:
        item_id = item.get("id", "?")
        # Render any item that has a template — that means it needs a file.
        # Items without a template (e.g. update_daily, link_to_moc) are
        # instruction-only and don't need rendering.
        if not item.get("template"):
            print(f"  [{item_id}] SKIP: no template (instruction-only)", file=sys.stderr)
            continue
        title = item.get("title") or item.get("source_path", "untitled")
        source_path = item.get("source_path", "")
        template_ref = item.get("template", "")
        tags = item.get("tags", [])
        parent_moc = item.get("parent_moc", "")
        parent_mocs = item.get("parent_mocs", [])
        destination = item.get("destination", "")
        summary = item.get("summary", "")

        print(f"  [{item_id}] Rendering: {title}", file=sys.stderr)

        # 1. Read template from vault
        if not template_ref:
            print(f"  [{item_id}] SKIP: no template specified", file=sys.stderr)
            errors += 1
            continue

        template_content = read_template(client, template_ref)
        if template_content is None:
            errors += 1
            continue

        # 2. Read source note body (uses pre-loaded inbox_path from config)
        body = ""
        if source_path:
            full_path = source_path
            if "/" not in full_path:
                full_path = f"{inbox_path.rstrip('/')}/{full_path}"
            if not full_path.endswith(".md"):
                full_path += ".md"
            body = read_note_body(client, full_path)

        # 3. Prepare tokens
        up_value = ""
        if parent_moc:
            # Use note name only (no path, no .md) — Obsidian resolves by name
            moc_stem = parent_moc.rsplit("/", 1)[-1]
            if moc_stem.endswith(".md"):
                moc_stem = moc_stem[:-3]
            up_value = f"[[{moc_stem}]]"

        # Tags as comma-separated string for inline YAML arrays:
        # tags: [existing, {{tags}}] → tags: [existing, topic/a, topic/b]
        # If passed as a list, format_list_token() would produce YAML block
        # syntax which breaks inline arrays in templates.
        tags_str = ", ".join(tags) if isinstance(tags, list) else (tags or "")

        tokens = {
            "title": title,
            "tags": tags_str,
            "up": up_value,
            "related": "",  # placeholder — populated by MOC creator post-MVP
            "body": body,
            "summary": summary or "",
        }

        # Write template and tokens to temp files
        tmpl_file = out_dir / f"{item_id}_template.md"
        tokens_file = out_dir / f"{item_id}_tokens.json"

        tmpl_file.write_text(template_content, encoding="utf-8")
        tokens_file.write_text(json.dumps(tokens, ensure_ascii=False), encoding="utf-8")

        # 4. Render
        rendered = render_via_script(str(tmpl_file), str(tokens_file), args.config)
        if rendered is None:
            errors += 1
            continue

        # 5. Write rendered file
        slug = slugify(title)
        filename = f"{date_prefix}_{slug}.md"
        rendered_path = out_dir / filename
        rendered_path.write_text(rendered, encoding="utf-8")

        manifest.append({
            "id": item_id,
            "action": item.get("action", "create_note"),
            "title": title,
            "source_path": source_path,
            "template": template_ref,
            "rendered_file": filename,
            "rendered_path": str(rendered_path),
            "destination": destination,
            "parent_moc": parent_moc,
            "parent_mocs": parent_mocs,
            "tags": tags,
            # Carry supporting_items so the create_moc action surfaces it in
            # instructions.json (the link_to_moc expansion already consumes it
            # from confirmed_items directly, but the field is useful context
            # for humans reading the instruction set).
            "supporting_items": item.get("supporting_items"),
        })

        # Clean up temp files
        tmpl_file.unlink(missing_ok=True)
        tokens_file.unlink(missing_ok=True)

        print(f"  [{item_id}] OK → {filename}", file=sys.stderr)

    # Write manifest (backwards compat — still the list of rendered files)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Build the unified action list (T1.1) ─────────────────────────────
    actions = build_actions(manifest, confirmed, daily_updates, skipped, cfg)

    # ── Resolve target_moc_path on link_to_moc actions via Kado ─────────
    # Best-effort; actions stay with `target_moc_path: null` if Kado is
    # unavailable or no match is found.
    resolved_paths = resolve_target_moc_paths(actions, client)
    if resolved_paths:
        print(f"  [resolve] target_moc_path populated for {resolved_paths} link_to_moc action(s)",
              file=sys.stderr)

    # ── Write instructions.json (T1.3) ───────────────────────────────────
    generated_iso = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_suggestions = _stem(args.suggestions)
    tomo_version = os.environ.get("TOMO_VERSION")
    instructions_doc = {
        "schema_version": "1",
        "type": "tomo-instructions",
        "source_suggestions": source_suggestions,
        "generated": generated_iso,
        "profile": profile_name,
        "tomo_version": tomo_version,
        "action_count": len(actions),
        "actions": actions,
    }
    instructions_json_path = out_dir / "instructions.json"
    instructions_json_path.write_text(
        json.dumps(instructions_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Render instructions.md (T1.4) ────────────────────────────────────
    md = render_instructions_md(
        actions,
        {
            "source_suggestions": source_suggestions,
            "generated": generated_iso,
            "profile": profile_name,
            "tomo_version": tomo_version,
        },
        cfg,
    )
    instructions_md_path = out_dir / "instructions.md"
    instructions_md_path.write_text(md, encoding="utf-8")

    print(
        f"instruction-render: rendered={len(manifest)} actions={len(actions)} "
        f"errors={errors} out={out_dir}",
        file=sys.stderr,
    )
    print(
        f"  manifest={manifest_path}\n"
        f"  instructions.json={instructions_json_path}\n"
        f"  instructions.md={instructions_md_path}",
        file=sys.stderr,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
