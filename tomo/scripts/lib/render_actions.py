# version: 0.19.0
"""render_actions.py — instruction-set action builders.

Extracted from instruction-render.py (#42, D-07 Constitution L2 split). Turns the
rendered manifest + confirmed items + daily/skip inputs into the ordered list of
machine-readable actions (create_moc, move_note, link_to_moc, add_relationship,
update_*, delete_source, skip). build_actions() is the entry point; the _build_*
helpers each own one action kind. Pure assembly plus a few Kado reads (passed the
client as an argument) for up:: preservation — no rendering, no post-build
resolution (that lives in render_resolve).
"""
from __future__ import annotations

import functools
import json
import re
import sys
from pathlib import Path

from lib.file_extensions import KNOWN_FILE_EXTENSIONS
from lib.kado_client import KadoError
from lib.obsidian_filename import sanitize_stem
from lib.profile_conventions import marker_word
from lib.render_helpers import (
    _moc_stem,
    _stem,
    resolve_sibling_path,
    resolve_source_path,
)
from lib.render_md import bare_stem
from lib.source_link import colliding_names, qualified_target
from lib.up_parse import up_marker_re as _up_marker_re
from lib.supporting_items import (
    parse_supporting_items as _parse_supporting_items,
    union_supporting_items as _union_supporting_items,
)

# tag-handler-group.py is a hyphenated top-level script in the scripts dir (not a
# lib module); load it via importlib for the stable group_id slug (spec 024 T4.1).
# Path is resolved relative to this module: scripts/lib/render_actions.py → scripts/.
import importlib.util as _ilu

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_thg_spec = _ilu.spec_from_file_location(
    "tag_handler_group", str(_SCRIPTS_DIR / "tag-handler-group.py")
)
_thg_mod = _ilu.module_from_spec(_thg_spec)
sys.modules["tag_handler_group"] = _thg_mod
_thg_spec.loader.exec_module(_thg_mod)
group_id = _thg_mod.group_id


def _next_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"I{counter[0]:02d}"


def _inbox_join(inbox: str, basename: str) -> str:
    """Join inbox path + basename, normalising the trailing slash."""
    return f"{(inbox or '').rstrip('/')}/{basename}"


# Moved to lib/file_extensions.py (spec 031 T1.1 code-quality fix) so a pure
# text library can classify a wikilink target without importing this module.
# Alias kept so existing references below (and any other consumer) are unchanged.
_KNOWN_FILE_EXTENSIONS = KNOWN_FILE_EXTENSIONS


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

# Matches the first ``<peer_marker>`` line in a note body (Rule 4.x). MULTILINE
# so ``^`` anchors to each line start. The marker literal is injected from the
# active profile (spec 028 T3.2); the default builders below preserve the
# historical ``related::`` pattern. The ``<parent_marker> [[Target]]`` counterpart
# is imported as ``_up_marker_re`` from lib.up_parse (SSoT).
@functools.lru_cache(maxsize=None)
def _related_marker_re(peer_marker: str) -> re.Pattern:
    return re.compile(rf"^[\s>\-]*{re.escape(peer_marker)}\s*(.*)", re.MULTILINE)


_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _extract_existing_related(content: str, peer_marker: str = "related::") -> list[str]:
    """Extract existing peer-marker wikilink targets from note content."""
    m = _related_marker_re(peer_marker).search(content)
    if not m:
        return []
    return [wl.group(1).strip() for wl in _WIKILINK_RE.finditer(m.group(1))]


def _aggregate_related_actions(
    actions: list[dict], kado_client, peer_marker: str = "related::",
) -> list[dict]:
    """Merge peer-marker actions per target note with existing vault values.

    Per contract (docs/instructions-json.md §882-886), Tomo reads the
    existing peer-marker line and emits one combined action per target.
    """
    if kado_client is None:
        return actions

    # Collect peer-marker actions grouped by target_moc_path
    related_by_target: dict[str, list[dict]] = {}
    non_related: list[dict] = []
    for a in actions:
        if a.get("action") == "add_relationship" and a.get("marker") == peer_marker:
            path = a["target_moc_path"]
            related_by_target.setdefault(path, []).append(a)
        else:
            non_related.append(a)

    if not related_by_target:
        return actions

    merged: list[dict] = []
    for path, rel_actions in related_by_target.items():
        # Read existing peer-marker line from vault
        try:
            note = kado_client.read_note(path)
            content = note.get("content", "") if isinstance(note, dict) else ""
            existing = _extract_existing_related(content, peer_marker)
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

        combined_line = f"{peer_marker} " + ", ".join(f"[[{s}]]" for s in all_stems)
        # Keep the first action as template, update line
        merged_action = dict(rel_actions[0])
        merged_action["line"] = combined_line
        merged.append(merged_action)

    # Reassemble: non-related actions + merged related actions (in original order)
    result = []
    seen_targets: set[str] = set()
    for a in actions:
        if a.get("action") == "add_relationship" and a.get("marker") == peer_marker:
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
    "move_asset": ("source", "destination"),
    "update_tracker": ("daily_note_path",),
    "update_log_entry": ("daily_note_path",),
    "update_log_link": ("daily_note_path",),
    "delete_source": ("source_path",),
    "add_relationship": ("target_moc_path",),
    "insert_under_marker": ("target_path",),
    "edit_frontmatter": ("path",),
}


# ──────────────────────────────────────────────────────────────────────────────
# Rule 4.x: per-child existing-up:: preservation (F-43 T4.2)
# ──────────────────────────────────────────────────────────────────────────────


