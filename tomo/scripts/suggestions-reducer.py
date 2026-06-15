#!/usr/bin/env python3
# suggestions-reducer.py — Phase C: aggregate per-item results into a
# suggestions-doc JSON which the orchestrator renders to markdown.
# version: 1.10.5
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
import sys
import time
from pathlib import Path

import yaml

# F-43 T1.5: clustering algorithm extracted into `lib/topic_clusters.py` so
# `moc-discovery.py` (Phase 2) can reuse it without copy-paste. Re-export
# `normalise_topic` here so external callers that import it from this module
# (e.g. `tests/test-004-phase3.sh`) keep working.
sys.path.insert(0, str(Path(__file__).resolve().parent))  # noqa: E402
from lib.doc_frontmatter import build_tomo_block  # noqa: E402 — F-47 T2.4
from lib.topic_clusters import (  # noqa: E402, F401
    ClusterCandidate,
    build_topic_clusters,
    normalise_topic,  # re-export for tests/test-004-phase3.sh
    strip_moc_marker,
)
from lib.slugify import slugify  # noqa: E402 — F-43 T3.1 MOC proposal filename
from lib.kado_client import KadoClient, KadoNotFoundError  # noqa: E402 — I38 Pass-1 existence check


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


# `normalise_topic` and `_compute_moc_tags` previously lived inline here.
# Both moved to `lib/topic_clusters.py` for F-43 T1.5 (shared with
# `moc-discovery.py`); `normalise_topic` is re-imported above for module-level
# access (still consumed by `tests/test-004-phase3.sh`).


# ── Rendering ────────────────────────────────────────────────────────────────

_LINE_TIER = (
    "**Placement:** under the note title (no matching section or callout found)"
    "    ← add a `## Heading` to target a section"
)


def _placement_line(anchor: dict) -> str:
    """Return the UX-locked **Placement:** line for a resolved anchor (spec 022 AC-12).

    Four formats keyed on anchor.type + new_section (verbatim wording is UX-locked):
      heading              → under `## <value>`
      callout + new_section → new section `## <new_section>` (created before the footer)
      callout (no new_section) → inside the `> [!<name>]` callout
      line / unresolved    → under the note title (no matching section or callout found)

    null-value guard: the schema allows value:null (unresolved LLM output). When
    value is falsy and the branch needs it (heading, or callout-without-new_section),
    fall back to the line-tier format — semantically correct (nothing was matched).
    """
    anchor_type = anchor.get("type", "")
    value = anchor.get("value") or ""
    new_section = anchor.get("new_section")

    if anchor_type == "heading":
        if not value:
            return _LINE_TIER
        return (
            f"**Placement:** under `## {value}`"
            "    ← edit the heading to move the link"
        )
    if anchor_type == "callout":
        if new_section:
            return (
                f"**Placement:** new section `## {new_section}` (created before the footer)"
                "    ← rename or change"
            )
        # null value without new_section → nothing was resolved; fall to line-tier.
        if not value:
            return _LINE_TIER
        # Extract `> [!name]` from value like "[!blocks] Key Concepts".
        # Guard: truncated LLM output like "[!blocks" (no closing "]") would
        # produce a garbled name via split("]")[0]. Fall to line-tier instead.
        if value.startswith("[!"):
            rest = value[2:]
            if "]" not in rest:
                return _LINE_TIER
            name = rest.split("]")[0]
            callout_ref = f"> [!{name}]"
        else:
            callout_ref = value
        return (
            f"**Placement:** inside the `{callout_ref}` callout"
            "    ← change to a `## Heading` to place under a section"
        )
    # type:line, unknown type, or unresolved — last-resort tier
    return _LINE_TIER


def moc_link_line(moc: dict) -> str:
    """Render a candidate-MOC checkbox line plus optional Placement hint (spec 022 T6.1).

    Returns a single checkbox line when no anchor is present (back-compat).
    Returns checkbox + **Placement:** line (newline-joined) when anchor is present.
    """
    path = moc.get("path", "")
    link = path[:-3] if path.endswith(".md") else path
    # pre_check is explicit per schema. If omitted, infer from score ≥ 0.5.
    if "pre_check" in moc:
        is_checked = bool(moc.get("pre_check"))
    else:
        is_checked = (moc.get("score") or 0) >= 0.5
    marker = "[x]" if is_checked else "[ ]"
    checkbox = f"- {marker} [[{link}]]"
    anchor = moc.get("anchor")
    if not anchor:
        return checkbox
    return checkbox + "\n" + _placement_line(anchor)


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


def _atomic_survives(action: dict) -> bool:
    """An atomic survives coexistence if it is worthy (>=0.5) or force_atomic.

    `force_atomic` is the action-level flag the analyst sets when the user
    ticked **Force Atomic Note**; it overrides a sub-threshold worthiness.
    """
    if action.get("force_atomic"):
        return True
    return action.get("atomic_note_worthiness", 0) >= 0.5


