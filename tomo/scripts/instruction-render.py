#!/usr/bin/env python3
# version: 0.42.3
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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# ADR-2: caller-supplied profiles dir — mirrors moc-discovery.py so the flattened
# instance layout resolves correctly (never derived inside profile_conventions).
DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"

from lib.doc_frontmatter import (  # noqa: E402
    FrontmatterMergeError,
    build_tomo_block,
    merge_tomo_block_into_markdown,
)
from lib.profile_conventions import resolve_conventions  # noqa: E402
from lib.kado_client import KadoClient, KadoError  # noqa: E402,F401
from lib.render_actions import (  # noqa: E402,F401
    _build_create_moc_actions,
    _build_delete_source_actions,
    _build_insert_under_marker_actions,
    _build_link_to_moc_actions,
    _build_move_note_actions,
    _dest_join,
    _disambiguate_filename,
    _load_tag_handler_groups,
    _marker_to_anchor_value,
    _validate_action_paths,
    _wikilink,
    build_actions,
    build_garden_audit_actions,
    emit_up_preservation_actions,
    extract_first_up_marker,
    group_id,
)
from lib.render_helpers import _moc_stem, _stem  # noqa: E402,F401
from lib.render_io import read_note_body, read_template  # noqa: E402,F401
from lib.render_md import (  # noqa: E402,F401
    SECTION_TITLES,
    _UPSTREAM_TYPES,
    _build_tomo_block_for_instructions,
    _compute_sha256,
    _md_section_for,
    _render_action_md,
    backfill_supporting_items_parents,
    render_instructions_md,
)
from lib.render_resolve import (  # noqa: E402,F401
    FOOTER_CALLOUTS,
    _emit_resolution_telemetry,
    _merge_new_section_links,
    _rewrite_existing_section_anchors,
    _serialize_new_sections,
    _strip_internal_link_fields,
    filter_missing_daily_notes,
    filter_missing_source_notes,
    filter_unappliable_relationships,
    resolve_section_names,
    resolve_target_moc_paths,
)
from lib.supporting_items import (  # noqa: E402
    parse_supporting_items as _parse_supporting_items,
    union_supporting_items as _union_supporting_items,  # noqa: F401 — re-exported for tests
)


# ──────────────────────────────────────────────────────────────────────────────
# Config loading (T1.5 — one load, all fields resolved up front)
# ──────────────────────────────────────────────────────────────────────────────