def extract_first_up_marker(content: str, parent_marker: str = "up::") -> str | None:
    """Return the first ``<parent_marker> [[Target]]`` target from note content, or None.

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
    match = _up_marker_re(parent_marker).search(body)
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
    parent_marker: str = "up::",
    peer_marker: str = "related::",
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
            "marker": parent_marker,
            "line": f"{parent_marker} [[{new_moc_stem}]]",
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
            "marker": parent_marker,
            "line": f"{parent_marker} [[{new_moc_stem}]]",
            "applied": False,
            "error": "non-markdown-asset",
        }]

    note = kado_client.read_note(child_path)
    content = note.get("content", "") if isinstance(note, dict) else ""
    existing_up_target = extract_first_up_marker(content, parent_marker)

    actions: list[dict] = []

    if existing_up_target is None:
        if override_flag:
            # Override checked + no existing parent link → peer marker (user chose peer for this MOC)
            actions.append(_make_add_rel(counter, child_path, peer_marker, new_moc_stem))
        else:
            # No existing parent link + no override → parent marker (new MOC becomes primary parent)
            actions.append(_make_add_rel(counter, child_path, parent_marker, new_moc_stem))
    elif existing_up_target == new_moc_stem:
        # Self-link guard: existing parent link already points to the new MOC → no-op
        pass
    else:
        # existing_up_target is a stem — resolve to verify it exists
        old_target_path = kado_client.resolve_stem_to_path(existing_up_target)
        if old_target_path:
            if override_flag:
                # Rule 4.5 — keep existing parent link, new MOC becomes peer
                actions.append(_make_add_rel(counter, child_path, peer_marker, new_moc_stem))
            else:
                # Rule 4.2 — new MOC becomes parent, existing target moves to peer
                actions.append(_make_add_rel(counter, child_path, parent_marker, new_moc_stem))
                actions.append(_make_add_rel(counter, child_path, peer_marker, existing_up_target))
        else:
            # Rule 4.3 — broken existing parent link (target not found); just set new parent
            actions.append(_make_add_rel(counter, child_path, parent_marker, new_moc_stem))

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


# Default asset folder — single source of truth for both the fallback used
# when a caller's cfg dict lacks "concepts.asset" (build_actions, below) and
# instruction-render.py's CONFIG_DEFAULTS entry for the same key.
DEFAULT_ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"


def _asset_dest_join(asset_folder: str, source_path: str) -> str:
    """Join the asset folder with the source path's basename, preserving it verbatim.

    Never _dest_join (appends a '.md' suffix) or _ensure_md_extension (a silent
    no-op for an allowlisted extension, a corrupting '.md' append for anything
    else) — an attachment's basename must survive exactly as-is, uppercase,
    unusual extension, and all, or the embed referencing it stops resolving.

    Raises ValueError if source_path has no basename (empty, or ending in
    "/") rather than silently returning a bare folder path.
    """
    basename = source_path.rsplit("/", 1)[-1]
    if not basename:
        raise ValueError(f"attachment source path has no filename: {source_path!r}")
    folder = (asset_folder or "").rstrip("/") + "/"
    return f"{folder}{basename}"


def _wikilink(title: str, destination: str | None = None) -> str:
    """Render an Obsidian wikilink whose target resolves to the safe filename.

    When the title contains Obsidian-forbidden chars the file is stored under
    a sanitised stem (see _dest_join), so the link must target that stem or it
    dangles. An alias preserves the original title as display text:
    ``[[safe-stem|Original: Title]]``. Titles already safe render as ``[[Title]]``.

    ``destination`` is passed only when this run claims one filename for more
    than one note (spec 034 T5.5), and makes the link name the note by path —
    ``[[Atlas/203 Sources/Dresden|Dresden]]``, the form the vault itself writes
    for a duplicate basename. The alias slot carries the display title either
    way, so the two cases compose: a sanitised title under a contested filename
    renders ``[[folder/safe-stem|Original: Title]]``.
    """
    stem = sanitize_stem(title)
    if destination:
        return f"[[{qualified_target(destination, title)}]]"
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
    # case-folded destination -> the action that claimed it (T6.0). The key
    # folds; the action it holds keeps the spelling its author wrote.
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
        # Compared case-folded (CON-6, spec 034 T6.0): `Travel (MOC)` and
        # `travel (MOC)` are one file on this filesystem, and the parser's
        # by-Name merge is exact so a case-only pair reaches here intact.
        existing = by_dest.get(destination.casefold())
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
        by_dest[destination.casefold()] = action
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
        # The origin note is addressed by item_key (ADR-1); the inbox-root
        # reconstruction is the fallback for a document minted before spec 034.
        origin_basename = m.get("source_path") or ""
        item_key = m.get("item_key")
        origin = resolve_source_path(item_key, origin_basename, inbox_path) or None
        # Append .md only for bare/dotted note names; preserve real
        # extensions (e.g. `.m4a` for audio sources kept as origin reference).
        origin = _ensure_md_extension(origin)
        # audio_peer is the companion audio file for voice transcripts. Triage
        # pairs it to the note by containing folder, so it resolves beside the
        # note — not at the inbox root. No _ensure_md_extension: keep the .m4a.
        audio_peer = resolve_sibling_path(
            item_key, m.get("audio_peer"), inbox_path
        ) or None
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


def _build_move_asset_actions(
    manifest: list[dict],
    inbox_path: str,
    asset_folder: str,
    counter: list[int],
) -> tuple[list[dict], list[dict]]:
    """Emit move_asset actions for every unique attachment path across the
    whole manifest, deduplicated globally (not per item) on the resolved path.

    Returns (actions, skipped) — mirrors filter_unappliable_relationships's
    shape. An attachment is skipped, reported to stderr, and added to
    `skipped` (never raises, never aborts the run) in two cases:

    - the path has no basename (_asset_dest_join raises ValueError)
    - a destination collision: two DIFFERENT paths (same basename, different
      source folders) resolve to the same destination — the first claim wins,
      the second is skipped. Renaming is not attempted. Destinations are
      compared case-folded (CON-6, spec 034 T6.0); the source `seen` dedup
      stays exact, so a case-only pair in one folder is examined twice and the
      second sighting leaves here as a reported skip rather than as nothing.

    Each skipped entry is {"source", "destination", "reason", "kind",
    "owner_source_items"} — destination is None for the no-basename case,
    since none could be computed. `kind` is "no_basename" or "collision" — the
    two cases need different remedies (a malformed inbox path vs. a real naming
    conflict), so callers rendering this for a user must not treat them as one
    case.

    `owner_source_items` names the notes that embed the refused attachment, by
    the same resolved path `_build_move_note_actions` puts in a move's
    `source_inbox_item` — that is what lets a caller keep such a note in the
    inbox with its file (spec 034 ADR-6). It is a list because the global
    `seen` dedup examines each path once while several notes may embed it.
    """
    out: list[dict] = []
    skipped: list[dict] = []
    seen: set[str] = set()
    # case-folded destination -> the path that claimed it, as it is spelled
    # (T6.0). Only the key folds: the reason the user reads names both paths
    # the way their notes embed them.
    claimed: dict[str, str] = {}
    skipped_by_path: dict[str, dict] = {}
    for m in manifest:
        owner = _ensure_md_extension(
            resolve_source_path(
                m.get("item_key"), m.get("source_path") or "", inbox_path
            ) or None
        )
        for path in m.get("attachments") or []:
            if path in seen:
                # A later note embedding an already-refused file owns the same
                # residue as the first one, so it joins that entry's owners.
                entry = skipped_by_path.get(path)
                if entry is not None and owner:
                    if owner not in entry["owner_source_items"]:
                        entry["owner_source_items"].append(owner)
                continue
            seen.add(path)
            owners = [owner] if owner else []
            try:
                destination = _asset_dest_join(asset_folder, path)
            except ValueError as exc:
                print(f"  [warn] skipping attachment — {exc}", file=sys.stderr)
                entry = {
                    "source": path, "destination": None, "reason": str(exc),
                    "kind": "no_basename", "owner_source_items": owners,
                }
                skipped.append(entry)
                skipped_by_path[path] = entry
                continue
            claimant = claimed.get(destination.casefold())
            if claimant is not None:
                reason = (
                    f"destination collision: {path!r} also resolves to "
                    f"{destination!r}, already claimed by {claimant!r}"
                )
                print(f"  [warn] {reason} — skipping {path!r}", file=sys.stderr)
                entry = {
                    "source": path, "destination": destination, "reason": reason,
                    "kind": "collision", "owner_source_items": owners,
                }
                skipped.append(entry)
                skipped_by_path[path] = entry
                continue
            claimed[destination.casefold()] = path
            out.append({
                "id": _next_id(counter),
                "action": "move_asset",
                "source": path,
                "destination": destination,
            })
    return out, skipped


# Names differing only in case are treated as one destination (CON-6). The
# comparison folds; nothing displayed is ever folded, so the user always reads
# the name they typed and the vault's own spelling of what is in its way.
_CASE_NOTE = (
    "The names differ only in case — the filesystem may treat them as one file."
)

_COUNT_WORDS = {2: "Two", 3: "Three", 4: "Four"}


def _unique_in_order(values: list[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        if v not in out:
            out.append(v)
    return out


def make_folder_listing(kado_client):
    """Return ``folder_listing(location) -> {folded destination: vault path}``.

    One ``list_dir(folder, depth=1)`` per distinct destination folder, cached
    for the life of the returned closure. Never a per-name ``note_exists``
    probe: a probe answers with whatever Kado's own case semantics decide, and
    CON-7 forbids this spec from running against a live vault to find out what
    those are. A listing returns the folder's real filenames, which puts the
    fold in Tomo where a test can reach it, and carries the vault's own
    spelling for the report.

    The cache key is the folder ``_dest_join`` derives, not the raw string: two
    claims whose location differs only by a trailing slash name one folder, and
    a raw key lists it twice. Kado failing is not a collision — an unreachable
    folder reads as empty, so the vault half degrades and the run-internal half
    keeps working (ADR-4).

    This is the twin of ``suggestions-reducer._vault_folder_notes``, which
    serves the Pass-1 proposal. Both compose through ``_dest_join`` and fold
    the same way so the proposal and the guard cannot disagree about what "the
    same place" means.
    """
    cache: dict[str, dict[str, str]] = {}

    def folder_listing(location: str) -> dict[str, str]:
        folder = (location or "").rstrip("/") + "/"
        if folder not in cache:
            found: dict[str, str] = {}
            try:
                for entry in kado_client.list_dir(folder, depth=1):
                    path = entry.get("path") or ""
                    name = path.rsplit("/", 1)[-1]
                    if entry.get("type") != "file" or not name.lower().endswith(".md"):
                        continue
                    # Recompose through _dest_join so both sides of the
                    # comparison are built by the same helper.
                    found[_dest_join(folder, name[:-3]).casefold()] = path
            except Exception:  # noqa: BLE001 — an error is not a collision
                found = {}
            cache[folder] = found
        return cache[folder]

    return folder_listing


def _destination_clash_reason(
    claim_dests: list[str], vault_note: str | None, case_only: bool
) -> str:
    """The sentence the user reads for one contested destination.

    Every destination is spelled the way its author wrote it — the claimants'
    as the user named them, the vault's as the vault holds it. A user told
    their name collides needs to see the name they actually typed.
    """
    n = len(claim_dests)
    if n >= 2:
        spelled = " and ".join(f"`{d}`" for d in _unique_in_order(claim_dests))
        head = f"{_COUNT_WORDS.get(n, str(n))} approved items claim {spelled}"
        if vault_note:
            head += f", and a note already exists at `{vault_note}`"
        tail = "neither is filed" if n == 2 else "none of them is filed"
    elif vault_note == claim_dests[0]:
        # The two-path form informs only when the two paths differ, which is
        # the case-only collision. On an exact match it names one path twice
        # and reads like a rendering bug — and the exact match is the common
        # case, so the degenerate sentence is the one most users would see.
        head = f"a note already exists at `{vault_note}`"
        tail = "this item is not filed"
    else:
        head = (
            f"a note already exists at `{vault_note}`, where this run would "
            f"file `{claim_dests[0]}`"
        )
        tail = "this item is not filed"
    reason = f"{head} — {tail}."
    return f"{reason} {_CASE_NOTE}" if case_only else reason


def _paired_delete_candidates(move: dict, withdrawn_paths: set[str]) -> list[str]:
    """The paths whose `delete_source` a dropped `move_note` takes with it.

    A move's origin and its audio peer each get a paired delete, and emitting
    either without the move removes an inbox note the run refused to file.
    `withdrawn_paths` accumulates across every drop in a run — including drops
    made by a *different* post-pass over the same list — so a path is claimed
    once and no report can count one withdrawal twice.
    """
    candidates: list[str] = []
    for field in ("source_inbox_item", "audio_peer"):
        path = move.get(field)
        if path and path not in withdrawn_paths:
            withdrawn_paths.add(path)
            candidates.append(path)
    return candidates


def _orphaned_link_titles(actions: list[dict], dropped_ids: set[str]) -> set[str]:
    """The `source_note_title` values whose every author is being dropped.

    A `link_to_moc` bullet is addressed by title, not by path, because title is
    the key it was minted under: `_emit` dedups by (target MOC, source title),
    so one bullet can have several authors and there is no single origin to
    join on. The rule is therefore "withdraw only when *no* surviving action
    would still write that bullet" — the dropped titles minus the titles the
    kept `move_note` and `create_moc` actions still put in the vault.

    That subtraction is what keeps the withdrawal from over-reaching:

    - a `create_moc` has no `move_note` at all, so "this title has no move"
      cannot mean "orphaned" — its own parent bullet must survive;
    - the garden-audit branch emits `link_to_moc` for notes already in the
      vault and no `move_note` whatsoever, so it must never lose a bullet;
    - a namesake that survives while its twin is dropped is still an author of
      the shared bullet, and the bullet stays.
    """
    surviving: set[str] = set()
    orphaned: set[str] = set()
    for action in actions:
        if action.get("action") not in ("move_note", "create_moc"):
            continue
        title = sanitize_stem(action.get("title") or "")
        if not title:
            continue
        if action.get("id") in dropped_ids:
            orphaned.add(title)
        else:
            surviving.add(title)
    return orphaned - surviving


def _links_for(withholding: dict, removed_moc_links: list[dict]) -> list[dict]:
    """The share of one run's withdrawn bullets that belongs to one report.

    Both post-passes may withhold in the same run, and each renders its own
    section. A bullet is attributed to the withholding whose dropped moves
    carry its title — the same key `_orphaned_link_titles` withdrew it under,
    so the two cannot disagree about which bullet belongs to which report.
    """
    titles = {
        sanitize_stem(d.get("title") or "")
        for d in withholding.get("dropped") or []
    }
    return [
        link for link in removed_moc_links
        if sanitize_stem(link.get("source_note_title") or "") in titles
    ]


def _drop_moves_with_paired_deletes(
    actions: list[dict], dropped_ids: set[str], withdrawn_paths: set[str]
) -> tuple[list[dict], set[str], list[dict]]:
    """Remove the dropped moves, the deletes paired with them, and their links.

    Returns ``(kept, removed_deletes, removed_moc_links)``. `removed_deletes`
    names the deletes that actually existed, not every path a dropped move
    touched: an item the user marked "Keep source files" has no paired delete,
    so listing its origin would have the report and the coverage audit both
    claim a withdrawal that never happened.

    `removed_moc_links` is the same discipline one action kind over. A
    `link_to_moc` for a note this run refused to file instructs the user to
    add a bullet pointing at a path that will hold nothing — the dead link the
    guard exists to prevent, written by the guard itself. T5.3 shipped with
    "a `link_to_moc` for a dropped note is harmless" as its named unverified
    assumption; the T5.5 document disproved it.

    Shared by both post-passes over the built action list
    (``validate_destinations`` and ``suppress_moves_for_unfiled_attachments``).
    They drop moves for different reasons and report them separately, but the
    withdrawal itself is one mechanism — a second copy is what drifted apart in
    T5.0c one module over.
    """
    orphaned_titles = _orphaned_link_titles(actions, dropped_ids)
    removed_deletes: set[str] = set()
    removed_moc_links: list[dict] = []
    kept: list[dict] = []
    for action in actions:
        if action.get("id") in dropped_ids:
            continue
        if (
            action.get("action") == "delete_source"
            and action.get("source_path") in withdrawn_paths
        ):
            removed_deletes.add(action.get("source_path"))
            continue
        if (
            action.get("action") == "link_to_moc"
            and (action.get("source_note_stem") or "") in orphaned_titles
        ):
            # Join on the stem (what the vault resolves by), report the title
            # (what the user reads) — spec 034 T6.4b. The record carries the
            # display title only: it is serialised into instructions.json's
            # `tomo` block, and `_links_for` derives the key from it the same
            # way the dropped side does, so both halves agree by construction.
            removed_moc_links.append({
                "source_note_title": action.get("source_note_title"),
                "target_moc": action.get("target_moc"),
            })
            continue
        kept.append(action)
    return kept, removed_deletes, removed_moc_links


def validate_destinations(
    actions: list[dict], folder_listing=None
) -> tuple[list[dict], list[dict]]:
    """Drop every move whose destination is contested; report what was dropped.

    Returns ``(kept_actions, clashes)``. Runs after ``build_actions``, over the
    whole assembled list, so it sees every claim at once (ADR-4).

    **Both** claimants are dropped, not the second one. This follows the
    reporting shape of ``_build_move_asset_actions`` and deliberately inverts
    its resolution: there, the first attachment keeps the destination because
    nothing is lost by skipping a duplicate file. Here the two names were both
    set by the user, and choosing between them would itself be a guess. Pass 1
    (``resolve_destination_clashes``) is the advisory half that keeps the
    common case away from this guard; this half binds.

    A dropped move takes its paired ``delete_source`` with it — the origin's
    and its audio peer's. Emitting the delete without the move would remove the
    user's inbox note while refusing to file it, which is the loss this guard
    exists to prevent. The withdrawal joins on the origin's resolved path
    (ADR-1), so a namesake in another inbox folder keeps its own delete.

    It takes its ``link_to_moc`` bullets too, on the title key those were
    minted under — see ``_orphaned_link_titles``. A bullet naming a note the
    guard refused to file is an instruction to create a dead link.

    ``folder_listing`` is the vault view from ``make_folder_listing``; ``None``
    skips the vault half and leaves the run-internal half working.

    The pass holds no state across calls: correcting one name and re-running
    Pass 2 emits both moves, with no memo of the earlier clash.
    """
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for action in actions:
        if action.get("action") != "move_note":
            continue
        destination = action.get("destination") or ""
        if not destination:
            continue
        key = destination.casefold()
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(action)

    # One listing per destination folder, only for folders this run writes to.
    vault_holders: dict[str, str] = {}
    if folder_listing is not None:
        for key in order:
            destination = groups[key][0].get("destination") or ""
            folder = destination.rsplit("/", 1)[0] if "/" in destination else ""
            holder = folder_listing(folder).get(key)
            if holder:
                vault_holders[key] = holder

    # One list of (clash, candidate paths) pairs rather than two parallel
    # lists: the second pass below needs each clash's candidates, and any
    # future early `continue` in this loop would desync two lists silently —
    # a clash would then report another clash's withdrawals, with no
    # exception and nothing for a test to catch. A tuple cannot desync.
    pending: list[tuple[dict, list[str]]] = []
    dropped_ids: set[str] = set()
    withdrawn_paths: set[str] = set()
    for key in order:
        claimants = groups[key]
        vault_note = vault_holders.get(key)
        if len(claimants) < 2 and vault_note is None:
            continue
        claim_dests = [c.get("destination") or "" for c in claimants]
        spellings = _unique_in_order(
            claim_dests + ([vault_note] if vault_note else [])
        )
        candidates: list[str] = []
        for claimant in claimants:
            dropped_ids.add(claimant.get("id"))
            candidates.extend(_paired_delete_candidates(claimant, withdrawn_paths))
        clash = {
            "kind": "run_collision" if len(claimants) >= 2 else "vault_collision",
            "destination": claim_dests[0],
            "case_only": len(spellings) > 1,
            "vault_note": vault_note,
            "reason": _destination_clash_reason(
                claim_dests, vault_note, len(spellings) > 1
            ),
            "dropped": [
                {
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "destination": c.get("destination"),
                    "source_inbox_item": c.get("source_inbox_item"),
                }
                for c in claimants
            ],
            # Filled in below, once it is known which of `candidates`
            # actually had a delete_source to withdraw.
            "withdrawn_deletes": [],
            "withdrawn_moc_links": [],
        }
        pending.append((clash, candidates))

    if not pending:
        return actions, []

    kept, removed_deletes, removed_moc_links = _drop_moves_with_paired_deletes(
        actions, dropped_ids, withdrawn_paths
    )
    for clash, candidates in pending:
        clash["withdrawn_deletes"] = [c for c in candidates if c in removed_deletes]
        clash["withdrawn_moc_links"] = _links_for(clash, removed_moc_links)
    return kept, [clash for clash, _candidates in pending]


_BULLET_LINK_RE = re.compile(r"^(\s*-\s*)\[\[([^\]]+)\]\](.*)$")


def contested_note_names(actions: list[dict]) -> set[str]:
    """The note filenames this run claims for more than one destination.

    Taken over the action list **as built** — before `validate_destinations`
    or `suppress_moves_for_unfiled_attachments` withhold anything. That timing
    is the whole point: the withheld twin is exactly the note that comes back.
    The user renames one claimant, re-runs Pass 2, and the other files as
    `Dresden.md`; a bullet this run wrote into a MOC then stops resolving, in a
    note nobody revisits. A set taken from the survivors would see one Dresden
    and render the bare link that the guard's own outcome invalidates.

    Keyed on the sanitised filename, because that is what the vault resolves
    by. Distinct **destinations**, not claimant count: two items claiming one
    path are both withheld and leave no bullet behind, so they are not what
    makes a name ambiguous — two items landing at two paths are.
    """
    return colliding_names(
        (sanitize_stem(a["title"]), a["destination"])
        for a in actions
        if a.get("action") in ("move_note", "create_moc")
        and a.get("title") and a.get("destination")
    )


def qualify_contested_moc_links(actions: list[dict], contested: set[str]) -> int:
    """Make every MOC bullet for a contested filename name its note by path.

    A `link_to_moc` bullet is written into a MOC and stays there, so unlike a
    line in the instruction document it has to survive the run that wrote it
    (spec 034 T5.5). `[[Dresden]]` resolves by name; once a second `Dresden`
    exists anywhere in the vault it resolves to whichever the vault picks.

    Runs **after** both withholding passes, over their output, because the
    path it writes must be one that will exist: the destination of the move
    that survived, never a withheld claimant's. `contested` is the claim set
    from before those passes (`contested_note_names`) — the two halves need
    opposite timings, which is why this is a pass and not an emit-time choice.

    Must run BEFORE `_merge_new_section_links` and `_serialize_new_sections`,
    while `line_to_add` is still one bare bullet. The display text is taken
    from the bullet itself rather than from `source_note_title`, so a title
    that was sanitised keeps the original as its alias.

    A contested name with no surviving move is left alone: there is no path to
    name it by, and the bullet is withdrawn by the withholding pass anyway.

    Returns the count of bullets rewritten.
    """
    if not contested:
        return 0
    survivors: dict[str, str] = {}
    for action in actions:
        if action.get("action") not in ("move_note", "create_moc"):
            continue
        title, destination = action.get("title"), action.get("destination")
        if title and destination:
            survivors.setdefault(sanitize_stem(title), destination)

    rewritten = 0
    for action in actions:
        if action.get("action") != "link_to_moc":
            continue
        name = action.get("source_note_stem") or ""
        destination = survivors.get(name) if name in contested else None
        if not destination:
            continue
        match = _BULLET_LINK_RE.match(action.get("line_to_add") or "")
        if not match:
            continue
        prefix, ref, suffix = match.groups()
        display = ref.split("|", 1)[1] if "|" in ref else ref
        if "|" in ref and ref.split("|", 1)[0] == _drop_md(destination):
            continue  # already qualified
        action["line_to_add"] = (
            f"{prefix}[[{qualified_target(destination, display)}]]{suffix}"
        )
        rewritten += 1
    return rewritten


def _drop_md(path: str) -> str:
    return path[:-3] if path.endswith(".md") else path


def _attachment_suppression_reason(entry: dict, note_count: int) -> str:
    """The sentence the user reads for one attachment that could not be filed.

    It must not read like a destination clash: that one is fixed by renaming a
    *note*, this one by renaming a *file*. A reader who cannot tell which
    happened cannot act.
    """
    source = entry.get("source") or "?"
    if entry.get("kind") == "collision":
        head = (
            f"`{source}` cannot be filed — another file of that name already "
            f"claims `{entry.get('destination')}`"
        )
        remedy = "rename one of the two files, then re-run Pass 2"
    else:
        head = f"`{source}` cannot be filed — {entry.get('reason') or 'no filename'}"
        remedy = "correct that inbox path, then re-run Pass 2"
    tail = (
        "the note that embeds it is not filed either"
        if note_count == 1
        else f"the {note_count} notes that embed it are not filed either"
    )
    return f"{head} — {tail}. To fix: {remedy}."


def suppress_moves_for_unfiled_attachments(
    actions: list[dict], skipped_assets: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Keep a note in the inbox when its attachment could not be filed.

    Returns ``(kept_actions, suppressions)``. Runs after ``build_actions`` as a
    sibling of ``validate_destinations``, over the whole assembled list, for a
    reason the ordering inside ``build_actions`` forces: the paired
    ``delete_source`` actions do not exist yet while ``_build_move_asset_actions``
    is running, so an inline suppression would have nothing to withdraw and the
    note's source would be deleted while the note stayed in the inbox — losing
    it outright, which is worse than filing it incompletely.

    This **reverses spec 031** (`plan/phase-2.md:85`), which let the note move
    without its attachment. That was right while a flat inbox made a basename
    clash unreachable; recursive discovery made it reachable, and moving a note
    never carries its attachments, so the file would stay in the inbox
    indefinitely `[ref: PRD/Feature 8, SDD/ADR-6]`.

    Only the *owning* notes are suppressed, joined on the resolved source path
    (ADR-1) that `_build_move_asset_actions` recorded on each skipped entry —
    never on the stem, which two notes in different inbox folders share.

    Composes with ``validate_destinations`` in either order: a move that pass
    already dropped is absent here, so no note is reported as withheld twice
    and no delete or MOC link is counted as withdrawn twice. Only suppressions that
    actually withheld a move are returned — the attachment itself is already
    reported through ``skipped_assets``.

    The pass holds no state across calls: renaming one file and re-running
    Pass 2 files everything, with no memo of the earlier clash.
    """
    if not skipped_assets:
        return actions, []

    moves_by_source: dict[str, list[dict]] = {}
    for action in actions:
        if action.get("action") != "move_note":
            continue
        source = action.get("source_inbox_item")
        if source:
            moves_by_source.setdefault(source, []).append(action)

    pending: list[tuple[dict, list[str]]] = []
    dropped_ids: set[str] = set()
    withdrawn_paths: set[str] = set()
    for entry in skipped_assets:
        dropped: list[dict] = []
        candidates: list[str] = []
        for owner in entry.get("owner_source_items") or []:
            for move in moves_by_source.get(owner) or []:
                if move.get("id") in dropped_ids:
                    continue
                dropped_ids.add(move.get("id"))
                dropped.append({
                    "id": move.get("id"),
                    "title": move.get("title"),
                    "destination": move.get("destination"),
                    "source_inbox_item": move.get("source_inbox_item"),
                })
                candidates.extend(
                    _paired_delete_candidates(move, withdrawn_paths)
                )
        if not dropped:
            continue
        pending.append((
            {
                "kind": entry.get("kind"),
                "attachment": entry.get("source"),
                "attachment_destination": entry.get("destination"),
                "reason": _attachment_suppression_reason(entry, len(dropped)),
                "dropped": dropped,
                # Filled in below, once it is known which of `candidates`
                # actually had a delete_source to withdraw.
                "withdrawn_deletes": [],
                "withdrawn_moc_links": [],
            },
            candidates,
        ))

    if not pending:
        return actions, []

    kept, removed_deletes, removed_moc_links = _drop_moves_with_paired_deletes(
        actions, dropped_ids, withdrawn_paths
    )
    for suppression, candidates in pending:
        suppression["withdrawn_deletes"] = [
            c for c in candidates if c in removed_deletes
        ]
        suppression["withdrawn_moc_links"] = _links_for(
            suppression, removed_moc_links
        )
    return kept, [suppression for suppression, _candidates in pending]