def _enforce_coexistence(actions: list[dict]) -> list[dict]:
    """Deterministic coexistence enforcement (analyst Step 9 table).

    F-41: an item may carry N create_atomic_note actions (one per topic) plus
    an update_daily with a log_entry. Resolve per-atomic instead of inspecting
    only the first:
      - Survivors = atomics with worthiness >= 0.5 OR force_atomic truthy.
      - Sub-worthy atomics are dropped individually.
      - If >=1 survivor remains, convert every log_entry → log_link targeting
        the FIRST survivor's title/stem; otherwise keep the log_entry as-is.
    """
    atomics = [a for a in actions if a.get("kind") == "create_atomic_note"]
    if not atomics:
        return actions

    has_log_entry = False
    for a in actions:
        if a.get("kind") != "update_daily":
            continue
        for u in a.get("updates") or []:
            if u.get("kind") == "log_entry":
                has_log_entry = True
                break

    if not has_log_entry:
        return actions

    survivors = [a for a in atomics if _atomic_survives(a)]
    sub_worthy = [a for a in atomics if not _atomic_survives(a)]

    # Drop sub-worthy atomics individually, preserving order of the rest.
    if sub_worthy:
        drop = {id(a) for a in sub_worthy}
        actions = [a for a in actions if id(a) not in drop]

    if survivors:
        first = survivors[0]
        target = first.get("suggested_title") or first.get("stem", "")
        for a in actions:
            if a.get("kind") != "update_daily":
                continue
            new_updates = []
            for u in a.get("updates") or []:
                if u.get("kind") == "log_entry":
                    new_updates.append({
                        "kind": "log_link",
                        "target_stem": target,
                        "time": u.get("time"),
                        "time_source": u.get("time_source"),
                        "position": u.get("position"),
                        "reason": u.get("reason", ""),
                    })
                else:
                    new_updates.append(u)
            a["updates"] = new_updates

    return actions


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
        topic = strip_moc_marker(action.get("proposed_moc_topic") or "")
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
    worthiness = action.get("atomic_note_worthiness")
    approve_mark = "[x]" if (worthiness is not None and worthiness >= 0.5) else "[ ]"
    lines.append(f"- {approve_mark} Approve")
    lines.append("- [ ] Keep origin (skip the implicit delete of the inbox source after move_note)")
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
    # AC-11: never emit a bare [[Target#section]] wikilink.
    # section_name was a dead field (section_name was never reliably populated
    # by the analyst — spec 022 uses the anchor field on candidate_mocs instead).
    target = action.get("target_moc", "")
    return (
        f"**Source:** [[{stem}]]\n"
        f"**Link to existing MOC:** [[{target}]]\n"
        "\n**Decision (link to MOC):**\n- [x] Approve\n- [ ] Skip"
    )


_MOC_SUFFIX = " (MOC)"


def _ensure_moc_suffix(title: str) -> str:
    """Ensure title ends with ' (MOC)', converting trailing ' MOC' if present."""
    if not title or title.strip() == "MOC":
        return title
    if title.endswith(_MOC_SUFFIX):
        return title
    if title.endswith(" MOC"):
        return title[:-4] + _MOC_SUFFIX
    return title + _MOC_SUFFIX


def _atomic_id(section_id: str, atomic_idx: int) -> str:
    """Per-atomic cluster/title key within a source section (F-41).

    A source may now emit N atomics. The 0th keeps the bare section_id so the
    single-thread case is byte-identical to the pre-F-41 keying (CON-2); later
    atomics get an `#idx` suffix so their titles do not overwrite each other in
    `section_titles` and resolve to their own atomic in `_enrich_proposed_mocs`.
    """
    return section_id if atomic_idx == 0 else f"{section_id}#{atomic_idx}"


def _enrich_proposed_mocs(
    proposed_mocs: list[dict],
    section_titles: dict[str, str],
) -> None:
    """Mutate each proposed_moc in-place: add name, note_titles, reason fields."""
    for pm in proposed_mocs:
        pm["name"] = _ensure_moc_suffix(pm["topic"])
        items: list[str] = pm.get("items") or []
        pm["note_titles"] = [
            section_titles.get(sid, sid) for sid in items
        ]
        n = len(items)
        topic = pm["topic"]
        pm["reason"] = (
            f"{n} note{'s' if n != 1 else ''} share topic {topic} "
            f"and have no dedicated MOC."
        )


def render_create_moc(action: dict, stem: str) -> str:
    moc_title = _ensure_moc_suffix(action.get("moc_title", ""))
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


