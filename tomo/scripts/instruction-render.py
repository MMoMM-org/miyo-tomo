#!/usr/bin/env python3
# version: 0.37.0
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

from lib.doc_frontmatter import (  # noqa: E402
    FrontmatterMergeError,
    build_tomo_block,
    merge_tomo_block_into_markdown,
)
from lib.kado_client import KadoClient, KadoError  # noqa: E402
from lib.obsidian_filename import sanitize_stem  # noqa: E402
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
    filter_unappliable_relationships,
    resolve_section_names,
    resolve_target_moc_paths,
)
from lib.supporting_items import (  # noqa: E402
    parse_supporting_items as _parse_supporting_items,
    union_supporting_items as _union_supporting_items,
)

# tag-handler-group.py is a hyphenated top-level script (not a lib module); load
# it via importlib for the stable group_id slug (spec 024 T4.1). SCRIPT_DIR is
# already on sys.path (inserted above).
import importlib.util as _ilu  # noqa: E402

_thg_spec = _ilu.spec_from_file_location(
    "tag_handler_group", str(SCRIPT_DIR / "tag-handler-group.py")
)
_thg_mod = _ilu.module_from_spec(_thg_spec)
sys.modules["tag_handler_group"] = _thg_mod
_thg_spec.loader.exec_module(_thg_mod)
group_id = _thg_mod.group_id  # noqa: E305


# ──────────────────────────────────────────────────────────────────────────────
# Config loading (T1.5 — one load, all fields resolved up front)
# ──────────────────────────────────────────────────────────────────────────────

