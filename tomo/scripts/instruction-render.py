#!/usr/bin/env python3
# version: 0.22.0
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

from lib.doc_frontmatter import build_tomo_block  # noqa: E402
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
    "move_note": ("origin_inbox_item",),
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
        # Append .md only for bare/dotted note names; preserve real
        # extensions (e.g. `.m4a` for audio sources kept as origin reference).
        origin = _ensure_md_extension(origin)
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


def _parse_supporting_items(raw: str | list | None) -> list[str]:
    """Parse supporting_items into a list of stems.

    Accepts two formats:
      - list: ["Thought Collisions", "Map of Content"] (moc-proposal-parser)
      - str:  "S02, S06, S12" (suggestion-parser, SNN IDs only)
    """
    if not raw:
        return []
    if isinstance(raw, list):
        return [s.strip() for s in raw if isinstance(s, str) and s.strip()]
    s = raw.strip().strip("[](){}")
    out: list[str] = []
    for tok in s.split(","):
        tok = tok.strip().strip("[]()").lstrip("#")
        if tok:
            out.append(tok)
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

    Both passes emit content-bullet links into the target MOC's content
    callout (anchor.type=callout, placement=inside). resolve_anchors
    populates anchor.value via Kado read; if the target MOC has no editable
    callout, the action lands with anchor.value=null (Hashi reports a
    runtime error in that case).

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
            # Default placement is "after" per the 2026-04-30 contract with
            # Hashi: content-bullet links land BELOW the matched callout, not
            # inside its body. The user's rule of thumb is "normally it is
            # always after". inside is reserved for the rare case where a
            # specific entry must be collected inside a callout's body — none
            # of today's emission paths produce that.
            "anchor": {"type": "callout", "value": None},
            "placement": "after",
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
) -> list[dict]:
    """Emit delete_source actions from three sources:

    1. `skipped[]` entries where the user explicitly checked "Delete source"
       (disposition == "delete_source").
    2. Daily-only items — source_stems that appear in accepted daily_updates
       but have no matching confirmed_item (content fully captured in the
       daily note, no atomic note will be created).
    3. move_note origins — for every move_note action whose corresponding
       confirmed item did NOT opt out via "Keep origin", emit a paired
       delete_source for the origin inbox item. Audio + transcript peer
       pairs are NOT included here (they're independent upstream artifacts);
       only the origin from which Tomo derived the rendered atomic note.
    """
    out: list[dict] = []
    confirmed_stems: set[str] = set()
    # expected_by_stem: count of approved atomics per origin stem (gate denominator).
    expected_by_stem: dict[str, int] = {}
    # keep_origin_stems: stems where ANY confirmed item opts out of deletion.
    keep_origin_stems: set[str] = set()
    for item in confirmed:
        sp = item.get("source_path")
        if sp:
            stem = _stem(sp)
            confirmed_stems.add(stem)
            expected_by_stem[stem] = expected_by_stem.get(stem, 0) + 1
            if item.get("keep_origin"):
                keep_origin_stems.add(stem)

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
        origin = mn.get("origin_inbox_item")
        if not origin:
            continue
        origin_stem = _stem(origin)
        bucket_list = moves_by_origin.setdefault(origin_stem, [])
        bucket_list.append(mn)

    for origin_stem, moves in moves_by_origin.items():
        if origin_stem in keep_origin_stems:
            continue
        expected = expected_by_stem.get(origin_stem, 1)
        if len(moves) < expected:
            continue  # not all atomics rendered yet — defer (OQ6)
        origin_path = moves[0].get("origin_inbox_item", "")
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
      6. delete_source
      7. skip
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
    out.extend(_build_delete_source_actions(
        confirmed, move_notes, daily_updates, skipped, inbox_path, counter,
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
    if kind in ("link_to_moc", "add_relationship"):
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


# Known upstream doc types for the --upstream-type CLI flag.
# T1.3 (XDD-018): source_* kwargs replaced by sources list in build_tomo_block.
_UPSTREAM_TYPES: list[str] = ["suggestions", "moc-proposal", "suggestions-fan"]


def _compute_sha256(file_path: str) -> str | None:
    """Compute SHA-256 checksum of a file's text contents.

    Returns 'sha256:<hex>' or None on read error. Reads as UTF-8 to match
    how vault docs are stored and transmitted.
    """
    import hashlib

    try:
        content = Path(file_path).read_text(encoding="utf-8")
        return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    except (FileNotFoundError, OSError):
        return None


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


# Footer-marker callouts: content sections live BEFORE the first of these.
# Used to anchor a new section ahead of the MOC footer (#28 / F-36). Mirrors
# the LYT MOC template footer (docs/XDD/reference/tier-3/lyt-moc/section-placement.md).
# TODO F-55: make this profile-configurable rather than a hardcoded set.
FOOTER_CALLOUTS = {"video", "calendar", "puzzle", "compass"}

# Heading for a brand-new content section when a MOC has neither an editable
# callout nor a content heading to anchor on (#28 / F-36). Matches the standard
# template's primary editable section.
DEFAULT_NEW_SECTION_TITLE = "Key Concepts"


def resolve_section_names(actions: list[dict], client, editable_callouts: list[str]) -> int:
    """Best-effort: resolve the insertion anchor on callout-typed link_to_moc
    actions by reading the target MOC. Three-tier anchor resolution per action:

      1. Editable callout — the highest-priority editable callout (config-driven,
         scored blocks > other > connect). Anchor stays type=callout.
      2. Content heading (#29 / F-30) — when the MOC has no editable callout,
         fall back to a content H2–H6 heading before the footer. Rewrites
         anchor.type to "heading" and placement to "after" (Hashi has no
         "inside" for headings).
      3. New section before footer (#28 / F-36) — when neither exists, anchor on
         the first footer-marker callout with placement="before" and prepend a
         "## <section>" block to line_to_add, so applying inserts a fresh
         content section ahead of the footer.

    Tiers are evaluated against the live MOC first, then (for not-yet-existing
    in-set MOCs) against the create_moc's `template` body — same rules apply.

    Function name retained for import stability. Leaves the anchor unresolved
    (action emitted as-is) when:
      - client is None (offline / test mode) or editable_callouts is empty
      - target_moc_path is null
      - neither the MOC nor its template yields a callout, heading, or footer
      - Kado read fails for both the MOC and (where applicable) the template

    Returns the count of actions resolved.
    """
    if client is None or not editable_callouts:
        return 0
    import re
    editable_set = {name for name in editable_callouts if name}
    callout_re = re.compile(r"^>\s*\[!([A-Za-z][A-Za-z0-9_-]*)\][+-]?.*$")
    heading_re = re.compile(r"^(#{2,6})\s+(.+?)\s*$")

    # `connect` is conventionally the navigation callout (up:: / related::),
    # not where content-note bullets belong. Drop it to the back of the line:
    # prefer `blocks` (Key Concepts) → any other editable → connect as last
    # resort.
    def _score(name: str) -> int:
        if name == "blocks":
            return 3
        if name == "connect":
            return 1
        return 2

    def _callout_name(line: str) -> str | None:
        m = callout_re.match(line)
        return m.group(1) if m else None

    def _strip_prefix(line: str) -> str:
        s = line.lstrip()
        if s.startswith(">"):
            s = s[1:].lstrip()
        return s

    def _footer_index(lines: list[str]) -> int:
        """Line index of the first footer-marker callout, or len(lines)."""
        for i, raw in enumerate(lines):
            name = _callout_name(raw.rstrip())
            if name and name in FOOTER_CALLOUTS:
                return i
        return len(lines)

    def _pick_editable_callout(content: str) -> str | None:
        """Scan content for editable callouts and return the highest-priority
        one's full first line (sans leading `> `). Used for both live MOC
        bodies and template bodies — same scoring rules apply."""
        candidates: list[tuple[int, str]] = []
        for raw in content.splitlines():
            line = raw.rstrip()
            name = _callout_name(line)
            if not name or name not in editable_set:
                continue
            candidates.append((_score(name), _strip_prefix(line)))
        if not candidates:
            return None
        # Highest score wins; ties resolved by first occurrence (stable).
        return max(enumerate(candidates), key=lambda x: (x[1][0], -x[0]))[1][1]

    def _pick_content_heading(content: str) -> str | None:
        """First content H2–H6 heading before the footer; prefer one that reads
        like a content section. Returns the heading text (sans leading #)."""
        lines = content.splitlines()
        cutoff = _footer_index(lines)
        headings = [
            m.group(2).strip()
            for raw in lines[:cutoff]
            if (m := heading_re.match(raw.rstrip()))
        ]
        if not headings:
            return None
        preferred = {"key concepts", "concepts", "notes"}
        for h in headings:
            if h.lower() in preferred:
                return h
        return headings[0]

    def _find_footer_callout(content: str) -> str | None:
        """Full first line (sans `> `) of the first footer-marker callout."""
        for raw in content.splitlines():
            line = raw.rstrip()
            name = _callout_name(line)
            if name and name in FOOTER_CALLOUTS:
                return _strip_prefix(line)
        return None

    def _pick_anchor(content: str) -> dict | None:
        """Three-tier anchor resolution. Returns the anchor decision as a dict
        (type/value plus optional placement + new_section), or None when nothing
        in the body is anchorable."""
        callout = _pick_editable_callout(content)
        if callout:
            return {"type": "callout", "value": callout}
        heading = _pick_content_heading(content)
        if heading:
            return {"type": "heading", "value": heading, "placement": "after"}
        footer = _find_footer_callout(content)
        if footer:
            return {
                "type": "callout", "value": footer, "placement": "before",
                "new_section": DEFAULT_NEW_SECTION_TITLE,
            }
        return None

    # Tier-1 cache: keyed by MOC path
    moc_cache: dict[str, dict | None] = {}

    def _resolve_from_moc(path: str) -> dict | None:
        if path in moc_cache:
            return moc_cache[path]
        try:
            result = client.read_note(path)
            content = result.get("content", "") or ""
        except Exception:  # noqa: BLE001
            moc_cache[path] = None
            return None
        res = _pick_anchor(content)
        moc_cache[path] = res
        return res

    # Tier-2 cache: keyed by template name (templates are usually shared
    # across many in-set create_moc actions — read each at most once).
    tmpl_cache: dict[str, dict | None] = {}

    def _resolve_from_template(template: str) -> dict | None:
        if template in tmpl_cache:
            return tmpl_cache[template]
        body = read_template(client, template)
        if body is None:
            tmpl_cache[template] = None
            return None
        res = _pick_anchor(body)
        tmpl_cache[template] = res
        return res

    # Index in-set create_moc actions by destination so tier-2 can find the
    # template that the not-yet-existing MOC will be built from.
    create_moc_by_dest: dict[str, dict] = {}
    for a in actions:
        if a.get("action") == "create_moc":
            dest = a.get("destination")
            if dest:
                create_moc_by_dest[dest] = a

    resolved = 0
    for a in actions:
        if a.get("action") != "link_to_moc":
            continue
        anchor = a.get("anchor")
        if not isinstance(anchor, dict):
            continue
        if anchor.get("type") != "callout":
            continue  # heading/line anchors are populated upstream, not here
        if anchor.get("value"):
            continue  # already set
        path = a.get("target_moc_path")
        if not path:
            continue
        res = _resolve_from_moc(path)
        if res is None:
            # Tier-2 fallback: in-set create_moc landing at this path
            create = create_moc_by_dest.get(path)
            if create:
                template = create.get("template")
                if template:
                    res = _resolve_from_template(template)
        if res:
            anchor["type"] = res["type"]
            anchor["value"] = res["value"]
            if res.get("placement"):
                a["placement"] = res["placement"]
            if res.get("new_section"):
                # Prepend a fresh "## <section>" block; the resolved footer
                # anchor + placement="before" drops it ahead of the footer.
                a["line_to_add"] = f"## {res['new_section']}\n\n{a.get('line_to_add', '')}"
            resolved += 1
    return resolved


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
    actions = build_actions(manifest, confirmed, daily_updates, skipped, cfg, kado_client=client)

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
    instructions_doc = {
        "schema_version": "1",
        "type": "tomo-instructions",
        "source_suggestions": source_suggestions,
        "generated": generated_iso,
        "profile": profile_name,
        "tomo_version": tomo_version,
        "action_count": len(actions),
        "md_peer": md_peer_stem,
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
            # F-47 T2.3: new fields drive the tomo: block + source_* cross-ref.
            "upstream_type": args.upstream_type,
            "upstream_path": args.upstream_path,
            "upstream_body_path": args.upstream_body,
            "run_id": args.run_id,
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