def render_daily_notes_updates_block(
    daily_notes_updates: list[dict],
    daily_only_stems: set[str] | None = None,
) -> str:
    """Render the ## Daily Notes Updates section from daily_notes_updates[]."""
    if not daily_notes_updates:
        return ""
    daily_only_stems = daily_only_stems or set()
    lines: list[str] = ["## Daily Notes Updates", ""]
    # Collect all source stems referenced across all date entries
    # to show delete suggestions at the end
    deletable_sources: set[str] = set()

    for entry in daily_notes_updates:
        stem = entry["daily_note_stem"]
        if entry.get("exists", True):
            lines.append(f"### [[{stem}]]")
        else:
            # I38: warn in the Pass-1 doc (where the user accepts) that this
            # date's daily note is absent. Hashi modifies daily notes, it does
            # not create them — see domain_hashi_modifies_never_creates. The
            # #58 Pass-2 backstop drops the action; this heading lets the user
            # create the note (or skip) before they ever accept the entry.
            lines.append(
                f"### [[{stem}]] ⚠️ daily note doesn't exist — "
                "create it first or the entry is skipped"
            )
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
                if t["source_stem"] in daily_only_stems:
                    deletable_sources.add(t["source_stem"])
            lines.append("")

        log_entries = entry.get("log_entries") or []
        if log_entries:
            lines.append("**Possible Log Entries (inline text):**")
            for le in log_entries:
                position = le.get("position", "after_last_line")
                time_str = le.get("time") or position
                lines.append(f"- {time_str} — {le['content']}")
                lines.append(f"  - Reason: {le['reason']}")
                lines.append(f"  - Source: [[{le['source_stem']}]]")
                lines.append("  - [ ] Accept")
                # Force Atomic Note: always available under every log_entry.
                # Even when the source already has an atomic-note suggestion
                # below (possibly with a [ ] default because worthiness < 0.5),
                # exposing the checkbox here keeps the decision local — the
                # user doesn't have to scroll down and hunt for the per-item
                # section to promote a daily-log item into its own note.
                lines.append(
                    "  - [ ] Force Atomic Note "
                    "(create/keep a standalone note for this item)"
                )
                if le["source_stem"] in daily_only_stems:
                    deletable_sources.add(le["source_stem"])
            lines.append("")

        log_links = entry.get("log_links") or []
        if log_links:
            lines.append("**Possible Log Links (reference substantive notes):**")
            for ll in log_links:
                position = ll.get("position", "after_last_line")
                time_str = ll.get("time") or position
                lines.append(f"- [[{ll['target_stem']}]]")
                lines.append(f"  - Position: {time_str}")
                lines.append(f"  - Reason: {ll['reason']}")
                lines.append("  - [ ] Accept")
            lines.append("")

    # Sources whose content is fully captured in daily note(s) — offer deletion
    if deletable_sources:
        lines.append("**Delete source notes (content fully captured above):**")
        for src in sorted(deletable_sources):
            lines.append(f"- [ ] Delete [[{src}]]")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_log_link_mirror(log_links_for_stem: list[dict]) -> str:
    """Render per-item Material für block for items that produced log_links."""
    if not log_links_for_stem:
        return ""
    lines: list[str] = []
    for ll in log_links_for_stem:
        daily_stem = ll["daily_note_stem"]
        position = ll.get("position", "after_last_line")
        time_str = ll.get("time") or position
        lines.append(f"**Material für [[{daily_stem}]]:**")
        lines.append(f"- Reason: {ll['reason']}")
        lines.append(f"- Position: {time_str}")
        lines.append("- [ ] Accept (add link from daily log)")
    return "\n".join(lines)


RENDERERS = {
    "create_atomic_note": render_create_atomic_note,
    "update_daily": render_update_daily,
    "link_to_moc": render_link_to_moc,
    "create_moc": render_create_moc,
    "modify_note": render_modify_note,
}


# ── MOC Proposal rendering (F-43 T3.1) ───────────────────────────────────────


def _child_annotation(stem: str, existing_up_rows: list[dict]) -> str:
    """Return the parenthetical annotation for a child stem.

    Three branches (per SDD UI Guide §1015-1019 + ADR-1):
      - state="absent"  → `(no up:: yet)`
      - state="valid"   → `(existing up:: [[<target>]] → becomes related::)`
      - state="broken"  → `(existing up:: broken — ignored)`

    Falls back to absent if the stem has no row in existing_up_rows.
    """
    for row in existing_up_rows:
        if row.get("stem") == stem:
            state = row.get("state", "absent")
            target = row.get("target")
            if state == "valid" and target:
                return f"(existing up:: [[{target}]] → becomes `related::`)"
            elif state == "broken":
                return "(existing up:: broken — ignored)"
            else:
                return "(no up:: yet)"
    return "(no up:: yet)"


