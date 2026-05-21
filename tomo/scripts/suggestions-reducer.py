#!/usr/bin/env python3
# suggestions-reducer.py — Phase C: aggregate per-item results into a
# suggestions-doc JSON which the orchestrator renders to markdown.
# version: 1.1.0
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
)
from lib.slugify import slugify  # noqa: E402 — F-43 T3.1 MOC proposal filename


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
      - state="absent"  → `(kein up:: bisher)`
      - state="valid"   → `(existing up:: [[<target>]] → wird related::)`
      - state="broken"  → `(existing up:: broken — ignored)`

    Falls back to absent if the stem has no row in existing_up_rows.
    """
    for row in existing_up_rows:
        if row.get("stem") == stem:
            state = row.get("state", "absent")
            target = row.get("target")
            if state == "valid" and target:
                return f"(existing up:: `[[{target}]]` → wird `related::`)"
            elif state == "broken":
                return "(existing up:: broken — ignored)"
            else:
                return "(kein up:: bisher)"
    return "(kein up:: bisher)"


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
            lines.append(f"- {marker} up:: `[[{moc_stem}]]` (confidence {opt_conf:.2f})")
        lines.append("- [ ] kein parent (top-level MOC)")
    else:
        lines.append("- [x] kein parent (top-level MOC)")
    lines.append("")

    lines.append(f"#### Children ({n_children})")
    lines.append("")
    for stem in candidate_stems:
        annotation = _child_annotation(stem, existing_up_rows)
        lines.append(f"- [x] `[[{stem}]]` {annotation}")
    lines.append("")

    lines.append("#### up::-Handling Override")
    lines.append("")
    lines.append(
        f"- [ ] **Bestehende up:: behalten, neue MOC als `related::`**"
        f" (gilt für alle {n_children} Children)"
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

    first = f"{n_children} Notes mit Topic-Overlap {topics_csv} haben keine dedizierte MOC."
    last = "Diese MOC würde die Lücke füllen."
    if parent_label and k_classified > 0:
        middle = f"{k_classified} davon haben up:: zur Klassifikation {parent_label}."
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
        (e.g. ``tomo-moc-proposal-20260507-1430-shell-and-terminal.md``);
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

    # Timestamp
    now_str = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    date_str = time.strftime("%Y%m%d", time.localtime())
    hhmm_str = time.strftime("%H%M", time.localtime())
    filename = f"tomo-moc-proposal-{date_str}-{hhmm_str}-{top_slug}.md"

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

    # Body
    body_lines: list[str] = [
        "",
        "# MOC-Vorschlag",
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
        body_lines.append(f"*Weitere {overflow} Cluster gefunden*")
        body_lines.append("")

    full_body = "\n".join(frontmatter_lines) + "\n" + "\n".join(body_lines)

    return filename, full_body


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
    field_sections = load_field_sections(Path(args.shared_ctx))

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
    # daily_note_stem -> {trackers, log_entries, log_links}
    daily_groups: dict[str, dict] = {}
    # stem -> [(daily_note_stem, time, reason)] for Material für mirror
    stem_log_links: dict[str, list[dict]] = {}
    # stems whose content is fully captured in daily note(s) — source can be deleted
    daily_only_stems: set[str] = set()

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
        for action in result.get("actions", []):
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
                            daily_groups[daily_stem]["log_links"].append({
                                "target_stem": target,
                                "time": u.get("time"),
                                "time_source": u.get("time_source"),
                                "position": u.get("position"),
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
            if rendered is not None:
                rendered_actions.append({"kind": kind, "rendered_md": rendered})

            # Collect Proposed-MOC candidates from atomic-note actions; the
            # actual normalisation + threshold + parent-vote + shared-tag fold
            # happens in `build_topic_clusters` after the action loop completes.
            if kind == "create_atomic_note" and action.get("needs_new_moc"):
                topic_raw = (action.get("proposed_moc_topic") or "").strip()
                if topic_raw:
                    cls = action.get("classification") or {}
                    parent = cls.get("category") or ""
                    item_tags = [t for t in (action.get("tags_to_add") or []) if t]
                    cluster_candidates.append(
                        ClusterCandidate(
                            section_id=section_id,
                            topic=topic_raw,
                            parent=parent,
                            tags=item_tags,
                        )
                    )

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

    needs_attention: list[dict] = []
    for stem, entry in failed_entries:
        err = entry.get("error") or {}
        needs_attention.append({
            "stem": stem,
            "error": f"{err.get('kind', 'unknown')}: {err.get('message', '')}".strip(": "),
        })

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
        f"proposed_mocs={len(proposed_mocs)} out={out_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
