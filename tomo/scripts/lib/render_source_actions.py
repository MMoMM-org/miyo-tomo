# version: 0.1.0
"""render_source_actions.py — tag-handler insert and delete_source action builders.

Split out of render_actions.py (#216, Constitution L2 file size). Owns the two
builders that act on inbox sources once their content has been carried
elsewhere: insert_under_marker for approved tag-handler groups, and
delete_source from all four of its sites. They live together because both
consult one target-resolvability gate, which must stay a single module
attribute so one patch reaches both call sites (ADR-5).
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from lib.render_emit import _next_id, _origin_key
from lib.render_helpers import _ensure_md_extension, resolve_source_path

logger = logging.getLogger(__name__)


# tag-handler-group.py is a hyphenated top-level script in the scripts dir (not a
# lib module); load it via importlib for the stable group_id slug (spec 024 T4.1).
# Path is resolved relative to this module: scripts/lib/render_source_actions.py → scripts/.
import importlib.util as _ilu

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_thg_spec = _ilu.spec_from_file_location(
    "tag_handler_group", str(_SCRIPTS_DIR / "tag-handler-group.py")
)
_thg_mod = _ilu.module_from_spec(_thg_spec)
sys.modules["tag_handler_group"] = _thg_mod
_thg_spec.loader.exec_module(_thg_mod)
group_id = _thg_mod.group_id


def _tag_handler_group_has_resolvable_target(group: dict) -> bool:
    """Target-resolvability gate for a tag-handler group (spec 036 T3.1/ADR-5).

    Tests the sole condition that must agree between the insert builder
    (line ~1913) and the delete loop (site 4, line ~1799): whether the
    group's `target_path` resolved to something non-empty. Approval and
    "Keep source files" filtering are NOT part of this predicate; each call
    site keeps that filtering exactly where it already lives, since the two
    sites' approval/keep filters are not identical (the delete loop also
    honors keep_source_group_ids; the insert builder does not).
    """
    return bool(group.get("target_path"))


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
    daily_action_ids_by_origin: dict[str, list[str]] | None = None,
    insert_action_ids_by_group: dict[str, str] | None = None,
    move_ids_by_origin: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Emit delete_source actions from four sources:

    1. `skipped[]` entries where the user explicitly checked "Delete source"
       (disposition == "delete_source").
    2. Daily-only items — origins that appear in accepted daily_updates but
       have no matching confirmed_item (content fully captured in the daily
       note, no atomic note will be created). Each such delete carries
       `depends_on` (spec 036 T1.2): the ids of every accepted daily action
       built from that origin, looked up in `daily_action_ids_by_origin` (the
       map `_build_daily_update_actions` returns) by the same `_origin_key`
       this site already computes.
    3. move_note origins — for every move_note action whose corresponding
       confirmed item did NOT opt out via "Keep source files", emit a paired
       delete_source for the origin inbox item. Audio + transcript peer
       pairs ARE included here: one paired delete_source per unique audio
       peer, naming the same move ids as the origin delete.
       Every delete from sites 1 and 3 carries `depends_on` (spec 036 T1.1):
       site 1 has no partner action and declares `depends_on: []`; site 3
       names the ids of every move_note for that origin, then the ids of the
       move_asset actions for the attachments that origin embeds (spec 039
       ADR-10, looked up in `move_ids_by_origin` by the origin's path), and the
       audio-peer delete names the same id list as its origin delete.
    4. Tag-handler group sources — for every APPROVED group not opted out via
       "Keep source files", one delete_source per `source_path`. The group's
       insert_under_marker (emitted earlier) copies the captures into the
       target note, so the inbox sources are now redundant. Parity with (3),
       but keyed by group_id rather than origin note.
       Every delete from site 4 carries `depends_on` (spec 036 T1.3): the id
       of that group's insert_under_marker action, looked up in
       `insert_action_ids_by_group` (the map `_build_insert_under_marker_actions`
       returns) by `group_id(group)`. A group reaches this loop only after
       passing `_tag_handler_group_has_resolvable_target` (the same gate the
       insert builder applies), so the map always has an entry here.
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
            "depends_on": [],
        })

    # (2) Daily-only origins
    # WHY: daily_action_ids_by_origin is the map _build_daily_update_actions
    # returns, bucketing action ids by origin key. Omitting it (None → {})
    # silently produces depends_on: [] for site-2 deletes — which asserts
    # "delete unconditionally". That is safe ONLY because build_actions (the
    # sole production path) always threads the real map. Direct callers
    # exercising daily-only deletes must supply it; two test callers omit it
    # and pass only because they do not assert on depends_on.
    daily_action_ids_by_origin = daily_action_ids_by_origin or {}
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
                # depends_on names every daily action built from this origin —
                # the ids _build_daily_update_actions already bucketed under
                # the same key. Populated here, before any guard runs
                # (SDD/Implementation Gotchas): a builder that adds it
                # afterwards reintroduces the ordering bug spec 036 fixes.
                out.append({
                    "id": _next_id(counter),
                    "action": "delete_source",
                    "source_path": full,
                    "reason": "Content fully captured in daily note.",
                    "depends_on": list(daily_action_ids_by_origin.get(key, [])),
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

    asset_ids_by_key = {
        _origin_key(owner): ids for owner, ids in (move_ids_by_origin or {}).items()
    }
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
        # depends_on names every move_note for this origin — the ids the
        # completion gate above already bucketed. Populated here, before any
        # guard runs (SDD/Implementation Gotchas): a builder that adds it
        # afterwards reintroduces the ordering bug spec 036 fixes.
        # Then the move_asset ids of the attachments this origin embeds, in the
        # move builder's emission order (spec 039 ADR-10): the delete must not
        # outlive the files its notes still point at.
        move_ids = [mn["id"] for mn in moves]
        move_ids += asset_ids_by_key.get(origin_key, [])
        out.append({
            "id": _next_id(counter),
            "action": "delete_source",
            "source_path": origin_path,
            "reason": reason,
            "depends_on": move_ids,
        })
        # Paired audio peer delete — one delete per unique audio peer for this
        # origin note. Normally 0 or 1 peer; set deduplicates the multi-atomic
        # case (two atomics from one transcript share the same peer path).
        # keep_source_keys and the gate both apply above, so arriving here
        # means both deletes are appropriate. Empty set → no audio delete (fail-safe).
        # The audio-peer delete names the SAME move ids as the origin delete —
        # they are separate actions hanging off the same move set; naming
        # only one leaves the other unguarded (SDD/Implementation Gotchas).
        audio_peers = {mn.get("audio_peer") for mn in moves if mn.get("audio_peer")}
        for ap in sorted(audio_peers):
            out.append({
                "id": _next_id(counter),
                "action": "delete_source",
                "source_path": ap,
                "reason": "Audio peer of consumed origin.",
                "depends_on": list(move_ids),
            })

    # (4) Tag-handler group sources — one delete per source_path of each
    # APPROVED group, unless the group opted out via "Keep source files".
    approved_groups = set(approved_tag_handler_group_ids or [])
    kept_groups = set(keep_source_group_ids or [])
    insert_action_ids_by_group = insert_action_ids_by_group or {}
    emitted: set[str] = {a["source_path"] for a in out}
    for group in (tag_handler_groups or []):
        gid = group_id(group)
        if gid not in approved_groups or gid in kept_groups:
            continue
        if not _tag_handler_group_has_resolvable_target(group):
            # Shared gate with insert builder (line ~1913, ADR-5): both must
            # agree that target_path is resolvable before proceeding.
            continue
        target = group.get("target_path") or ""
        handler = group.get("handler") or ""
        # depends_on names the insert_under_marker built for THIS group — the
        # id _build_insert_under_marker_actions bucketed under the same gid.
        # This gate (approved + resolvable target) mirrors the insert builder's
        # own gate, so the map is expected to have an entry here. If it doesn't
        # — a refactor, a partial-groups call, anything that breaks the mirror
        # — this delete has lost its justification and must be withheld, not
        # emitted with an empty depends_on (fail-safe, matching the audio-peer
        # branch above).
        insert_id = insert_action_ids_by_group.get(gid)
        if not insert_id:
            logger.warning(
                "tag-handler group %s has no insert action (target_path=%s); "
                "withholding its delete_source actions",
                gid,
                target,
            )
            continue
        depends_on = [insert_id]
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
                "depends_on": list(depends_on),
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
) -> tuple[list[dict], dict[str, str]]:
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

    Returns `(actions, insert_action_ids_by_group)` (spec 036 T1.3): the second
    element maps each emitted group's `group_id(group)` to the id of the
    insert_under_marker action built for it. The delete loop (site 4) is the
    consumer — it names this id in `depends_on` so a delete never outlives the
    insert that justifies it. A group that produces no action (not approved, or
    unresolvable target) has no entry in the map.
    """
    if not groups or not approved_group_ids:
        return [], {}
    approved = set(approved_group_ids)
    out: list[dict] = []
    insert_action_ids_by_group: dict[str, str] = {}
    for group in groups:
        gid = group_id(group)
        if gid not in approved:
            continue
        if not _tag_handler_group_has_resolvable_target(group):
            # Shared gate with delete loop (site 4, line ~1799, ADR-5): both
            # must agree that target_path is resolvable before proceeding.
            continue
        target_path = group.get("target_path")

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

        action_id = _next_id(counter)
        out.append({
            "id": action_id,
            "action": "insert_under_marker",
            "target_path": target_path,
            "anchor": anchor,
            "placement": placement,
            "content": content,
        })
        # Last-write-wins on gid collision: an upstream duplicate group id
        # would silently route a delete to a sibling group's insert. Nothing
        # in this pipeline de-duplicates group ids, so this is not guarded.
        insert_action_ids_by_group[gid] = action_id
    return out, insert_action_ids_by_group