def _render_cluster_section(
    moc_id: str,
    cluster: dict,
    parent_opts: list[dict],
    trigger_arg: str,
) -> str:
    """Render one `### MOCxx — <Title>` section for the proposal-doc body.

    Args:
        moc_id:       Heading ID, e.g. "MOC01".
        cluster:      Enriched topic_cluster dict from DiscoveryReport.
        parent_opts:  parent_options_per_cluster[cluster_id] list.
        trigger_arg:  The original discovery trigger (for **Trigger:** field).
    """
    title = (cluster.get("title") or "").strip()
    confidence = cluster.get("confidence", 0.0)
    location = (cluster.get("location") or "Atlas/200 Maps/").rstrip("/") + "/"
    template = (cluster.get("template") or "t_moc_tomo").strip()
    if template.endswith(".md"):
        template = template[:-3]
    topic_keywords = cluster.get("topic_keywords") or []
    candidate_stems = cluster.get("candidate_stems") or []
    existing_up_rows: list[dict] = cluster.get("existing_up") or []

    n_children = len(candidate_stems)
    topics_csv = ", ".join(str(t) for t in topic_keywords) if topic_keywords else title.lower()

    lines: list[str] = [
        f"### {moc_id} — {title}",
        "",
        "- [ ] Accept",
        "",
        f"**Title:** `{title}`",
        f"**Location:** `{location}`",
        f"**Template:** [[{template}]]",
        "",
        f"**Trigger:** {trigger_arg}",
        f"**Confidence:** {int(round(confidence * 100))}%",
        f"**Cluster:** {n_children} Notes — {topics_csv}",
        "",
        "#### Parent",
        "",
    ]

    if parent_opts:
        for i, opt in enumerate(parent_opts):
            moc_stem = opt.get("moc_stem", "")
            opt_conf = opt.get("confidence", 0.0)
            marker = "[x]" if i == 0 else "[ ]"
            lines.append(f"- {marker} up:: [[{moc_stem}]] (confidence {opt_conf:.2f})")
        lines.append("- [ ] no parent (top-level MOC)")
    else:
        lines.append("- [x] no parent (top-level MOC)")
    lines.append("")

    lines.append(f"#### Children ({n_children})")
    lines.append("")
    for stem in candidate_stems:
        annotation = _child_annotation(stem, existing_up_rows)
        lines.append(f"- [x] [[{stem}]] {annotation}")
    lines.append("")

    lines.append("#### up::-Handling Override")
    lines.append("")
    lines.append(
        f"- [ ] **Keep existing up::, add new MOC as `related::`**"
        f" (applies to all {n_children} children)"
    )
    lines.append("")

    # Why-narrative (ADR-9): template-rendered, no LLM
    lines.append("#### Why this proposal")
    lines.append("")
    # Count children with a valid classification parent (state="valid")
    k_classified = sum(
        1 for r in existing_up_rows if r.get("state") == "valid"
    )
    # Determine parent label from parent_opts (top option)
    parent_label: str | None = None
    if parent_opts:
        top_opt = parent_opts[0]
        label = (top_opt.get("label") or "").strip()
        parent_label = label if label else None

    first = f"{n_children} notes with topic overlap {topics_csv} have no dedicated MOC."
    last = "This MOC would fill the gap."
    if parent_label and k_classified > 0:
        middle = f"{k_classified} of them have up:: to classification {parent_label}."
        why = f"{first}\n{middle} {last}"
    else:
        why = f"{first}\n{last}"
    lines.append(why)

    return "\n".join(lines)