def claimed_rendered_files(actions: list[dict]) -> set[str]:
    """The staging notes an action list claims, by ``rendered_file``.

    Taken once over ``build_actions``' output and once over the guards'
    output; the difference is what a guard withheld. See
    ``manifest_without_withheld_staging``.
    """
    return {a.get("rendered_file") for a in actions if a.get("rendered_file")}


def manifest_without_withheld_staging(
    manifest: list[dict], actions: list[dict], claimed_before: set[str]
) -> tuple[list[dict], list[str]]:
    """Drop the manifest entries whose claim a guard withheld.

    Returns ``(kept_entries, withheld_filenames)``. Each manifest entry is a
    staging note that a later upload step writes into the inbox, and each is
    claimed by exactly one ``move_note`` or ``create_moc``. When a guard
    withholds that action the staging note has nothing left to move it, so the
    upload must not write it.

    Keyed on ``rendered_file``, which both action builders copy from the
    manifest entry — an action ``id`` is a fresh counter value and does not
    join back to the entry it came from.

    ``claimed_before`` is that key set as ``build_actions`` left it, and is
    what makes the pass precise rather than merely plausible: an entry no
    action ever claimed is **kept**, because nothing withheld it. Without that
    half, a run whose action building produced nothing would silently drop
    every staging note — indistinguishable here from a run where every move
    was withheld.

    Written against the surviving actions rather than against a withholding
    report, so both guards are covered by one pass and a third one would need
    no change here. An entry with no ``rendered_file`` is kept: nothing was
    rendered for it to leave behind.
    """
    surviving = claimed_rendered_files(actions)
    kept: list[dict] = []
    withheld: list[str] = []
    for entry in manifest:
        rendered = entry.get("rendered_file")
        if rendered and rendered in claimed_before and rendered not in surviving:
            withheld.append(rendered)
            continue
        kept.append(entry)
    return kept, withheld


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
            # Wikilink target resolves to the (possibly sanitised) filename
            # so a forbidden-char note round-trips to the renamed file (#69).
            # The two identity fields split the two jobs (spec 034 T6.4b):
            # source_note_title is DISPLAY text and stays raw, because the
            # coverage audit and every report join on the title the user reads;
            # source_note_stem is the vault's own key, which the withholding
            # passes join on. Writing the stem into the title field made the
            # audit hard-fail every correct run whose title held a `:`.
            # source_note_stem is Tomo-internal — _strip_internal_link_fields
            # removes it before the wire.
            "line_to_add": f"- {_wikilink(source_title)}",
            "source_note_title": source_title,
            "source_note_stem": sanitize_stem(source_title),
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
    # {field_name: {"syntax": …, "section": …}} resolved from the vault config.
    # The review document never displays either value, so neither survives the
    # markdown round trip back through suggestion-parser — they are looked up
    # here, at the point of use, where the config is the authority (#162).
    # `.get` and the per-field fallbacks below keep an absent map a no-op.
    tracker_fields = cfg.get("daily_notes.tracker_fields") or {}
    out: list[dict] = []
    for day in daily_updates:
        date = day.get("date", "")
        note_path = _resolve_daily_path(daily_path_cfg, date, day.get("daily_note_path"))
        for tr in day.get("trackers", []) or []:
            if not tr.get("accepted"):
                continue
            configured = tracker_fields.get(tr.get("field", "")) or {}
            out.append({
                "id": _next_id(counter),
                "action": "update_tracker",
                "daily_note_path": note_path,
                "date": date,
                "field": tr.get("field", ""),
                "value": tr.get("value", ""),
                "syntax": (
                    configured.get("syntax") or tr.get("syntax") or "inline_field"
                ),
                "section": configured.get("section") or tr.get("section") or None,
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


def _origin_key(resolved_path: str | None) -> str:
    """The per-note identity the delete bookkeeping joins on (spec 034 T5.0b).

    `_build_delete_source_actions` joins three inputs that describe the same
    inbox note in three different spellings — a confirmed item, a move_note
    origin and a daily entry. That join used to be the bare filename stem,
    which two notes in different inbox subfolders share once discovery is
    recursive: each collection collapsed two distinct notes into one bucket.

    The key is the resolved vault-relative path (ADR-1) with a trailing `.md`
    removed, because the three inputs disagree about that one extension: a
    confirmed item's `source_path` carries it, a daily entry's `source_stem`
    does not, and a move_note origin has already been through
    `_ensure_md_extension`. Every other extension is significant and is kept —
    an `.m4a` origin is a different file from an `.md` note of the same name.
    """
    if not resolved_path:
        return ""
    return resolved_path[:-3] if resolved_path.endswith(".md") else resolved_path


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
    2. Daily-only items — origins that appear in accepted daily_updates but
       have no matching confirmed_item (content fully captured in the daily
       note, no atomic note will be created).
    3. move_note origins — for every move_note action whose corresponding
       confirmed item did NOT opt out via "Keep source files", emit a paired
       delete_source for the origin inbox item. Audio + transcript peer
       pairs are NOT included here (they're independent upstream artifacts);
       only the origin from which Tomo derived the rendered atomic note.
    4. Tag-handler group sources — for every APPROVED group not opted out via
       "Keep source files", one delete_source per `source_path`. The group's
       insert_under_marker (emitted earlier) copies the captures into the
       target note, so the inbox sources are now redundant. Parity with (3),
       but keyed by group_id rather than origin note.
    """
    out: list[dict] = []
    confirmed_keys: set[str] = set()
    # expected_by_key: number of approved atomics per ORIGIN NOTE — the OQ6
    # completion-gate denominator. Keyed by the note's own path, it counts the
    # atomics of THIS note; a namesake in another inbox folder is a different
    # file, and how many atomics that one produced says nothing about whether
    # this one is fully captured. Keyed by stem the two shared a denominator,
    # which mis-counted in both directions: two namesakes with one atomic each
    # passed the gate coincidentally (2 >= 2) and emitted a single delete, and
    # one namesake's unrendered atomic deferred the other's delete forever.
    expected_by_key: dict[str, int] = {}
    # keep_source_keys: origins where ANY confirmed item opts out of deletion.
    keep_source_keys: set[str] = set()
    for item in confirmed:
        sp = item.get("source_path")
        if sp:
            key = _origin_key(resolve_source_path(item.get("item_key"), sp, inbox_path))
            confirmed_keys.add(key)
            expected_by_key[key] = expected_by_key.get(key, 0) + 1
            if item.get("keep_source"):
                keep_source_keys.add(key)

    # (1) Explicit user "Delete source" on skipped items
    for sk in skipped:
        if sk.get("disposition") != "delete_source":
            continue
        sp = sk.get("source_path") or ""
        if not sp:
            continue
        full = _ensure_md_extension(
            resolve_source_path(sk.get("item_key"), sp, inbox_path)
        )
        out.append({
            "id": _next_id(counter),
            "action": "delete_source",
            "source_path": full,
            "reason": "User marked source for deletion (no atomic note created).",
        })

    # (2) Daily-only origins
    seen: set[str] = set()
    for day in daily_updates:
        for bucket in ("trackers", "log_entries", "log_links"):
            for entry in day.get(bucket, []) or []:
                if not entry.get("accepted"):
                    continue
                key = _origin_key(resolve_source_path(
                    entry.get("source_item_key"), entry.get("source_stem"), inbox_path
                ))
                if not key or key in confirmed_keys or key in seen:
                    continue
                seen.add(key)
                # This site emits a DELETE for a note the run never rendered,
                # so it must name the note it came from and not a path composed
                # from the display stem: with a namesake at the inbox root, a
                # composed path names that note instead. `source_item_key` is
                # the daily entry's identity (ADR-1).
                full = _ensure_md_extension(resolve_source_path(
                    entry.get("source_item_key"), entry.get("source_stem"), inbox_path
                ))
                out.append({
                    "id": _next_id(counter),
                    "action": "delete_source",
                    "source_path": full,
                    "reason": "Content fully captured in daily note.",
                })

    # (3) move_note origins — completion gate: emit one delete per origin note
    # only after ALL expected atomics are represented in move_notes (OQ6).
    # Collect accepted daily origins for reason-string annotation (" + daily").
    # The user approves on that string (CON-2), so it must credit the note that
    # actually made the daily entry, not a namesake in another folder.
    daily_keys: set[str] = set()
    for day in daily_updates:
        for bucket in ("trackers", "log_entries", "log_links"):
            for entry in day.get(bucket, []) or []:
                if entry.get("accepted"):
                    k = _origin_key(resolve_source_path(
                        entry.get("source_item_key"), entry.get("source_stem"),
                        inbox_path,
                    ))
                    if k:
                        daily_keys.add(k)

    # Group move_notes by origin note. `source_inbox_item` is already the
    # resolved vault-relative path (_build_move_note_actions), so it needs no
    # second resolution — only the shared normalisation.
    moves_by_origin: dict[str, list[dict]] = {}
    for mn in move_notes:
        if mn.get("action") != "move_note":
            continue
        origin = mn.get("source_inbox_item")
        if not origin:
            continue
        bucket_list = moves_by_origin.setdefault(_origin_key(origin), [])
        bucket_list.append(mn)

    for origin_key, moves in moves_by_origin.items():
        if origin_key in keep_source_keys:
            continue
        expected = expected_by_key.get(origin_key, 1)
        if len(moves) < expected:
            continue  # not all atomics rendered yet — defer (OQ6)
        origin_path = moves[0].get("source_inbox_item", "")
        n = len(moves)
        has_daily = origin_key in daily_keys
        daily_suffix = " + daily" if has_daily else ""
        reason = f"Origin consumed by {n} atomic{'s' if n > 1 else ''}{daily_suffix}."
        out.append({
            "id": _next_id(counter),
            "action": "delete_source",
            "source_path": origin_path,
            "reason": reason,
        })
        # Paired audio peer delete — one delete per unique audio peer for this
        # origin note. Normally 0 or 1 peer; set deduplicates the multi-atomic
        # case (two atomics from one transcript share the same peer path).
        # keep_source_keys and the gate both apply above, so arriving here
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
            # Group source_paths are vault-relative by contract (they come from
            # triage's `item["path"]`), so this resolves to `sp` untouched. It
            # goes through the shared resolver anyway: one rule for every inbox
            # path in this module, and no second spelling to drift.
            full = _ensure_md_extension(resolve_source_path(None, sp, inbox_path))
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
    for sk in skipped:
        if sk.get("disposition") != "skip":
            continue
        sp = resolve_source_path(
            sk.get("item_key"), sk.get("source_path"), inbox_path
        ) or None
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
    parent_marker: str = "up::",
    peer_marker: str = "related::",
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
                    parent_marker=parent_marker, peer_marker=peer_marker,
                )
            )
    return out


def _build_edit_note_text_actions(
    items: list[dict],
    counter: list[int],
) -> list[dict]:
    """Emit edit_note_text actions for body-level text edits (ADR-3, spec 030).

    Each item must carry: path (str), match (str), replace (str).
    occurrence defaults to "first" when absent.

    Covers three fix cases with one primitive:
      - dead wikilink fix:    match="[[Old]]", replace="[[New]]"
      - dead wikilink remove: match="[[Old]]", replace=""
      - broken up:: remove:   match="up:: [[Deleted MOC]]", replace=""

    Broken-up REPOINT stays on add_relationship (marker-located line replace) —
    this builder is ONLY for removal + free-text wikilink substitution (ADR-5,
    Rule 7). Never call this builder for repoints.

    Caller is responsible for stamping ``applied: False`` before wire emission —
    this builder does not emit ``applied``, matching the convention of _build_*
    helpers normally stamped centrally by build_actions(). T4.2's garden-audit-
    parser calls this builder directly via build_from_wire, bypassing build_actions,
    so the caller must stamp applied explicitly.
    """
    out: list[dict] = []
    for item in items:
        out.append({
            "id": _next_id(counter),
            "action": "edit_note_text",
            "path": item["path"],
            "match": item["match"],
            "replace": item["replace"],
            "occurrence": item.get("occurrence", "first"),
        })
    return out


class UnsupportedShapeError(ValueError):
    """Raised by ``_construct_edit_frontmatter_fields`` when ``up_value``'s
    shape has no defined transform (spec 032 T3.2 — a YAML map, today the only
    such shape).

    A distinct exception rather than a sentinel return: it keeps the success
    contract of ``_construct_edit_frontmatter_fields`` to exactly one shape
    (always the ``{operation, value?, expected}`` triad) instead of a second,
    easy-to-forget-to-check return shape. The caller (``_route_broken_up``,
    T3.2's minimal parser touch) never actually triggers this — it detects the
    map shape itself before calling the transform, using the SAME
    ``isinstance(up_value, dict)`` test, and records "unsupported-shape" in
    ``unroutable`` directly. This exception exists so the transform's own
    contract is enforced and independently testable, per the SDD: "guessing a
    transform for a shape we have never seen is how the current defect was
    born."
    """


def _construct_edit_frontmatter_fields(
    up_value, up_target: str, choice: str, *, new_target: str | None = None,
) -> dict:
    """Build the ``{operation, value, expected}`` triad for one broken-`up`
    frontmatter fix (spec 032 T3.2 — SDD "Constructing value and expected —
    traced walkthrough").

    Pure transform only: given the observed property value, the broken stem,
    and the user's remove/repoint choice, decides ``operation`` (``set`` vs
    ``remove``), builds ``value`` (only for ``set``), and carries ``expected``
    through untouched. Does NOT assemble an action dict, derive the property
    name, stamp ``applied``, or touch a confirmed_item — that wiring is T3.3's
    ``_build_edit_frontmatter_actions``.

    ``new_target`` is required (and used) only when ``choice == "repoint"`` —
    keyword-only so a caller cannot accidentally supply it positionally for a
    "remove" call.

    Three rules this function exists to get right (SDD, "three consequences
    worth stating plainly"):

    1. **"Remove" is usually ``operation: "set"``, not ``"remove"``.**
       ``remove`` deletes the WHOLE property and is correct only when the
       broken entry was its sole content — reaching for ``remove`` on user
       choice alone would delete a legitimate sibling parent MOC.
    2. **Order is preserved by construction.** A copy of ``up_value`` is
       transformed in place (index-replaced for repoint, filtered for
       remove) — never rebuilt from a re-derived set of stems.
    3. **Scalar shape is preserved.** A scalar ``up_value`` yields a scalar
       ``value``; it is never normalised into a one-item list. Normalising
       would change the note beyond the approved fix AND fail Hashi's
       deep-equal ``expected`` guard.

    4. **CONTRACT — ``up_value`` is never normalised, anywhere on the path
       from cache to wire.** Not sorted, not de-duplicated, not re-wrapped.
       Hashi confirmed the mechanism 2026-09-03 (handoff
       ``2026-09-03_hashi-to-tomo_up-source-routing-confirmed-and-one-rerun-asymmetry``):
       their ``expected`` comparison is ``deepEqual`` over the PARSED YAML
       value, and for arrays it is element-wise **and order-sensitive** —
       ``[A, B]`` does not match ``[B, A]``, deliberately, so the guard
       cannot pass on a note someone reordered. A normalising "cleanup" here
       would therefore fail every guard at APPLY time in a user's vault
       while every fixture in this repo stayed green. Treat as a contract,
       not a convention.

    ``expected`` is always the ``up_value`` argument itself, byte-for-byte,
    in every branch — never the transformed copy. ``expected_absent`` is
    never emitted: every property this spec targets exists (it is the source
    of the broken target), so the guard is a plain absence, not a code path.

    A map-shaped ``up_value`` has no defined transform (SDD, Complex Logic:
    "no known occurrence in the measured population, and guessing a transform
    for a shape we have never seen is how the current defect was born") and
    raises ``UnsupportedShapeError`` rather than silently guessing one.
    """
    if isinstance(up_value, dict):
        raise UnsupportedShapeError(
            f"up_value is a map — no transform defined (up_target={up_target!r})"
        )
    if choice not in ("remove", "repoint"):
        raise ValueError(f"unknown choice: {choice!r}")
    if choice == "repoint" and new_target is None:
        raise ValueError("repoint requires new_target")

    match_key = bare_stem(up_target)
    is_scalar = not isinstance(up_value, list)

    if choice == "repoint":
        replacement = f"[[{new_target}]]"
        if is_scalar:
            # No match (observed value != the broken target) is a deliberate
            # no-op — a stale/inconsistent cache must never crash the pipeline
            # or guess a transform; locked by test (T3.3 code-quality carryover).
            value = replacement if bare_stem(up_value) == match_key else up_value
            return {"operation": "set", "value": value, "expected": up_value}
        value = list(up_value)
        for i, entry in enumerate(value):
            if bare_stem(entry) == match_key:
                value[i] = replacement
        return {"operation": "set", "value": value, "expected": up_value}

    # choice == "remove"
    if is_scalar:
        if bare_stem(up_value) == match_key:
            return {"operation": "remove", "expected": up_value}
        # Same deliberate no-op as the repoint branch above: no match, no guess.
        return {"operation": "set", "value": up_value, "expected": up_value}
    remaining = [e for e in up_value if bare_stem(e) != match_key]
    if not remaining:
        return {"operation": "remove", "expected": up_value}
    return {"operation": "set", "value": remaining, "expected": up_value}


def _build_edit_frontmatter_actions(
    items: list[dict], counter: list[int], parent_marker: str = "up::",
) -> list[dict]:
    """Build ``edit_frontmatter`` actions for broken-`up` fixes whose parent is
    declared in frontmatter (spec 032 T3.3 — the wiring named by the SDD's
    Integration Points).

    Each item is an ``edit_frontmatter`` confirmed_item carrying ``up_value``,
    ``up_target``, ``choice`` (and ``new_target`` for a repoint) — threaded by
    garden-audit-parser.py exactly as ``add_relationship`` carries ``up_line``
    and ``remove_up_link`` carries ``link``. This builder derives ``property``
    via ``marker_word(parent_marker)`` (ADR-6 — never hardcoded, so a profile
    configured with a different marker yields a different property name), and
    delegates ``operation``/``value``/``expected`` to the pure transform
    ``_construct_edit_frontmatter_fields`` (T3.2). ``value`` is included only
    when the transform returns it (operation='set') — T3.2 omits the key
    entirely for 'remove', and this builder must not re-add it via a default.

    Caller is responsible for stamping ``applied: False`` before wire emission
    — this builder does not emit it, matching ``_build_edit_note_text_actions``'
    convention; ``build_garden_audit_actions`` stamps the whole output
    centrally.
    """
    property_name = marker_word(parent_marker)
    out: list[dict] = []
    for item in items:
        fields = _construct_edit_frontmatter_fields(
            item["up_value"], item["up_target"], item["choice"],
            new_target=item.get("new_target"),
        )
        action = {
            "id": _next_id(counter),
            "action": "edit_frontmatter",
            "path": item["path"],
            "property": property_name,
            "operation": fields["operation"],
            "expected": fields["expected"],
        }
        if "value" in fields:
            action["value"] = fields["value"]
        out.append(action)
    return out


def build_garden_audit_actions(
    confirmed: list[dict],
    counter: list[int] | None = None,
    parent_marker: str = "up::",
) -> list[dict]:
    """Assemble Hashi actions from garden-audit confirmed_items (spec 030).

    Isolated from build_actions — garden-audit's confirmed_items are semantic
    fix items (garden_check / garden_action), NOT the suggestions manifest shape.
    Keeping a separate assembler leaves the suggestions/moc-proposal hot path in
    build_actions untouched (ADR: "no new apply path… mirror /moc-propose").

    garden_action → actions:
      - resolve_dead_link → one resolve_dead_link (dead_link unlink/repoint —
        Hashi edits the body with alias/embed awareness; replace='' unlinks
        keeping the display, '[[New]]' repoints). Supersedes the literal
        edit_note_text construction, which no-opped on aliased links.
      - remove_up_link  → one remove_up_link (broken_up empty=remove — Hashi
        removes ONLY the broken link from the up:: line, keeps the up:: field
        (emptied) when it was the last link).
      - edit_note_text  → forward-compat only: no garden_action emits it now
        (dead_link moved to resolve_dead_link, broken_up remove to
        remove_up_link). Kept for the shared builder + Hashi's shipped surface.
      - add_relationship→ one add_relationship up:: (broken_up repoint).
      - file_note       → link_to_moc (bullet on the MOC) + add_relationship up::
        (up-link on the note). Files an unparented/orphan note under a MOC.
      - edit_frontmatter→ one edit_frontmatter (broken_up frontmatter-declared
        parent — spec 032 T3.3). Property name derived via
        marker_word(parent_marker) (ADR-6); operation/value/expected from
        _construct_edit_frontmatter_fields (T3.2).

    Single loop over ``confirmed`` — action IDs track input order (a file_note
    before an edit_note_text yields link_to_moc, add_relationship, edit_note_text
    with ascending IDs). Every action is stamped applied=False (build_actions does
    this centrally; this assembler bypasses it, so it stamps here).
    """
    counter = counter or [0]
    out: list[dict] = []

    for c in confirmed:
        ga = c.get("garden_action")
        if ga == "edit_note_text":
            # Reuse the shared builder on a one-item list — wires in dead code
            # while keeping this item's action in input order.
            out.extend(_build_edit_note_text_actions([c], counter))
        elif ga == "remove_up_link":
            out.append({
                "id": _next_id(counter),
                "action": "remove_up_link",
                "path": c["path"],
                "link": c["link"],
            })
        elif ga == "resolve_dead_link":
            out.append({
                "id": _next_id(counter),
                "action": "resolve_dead_link",
                "path": c["path"],
                "target": c["target"],
                "replace": c["replace"],
            })
        elif ga == "add_relationship":
            out.append({
                "id": _next_id(counter),
                "action": "add_relationship",
                "target_moc": None,
                "target_moc_path": c["path"],
                "marker": "up::",
                "line": c["up_line"],
                "source_note_title": None,
            })
        elif ga == "file_note":
            target_moc = c.get("target_moc", "")
            out.append({
                "id": _next_id(counter),
                "action": "link_to_moc",
                "target_moc": target_moc,
                "target_moc_path": c.get("target_moc_path"),
                "anchor": {"type": "callout", "value": None},
                "placement": "after",
                "line_to_add": f"- [[{c['stem']}]]",
                # A garden item is already in the vault, so its on-disk stem is
                # both its display name and its key — no split is needed here.
                # source_note_stem is deliberately ABSENT (spec 034 T6.4b): the
                # withholding passes that join on it act on move_note /
                # create_moc, which this branch never emits, and this builder's
                # output goes to the wire WITHOUT _strip_internal_link_fields —
                # scripts/gen-garden-audit-hashi-example.py calls it directly
                # and embeds the result in a Hashi handoff document. An internal
                # field here reaches Hashi and its schema rejects the action.
                "source_note_title": c["stem"],
            })
            out.append({
                "id": _next_id(counter),
                "action": "add_relationship",
                "target_moc": target_moc,
                "target_moc_path": c["path"],
                "marker": "up::",
                "line": f"up:: [[{target_moc}]]",
                "source_note_title": None,
            })
        elif ga == "edit_frontmatter":
            # Reuse the shared builder on a one-item list — same pattern as
            # edit_note_text above, keeping this item's action in input order.
            out.extend(_build_edit_frontmatter_actions([c], counter, parent_marker))

    for a in out:
        a["applied"] = False
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
    parent_marker: str = "up::",
    peer_marker: str = "related::",
) -> tuple[list[dict], list[dict]]:
    """Assemble the full ordered action list.

    Returns (actions, skipped_assets) — skipped_assets are attachments that
    could not be filed (no basename, or a destination collision); see
    _build_move_asset_actions.

    Execution order matters: create_moc comes first because subsequent
    link_to_moc actions may target the newly-created MOCs (via supporting_items
    expansion). move_note follows, then attachments, then all links (parent_mocs
    + supporting items), then daily updates, deletions, and skips.

    Emitted order:
      1. create_moc         — new MOCs must exist before anything links into them
      2. up_preservation    — per-child up:: / related:: on ConfirmedMOCProposal children
      3. move_note          — atomic notes
      4. move_asset         — attachments named on the manifest, deduplicated globally
      5. link_to_moc        — parent_mocs up-links + supporting_items down-links
      6. update_tracker / update_log_entry / update_log_link
      7. insert_under_marker — approved tag-handler group blocks (spec 024 T4.1)
      8. delete_source      — incl. approved tag-handler group sources (after their insert)
      9. skip
    """
    counter = [0]
    inbox_path = cfg["concepts.inbox"]
    # cfg.get, not cfg[...]: concepts.asset is resolved with the same default
    # here as instruction-render.py's CONFIG_DEFAULTS, so a caller passing a
    # bare cfg dict without the key (as most existing tests do) still works.
    asset_folder = cfg.get("concepts.asset", DEFAULT_ASSET_FOLDER)
    out: list[dict] = []
    out.extend(_build_create_moc_actions(manifest, inbox_path, counter))
    out.extend(_build_up_preservation_actions(
        manifest, kado_client, counter,
        parent_marker=parent_marker, peer_marker=peer_marker,
    ))
    move_notes = _build_move_note_actions(manifest, inbox_path, counter)
    out.extend(move_notes)
    move_assets, skipped_assets = _build_move_asset_actions(
        manifest, inbox_path, asset_folder, counter
    )
    out.extend(move_assets)
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
    out = _aggregate_related_actions(out, kado_client, peer_marker)

    # Stamp the per-action applied flag. Tomo Hashi (the consumer) flips this
    # to true on successful execution; Tomo only ever emits false. See
    # docs/instructions-json.md.
    for a in out:
        a["applied"] = False
    return out, skipped_assets


