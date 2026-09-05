# version: 0.8.2
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
from lib.render_helpers import _moc_stem, _stem
from lib.render_md import bare_stem
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
    out.extend(_build_up_preservation_actions(
        manifest, kado_client, counter,
        parent_marker=parent_marker, peer_marker=peer_marker,
    ))
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
    out = _aggregate_related_actions(out, kado_client, peer_marker)

    # Stamp the per-action applied flag. Tomo Hashi (the consumer) flips this
    # to true on successful execution; Tomo only ever emits false. See
    # docs/instructions-json.md.
    for a in out:
        a["applied"] = False
    return out