def render_moc_proposal_doc(
    report: dict,
    config,
) -> tuple[str, str]:
    """Render a DiscoveryReport into a MOC proposal-doc (filename, body) pair.

    Implements the `--moc-proposal-mode` producer path (F-43 T3.1, ADR-2/4/9).
    Pure render function — does NOT write to disk. File-write is the caller's
    responsibility (CLI wrapper calls this, then writes the file itself).

    Args:
        report:  DiscoveryReport dict from moc-discovery.py.
        config:  Any object exposing `max_results: int` (duck-typed).

    Returns:
        (filename, body) — `filename` is the deterministic filename string
        (e.g. ``2026-05-07_1430_moc-proposal-shell-and-terminal.md``);
        `body` is the full markdown text.

    Behaviour:
      - Clusters are sorted by `confidence` DESC before rendering.
      - At most `config.max_results` cluster sections are emitted.
      - When more clusters exist, a footer line is appended.
      - The filename slug uses the top-confidence cluster's slug (ADR-2).
      - Frontmatter fields: type, proposal_kind, created, trigger, status,
        tomo_skip_inbox_analysis — all required by AC-3.1.
    """
    max_results: int = getattr(config, "max_results", 5)
    trigger_arg: str = report.get("trigger_arg") or ""
    mode: str = report.get("mode") or "tag"

    clusters: list[dict] = list(report.get("topic_clusters") or [])
    parent_options: dict[str, list[dict]] = report.get("parent_options_per_cluster") or {}

    # Sort clusters by confidence DESC (stable)
    clusters.sort(key=lambda c: c.get("confidence", 0.0), reverse=True)

    # Top-confidence cluster → filename slug (ADR-2)
    top_cluster = clusters[0] if clusters else {}
    top_slug = (
        top_cluster.get("slug")
        or slugify(top_cluster.get("title") or "moc")
        or "moc"
    )

    # Timestamp — matches the canonical Tomo artifact pattern used by
    # suggestions, instructions, suggestions-fan: <YYYY-MM-DD>_<HHMM>_<role>.md
    now_str = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    date_str = time.strftime("%Y-%m-%d", time.localtime())
    hhmm_str = time.strftime("%H%M", time.localtime())
    filename = f"{date_str}_{hhmm_str}_moc-proposal-{top_slug}.md"

    # Frontmatter
    trigger_field = f"{mode}:{trigger_arg}" if trigger_arg else mode
    # F-47 T2.4: build tomo: block (doc_type=moc-proposal, state=pending-accept)
    run_id: str = report.get("run_id") or ""
    tomo_block = build_tomo_block(
        doc_type="moc-proposal",
        state="pending-accept",
        run_id=run_id,
    )
    tomo_yaml = yaml.dump(
        {"tomo": tomo_block},
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip("\n")
    frontmatter_lines = [
        "---",
        "type: tomo-proposal",
        "proposal_kind: moc",
        f"created: {now_str}",
        f"trigger: {trigger_field}",
        "status: pending",
        "tomo_skip_inbox_analysis: true",
    ] + tomo_yaml.splitlines() + ["---"]

    # ADR-12: check-moc-uplinks reports carry no clusters — just the MOC orphan
    # audit. Title + orphan-section heading adapt so the doc reads as an audit.
    check_mode: bool = mode == "check-moc-uplinks"

    # Body
    body_lines: list[str] = [
        "",
        "# MOC Uplink Check" if check_mode else "# MOC Proposal",
        "",
    ]

    rendered = clusters[:max_results]
    overflow = len(clusters) - len(rendered)

    for i, cluster in enumerate(rendered, start=1):
        moc_id = f"MOC{i:02d}"
        cluster_id = cluster.get("cluster_id") or moc_id
        opts = parent_options.get(cluster_id) or parent_options.get(moc_id) or []
        section = _render_cluster_section(moc_id, cluster, opts, trigger_field)
        body_lines.append(section)
        body_lines.append("")

    if overflow > 0:
        body_lines.append("---")
        body_lines.append(f"*{overflow} additional cluster(s) found*")
        body_lines.append("")

    # Case-(a) orphan link-or-create section (spec 021 T2.4). Rendered AFTER the
    # cluster sections; absent entirely when there are no orphan suggestions.
    # ADR-12: orphan_overflow drives a footer when the list was capped; check_mode
    # relabels the section as a MOC-uplink audit.
    orphan_suggestions: list[dict] = report.get("orphan_suggestions") or []
    orphan_overflow: int = report.get("orphan_overflow") or 0
    if orphan_suggestions:
        body_lines.append(
            _render_orphan_section(
                orphan_suggestions, overflow=orphan_overflow, check_mode=check_mode
            )
        )
        body_lines.append("")

    full_body = "\n".join(frontmatter_lines) + "\n" + "\n".join(body_lines)

    return filename, full_body


def _render_orphan_section(
    orphan_suggestions: list[dict], *, overflow: int = 0, check_mode: bool = False
) -> str:
    """Render the case-(a) orphan link-or-create section (spec 021 T2.4, OQ-6).

    Per orphan (a cache entry with no parent — note OR moc), emit either:
      - link_existing → up to top-N selectable `up:: [[MOC]] (score …)` options;
      - create_new    → the reason line + a note that `/inbox` turns the accepted
        proposal into an instruction that stamps the reason into the note(s).

    `overflow` (ADR-12): when > 0, the orphan list was capped at
    orphan_display_cap; a footer states how many more were omitted and to re-run
    scoped. `check_mode` (ADR-12) relabels the heading as a MOC-uplink audit.

    `/moc-propose` writes NO vault note (CON-3) — this is proposal-doc markup
    only; the `up:`/note write happens later via the instruction set `/inbox`
    renders from the accepted proposal (then applied via Hashi/manually).
    """
    if check_mode:
        heading = "## MOC Uplink Check"
        intro = "*MOCs with no parent `up::`. Pick a link target or accept a new MOC.*"
    else:
        heading = "## Orphan Notes & MOCs"
        intro = "*Notes and MOCs with no parent. Pick a link target or accept a new MOC.*"
    lines: list[str] = [heading, "", intro, ""]

    for i, orphan in enumerate(orphan_suggestions, start=1):
        orphan_id = f"O{i:02d}"
        stem = (orphan.get("stem") or "").strip()
        kind = (orphan.get("kind") or "note").strip()
        mode = orphan.get("mode") or "create_new"

        lines.append(f"### {orphan_id} — [[{stem}]] ({kind})")
        lines.append("")

        if mode == "link_existing":
            lines.append("- [ ] Link to an existing MOC")
            lines.append("")
            candidates = orphan.get("candidates") or []
            for j, cand in enumerate(candidates):
                target = (cand.get("target_moc") or "").strip()
                # `or 0.0` (not get's default) so an explicitly-None score — the
                # key present but null — collapses to 0.0 before f-string format,
                # which would otherwise raise TypeError on None.{:.2f}.
                score = cand.get("score") or 0.0
                marker = "[x]" if j == 0 else "[ ]"
                lines.append(f"- {marker} up:: [[{target}]] (score {score:.2f})")
            lines.append("- [ ] no parent (leave as-is)")
        else:  # create_new
            lines.append("- [ ] Create a new MOC for this orphan")
            lines.append("")
            reason = (orphan.get("reason") or "").strip()
            lines.append(f"**Reason:** {reason}")
            lines.append("")
            lines.append(
                "*On accept, running `/inbox` turns this into an instruction that "
                f"stamps the reason into the {kind} and creates the new MOC. "
                "`/moc-propose` writes nothing.*"
            )
        lines.append("")

    if overflow > 0:
        lines.append("---")
        lines.append(
            f"*{overflow} more orphan(s) not shown — re-run with a scoped query "
            "(`folder:`/`tag:`/`class:`) to narrow the set.*"
        )
        lines.append("")

    return "\n".join(lines).rstrip("\n")


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

# ── I38 Pass-1: flag daily-note groups whose target note doesn't exist ────────
# Symmetric with instruction-render.filter_missing_daily_notes (#58, Pass-2).

def annotate_daily_note_existence(
    daily_groups: dict[str, dict],
    daily_path_by_stem: dict[str, str],
    client,
) -> int:
    """Set entry["exists"]=False for daily-note groups whose note is absent.

    One deduplicated Kado read per unique daily-note path. Fail-open: a None
    client (offline/test) or any error other than a definitive not-found keeps
    exists=True — never raise a false "missing" alarm. Returns the count of
    groups flagged missing.
    """
    if client is None:
        return 0
    missing = 0
    cache: dict[str, bool] = {}
    for stem, entry in daily_groups.items():
        path = daily_path_by_stem.get(stem)
        if not path:
            continue
        # The analyst emits an extensionless daily_note_path (e.g.
        # "Calendar/301 Daily/2026-04-29"). Kado's kado-read note op is .md-only
        # and returns VALIDATION_ERROR (not NOT_FOUND) without the extension —
        # which the fail-open branch below would swallow, leaving exists=True and
        # the warning silently absent. Normalise to .md (mirrors
        # instruction-render._resolve_daily_path) so a missing note reads as a
        # clean not-found.
        read_path = path if path.endswith(".md") else f"{path}.md"
        if read_path not in cache:
            ok = True  # fail-open default
            try:
                client.read_note(read_path)
            except KadoNotFoundError:
                ok = False
            except Exception:  # noqa: BLE001 — transient/other error: keep exists=True
                ok = True
            cache[read_path] = ok
        if not cache[read_path]:
            entry["exists"] = False
            missing += 1
    return missing


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Reduce per-item result JSONs into a single suggestions-doc JSON."
    )
    # ── MOC-proposal mode (F-43 T3.1) — mutually exclusive with inbox mode ──
    p.add_argument(
        "--moc-proposal-mode",
        action="store_true",
        help="Render a DiscoveryReport (from moc-discovery.py) into a proposal-doc. "
             "Requires --input; ignores --state/--items-dir/--run-id/--profile/--output.",
    )
    p.add_argument(
        "--input",
        default=None,
        help="Path to DiscoveryReport JSON (required when --moc-proposal-mode is set).",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        # T3.1 extension: required for T3.2 agent integration — agent tells the
        # script where the inbox is; not part of the core spec flags but
        # operationally unavoidable.
        help="Directory to write the proposal-doc (required when --moc-proposal-mode is set).",
    )
    # ── Inbox mode (existing) ─────────────────────────────────────────────────
    p.add_argument("--state")
    p.add_argument("--items-dir")
    p.add_argument("--run-id")
    p.add_argument("--profile")
    p.add_argument("--output")
    p.add_argument("--shared-ctx", default="tomo-tmp/shared-ctx.json",
                   help="Path to shared-ctx.json (for field→section lookup)")
    p.add_argument("--threshold", type=int, default=1,
                   help="Minimum cluster size to emit a Proposed MOC section (default 1 — "
                        "every needs_new_moc surfaces; cluster size shown in heading)")
    p.add_argument("--fan-resolve", action="store_true",
                   help="XDD 012 fan-resolve mode: include ONLY items whose result.json has "
                        "force_atomic=true; skip daily_notes_updates, proposed_mocs, and "
                        "needs_attention; emit doc_variant='fan-resolve' for the renderer.")
    p.add_argument("--no-kado", action="store_true",
                   help="Skip the live Kado daily-note existence check (I38). "
                        "Offline/test mode: all daily notes are assumed to exist.")
    return p


