# version: 0.1.0
"""instructions_diff_expected.py — both sides of the Pass-2 coverage comparison.

Extracted from instructions-diff.py (#216). `derive_expected` re-derives what
the renderer should have emitted from parsed-suggestions.json alone, and
`summarize_actual` flattens instructions.json into the same shape. They sit
together because they must agree on shape and key conventions; the
subtractions that reconcile them live in instructions_diff_reconcile.
"""
from __future__ import annotations

import importlib.util as _ilu
import sys
from pathlib import Path

from lib.instructions_diff_keys import (
    _bullet_titles,
    _confirmed_key,
    _daily_key,
    _moc_stem,
    _parse_supporting_items,
    _same_note_as_any,
    _stem,
    _unique_members,
)
from lib.item_key import derive as _item_key

# tag-handler-group.py is a hyphenated top-level script; load it via importlib
# for the stable group_id slug (spec 024 T4.1) — the SAME id the renderer keys
# its tag-handler delete_source actions on, so coverage matching stays aligned.
# Path is resolved relative to this module: scripts/lib/ → scripts/.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_thg_spec = _ilu.spec_from_file_location(
    "tag_handler_group", str(_SCRIPTS_DIR / "tag-handler-group.py")
)
_thg_mod = _ilu.module_from_spec(_thg_spec)
sys.modules["tag_handler_group"] = _thg_mod
_thg_spec.loader.exec_module(_thg_mod)
group_id = _thg_mod.group_id


# ──────────────────────────────────────────────────────────────────────────────
# Expected-action derivation from parsed-suggestions.json
# Mirrors scripts/instruction-render.py:build_actions (without the renderer)
# so the diff has an independent source of truth for the count math.
# ──────────────────────────────────────────────────────────────────────────────