CONFIG_DEFAULTS = {
    "concepts.inbox": "100 Inbox/",
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": None,
    # Fallback set of callout names Tomo treats as editable when the user
    # hasn't run /explore-vault yet. Config wins when present.
    "callouts.editable": ["connect", "blocks", "anchor"],
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

    # Normalise callouts.editable — tolerate both the list form (legacy
    # /explore-vault output) and the dict form (vault-config-writer output).
    editable = resolved.get("callouts.editable")
    if isinstance(editable, dict):
        resolved["callouts.editable"] = list(editable.keys())
    elif isinstance(editable, list):
        resolved["callouts.editable"] = [str(x) for x in editable if x]
    else:
        resolved["callouts.editable"] = list(CONFIG_DEFAULTS["callouts.editable"])
    return resolved


# Re-export for backwards compatibility — the canonical implementation now
# lives in `lib/slugify.py` so moc-discovery.py can reuse it cleanly without
# the hyphenated-module import dance. F-43 Phase 2 T2.5 (slugify extraction).
from lib.slugify import slugify  # noqa: E402,F401  — re-exported for callers


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


def main() -> int:
    p = argparse.ArgumentParser(description="Render approved suggestions into note files.")
    p.add_argument("--suggestions", required=True, help="Path to parsed suggestions JSON")
    p.add_argument("--output-dir", required=True, help="Directory for rendered files")
    p.add_argument("--config", default="config/vault-config.yaml", help="vault-config.yaml path")
    # F-47 T2.3: upstream doc identity for the tomo: block + source_* cross-ref.
    p.add_argument(
        "--upstream-type",
        choices=_UPSTREAM_TYPES,
        default=None,
        help="Upstream doc type: suggestions | moc-proposal | suggestions-fan | garden-audit",
    )
    p.add_argument(
        "--upstream-path",
        default=None,
        help="Vault-relative path to the upstream doc (populates tomo.source_* field)",
    )
    p.add_argument(
        "--run-id",
        default=None,
        help="Pass-2 run ID (NOT the upstream doc's run_id — SDD §Implementation Gotchas)",
    )
    p.add_argument(
        "--upstream-body",
        default=None,
        help="Local path to cached upstream doc body (for SHA-256 checksum computation)",
    )
    p.add_argument(
        "--tag-handler-groups-dir",
        default="tomo-tmp/tag-handler-groups",
        help="Directory of tag-handler group-result JSONs (spec 024 T4.1). Each "
             "group whose group_id is approved in the suggestions doc becomes one "
             "insert_under_marker action. Default: cwd-relative "
             "tomo-tmp/tag-handler-groups (instance runtime); absent/empty → no "
             "such actions. Host/tests override.",
    )
    args = p.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.suggestions, encoding="utf-8") as f:
        suggestions = json.load(f)

    confirmed = suggestions.get("confirmed_items", [])
    daily_updates = suggestions.get("daily_updates", [])
    skipped = suggestions.get("skipped", [])
    # spec 024 T4.1: approved tag-handler group ids (from suggestion-parser) +
    # the group-result JSONs they map to. Either being empty means no
    # insert_under_marker actions are emitted.
    approved_tag_handler_group_ids = suggestions.get(
        "approved_tag_handler_group_ids", []
    )
    # Group ids the user opted out of source-deletion via "Keep source files".
    tag_handler_keep_source_group_ids = suggestions.get(
        "tag_handler_keep_source_group_ids", []
    )
    tag_handler_groups = _load_tag_handler_groups(args.tag_handler_groups_dir)

    cfg = load_config(args.config)
    inbox_path = cfg["concepts.inbox"]
    profile_name = cfg["profile"]
    conventions = resolve_conventions(
        profile_override=profile_name, profiles_dir=DEFAULT_PROFILES_DIR
    )

    # No confirmed items AND no daily updates AND no skipped items AND no
    # approved tag-handler groups → nothing to do.
    if (not confirmed and not daily_updates and not skipped
            and not approved_tag_handler_group_ids):
        print("instruction-render: no confirmed items, daily updates, skips, or tag-handler groups", file=sys.stderr)
        return 0

    client: KadoClient | None = None
    if confirmed:
        try:
            client = KadoClient()
        except KadoError as exc:
            print(f"FATAL: Cannot connect to Kado: {exc}", file=sys.stderr)
            return 2

    # #116: drop confirmed items whose source note is gone BEFORE anything
    # consumes the list — otherwise the renderer fabricates an empty stub and
    # build_actions emits a link_to_moc pointing at a note that never existed.
    confirmed, dropped_missing_source = filter_missing_source_notes(
        confirmed, client, inbox_path
    )
    if dropped_missing_source:
        print(
            f"  [skip] {len(dropped_missing_source)} confirmed item(s) skipped — "
            "source note missing, not fabricating a stub:",
            file=sys.stderr,
        )
        for item in dropped_missing_source:
            print(
                f"    • {item.get('id', '?')} → {item.get('source_path', '')}",
                file=sys.stderr,
            )

    # Back-fill parent_mocs on supporting items of create_moc items — BEFORE
    # the rendering loop reads parent_moc to compute {{up}}. Ensures atomic
    # notes that justify a new MOC actually get `up:: [[<new MOC>]]` written.
    backfill_supporting_items_parents(confirmed)

    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%Y-%m-%d_%H%M")

    manifest: list[dict] = []
    used_filenames: set[str] = set()
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
        audio_peer = item.get("audio_peer")
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

        # Build children token for MOC proposal items: callout-prefixed bullets.
        children_value = ""
        if "override_preserve_existing_up" in item:
            children_stems = _parse_supporting_items(item.get("supporting_items"))
            if children_stems:
                children_value = "\n".join(
                    f"> - [[{stem}]]" for stem in children_stems
                )

        tokens = {
            "title": title,
            "tags": tags_str,
            "up": up_value,
            "related": "",  # placeholder — populated by MOC creator post-MVP
            "body": body,
            "summary": summary or "",
            "children": children_value,
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

        # 4b. Stamp the tomo: lifecycle block so triage skips this staged note as
        # a fresh source until Hashi applies move_note/create_moc (which strips
        # the block). Fail-safe: a note whose frontmatter cannot take the block
        # is written unstamped — worst case is pre-fix re-ingestion, never a
        # corrupted note.
        try:
            rendered = merge_tomo_block_into_markdown(
                rendered,
                build_tomo_block("rendered-note", "pending-move", args.run_id),
            )
        except FrontmatterMergeError as exc:
            print(
                f"  [{item_id}] WARNING: tomo: block not stamped ({exc}); "
                "note may be re-ingested by triage before apply",
                file=sys.stderr,
            )

        # 5. Write rendered file — guard against same-slug collision (C5, ADR-7)
        slug = slugify(title)
        base_filename = f"{date_prefix}_{slug}.md"
        try:
            filename = _disambiguate_filename(base_filename, used_filenames)
        except ValueError as exc:
            print(f"  [{item_id}] ERROR: {exc}", file=sys.stderr)
            errors += 1
            continue
        used_filenames.add(filename)
        rendered_path = out_dir / filename
        rendered_path.write_text(rendered, encoding="utf-8")

        entry: dict = {
            "id": item_id,
            "action": item.get("action", "create_note"),
            "title": title,
            "source_path": source_path,
            "audio_peer": audio_peer,
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
        }
        # Carry override_preserve_existing_up when present (ConfirmedMOCProposal
        # path only — inbox-flow create_moc items do not set this field).
        # _build_up_preservation_actions uses its presence as a gate.
        if "override_preserve_existing_up" in item:
            entry["override_preserve_existing_up"] = item["override_preserve_existing_up"]
        manifest.append(entry)

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
    # garden-audit confirmed_items are semantic fix items (garden_check /
    # garden_action), NOT the suggestions manifest shape — assemble them with
    # the isolated builder so the suggestions/moc-proposal hot path stays
    # untouched (spec 030 SDD: "no new apply path… mirror /moc-propose").
    if args.upstream_type == "garden-audit":
        actions = build_garden_audit_actions(
            confirmed, parent_marker=conventions.parent_marker,
        )
    else:
        actions = build_actions(
            manifest, confirmed, daily_updates, skipped, cfg, kado_client=client,
            tag_handler_groups=tag_handler_groups,
            approved_tag_handler_group_ids=approved_tag_handler_group_ids,
            tag_handler_keep_source_group_ids=tag_handler_keep_source_group_ids,
            parent_marker=conventions.parent_marker,
            peer_marker=conventions.peer_marker,
        )

    # ── Resolve target_moc_path on link_to_moc actions via Kado ─────────
    # Best-effort; actions stay with `target_moc_path: null` if Kado is
    # unavailable or no match is found.
    resolved_paths = resolve_target_moc_paths(actions, client)
    if resolved_paths:
        print(f"  [resolve] target_moc_path populated for {resolved_paths} link_to_moc action(s)",
              file=sys.stderr)

    # ── Resolve anchor.value by reading each target MOC ─────────────────
    # For each link_to_moc with a resolved target_moc_path, open the MOC via
    # Kado and capture the full first line of its first editable callout.
    # Actions targeting not-yet-existing MOCs (tier-1 in-set) stay null —
    # the create_moc template provides its own callout, which Tomo Hashi
    # can discover at execute time.
    resolved_sections = resolve_section_names(actions, client, cfg["callouts.editable"])
    if resolved_sections:
        print(f"  [resolve] anchor.value populated for {resolved_sections} link_to_moc action(s)",
              file=sys.stderr)

    # ── Merge same-section links (#70) ───────────────────────────────────
    # Collapse link_to_moc actions sharing (target_moc, new_section) into one
    # bullet list BEFORE serialization, so two notes in the same new section
    # yield one heading, not duplicate `## <section>` headings.
    merged_sections = _merge_new_section_links(actions)
    if merged_sections:
        print(f"  [render] {merged_sections} duplicate new-section link(s) merged",
              file=sys.stderr)

    # ── Rewrite new_section → existing-heading anchor (#73) ───────────────
    # Before serializing a fresh `## <name>`, check the live MOC: if a heading
    # with that name already exists (re-run, cross-run, or LLM proposing an
    # existing name), anchor under it instead of emitting a duplicate heading.
    rewritten_sections = _rewrite_existing_section_anchors(actions, client)
    if rewritten_sections:
        print(f"  [render] {rewritten_sections} new-section link(s) rewritten to existing heading",
              file=sys.stderr)

    # ── Serialize new-section headings (T5.2 / ADR-3) ────────────────────
    # Build line_to_add from anchor.new_section for ALL link_to_moc actions
    # (both honored Pass-1 anchors and heuristic-resolved ones). Runs here so
    # both paths are covered exactly once before the JSON/MD writes.
    serialized_sections = _serialize_new_sections(actions)
    if serialized_sections:
        print(f"  [render] new-section heading serialized for {serialized_sections} link_to_moc action(s)",
              file=sys.stderr)

    # ── T7.1: Metadata-only four-tier resolution telemetry ───────────────
    # Emits ONE tagged stderr line with per-tier counts and MOC paths.
    # Privacy (Constitution L2): no heading text or note content — metadata only.
    _emit_resolution_telemetry(actions)

    # ── Strip Tomo-internal link_to_moc fields before the wire (#68/#64) ──
    stripped_internal = _strip_internal_link_fields(actions)
    if stripped_internal:
        print(f"  [render] {stripped_internal} internal link_to_moc field(s) stripped before wire",
              file=sys.stderr)

    # ── Drop daily-note actions whose target daily note doesn't exist ────
    # Hashi modifies, never creates, a daily note (#37/I38). Skip unappliable
    # daily-note actions and surface them rather than emit a failing action.
    actions, skipped_daily = filter_missing_daily_notes(actions, client)
    if skipped_daily:
        print(
            f"  [skip] {len(skipped_daily)} daily-note action(s) skipped — "
            "target daily note does not exist (Hashi cannot create it):",
            file=sys.stderr,
        )
        for a in skipped_daily:
            print(f"    • {a.get('id')} {a.get('action')} → {a.get('daily_note_path')}",
                  file=sys.stderr)

    # ── Drop add_relationship sentinels with an error (child-missing / ──────
    # non-markdown-asset). Hashi's additionalProperties:false wire schema has
    # no `error` field — a single error-bearing action causes Hashi to reject
    # the ENTIRE instruction set. Filter here and surface to the user.
    actions, skipped_rel = filter_unappliable_relationships(actions)
    if skipped_rel:
        print(
            f"  [skip] {len(skipped_rel)} add_relationship action(s) skipped — "
            "child note missing or non-markdown (cannot add up-link):",
            file=sys.stderr,
        )
        for a in skipped_rel:
            print(
                f"    • {a.get('id')} {a.get('action')} → {a.get('target_moc_path')} "
                f"[{a.get('error')}]",
                file=sys.stderr,
            )

    # ── Path Shape Contract guard (Hashi handoff 2026-04-26) ─────────────
    # Catch non-conforming paths before they reach the JSON. Hashi fails
    # closed on these with non-actionable error messages — catching upstream
    # surfaces the renderer-level cause directly.
    path_violations = _validate_action_paths(actions)
    if path_violations:
        print(
            "instruction-render: aborting — path-shape violations "
            f"({len(path_violations)}):",
            file=sys.stderr,
        )
        for v in path_violations:
            print(f"  • {v}", file=sys.stderr)
        return 2

    # ── Write instructions.json (T1.3) ───────────────────────────────────
    generated_iso = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_suggestions = _stem(args.suggestions)
    tomo_version = os.environ.get("TOMO_VERSION")
    # md_peer: explicit link back to the human-review .md sibling. Kokoro
    # 2026-04-23 review requested this over the implicit "same folder +
    # matching stem" convention — deterministic linkage on the consumer
    # side, clearer failure mode if the user later renames the .md.
    md_peer_stem = f"{date_prefix}_instructions"
    # Build the tomo: block once and carry it in the machine doc too (#74):
    # Hashi ≥ v0.11.0 accepts an optional top-level `tomo` object (handoff
    # 2026-06-20) and ignores it for execution, so the .json is self-describing
    # (state + sources) — matching the .md frontmatter. Omitted entirely when no
    # run_id is available (never emitted as null — schema types it as object).
    instructions_tomo_block = _build_tomo_block_for_instructions({
        "upstream_type": args.upstream_type,
        "upstream_path": args.upstream_path,
        "upstream_body_path": args.upstream_body,
        "run_id": args.run_id,
    })
    instructions_doc = {
        "schema_version": "2",
        "type": "tomo-instructions",
        "source_suggestions": source_suggestions,
        "generated": generated_iso,
        "profile": profile_name,
        "tomo_version": tomo_version,
        "action_count": len(actions),
        "md_peer": md_peer_stem,
        "actions": actions,
    }
    if instructions_tomo_block is not None:
        instructions_doc["tomo"] = instructions_tomo_block
    # Record daily-note actions dropped as unappliable (target daily note
    # missing) so instructions-diff can reconcile expected vs actual instead of
    # reading a legitimate drop as a coverage gap. Metadata only (Constitution
    # L2): action/date/path, never content. Nested under the permissive `tomo`
    # block — Tomo-owned, Hashi ignores it.
    if skipped_daily:
        tomo_block = instructions_doc.get("tomo")
        if tomo_block is None:
            tomo_block = {}
            instructions_doc["tomo"] = tomo_block
        tomo_block["skipped_daily"] = [
            {
                "action": a.get("action"),
                "date": a.get("date"),
                "daily_note_path": a.get("daily_note_path"),
            }
            for a in skipped_daily
        ]
    instructions_json_path = out_dir / "instructions.json"
    instructions_json_path.write_text(
        json.dumps(instructions_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Render instructions.md (T1.4) ────────────────────────────────────
    md = render_instructions_md(
        actions,
        {
            # F-47 T2.3: new fields drive the tomo: block + source_* cross-ref.
            "upstream_type": args.upstream_type,
            "upstream_path": args.upstream_path,
            "upstream_body_path": args.upstream_body,
            "run_id": args.run_id,
            "generated": generated_iso,
            "profile": profile_name,
            "tomo_version": tomo_version,
            "skipped_daily": skipped_daily,
            "skipped_rel": skipped_rel,
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