def _main_moc_proposal(args: argparse.Namespace) -> int:
    """Handle --moc-proposal-mode: read DiscoveryReport, render proposal-doc, write to disk."""
    if not args.input:
        print(
            "suggestions-reducer: --moc-proposal-mode requires --input <discovery-report.json>",
            file=sys.stderr,
        )
        return 1
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"suggestions-reducer: input not found: {input_path}", file=sys.stderr)
        return 1

    try:
        report = json.loads(input_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"suggestions-reducer: failed to read input: {exc}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else Path(".")

    # Duck-typed config: only max_results is consulted by render_moc_proposal_doc.
    # max_results comes from MocProposalConfig (not a CLI flag — spec AC-3.1).
    class _InlineCfg:
        max_results: int = 5

    cfg = _InlineCfg()

    filename, body = render_moc_proposal_doc(report, cfg)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename
    out_path.write_text(body, encoding="utf-8")
    print(f"suggestions-reducer: moc-proposal written to {out_path}", file=sys.stderr)
    # Print just the resolved path to stdout so the agent can capture it
    print(str(out_path))
    return 0


def main() -> int:
    args = build_arg_parser().parse_args()

    # F-43 T3.1: --moc-proposal-mode is mutually exclusive with the inbox flow.
    if args.moc_proposal_mode:
        return _main_moc_proposal(args)

    # Validate required inbox-mode args
    for flag in ("state", "items_dir", "run_id", "profile", "output"):
        if getattr(args, flag, None) is None:
            print(
                f"suggestions-reducer: --{flag.replace('_', '-')} is required in inbox mode",
                file=sys.stderr,
            )
            return 1
    state_path = Path(args.state)
    items_dir = Path(args.items_dir)
    out_path = Path(args.output)
    load_field_sections(Path(args.shared_ctx))

    state = last_state_per_stem(state_path)
    done_stems = sorted(s for s, e in state.items() if e.get("status") == "done")
    failed_entries = sorted(
        ((s, e) for s, e in state.items() if e.get("status") == "failed"),
        key=lambda kv: kv[0],
    )

    # XDD 012 fan-resolve mode: filter done_stems to items whose result.json
    # carries force_atomic=true. This keeps the resolve doc focused on the
    # FAN-triggered atomic proposals only, regardless of what else the
    # state-file contains.
    if args.fan_resolve:
        def _has_force_atomic(stem: str) -> bool:
            rp = items_dir / f"{stem}.result.json"
            if not rp.exists():
                return False
            try:
                return bool(json.loads(rp.read_text(encoding="utf-8")).get("force_atomic"))
            except (json.JSONDecodeError, OSError):
                return False
        done_stems = [s for s in done_stems if _has_force_atomic(s)]
        failed_entries = []  # resolve doc does not surface other failures

    sections: list[dict] = []
    # F-43 T1.5: clustering moved to `lib.topic_clusters.build_topic_clusters`.
    # We now collect a flat list of candidates while looping over actions and
    # let the helper handle normalisation + threshold + parent-vote + tag-fold.
    cluster_candidates: list[ClusterCandidate] = []
    # section_id -> suggested_title (for note_titles in proposed_mocs)
    section_titles: dict[str, str] = {}
    # daily_note_stem -> {trackers, log_entries, log_links}
    daily_groups: dict[str, dict] = {}
    # daily_note_stem -> daily_note_path (I38: for the Kado existence check;
    # kept off the entry dict because the output schema is additionalProperties:false)
    daily_path_by_stem: dict[str, str] = {}
    # stem -> [(daily_note_stem, time, reason)] for Material für mirror
    stem_log_links: dict[str, list[dict]] = {}
    # stems whose content is fully captured in daily note(s) — source can be deleted
    daily_only_stems: set[str] = set()
    # F-41 T1: global flat counter for suggestion_ids (S01, S02, …); increments
    # for every rendered create_atomic_note across all sources.  Daily-only items
    # (0 atomics) do NOT increment this counter.
    suggestion_counter: int = 0
    # title -> flat suggestion_id; populated as atomics are rendered so that
    # log_link.source_section can reference the correct suggestion_id.
    title_to_suggestion_id: dict[str, str] = {}

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
        had_update_daily = False
        # F-41: index atomics within this source so each gets a distinct
        # cluster/title key (see _atomic_id). 0th keeps the bare section_id.
        atomic_idx = 0
        actions = _enforce_coexistence(result.get("actions", []))
        # F-41 T1 W1: pre-pass — assign flat suggestion_ids to all
        # create_atomic_note actions before the main loop processes
        # update_daily.  This makes log_link.source_section resolution
        # order-independent: title_to_suggestion_id is fully populated
        # regardless of whether update_daily appears before or after the
        # atomics in actions[].
        _pre_counter = suggestion_counter
        for _pre_action in actions:
            if _pre_action.get("kind") == "create_atomic_note":
                _pre_counter += 1
                _pre_title = (
                    (_pre_action.get("suggested_title") or "").strip()
                    or stem
                )
                title_to_suggestion_id[_pre_title] = f"S{_pre_counter:02d}"
        for action in actions:
            kind = action.get("kind")
            renderer = RENDERERS.get(kind)
            if not renderer:
                continue
            if kind == "update_daily":
                # Do NOT render the per-item `**Daily update:**` /
                # `**Decision (daily update):**` block — the aggregated
                # ## Daily Notes Updates block at the top already captures
                # every tracker / log_entry / log_link for the user to
                # accept in one place. Per-item duplication was the
                # 2026-04-22 UX ask ("unten sollte nicht nochmal alles
                # bzgl. der daily note auftauchen").
                had_update_daily = True
                rendered = None
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
                    dpath = action.get("daily_note_path")
                    if dpath and daily_stem not in daily_path_by_stem:
                        daily_path_by_stem[daily_stem] = dpath
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
                                "position": u.get("position"),
                                "content": u.get("content", ""),
                                "reason": u.get("reason", ""),
                                "source_stem": stem,
                                "source_section": section_id,
                            })
                        elif ukind == "log_link":
                            target = u.get("target_stem", stem)
                            # F-41 T1: source_section for atomic-derived log_links
                            # must reference the flat suggestion_id of the atomic,
                            # not the per-source section_id.  title_to_suggestion_id
                            # is pre-populated before this loop so the lookup is
                            # order-independent (W1).
                            log_link_source_section = title_to_suggestion_id.get(
                                target, section_id
                            )
                            daily_groups[daily_stem]["log_links"].append({
                                "target_stem": target,
                                "time": u.get("time"),
                                "time_source": u.get("time_source"),
                                "position": u.get("position"),
                                "reason": u.get("reason", ""),
                                "source_stem": stem,
                                "source_section": log_link_source_section,
                            })
                            # Record for per-item Material für mirror
                            stem_log_links.setdefault(stem, []).append({
                                "daily_note_stem": daily_stem,
                                "time": u.get("time"),
                                "reason": u.get("reason", ""),
                            })
            else:
                rendered = renderer(action, stem)
            if rendered is not None:
                rendered_action: dict = {"kind": kind, "rendered_md": rendered}
                # F-41 T1: assign a flat global suggestion_id to each rendered
                # atomic so the renderer (T2) can display SNN headers.
                if kind == "create_atomic_note":
                    suggestion_counter += 1
                    suggestion_id_flat = f"S{suggestion_counter:02d}"
                    rendered_action["suggestion_id"] = suggestion_id_flat
                rendered_actions.append(rendered_action)

            # Collect Proposed-MOC candidates from atomic-note actions; the
            # actual normalisation + threshold + parent-vote + shared-tag fold
            # happens in `build_topic_clusters` after the action loop completes.
            if kind == "create_atomic_note":
                atomic_key = _atomic_id(section_id, atomic_idx)
                if action.get("needs_new_moc"):
                    topic_raw = (action.get("proposed_moc_topic") or "").strip()
                    if topic_raw:
                        cls = action.get("classification") or {}
                        parent = cls.get("category") or ""
                        item_tags = [t for t in (action.get("tags_to_add") or []) if t]
                        cluster_candidates.append(
                            ClusterCandidate(
                                section_id=atomic_key,
                                topic=topic_raw,  # strip_moc_marker is applied in build_topic_clusters
                                parent=parent,
                                tags=item_tags,
                            )
                        )
                # Record per-atomic key → title for note_titles post-processing.
                title = (action.get("suggested_title") or "").strip() or stem
                section_titles[atomic_key] = title
                # F-41 T1: keep title_to_suggestion_id current for any callers
                # that read it after the main loop.  The pre-pass already wrote
                # this entry; the update here uses suggestion_id_flat (already
                # computed above) rather than reconstructing from the counter.
                if rendered is not None:
                    title_to_suggestion_id[title] = suggestion_id_flat
                atomic_idx += 1

        # The per-item `Material für [[daily]]` mirror block is gone as of
        # 2026-04-22 — the top Daily Notes Updates block owns the log_link
        # decision. stem_log_links is still populated above because the
        # DELETE-SOURCE bookkeeping in the daily-notes renderer needs to
        # know which stems fed log_links; the rendering itself no longer
        # happens here.

        # After the filter above, rendered_actions contains no update_daily
        # entries — update_daily-only items produce an empty list. Items
        # that ONLY produce update_daily are "daily-only" → fully captured
        # by the top block → mark the source for deletion and skip the
        # per-item section. Items that also produce a non-daily action
        # (create_atomic_note, etc.) still get a per-item section; the
        # atomic decision lives there, the daily decision stays at the top.
        if had_update_daily and not rendered_actions:
            daily_only_stems.add(stem)
        if rendered_actions:
            sections.append({
                "id": section_id,
                "stem": stem,
                "actions": rendered_actions,
            })

    # F-43 T1.5: clustering algorithm extracted; same input, same output.
    # The helper is also called by `moc-discovery.py` (Phase 2) so the two
    # call sites cannot drift in normalisation or tag-fold semantics.
    proposed_mocs: list[dict] = list(
        build_topic_clusters(cluster_candidates, args.threshold)
    )

    # Post-process: add name, note_titles, reason fields.
    _enrich_proposed_mocs(proposed_mocs, section_titles)

    needs_attention: list[dict] = []
    for stem, entry in failed_entries:
        err = entry.get("error") or {}
        needs_attention.append({
            "stem": stem,
            "error": f"{err.get('kind', 'unknown')}: {err.get('message', '')}".strip(": "),
        })

    # I38: flag groups whose daily note doesn't exist so Pass 1 surfaces it
    # (not just the #58 Pass-2 backstop). On by default; --no-kado disables.
    # Fail-open — no Kado config / unreachable → all exists=True (prior behavior).
    kado_client = None
    if not args.no_kado and not args.fan_resolve:
        try:
            kado_client = KadoClient()
        except Exception:  # noqa: BLE001 — no Kado config → fail-open
            kado_client = None
    missing_daily = annotate_daily_note_existence(
        daily_groups, daily_path_by_stem, kado_client
    )

    daily_notes_updates = sorted(daily_groups.values(), key=lambda d: d["daily_note_stem"])
    daily_notes_updates_sorted = daily_notes_updates
    rendered_daily_updates_md = render_daily_notes_updates_block(
        daily_notes_updates_sorted, daily_only_stems=daily_only_stems
    )

    # XDD 012 fan-resolve: drop the aggregated blocks the resolve doc
    # doesn't need. Keep sections (atomic proposals) and override the
    # precedence note so the user sees what this doc is for.
    if args.fan_resolve:
        daily_notes_updates = []
        rendered_daily_updates_md = ""
        proposed_mocs = []
        needs_attention = []
        precedence_note = (
            "This is a **Force-Atomic Resolve** doc. Tomo noticed you ticked "
            "**Force Atomic Note** on log entries whose inbox items had no "
            "atomic-note proposal in the primary suggestions doc. Each section "
            "below is a freshly-proposed atomic for one of those items. Review, "
            "approve (or skip) the proposals, then tick **[x] Approved** at the "
            "top and re-run `/inbox` — Pass 2 will merge these approvals back "
            "into the primary doc and render instructions for both together."
        )
        doc_variant = "fan-resolve"
    else:
        precedence_note = (
            "Daily-note decisions (trackers, log entries, log links) live in the "
            "Daily Notes Updates block above. Per-item Suggestion sections only "
            "cover the atomic-note decision. Use **Force Atomic Note** on a log "
            "entry to create a standalone note even when the item was only "
            "proposed for the daily log."
        )
        doc_variant = "primary"

    doc = {
        "schema_version": "1",
        "generated": now_iso(),
        "run_id": args.run_id,
        "profile": args.profile,
        "doc_variant": doc_variant,  # XDD 012 — primary | fan-resolve
        "source_items": len(done_stems) + len(failed_entries),
        "sections": sections,
        "daily_notes_updates": daily_notes_updates,
        "rendered_daily_updates_md": rendered_daily_updates_md,
        "decision_precedence_note": precedence_note,
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
        f"daily_notes_missing={missing_daily} "
        f"proposed_mocs={len(proposed_mocs)} out={out_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