def derive_expected(parsed: dict, tag_handler_groups: list[dict] | None = None) -> dict:
    """Derive expected action counts & per-item coverage from parsed suggestions.

    Returns:
      {
        "counts": {kind: int},
        "by_item": {item_id: {"kind": "move_note"|"create_moc",
                              "title": str,
                              "expected_links": [moc_stem, ...],
                              "item_key": str}},
        "expected_daily_kinds": [
            {"kind": "update_tracker", "date", "value", "source_stem"},
            {"kind": "update_log_entry", "date", "source_stem"},
            {"kind": "update_log_link", "date", "source_stem"},
        ],
        # No "key" on any of the three (removed 2026-09-11): matching below
        # is by "kind" alone (_subtract_skipped_daily) — "key"'s value was
        # never read on any of them, whether it held a tracker field name
        # (update_tracker), a note stem (update_log_link), or 40 characters
        # of the note's own content (update_log_entry — the one with an
        # actual privacy concern, MiYo Constitution L2). Removed uniformly
        # rather than only the risky one: leaving two "key"s present and one
        # absent would be an inconsistently populated structure with no
        # reason a future reader could reconstruct, for a field that carried
        # zero benefit in any of the three cases.
        "expected_deletions": [source_path],
        "expected_skips": [source_path_or_None],
      }
    """
    confirmed = parsed.get("confirmed_items") or []
    daily_updates = parsed.get("daily_updates") or []
    skipped = parsed.get("skipped") or []

    counts: dict[str, int] = {
        "move_note": 0,
        "move_asset": 0,
        "create_moc": 0,
        "link_to_moc": 0,
        "update_tracker": 0,
        "update_log_entry": 0,
        "update_log_link": 0,
        "delete_source": 0,
        "skip": 0,
        "edit_frontmatter": 0,
    }

    by_item: dict[str, dict] = {}
    id_index: dict[str, dict] = {}
    extensions: list[dict] = []
    for item in confirmed:
        item_id = item.get("id", "?")
        id_index[item_id] = item
        if item.get("action") == "extend_moc":
            # No file action: one link per member until the renderer's
            # already-linked record is subtracted (_reconcile_extensions).
            members = _unique_members(
                _parse_supporting_items(item.get("supporting_items"))
            )
            extensions.append({
                "id": item_id,
                "target_moc": _moc_stem(item.get("target_moc")),
                "members": members,
            })
            counts["link_to_moc"] += len(members)
            continue
        parents = item.get("parent_mocs") or []
        if not parents and item.get("parent_moc"):
            parents = [item["parent_moc"]]
        parent_stems = [_moc_stem(p) for p in parents if p]
        title = item.get("title") or _stem(item.get("source_path"))
        if item.get("action") == "create_moc":
            counts["create_moc"] += 1
            by_item[item_id] = {
                "kind": "create_moc",
                "title": title,
                "expected_links": parent_stems,
                "item_key": _confirmed_key(item),
                "supporting_items": item.get("supporting_items"),
            }
        else:
            counts["move_note"] += 1
            by_item[item_id] = {
                "kind": "move_note",
                "title": title,
                "expected_links": parent_stems,
                "item_key": _confirmed_key(item),
            }
        counts["link_to_moc"] += len(parent_stems)

    # Supporting_items down-links: each create_moc pulls its supporting items
    # as children. Mirror the renderer's dedupe so our expected count matches.
    link_keys: set[tuple[str, str]] = set()
    for item in confirmed:
        parents = item.get("parent_mocs") or []
        if not parents and item.get("parent_moc"):
            parents = [item["parent_moc"]]
        if item.get("action") == "create_moc":
            src_title = item.get("title", "")
        else:
            src_title = item.get("title") or _stem(item.get("source_path"))
        for p in parents:
            link_keys.add((_moc_stem(p), src_title))
    # Now supporting_items — these add NEW keys beyond parent_mocs.
    supporting_added = 0
    for item in confirmed:
        if item.get("action") != "create_moc":
            continue
        new_moc_title = item.get("title", "")
        for sid in _parse_supporting_items(item.get("supporting_items")):
            sup = id_index.get(sid)
            if not sup or sup.get("action") == "create_moc":
                continue
            sup_title = sup.get("title") or _stem(sup.get("source_path"))
            if not sup_title:
                continue
            key = (new_moc_title, sup_title)
            if key not in link_keys:
                link_keys.add(key)
                supporting_added += 1
                # Track expected link on the supporting item for per-item coverage
                by_item[sid]["expected_links"].append(new_moc_title)
    counts["link_to_moc"] += supporting_added

    expected_daily: list[dict] = []
    for day in daily_updates:
        date = day.get("date")
        for t in day.get("trackers") or []:
            if not t.get("accepted"):
                continue
            counts["update_tracker"] += 1
            expected_daily.append({
                "kind": "update_tracker",
                "date": date,
                "value": t.get("value"),
                "source_stem": _stem(t.get("source_stem")),
            })
        for le in day.get("log_entries") or []:
            if not le.get("accepted"):
                continue
            counts["update_log_entry"] += 1
            # No "key" on this or its two sibling appends — see derive_expected's
            # docstring ("expected_daily_kinds"): unread on all three, and this
            # one held the note's own content (MiYo Constitution L2).
            expected_daily.append({
                "kind": "update_log_entry",
                "date": date,
                "source_stem": _stem(le.get("source_stem")),
            })
        for ll in day.get("log_links") or []:
            if not ll.get("accepted"):
                continue
            counts["update_log_link"] += 1
            expected_daily.append({
                "kind": "update_log_link",
                "date": date,
                "source_stem": _stem(ll.get("source_stem", "")),
            })

    # Delete source has four sources:
    #   1. explicit skipped[] disposition=delete_source
    #   2. daily-only inferences (source_stem in daily_updates but not confirmed)
    #   3. paired with move_note: confirmed atomic notes default to deleting
    #      their inbox origin unless the user opted out via "Keep source files".
    #   4. tag-handler group sources: each APPROVED group (not "Keep source files")
    #      deletes every consolidated inbox source (instruction-render branch 4).
    # The daily-only suppression joins daily entries against confirmed items,
    # and both describe an inbox note that two notes can now share a filename
    # with (recursive discovery, Phase 3). It therefore joins on the note's
    # identity (ADR-1), matching the emitter, which keys this same suppression
    # on the resolved vault-relative path. Membership is `_same_note_as_any`,
    # not a set lookup: the mixed keyed/keyless input a set splits still names
    # one note.
    confirmed_keys = [_confirmed_key(it) for it in confirmed if it.get("source_path")]
    expected_deletions: list[str] = []
    for sk in skipped:
        if sk.get("disposition") == "delete_source":
            expected_deletions.append(_stem(sk.get("source_path")))
    # Daily-only: accepted daily items naming no confirmed note. The appended
    # VALUE stays the bare stem, as sources 1, 3 and 4 append theirs — the
    # tag-handler dedup below reads these values as stems.
    daily_only_keys: list[str] = []
    for day in daily_updates:
        for bucket in ("trackers", "log_entries", "log_links"):
            for entry in day.get(bucket) or []:
                if not entry.get("accepted"):
                    continue
                key = _daily_key(entry)
                if not key or _same_note_as_any(key, confirmed_keys):
                    continue
                if _same_note_as_any(key, daily_only_keys):
                    continue
                daily_only_keys.append(key)
                expected_deletions.append(_stem(key))
    # Paired with move_note: every confirmed atomic note with a source_path
    # AND keep_source=False expects a paired delete on its origin. Dedup on
    # the item_key (the full source_path, ADR-1), not the bare stem — two
    # confirmed items sharing a filename in different subfolders are two
    # distinct origins, each owed its own paired delete; a stem-keyed dedup
    # would drop the second one's expected deletion silently.
    paired_origins_seen: set[str] = set()
    audio_peers_seen: set[str] = set()
    for item in confirmed:
        if item.get("action") == "create_moc":
            continue
        if item.get("keep_source"):
            continue
        sp = item.get("source_path")
        if not sp:
            continue
        key = _confirmed_key(item)
        if key not in paired_origins_seen:
            paired_origins_seen.add(key)
            expected_deletions.append(_stem(sp))
        # Voice source set (spec 027 ADR-1): a confirmed non-kept item with an
        # audio_peer expects a SECOND paired delete for the audio file. The
        # renderer emits one audio delete_source per origin stem group; mirror it
        # here (deduped per peer) so the coverage count reconciles instead of
        # flagging a false mismatch on every voice item.
        peer = item.get("audio_peer")
        if peer and peer not in audio_peers_seen:
            audio_peers_seen.add(peer)
            expected_deletions.append(peer)
    # (4) tag-handler group sources — one expected delete per source_path of
    # each approved, non-kept group. Keyed by the same group_id the renderer
    # uses; deduped against sources 1-3 to mirror the renderer's emit dedup.
    approved_groups = set(parsed.get("approved_tag_handler_group_ids") or [])
    kept_groups = set(parsed.get("tag_handler_keep_source_group_ids") or [])
    th_seen = set(expected_deletions)
    for group in (tag_handler_groups or []):
        gid = group_id(group)
        if gid not in approved_groups or gid in kept_groups:
            continue
        for sp in group.get("source_paths") or []:
            stem = _stem(sp)
            if stem in th_seen:
                continue
            th_seen.add(stem)
            expected_deletions.append(stem)
    counts["delete_source"] = len(expected_deletions)

    # Attachment moves (spec 031 ADR-5/ADR-6): mirror the renderer's GLOBAL
    # dedup (render_actions._build_move_asset_actions spans the whole
    # manifest, not a per-item loop) and key on the resolved path, not the
    # basename, so this stays in lockstep with the renderer's own dedup key.
    # create_moc items carry no attachments; an attachment is never appended
    # to expected_deletions — filing is the audio_peer's exact inversion.
    attachments_seen: set[str] = set()
    for item in confirmed:
        if item.get("action") == "create_moc":
            continue
        for path in item.get("attachments") or []:
            attachments_seen.add(path)
    counts["move_asset"] = len(attachments_seen)

    expected_skips: list[str] = []
    for sk in skipped:
        if sk.get("disposition") == "skip":
            expected_skips.append(_stem(sk.get("source_path")))
    counts["skip"] = len(expected_skips)

    return {
        "counts": counts,
        "by_item": by_item,
        "expected_daily": expected_daily,
        "expected_deletions": expected_deletions,
        "expected_skips": expected_skips,
        "extensions": extensions,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Actual-action summarization from instructions.json
# ──────────────────────────────────────────────────────────────────────────────

def summarize_actual(instrs: dict) -> dict:
    """Flatten the actual action list into the same shape used for diff.

    link_to_moc is counted as (note, MOC) pairs (one per bullet/source note),
    not as raw action count, so #70-batched actions reconcile per merged note.
    """
    actions = instrs.get("actions") or []
    counts: dict[str, int] = {}
    for a in actions:
        counts[a["action"]] = counts.get(a["action"], 0) + 1

    move_by_key: dict[str, dict] = {}
    create_mocs: list[dict] = []
    links_by_source: dict[str, list[str]] = {}
    # link_to_moc COVERAGE is counted as (note, MOC) pairs, not raw actions: a
    # #70-batched action merges several notes under one (target_moc, new_section),
    # so it covers one pair per bullet. This keeps the count table reconciling
    # with the expected pair count and credits each merged note in per-item.
    link_pairs = 0
    for a in actions:
        kind = a["action"]
        if kind == "move_note":
            # Match by the item_key of source_inbox_item (traceability field);
            # falls back to rendered_file if source wasn't captured. Keying on
            # the full path (not the bare stem) keeps two same-named items in
            # different subfolders from collapsing onto one dict entry — see
            # _keys_match for how this reconciles with a bare-name origin's
            # inbox-joined prefix.
            raw_origin = a.get("source_inbox_item") or a.get("rendered_file")
            key = _item_key(raw_origin) if raw_origin else ""
            move_by_key[key] = a
        elif kind == "create_moc":
            create_mocs.append(a)
        elif kind == "link_to_moc":
            target = _moc_stem(a.get("target_moc"))
            src = a.get("source_note_title")
            if src:
                links_by_source.setdefault(src, []).append(target)
                link_pairs += 1
            else:
                bullets = _bullet_titles(a.get("line_to_add"))
                for note_title in bullets:
                    links_by_source.setdefault(note_title, []).append(target)
                    link_pairs += 1
                if not bullets:
                    links_by_source.setdefault("", []).append(target)
                    link_pairs += 1
    counts["link_to_moc"] = link_pairs

    # Daily actions — bucket by kind
    daily_by_kind: dict[str, list[dict]] = {
        "update_tracker": [],
        "update_log_entry": [],
        "update_log_link": [],
    }
    for a in actions:
        if a["action"] in daily_by_kind:
            daily_by_kind[a["action"]].append(a)

    deletes = [a.get("source_path") for a in actions if a["action"] == "delete_source"]
    skips = [a.get("source_path") for a in actions if a["action"] == "skip"]

    return {
        "counts": counts,
        "move_by_key": move_by_key,
        "create_mocs": create_mocs,
        "links_by_source": links_by_source,
        "daily_by_kind": daily_by_kind,
        "deletes": deletes,
        "skips": skips,
    }