CONFIG_DEFAULTS = {
    "concepts.inbox": "100 Inbox/",
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


# ──────────────────────────────────────────────────────────────────────────────
# Action building (T1.1)
# ──────────────────────────────────────────────────────────────────────────────

def _next_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"I{counter[0]:02d}"


def _inbox_join(inbox: str, basename: str) -> str:
    """Join inbox path + basename, normalising the trailing slash."""
    return f"{(inbox or '').rstrip('/')}/{basename}"


# Obsidian-resolvable extensions seen in vault paths derived from wikilinks.
# Used by `_ensure_md_extension` to discriminate a real file extension
# (`Voice.m4a`, `Notes.html`) from a dotted note name (`Foo.Bar`,
# `2026-04-29.draft`). Obsidian allows dots in note titles, so "any dot
# means extension" is wrong — match against this allowlist instead.
_KNOWN_FILE_EXTENSIONS = frozenset({
    "md",
    "m4a", "mp3", "wav", "flac", "ogg", "aac", "opus",
    "mp4", "mov", "webm", "mkv", "avi",
    "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp",
    "pdf", "html", "txt", "csv", "json", "yaml", "yml",
    "zip",
})


def _ensure_md_extension(path: str | None) -> str | None:
    """Append `.md` to a wikilink-derived path unless it already names a file.

    Wikilink-derived paths come in three shapes:
      1. bare stem (`FooBar`)            — atomic note  → append `.md`
      2. dotted note name (`Foo.Bar`)    — atomic note  → append `.md`
      3. file with extension (`X.m4a`,
         `Y.html`, `Z.md`)               — leave alone

    The discriminator is the suffix after the basename's last dot: if it is
    ≤4 chars and matches a known Obsidian-resolvable extension, treat as a
    real file (case 3); otherwise it is part of a dotted note name and `.md`
    must be appended (case 1 or 2). Mirrors Obsidian's wikilink semantics —
    `[[FooBar]]` resolves to `FooBar.md`, `[[FooBar.m4a]]` resolves to the
    literal media file.

    Hashi consumes paths verbatim (no resolution), so the JSON `source_path`
    must equal the `.md` peer's wikilink target byte-for-byte. See handoff
    `_inbox/from-hashi/2026-04-29_hashi-to-tomo_audio-peer-path-emission.md`.
    """
    if not path:
        return path
    basename = path.rsplit("/", 1)[-1]
    last_dot = basename.rfind(".")
    if last_dot < 0:
        return path + ".md"
    suffix = basename[last_dot + 1:]
    if len(suffix) <= 4 and suffix.lower() in _KNOWN_FILE_EXTENSIONS:
        return path
    return path + ".md"


# Path-shape contract (Hashi-driven, 2026-04-26 handoff): every path field
# emitted into instructions.json must be vault-relative, absolute within the
# vault, forward-slash separated, control-char free, and free of plugin
# aliases. Hashi's executor refuses non-conforming paths with cryptic
# `Path escapes vault root` / `path-symlink-escape` errors; catching them at
# emit time produces actionable Tomo-side diagnostics instead.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

# Matches the first ``up:: [[Target]]`` line in a note body (Rule 4.x).
# MULTILINE so ``^`` anchors to each line start.  Non-greedy ``(.+?)`` stops
# at the first ``]]`` to avoid over-matching when the target contains brackets.
_UP_MARKER_RE = re.compile(r"^[\s>\-]*up::\s*\[\[(.+?)\]\]", re.MULTILINE)
_RELATED_MARKER_RE = re.compile(r"^[\s>\-]*related::\s*(.*)", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
# Extracts the callout type from a stripped (no leading `> `) callout opening


def _extract_existing_related(content: str) -> list[str]:
    """Extract existing related:: wikilink targets from note content."""
    m = _RELATED_MARKER_RE.search(content)
    if not m:
        return []
    return [wl.group(1).strip() for wl in _WIKILINK_RE.finditer(m.group(1))]


def _aggregate_related_actions(
    actions: list[dict], kado_client,
) -> list[dict]:
    """Merge related:: actions per target note with existing vault values.

    Per contract (docs/instructions-json.md §882-886), Tomo reads the
    existing related:: line and emits one combined action per target.
    """
    if kado_client is None:
        return actions

    # Collect related:: actions grouped by target_moc_path
    related_by_target: dict[str, list[dict]] = {}
    non_related: list[dict] = []
    for a in actions:
        if a.get("action") == "add_relationship" and a.get("marker") == "related::":
            path = a["target_moc_path"]
            related_by_target.setdefault(path, []).append(a)
        else:
            non_related.append(a)

    if not related_by_target:
        return actions

    merged: list[dict] = []
    for path, rel_actions in related_by_target.items():
        # Read existing related:: from vault
        try:
            note = kado_client.read_note(path)
            content = note.get("content", "") if isinstance(note, dict) else ""
            existing = _extract_existing_related(content)
        except Exception:
            existing = []

        # Collect new stems from actions
        new_stems = []
        for a in rel_actions:
            for wl in _WIKILINK_RE.finditer(a.get("line", "")):
                stem = wl.group(1).strip()
                if stem and stem not in existing and stem not in new_stems:
                    new_stems.append(stem)

        all_stems = existing + new_stems
        if not all_stems:
            continue

        combined_line = "related:: " + ", ".join(f"[[{s}]]" for s in all_stems)
        # Keep the first action as template, update line
        merged_action = dict(rel_actions[0])
        merged_action["line"] = combined_line
        merged.append(merged_action)

    # Reassemble: non-related actions + merged related actions (in original order)
    result = []
    seen_targets: set[str] = set()
    for a in actions:
        if a.get("action") == "add_relationship" and a.get("marker") == "related::":
            path = a["target_moc_path"]
            if path not in seen_targets:
                seen_targets.add(path)
                # Find the merged action for this target
                for m in merged:
                    if m["target_moc_path"] == path:
                        result.append(m)
                        break
        else:
            result.append(a)
    return result


# Optional path fields per action kind. Required path fields are derived from
# the JSON Schema (see tomo/schemas/instructions.schema.json) — this map only
# names additionally permitted nullable path fields so the validator skips
# them when null/missing but still validates non-null values.
_OPTIONAL_PATH_FIELDS = {
    "move_note": ("source_inbox_item",),
    "link_to_moc": ("target_moc_path",),
    "skip": ("source_path",),
}

_REQUIRED_PATH_FIELDS = {
    "create_moc": ("source", "destination"),
    "move_note": ("source", "destination"),
    "update_tracker": ("daily_note_path",),
    "update_log_entry": ("daily_note_path",),
    "update_log_link": ("daily_note_path",),
    "delete_source": ("source_path",),
    "add_relationship": ("target_moc_path",),
    "insert_under_marker": ("target_path",),
}


# ──────────────────────────────────────────────────────────────────────────────
# Rule 4.x: per-child existing-up:: preservation (F-43 T4.2)
# ──────────────────────────────────────────────────────────────────────────────


def extract_first_up_marker(content: str) -> str | None:
    """Return the first ``up:: [[Target]]`` target from note content, or None.

    Searches the note body (frontmatter stripped) for the first line that
    matches the up:: wikilink pattern.  Frontmatter is excluded to prevent
    false positives when a user's YAML frontmatter contains an ``up::`` key.

    Stripping logic: if content begins with ``---\n`` and contains a closing
    ``---`` on its own line, the body starts after that closing fence.
    Otherwise the full content is searched.

    This is a self-contained inline-only `up::` extractor for the renderer.
    NOTE (spec 021 T2.2): moc-discovery and moc-tree-builder migrated their
    `up` resolution to lib/up_parse.parse_up_from_content (dual-up: inline +
    frontmatter). instruction-render was intentionally NOT retrofitted in spec
    021 — it deliberately strips frontmatter and matches inline `up::` ONLY
    (see test_extract_first_up_marker_ignores_frontmatter_up). Migrating it to
    the dual-up SSoT is a separate change, out of T2.2 scope.

    Multiple ``up::`` lines on the same note → only the first is returned;
    callers are responsible for warning when that case is detected.
    """
    if not content:
        return None
    # Strip YAML frontmatter before regex search to avoid false positives.
    body = content
    if content.startswith("---\n"):
        closing = content.find("\n---", 4)
        if closing != -1:
            body = content[closing + 4:]  # skip past closing ---\n
    match = _UP_MARKER_RE.search(body)
    if not match:
        return None
    target = match.group(1).strip()
    return target or None


def _make_add_rel(
    counter: list[int],
    target_note_path: str,
    marker: str,
    target_stem: str,
) -> dict:
    """Build a single add_relationship action dict.

    ``target_moc_path`` holds the child note's vault path (the note being
    modified).  ``marker`` is the dataview field (``up::`` or ``related::``).
    ``line`` is the pre-formatted replacement line that Hashi will write.
    """
    return {
        "id": _next_id(counter),
        "action": "add_relationship",
        "target_moc_path": target_note_path,
        "marker": marker,
        "line": f"{marker} [[{target_stem}]]",
        "source_note_title": None,
        "applied": None,
    }


def emit_up_preservation_actions(
    child_stem: str,
    new_moc_stem: str,
    override_flag: bool,
    kado_client,
    counter: list[int],
) -> list[dict]:
    """For one child, emit 1 or 2 add_relationship actions per Rule 4.x.

    Implements SDD Example 1 verbatim.  Called once per accepted child of a
    ConfirmedMOCProposal.  ``override_flag`` is the group-level up::-handling
    override toggle from the proposal doc.

    Rules:
      4.1 / 4.4 — no existing up:: → up:: <newMOC> (Override is a no-op here)
      4.2        — unchecked Override + valid existing up:: <X> →
                   up:: <newMOC> + related:: <X>
      4.5        — checked Override + valid existing up:: <X> →
                   related:: <newMOC> (existing up:: kept, not touched)
      4.3        — unchecked Override + broken existing up:: →
                   up:: <newMOC> only (broken target silently dropped)

    Edge cases:
      - Self-link: if existing_up_target == new_moc_stem → no actions emitted.
      - Child missing: KadoError(NOT_FOUND) on resolve → one action with
        applied=False and error="child-missing"; does NOT raise.
      - Multiple up:: lines: extract_first_up_marker returns the first; callers
        may log a warning for multi-up:: notes.
    """
    try:
        child_path = kado_client.resolve_stem_to_path(child_stem)
    except KadoError:
        child_path = None

    if child_path is None:
        return [{
            "id": _next_id(counter),
            "action": "add_relationship",
            "target_moc_path": child_stem,
            "marker": "up::",
            "line": f"up:: [[{new_moc_stem}]]",
            "applied": False,
            "error": "child-missing",
        }]

    if not child_path.endswith(".md"):
        print(
            f"  [warn] {child_stem!r} resolved to non-markdown: {child_path} — skipping",
            file=sys.stderr,
        )
        return [{
            "id": _next_id(counter),
            "action": "add_relationship",
            "target_moc_path": child_path,
            "marker": "up::",
            "line": f"up:: [[{new_moc_stem}]]",
            "applied": False,
            "error": "non-markdown-asset",
        }]

    note = kado_client.read_note(child_path)
    content = note.get("content", "") if isinstance(note, dict) else ""
    existing_up_target = extract_first_up_marker(content)

    actions: list[dict] = []

    if existing_up_target is None:
        if override_flag:
            # Override checked + no existing up:: → related:: (user chose related for this MOC)
            actions.append(_make_add_rel(counter, child_path, "related::", new_moc_stem))
        else:
            # No existing up:: + no override → up:: (new MOC becomes primary parent)
            actions.append(_make_add_rel(counter, child_path, "up::", new_moc_stem))
    elif existing_up_target == new_moc_stem:
        # Self-link guard: existing up:: already points to the new MOC → no-op
        pass
    else:
        # existing_up_target is a stem — resolve to verify it exists
        old_target_path = kado_client.resolve_stem_to_path(existing_up_target)
        if old_target_path:
            if override_flag:
                # Rule 4.5 — keep existing up::, new MOC becomes related::
                actions.append(_make_add_rel(counter, child_path, "related::", new_moc_stem))
            else:
                # Rule 4.2 — new MOC becomes up::, existing target moves to related::
                actions.append(_make_add_rel(counter, child_path, "up::", new_moc_stem))
                actions.append(_make_add_rel(counter, child_path, "related::", existing_up_target))
        else:
            # Rule 4.3 — broken existing up:: (target not found); just set new up::
            actions.append(_make_add_rel(counter, child_path, "up::", new_moc_stem))

    return actions


def _check_path_shape(value: str) -> str | None:
    """Return None if `value` conforms to the Path Shape Contract, else the
    first violation message."""
    if value.startswith("/"):
        return "leading-slash absolute path (must be vault-relative)"
    if value.startswith("~"):
        return "home-tilde prefix (must be vault-relative)"
    if "\\" in value:
        return "backslash separator (must be forward-slash only)"
    if value.startswith("./"):
        return "relative './' prefix (must be absolute within vault)"
    parts = value.split("/")
    if any(p == ".." for p in parts):
        return "'..' segment (must be absolute within vault)"
    if "{{" in value or "<%" in value:
        return "plugin alias / template syntax (must be a resolved path)"
    # Drive letter (e.g. 'C:/...') — covers Windows-style absolute paths.
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return "drive-letter absolute path (must be vault-relative)"
    if _CONTROL_CHARS_RE.search(value):
        return "control character (\\n, \\r, \\x00, etc.)"
    return None


def _validate_action_paths(actions: list[dict]) -> list[str]:
    """Validate every path field on every action against the Path Shape Contract.

    Returns a list of violation messages (one per offending field). Empty list
    means all paths conform. Caller is expected to abort on non-empty result.
    """
    violations: list[str] = []
    for action in actions:
        kind = action.get("action", "<unknown>")
        action_id = action.get("id", "<no-id>")
        for field in _REQUIRED_PATH_FIELDS.get(kind, ()):
            value = action.get(field)
            if not isinstance(value, str) or not value:
                violations.append(
                    f"{action_id} ({kind}): required path field '{field}' "
                    f"is missing or empty"
                )
                continue
            err = _check_path_shape(value)
            if err:
                violations.append(
                    f"{action_id} ({kind}): '{field}'={value!r} — {err}"
                )
        for field in _OPTIONAL_PATH_FIELDS.get(kind, ()):
            value = action.get(field)
            if value in (None, ""):
                continue
            if not isinstance(value, str):
                violations.append(
                    f"{action_id} ({kind}): optional path field '{field}' "
                    f"is not a string ({type(value).__name__})"
                )
                continue
            err = _check_path_shape(value)
            if err:
                violations.append(
                    f"{action_id} ({kind}): '{field}'={value!r} — {err}"
                )
    return violations


def _disambiguate_filename(base_filename: str, used_filenames: set[str]) -> str:
    """Return a filename that is not in *used_filenames*.

    When *base_filename* is not yet used, returns it unchanged (common case —
    CON-2 regression guarantee).  On collision, appends a stable ``_NN`` suffix
    (``_01``, ``_02``, …) in the order callers present collisions.  Raises
    ``ValueError`` if all suffixes up to ``_99`` are already taken.

    Args:
        base_filename: The derived filename, e.g. ``2026-06-11_0900_my-topic.md``.
        used_filenames: Set of filenames already claimed in this render run.
            The caller is responsible for adding the returned name to this set.

    Returns:
        A distinct filename (may equal *base_filename* when there is no collision).

    Raises:
        ValueError: When the collision cannot be resolved within 99 attempts.
    """
    assert base_filename.endswith(".md"), (
        f"_disambiguate_filename requires a .md filename, got: {base_filename!r}"
    )

    if base_filename not in used_filenames:
        return base_filename

    # Strip .md, append _NN, restore .md
    stem = base_filename[:-3]

    for i in range(1, 100):
        candidate = f"{stem}_{i:02d}.md"
        if candidate not in used_filenames:
            return candidate

    raise ValueError(
        f"filename collision guard exhausted for slug '{stem}' — "
        "all suffixes _01 through _99 are taken; cannot render without overwrite"
    )


def _dest_join(folder: str, title: str) -> str:
    """Join destination folder + Obsidian-safe title as filename (with .md)."""
    if not folder:
        folder = ""
    folder = folder.rstrip("/") + "/"
    # Obsidian allows Umlauts, em-dash etc. — no slug. Forbidden chars
    # (\ / : * ? " < > |) in the title would crash Hashi's rename/create, so
    # the filename stem is sanitised; the note's displayed title (frontmatter/H1)
    # keeps the original. Link targets are sanitised the same way (_wikilink).
    stem = title[:-3] if title.endswith(".md") else title
    return f"{folder}{sanitize_stem(stem)}.md"


def _wikilink(title: str) -> str:
    """Render an Obsidian wikilink whose target resolves to the safe filename.

    When the title contains Obsidian-forbidden chars the file is stored under
    a sanitised stem (see _dest_join), so the link must target that stem or it
    dangles. An alias preserves the original title as display text:
    ``[[safe-stem|Original: Title]]``. Titles already safe render as ``[[Title]]``.
    """
    stem = sanitize_stem(title)
    if stem != title:
        return f"[[{stem}|{title}]]"
    return f"[[{title}]]"


def _build_create_moc_actions(
    manifest: list[dict],
    inbox_path: str,
    counter: list[int],
) -> list[dict]:
    """Emit create_moc actions for rendered MOCs. MUST run before move_note and
    link_to_moc so IDs for new MOCs precede anything that links into them.
    """
    out: list[dict] = []
    by_dest: dict[str, dict] = {}
    for m in manifest:
        if m.get("action") != "create_moc":
            continue
        title = m.get("title", "")
        rendered = m.get("rendered_file", "")
        destination = _dest_join(m.get("destination", ""), title)
        # Defense-in-depth (#67): two approved proposals resolving to the same
        # destination would emit two create_moc; the second overwrites the first
        # on apply, dropping the first's children. The parser merges by Name
        # upstream; this guard ensures a duplicate can never reach Hashi even if
        # upstream misses it — union supporting_items into the survivor.
        existing = by_dest.get(destination)
        if existing is not None:
            existing["supporting_items"] = _union_supporting_items(
                existing.get("supporting_items"), m.get("supporting_items")
            ) or None
            continue
        action = {
            "id": _next_id(counter),
            "action": "create_moc",
            "source": _inbox_join(inbox_path, rendered) if rendered else "",
            "destination": destination,
            "title": title,
            "rendered_file": rendered,
            "parent_moc": _moc_stem(m.get("parent_moc")) or None,
            "template": m.get("template") or None,
            "tags": m.get("tags", []) or [],
            "supporting_items": m.get("supporting_items") or None,
        }
        by_dest[destination] = action
        out.append(action)
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
        # Append .md only for bare/dotted note names; preserve real
        # extensions (e.g. `.m4a` for audio sources kept as origin reference).
        origin = _ensure_md_extension(origin)
        # audio_peer is the companion audio file for voice transcripts.
        # Join a bare basename with inbox_path exactly as we do for origin,
        # but do NOT apply _ensure_md_extension — the .m4a must be preserved.
        audio_peer = m.get("audio_peer")
        if audio_peer and "/" not in audio_peer:
            audio_peer = _inbox_join(inbox_path, audio_peer)
        out.append({
            "id": _next_id(counter),
            "action": "move_note",
            "source": _inbox_join(inbox_path, rendered) if rendered else "",
            "destination": _dest_join(m.get("destination", ""), title),
            "title": title,
            "rendered_file": rendered,
            "source_inbox_item": origin,
            "audio_peer": audio_peer,
            "parent_mocs": [_moc_stem(x) for x in (m.get("parent_mocs") or []) if x],
            "tags": m.get("tags", []) or [],
        })
    return out


def _build_link_to_moc_actions(confirmed: list[dict], counter: list[int]) -> list[dict]:
    """Emit link_to_moc actions from two sources:

    1. Each confirmed item's parent_mocs[] — child-listing bullets on the
       parent MOC. The atomic note's own `up:: [[parent]]` line is written
       by the template renderer ({{up}} token), not as an instruction-set
       action.
    2. Each create_moc item's supporting_items — down-links FROM the new MOC
       TO each confirmed atomic note referenced by ID. Fills the gap where
       the suggestions doc cannot offer a future-MOC as a parent option when
       reviewing atomic items.

    Both passes emit content-bullet links into the target MOC. Default
    placement is "after" (the bullet lands below the matched callout, not
    inside its body — the standing contract with Hashi). resolve_section_names
    populates anchor.value via Kado read; if the target MOC has no editable
    callout it falls back to a heading anchor, and if it has none of those
    either the action lands with anchor.value=null.

    Dedup by (target_moc, line_to_add) so a parent_moc that happens to also
    appear in supporting_items isn't double-emitted.
    """
    id_index: dict[str, dict] = {it.get("id"): it for it in confirmed if it.get("id")}
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _find_candidate(item: dict, target_stem: str) -> dict | None:
        """Return the candidate_mocs[] entry whose path stem matches target_stem, or None."""
        for cand in item.get("candidate_mocs") or []:
            if _moc_stem(cand.get("path", "")) == target_stem:
                return cand
        return None

    def _emit(target_moc: str, source_title: str, anchor: dict | None = None) -> None:
        key = (target_moc, source_title)
        if not target_moc or not source_title or key in seen:
            return
        seen.add(key)
        # Internal-field lifetime: new_section / fit_confidence (and any future
        # alt_headings) live on the action from here until
        # _strip_internal_link_fields removes them — never on the wire.
        # Decompose the Pass-1 anchor: the instructions.schema.json `anchor`
        # object allows ONLY {type, value} (additionalProperties:false).
        # `placement` and `new_section` are TOP-LEVEL fields on link_to_moc,
        # not nested inside the anchor. Honor their values from the Pass-1
        # anchor but lift them out before writing. When no anchor is provided,
        # fall back to a null-callout so resolve_section_names can populate it.
        stamped_anchor = {
            "type": (anchor or {}).get("type", "callout"),
            "value": (anchor or {}).get("value"),
        }
        out.append({
            "id": _next_id(counter),
            "action": "link_to_moc",
            "target_moc": target_moc,
            "target_moc_path": None,
            # Default placement is "after" per the 2026-04-30 contract with
            # Hashi: content-bullet links land BELOW the matched callout, not
            # inside its body. The user's rule of thumb is "normally it is
            # always after". inside is reserved for the rare case where a
            # specific entry must be collected inside a callout's body — none
            # of today's emission paths produce that.
            "anchor": stamped_anchor,
            "placement": (anchor or {}).get("placement", "after"),
            # new_section lifted to top-level per instructions schema (T5.2/ADR-3).
            "new_section": (anchor or {}).get("new_section"),
            # fit_confidence lifted to top-level (parallel to new_section) so
            # _emit_resolution_telemetry can observe the per-placement score
            # (#64). Both are Tomo-internal and stripped before the wire — the
            # anchor itself stays {type, value} (anchor no-leak contract).
            "fit_confidence": (anchor or {}).get("fit_confidence"),
            # Wikilink target resolves to the (possibly sanitised) filename;
            # source_note_title carries the safe stem so every reference to a
            # forbidden-char note round-trips to the renamed file (#69).
            "line_to_add": f"- {_wikilink(source_title)}",
            "source_note_title": sanitize_stem(source_title),
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
            cand = _find_candidate(item, _moc_stem(parent))
            _emit(_moc_stem(parent), source_title, anchor=cand.get("anchor") if cand else None)

    # Pass 2 — supporting_items down-links: each new MOC pulls its approved
    # supporting atomic notes as children. Required because the suggestions
    # doc cannot offer a not-yet-created MOC as a parent option at review time.
    #
    # Two flows: suggestion flow (supporting_items are SNN IDs → id_index lookup)
    # vs MOC proposal flow (children baked into rendered MOC via {{children}} token,
    # no link_to_moc actions needed).
    # Gate: MOC proposal items carry override_preserve_existing_up field.
    for item in confirmed:
        if item.get("action") != "create_moc":
            continue
        if "override_preserve_existing_up" in item:
            continue  # MOC proposal: children baked into rendered body
        new_moc_title = item.get("title", "")
        if not new_moc_title:
            continue
        for sid in _parse_supporting_items(item.get("supporting_items")):
            sup = id_index.get(sid)
            if not sup or sup.get("action") == "create_moc":
                continue
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
    move_notes: list[dict],
    daily_updates: list[dict],
    skipped: list[dict],
    inbox_path: str,
    counter: list[int],
    tag_handler_groups: list[dict] | None = None,
    approved_tag_handler_group_ids: list[str] | None = None,
    keep_source_group_ids: list[str] | None = None,
) -> list[dict]:
    """Emit delete_source actions from four sources:

    1. `skipped[]` entries where the user explicitly checked "Delete source"
       (disposition == "delete_source").
    2. Daily-only items — source_stems that appear in accepted daily_updates
       but have no matching confirmed_item (content fully captured in the
       daily note, no atomic note will be created).
    3. move_note origins — for every move_note action whose corresponding
       confirmed item did NOT opt out via "Keep source files", emit a paired
       delete_source for the origin inbox item. Audio + transcript peer
       pairs are NOT included here (they're independent upstream artifacts);
       only the origin from which Tomo derived the rendered atomic note.
    4. Tag-handler group sources — for every APPROVED group not opted out via
       "Keep source files", one delete_source per `source_path`. The group's
       insert_under_marker (emitted earlier) copies the captures into the
       target note, so the inbox sources are now redundant. Parity with (3),
       but keyed by group_id rather than origin stem.
    """
    out: list[dict] = []
    confirmed_stems: set[str] = set()
    # expected_by_stem: count of approved atomics per origin stem (gate denominator).
    expected_by_stem: dict[str, int] = {}
    # keep_source_stems: stems where ANY confirmed item opts out of deletion.
    keep_source_stems: set[str] = set()
    for item in confirmed:
        sp = item.get("source_path")
        if sp:
            stem = _stem(sp)
            confirmed_stems.add(stem)
            expected_by_stem[stem] = expected_by_stem.get(stem, 0) + 1
            if item.get("keep_source"):
                keep_source_stems.add(stem)

    inbox = inbox_path.rstrip("/") + "/"

    # (1) Explicit user "Delete source" on skipped items
    for sk in skipped:
        if sk.get("disposition") != "delete_source":
            continue
        sp = sk.get("source_path") or ""
        if not sp:
            continue
        full = sp if "/" in sp else f"{inbox}{sp}"
        full = _ensure_md_extension(full)
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

    # (3) move_note origins — completion gate: emit one delete per origin stem
    # only after ALL expected atomics are represented in move_notes (OQ6).
    # Collect accepted daily stems for reason-string annotation (" + daily").
    daily_stems: set[str] = set()
    for day in daily_updates:
        for bucket in ("trackers", "log_entries", "log_links"):
            for entry in day.get(bucket, []) or []:
                if entry.get("accepted"):
                    s = _stem(entry.get("source_stem"))
                    if s:
                        daily_stems.add(s)

    # Group move_notes by origin stem.
    moves_by_origin: dict[str, list[dict]] = {}
    for mn in move_notes:
        if mn.get("action") != "move_note":
            continue
        origin = mn.get("source_inbox_item")
        if not origin:
            continue
        origin_stem = _stem(origin)
        bucket_list = moves_by_origin.setdefault(origin_stem, [])
        bucket_list.append(mn)

    for origin_stem, moves in moves_by_origin.items():
        if origin_stem in keep_source_stems:
            continue
        expected = expected_by_stem.get(origin_stem, 1)
        if len(moves) < expected:
            continue  # not all atomics rendered yet — defer (OQ6)
        origin_path = moves[0].get("source_inbox_item", "")
        n = len(moves)
        has_daily = origin_stem in daily_stems
        daily_suffix = " + daily" if has_daily else ""
        reason = f"Origin consumed by {n} atomic{'s' if n > 1 else ''}{daily_suffix}."
        out.append({
            "id": _next_id(counter),
            "action": "delete_source",
            "source_path": origin_path,
            "reason": reason,
        })
        # Paired audio peer delete — one delete per unique audio peer for this
        # origin stem. Normally 0 or 1 peer; set deduplicates the multi-atomic
        # case (two atomics from one transcript share the same peer path).
        # keep_source_stems and the gate both apply above, so arriving here
        # means both deletes are appropriate. Empty set → no audio delete (fail-safe).
        audio_peers = {mn.get("audio_peer") for mn in moves if mn.get("audio_peer")}
        for ap in sorted(audio_peers):
            out.append({
                "id": _next_id(counter),
                "action": "delete_source",
                "source_path": ap,
                "reason": "Audio peer of consumed origin.",
            })

    # (4) Tag-handler group sources — one delete per source_path of each
    # APPROVED group, unless the group opted out via "Keep source files".
    approved_groups = set(approved_tag_handler_group_ids or [])
    kept_groups = set(keep_source_group_ids or [])
    emitted: set[str] = {a["source_path"] for a in out}
    for group in (tag_handler_groups or []):
        gid = group_id(group)
        if gid not in approved_groups or gid in kept_groups:
            continue
        target = group.get("target_path") or ""
        handler = group.get("handler") or ""
        for sp in group.get("source_paths") or []:
            full = sp if "/" in sp else f"{inbox}{sp}"
            full = _ensure_md_extension(full)
            if full in emitted:
                continue
            emitted.add(full)
            out.append({
                "id": _next_id(counter),
                "action": "delete_source",
                "source_path": full,
                "reason": f"Source consolidated into {target} by {handler} handler.",
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
        sp = _ensure_md_extension(sp)
        out.append({
            "id": _next_id(counter),
            "action": "skip",
            "source_path": sp,
            "reason": "Skipped by user (kept in inbox).",
        })
    return out


def _marker_to_anchor_value(marker: str) -> str:
    """Strip a heading marker down to its anchor text (spec 024 T4.1).

    Hashi's `heading` anchor matches heading text WITHOUT the leading `#` run,
    so a config marker like ``## Captures`` must be normalised to ``Captures``.
    Strips the leading run of ``#`` and the single following space, then trims.
    A marker with no leading ``#`` is returned trimmed unchanged.
    """
    m = (marker or "").strip()
    stripped = m.lstrip("#")
    # Drop exactly the conventional single space after the #-run.
    if stripped.startswith(" "):
        stripped = stripped[1:]
    return stripped.strip()


def _load_tag_handler_groups(groups_dir: str | None) -> list[dict]:
    """Load all tag-handler group-result JSONs from `groups_dir`.

    Mirrors suggestions-reducer.collect_tag_handler_groups: returns [] when the
    dir is None, missing, or empty; skips unreadable/invalid files silently.
    """
    if not groups_dir:
        return []
    p = Path(groups_dir)
    if not p.exists() or not p.is_dir():
        return []
    groups: list[dict] = []
    for f in sorted(p.glob("*.json")):
        try:
            groups.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return groups


def _build_insert_under_marker_actions(
    groups: list[dict],
    approved_group_ids: list[str],
    counter: list[int],
) -> list[dict]:
    """Emit one insert_under_marker action per APPROVED tag-handler group (T4.1).

    A group is emitted only when its `group_id` is in `approved_group_ids` (the
    Pass-2 approval gate from suggestion-parser). A group not in the approved
    set produces NO instruction. The composed_block already carries the dated
    status block; it is inserted verbatim as `content` (append semantics live in
    Hashi's executor — Tomo just emits the instruction).

    Structured groups (output_format + resolved_anchor, spec 025 T5.1):
      When the group carries a resolved_anchor (produced by Phase 4), the anchor
      is passed through verbatim — type/value/placement from resolved_anchor,
      never reconstructed. For block anchors (table_row + newest_first), the
      blank-line prepend for placement="after" is SKIPPED: the content lands as
      the first data row directly after the separator, preserving table structure.

    Legacy groups (no output_format / no resolved_anchor):
      anchor = heading derived from marker via _marker_to_anchor_value;
      placement = group.placement (default "inside");
      content = composed_block, with a single blank-line prepend when
      placement="after" (top-of-section readability for heading anchors).
    """
    if not groups or not approved_group_ids:
        return []
    approved = set(approved_group_ids)
    out: list[dict] = []
    for group in groups:
        if group_id(group) not in approved:
            continue
        target_path = group.get("target_path")
        if not target_path:
            # Unresolved target (null) — never emit a path-less instruction.
            continue

        resolved_anchor = group.get("resolved_anchor")
        content = group.get("composed_block") or ""

        if resolved_anchor:
            # Structured path (spec 025): pass resolved_anchor through byte-exact.
            anchor = {
                "type": resolved_anchor["type"],
                "value": resolved_anchor["value"],
            }
            placement = resolved_anchor["placement"]
            # Block anchors (e.g. table header+separator) must NOT receive a
            # leading blank line — the content is the first data row and must
            # land immediately after the separator to keep the table valid.
            # Heading anchors with placement="after" keep the legacy prepend.
            if (
                placement == "after"
                and resolved_anchor["type"] != "block"
                and content
                and not content.startswith("\n")
            ):
                content = "\n" + content
        else:
            # Legacy path: derive heading anchor from the marker string.
            anchor = {
                "type": "heading",
                "value": _marker_to_anchor_value(group.get("marker") or ""),
            }
            placement = group.get("placement") or "inside"
            # placement="after" inserts content immediately after the heading
            # line; Hashi writes it verbatim with no padding, so guarantee one
            # blank line between the heading and the block (top-of-section).
            if placement == "after" and content and not content.startswith("\n"):
                content = "\n" + content

        out.append({
            "id": _next_id(counter),
            "action": "insert_under_marker",
            "target_path": target_path,
            "anchor": anchor,
            "placement": placement,
            "content": content,
        })
    return out


def _build_up_preservation_actions(
    manifest: list[dict],
    kado_client,
    counter: list[int],
) -> list[dict]:
    """Emit add_relationship actions for existing-up:: preservation on MOC children.

    Iterates create_moc manifest items that originate from a ConfirmedMOCProposal.
    The conservative gate: the item must carry BOTH ``supporting_items`` (the
    accepted-children stems, comma-joined) AND ``override_preserve_existing_up``
    (presence flag — value may be True or False).  Items that lack either field
    were produced by the regular inbox flow and are skipped.

    For each qualifying create_moc item, dispatches to
    ``emit_up_preservation_actions`` once per child stem parsed from
    ``supporting_items``.  Returned actions are appended in child order.

    Called by ``build_actions`` after create_moc but before link_to_moc so
    the up:: actions on the children are present in the ordered output.
    """
    if kado_client is None:
        return []
    out: list[dict] = []
    for m in manifest:
        if m.get("action") != "create_moc":
            continue
        if not m.get("supporting_items"):
            continue
        if "override_preserve_existing_up" not in m:
            # Inbox-flow create_moc items lack this field → skip preservation.
            continue
        new_moc_stem = m.get("title", "")
        override_flag = bool(m.get("override_preserve_existing_up", False))
        for child_stem in _parse_supporting_items(m.get("supporting_items")):
            out.extend(
                emit_up_preservation_actions(
                    child_stem, new_moc_stem, override_flag, kado_client, counter,
                )
            )
    return out


def build_actions(
    manifest: list[dict],
    confirmed: list[dict],
    daily_updates: list[dict],
    skipped: list[dict],
    cfg: dict,
    kado_client=None,
    tag_handler_groups: list[dict] | None = None,
    approved_tag_handler_group_ids: list[str] | None = None,
    tag_handler_keep_source_group_ids: list[str] | None = None,
) -> list[dict]:
    """Assemble the full ordered action list.

    Execution order matters: create_moc comes first because subsequent
    link_to_moc actions may target the newly-created MOCs (via supporting_items
    expansion). move_note follows, then all links (parent_mocs + supporting
    items), then daily updates, deletions, and skips.

    Emitted order:
      1. create_moc         — new MOCs must exist before anything links into them
      2. up_preservation    — per-child up:: / related:: on ConfirmedMOCProposal children
      3. move_note          — atomic notes
      4. link_to_moc        — parent_mocs up-links + supporting_items down-links
      5. update_tracker / update_log_entry / update_log_link
      6. insert_under_marker — approved tag-handler group blocks (spec 024 T4.1)
      7. delete_source      — incl. approved tag-handler group sources (after their insert)
      8. skip
    """
    counter = [0]
    inbox_path = cfg["concepts.inbox"]
    out: list[dict] = []
    out.extend(_build_create_moc_actions(manifest, inbox_path, counter))
    out.extend(_build_up_preservation_actions(manifest, kado_client, counter))
    move_notes = _build_move_note_actions(manifest, inbox_path, counter)
    out.extend(move_notes)
    out.extend(_build_link_to_moc_actions(confirmed, counter))
    out.extend(_build_daily_update_actions(daily_updates, cfg, counter))
    out.extend(_build_insert_under_marker_actions(
        tag_handler_groups or [], approved_tag_handler_group_ids or [], counter,
    ))
    out.extend(_build_delete_source_actions(
        confirmed, move_notes, daily_updates, skipped, inbox_path, counter,
        tag_handler_groups=tag_handler_groups or [],
        approved_tag_handler_group_ids=approved_tag_handler_group_ids or [],
        keep_source_group_ids=tag_handler_keep_source_group_ids or [],
    ))
    out.extend(_build_skip_actions(skipped, inbox_path, counter))
    # Aggregate related:: actions per target note: read existing related::,
    # merge with all new related:: links, emit one action per target with
    # the combined line. Per contract (docs/instructions-json.md §882-886),
    # multi-link aggregation is done Tomo-side before emission.
    out = _aggregate_related_actions(out, kado_client)

    # Stamp the per-action applied flag. Tomo Hashi (the consumer) flips this
    # to true on successful execution; Tomo only ever emits false. See
    # docs/instructions-json.md.
    for a in out:
        a["applied"] = False
    return out



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
        help="Upstream doc type: suggestions | moc-proposal | suggestions-fan",
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
    actions = build_actions(
        manifest, confirmed, daily_updates, skipped, cfg, kado_client=client,
        tag_handler_groups=tag_handler_groups,
        approved_tag_handler_group_ids=approved_tag_handler_group_ids,
        tag_handler_keep_source_group_ids=tag_handler_keep_source_group_ids,
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
