# version: 0.2.1
"""render_md.py — deterministic markdown rendering for the instruction set.

Extracted from instruction-render.py (#42, D-07 Constitution L2 split). Turns the
machine-readable action list into the human-readable `instructions.md` view, in
the same format the LLM used (T1.4). Pure rendering — no Kado calls; the only
inputs are the already-built actions, run metadata, and config.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from lib.doc_frontmatter import body_after_frontmatter, build_tomo_block
from lib.render_helpers import _moc_stem, _stem
from lib.supporting_items import parse_supporting_items as _parse_supporting_items

SECTION_TITLES = [
    ("new_files", "New Files"),
    ("moc_links", "MOC Links"),
    ("daily_updates", "Daily Updates"),
    ("tag_handler_updates", "Tag-Handler Updates"),
    ("deletions", "Source Deletions"),
    ("skips", "Skips"),
]


def _md_section_for(action: dict) -> str:
    kind = action["action"]
    if kind in ("move_note", "create_moc"):
        return "new_files"
    if kind in ("link_to_moc", "add_relationship"):
        return "moc_links"
    if kind in ("update_tracker", "update_log_entry", "update_log_link"):
        return "daily_updates"
    if kind == "insert_under_marker":
        return "tag_handler_updates"
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
        if action.get("source_inbox_item"):
            lines.append(f"- **Source (reference):** [[{_stem(action['source_inbox_item'])}]]")
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
        if action.get("target_moc_path"):
            lines.append(f"- **Path:** `{action['target_moc_path']}`")
        anchor = action.get("anchor") or {}
        anchor_type = anchor.get("type") or "callout"
        anchor_value = anchor.get("value")
        placement = action.get("placement", "after")
        if anchor_value:
            lines.append(f"- **Anchor:** `{anchor_value}` ({anchor_type}, placement: {placement})")
            if anchor_type == "callout" and placement == "inside":
                lines.append("- **Open the MOC and find that callout**, then add the line below as the last line of its body.")
            elif placement == "after":
                lines.append(f"- **Open the MOC and find that {anchor_type}**, then add the line below immediately after it.")
        else:
            lines.append(f"- **Anchor:** (unresolved {anchor_type}, placement: {placement})")
            lines.append("- **Open the MOC**, find the first editable callout (e.g. `> [!blocks]`) or the matching section.")
        lines.append(f"- **Add this line:** `{action.get('line_to_add', '')}`")
        return "\n".join(lines)

    if kind == "add_relationship":
        moc = action.get("target_moc") or _stem(action.get("target_moc_path", ""))
        marker = action.get("marker", "")
        line = action.get("line", "")
        lines = [f"{heading_prefix}Update {marker} on [[{moc}]]", "- [ ] Applied"]
        if action.get("target_moc_path"):
            lines.append(f"- **Path:** `{action['target_moc_path']}`")
        lines.append(f"- **Marker:** `{marker}`")
        lines.append(f"- **Replace marker line with:** `{line}`")
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

    if kind == "insert_under_marker":
        target = action.get("target_path", "")
        anchor = action.get("anchor") or {}
        anchor_value = anchor.get("value", "")
        placement = action.get("placement", "inside")
        lines = [f"{heading_prefix}Insert under `{anchor_value}` in [[{_stem(target)}]]", "- [ ] Applied"]
        lines.append(f"- **Target:** [[{_stem(target)}]]")
        lines.append(f"- **Marker:** `{anchor_value}` (heading, placement: {placement})")
        lines.append("- **Insert this block:**")
        for content_line in (action.get("content", "") or "").splitlines():
            lines.append(f"  > {content_line}")
        return "\n".join(lines)

    # Fallback — unknown action type
    return f"{heading_prefix}(unknown action: {kind})\n- [ ] Applied"


# Known upstream doc types for the --upstream-type CLI flag.
# T1.3 (XDD-018): source_* kwargs replaced by sources list in build_tomo_block.
_UPSTREAM_TYPES: list[str] = ["suggestions", "moc-proposal", "suggestions-fan", "garden-audit"]


def _compute_sha256(file_path: str) -> str | None:
    """Compute the SHA-256 checksum of a doc's BODY (frontmatter stripped).

    Returns 'sha256:<hex>' or None on read error. Hashes the body only — Tomo
    mutates the `tomo:` frontmatter (state/updated_at) after rendering, so a
    frontmatter-inclusive hash would make every covered doc read as drifted on
    the next /inbox run (#78). The consumer side (inbox-triage._compute_checksum)
    strips identically, so recorded and current checksums stay comparable.
    """
    import hashlib

    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    body = body_after_frontmatter(content)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def compute_payload_digest(payload: dict) -> str:
    """Return 'sha256:<hex>' over the canonical serialization of an editable payload.

    Change signal for the suggestions wire (ADR-026). The digest excludes the
    'emit_digest' key and uses a canonical form (sorted keys, no incidental
    whitespace) so it is invariant to re-serialization order — only semantic
    content changes move it. A consumer recomputes the digest and compares it
    against the stored value: a mismatch means the payload was edited.
    """
    import hashlib
    import json

    editable = {k: v for k, v in payload.items() if k != "emit_digest"}
    canonical = json.dumps(
        editable, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def unwrap_list_repr(value):
    """Unwrap a stringified list-repr `"['a', 'b']"` → the Python list `['a','b']`.

    DEFENSIVE against dirty caches: some moc-structure caches persist a
    frontmatter `up:` list as its Python str repr (e.g. "['020 Active MOC']").
    Rendered naively this leaks `[[['020 Active MOC']]]`. The real fix is upstream
    in up_parse (so freshly-explored caches are clean), but existing caches stay
    dirty until re-explored — so the renderers unwrap here too. Non-list-repr
    strings (bare stems, `[[wikilinks]]`) pass through unchanged.
    """
    if isinstance(value, str):
        s = value.strip()
        # A [[wikilink]] also starts with "[" — never treat it as a list-repr.
        if s.startswith("[") and not s.startswith("[["):
            try:
                parsed = yaml.safe_load(s)
            except yaml.YAMLError:
                parsed = None
            if isinstance(parsed, list):
                return parsed
    return value


def bare_stem(ref) -> str:
    """Bare stem of a note/MOC ref: strip [[ ]], a folder prefix, and .md.

    Shared by garden-audit-render (structural comment) and garden-audit-parser
    (confirmed_item reconstruction). Load-bearing round-trip contract: both sides
    must derive the same stem from a given ref, so it lives here (single home).
    Defensively unwraps a stringified list-repr (dirty cache) to its first element.
    """
    ref = unwrap_list_repr(ref)
    if isinstance(ref, (list, tuple)):
        ref = next((r for r in ref if r is not None and str(r).strip()), "")
    s = str(ref or "").strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2].strip()
    s = s.rsplit("/", 1)[-1]
    if s.endswith(".md"):
        s = s[:-3]
    return s.strip()


def up_line(up_target) -> str:
    """Render an up:: value (str | list of stems) as `up:: [[a]], [[b]]`.

    The graph cache stores up:: as a multi-value list, so up_target may arrive as
    e.g. ['020 Active MOC']. Reduces to clean stems (strip [[ ]], whitespace,
    empties) so the reconstructed frontmatter line is exact — never a list repr.
    Also defensively unwraps a stringified list-repr (dirty cache) before formatting.

    Shared by garden-audit-render (structural comment `match`) and
    garden-audit-parser (edit_note_text removal `match`). Parity-locked: if the
    two sides diverge, the comment's match no longer matches what the parser
    reconstructs and the fix silently no-ops. Single home enforces parity.
    """
    up_target = unwrap_list_repr(up_target)
    raw = up_target if isinstance(up_target, (list, tuple)) else [up_target]
    stems = []
    for t in raw:
        s = str(t or "").strip()
        if s.startswith("[[") and s.endswith("]]"):
            s = s[2:-2].strip()
        if s:
            stems.append(s)
    return "up:: " + ", ".join(f"[[{s}]]" for s in stems)


def _build_tomo_block_for_instructions(metadata: dict) -> dict | None:
    """Build the tomo: block for an instructions doc from renderer metadata.

    Returns the inner block dict (without the 'tomo' wrapper key) or None
    if the metadata lacks the fields required to build a valid block.

    T1.3 (XDD-018): upstream cross-ref now stored as sources=[{path}] list.
    T1.4 (XDD-018): when upstream_body_path is present, sources[0] also
    carries a sha256 checksum computed from the cached body file.
    SDD §Implementation Gotchas: uses metadata['run_id'] (Pass-2 run),
    NOT any upstream run_id.
    """
    upstream_type = metadata.get("upstream_type")
    upstream_path = metadata.get("upstream_path")
    upstream_body_path = metadata.get("upstream_body_path")
    run_id = metadata.get("run_id")
    if not run_id:
        return None
    if upstream_type and upstream_type not in _UPSTREAM_TYPES:
        print(
            f"  [warn] Unknown upstream_type {upstream_type!r} — "
            "omitting source from tomo: block",
            file=sys.stderr,
        )
    sources_list = []
    if upstream_path and upstream_type in _UPSTREAM_TYPES:
        source: dict[str, str] = {"path": upstream_path}
        if upstream_body_path:
            checksum = _compute_sha256(upstream_body_path)
            if checksum:
                source["checksum"] = checksum
        sources_list.append(source)
    return build_tomo_block(
        doc_type="instructions",
        state="pending-apply",
        run_id=run_id,
        sources=sources_list if sources_list else None,
    )


def render_instructions_md(actions: list[dict], metadata: dict, cfg: dict) -> str:
    """Produce the full human-readable instruction set markdown."""
    import yaml

    fm_lines = ["---"]
    fm_lines.append("type: tomo-instructions")
    # Emit the tomo: block (F-47 AC-1.3) when run_id is present in metadata.
    tomo_block = _build_tomo_block_for_instructions(metadata)
    if tomo_block is not None:
        # Serialize the nested block as indented YAML (strip trailing newline).
        tomo_yaml = yaml.dump(
            {"tomo": tomo_block},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
        fm_lines.append(tomo_yaml)
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

    # Skipped daily-note actions (#37/I38): surfaced so the user knows a log
    # entry / tracker was dropped because its daily note does not exist (Hashi
    # cannot create one). Create the daily note and re-run to apply these.
    skipped_daily = metadata.get("skipped_daily") or []
    skipped_rel = metadata.get("skipped_rel") or []
    if skipped_daily or skipped_rel:
        body_parts.append("## Skipped — un-appliable actions")
        body_parts.append("")
        if skipped_daily:
            body_parts.append(
                "**Daily note missing** — Create the daily note in Obsidian "
                "and re-run `/inbox` to apply:")
            body_parts.append("")
            for a in skipped_daily:
                stem = _stem(a.get("daily_note_path")) or a.get("date", "?")
                detail = a.get("content") or a.get("field") or a.get("target_stem") or ""
                body_parts.append(f"- `{a.get('action')}` → [[{stem}]] — {detail}".rstrip(" —"))
            body_parts.append("")
        if skipped_rel:
            body_parts.append(
                "**Up-link child not found** — The child note was missing or "
                "non-markdown at render time. Create the note and re-run `/inbox` "
                "to add the up-link:")
            body_parts.append("")
            for a in skipped_rel:
                target = a.get("target_moc_path") or "?"
                error = a.get("error") or "?"
                line = a.get("line") or ""
                body_parts.append(f"- `add_relationship` → `{target}` [{error}] — {line}".rstrip(" —"))
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

