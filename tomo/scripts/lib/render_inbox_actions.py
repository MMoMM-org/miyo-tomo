# version: 0.1.0
"""render_inbox_actions.py — move_note, move_asset and daily-update action builders.

Split out of render_actions.py (#216, Constitution L2 file size). Owns the
actions that file an inbox item's content: the rendered note's move, the
moves of the attachments it embeds (projected from the attachment plan), and
the tracker / log-entry / log-link updates to daily notes. Each origin is
addressed by its item_key (ADR-1), never by a path rebuilt from a stem.
"""
from __future__ import annotations

from lib.attachment_plan import AttachmentPlan
from lib.render_emit import _inbox_join, _next_id, _origin_key
from lib.render_helpers import (
    _ensure_md_extension,
    _moc_stem,
    _stem,
    resolve_sibling_path,
    resolve_source_path,
)
from lib.vault_paths import _dest_join


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
    plan: AttachmentPlan,
    counter: list[int],
    inbox_path: str,
) -> tuple[list[dict], list[dict], dict[str, list[str]]]:
    """Project the attachment plan onto the rendered manifest.

    Returns ``(moves, skipped, move_ids_by_origin)``. Walks the manifest in
    order and visits each attachment path once (first appearance): a planned
    target becomes one ``move_asset`` with the next id; a withheld decision
    becomes its ``skipped_assets`` entry. Every outcome, reason and entry is
    the plan's (``lib.attachment_plan``) — nothing is decided here.

    A source the plan knows but no manifest entry embeds (its item did not
    render) emits nothing. A withheld entry names only the owners that
    rendered. ``move_ids_by_origin`` maps every owner the plan names to the
    ids of the moves it embeds. A manifest attachment the plan does not cover
    is a wiring error and raises ``ValueError``.
    """
    rendered_owners = {
        _ensure_md_extension(
            resolve_source_path(m.get("item_key"), m.get("source_path") or "", inbox_path)
            or None
        )
        for m in manifest
    }
    moves: list[dict] = []
    skipped: list[dict] = []
    move_ids_by_origin: dict[str, list[str]] = {}
    visited: set[str] = set()
    for m in manifest:
        for path in m.get("attachments") or []:
            if path in visited:
                continue
            visited.add(path)
            decision = plan.by_source.get(path)
            if decision is None:
                raise ValueError(
                    f"attachment {path!r} is not in the attachment plan — "
                    f"the plan must be built from the items that rendered it"
                )
            if decision.withheld is not None:
                entry = dict(decision.withheld)
                entry["owner_source_items"] = [
                    o for o in entry["owner_source_items"] if o in rendered_owners
                ]
                skipped.append(entry)
                continue
            move_id = _next_id(counter)
            moves.append({
                "id": move_id,
                "action": "move_asset",
                "source": path,
                "destination": decision.target,
            })
            for owner in decision.owners:
                move_ids_by_origin.setdefault(owner, []).append(move_id)
    return moves, skipped, move_ids_by_origin


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
    # Defensive: vault-config values are not trusted (established by
    # shared-ctx-builder.py's same-key read). A trailing space after a
    # trailing slash survives a bare .rstrip("/"), leaving the slash in
    # place and producing a double-separator path that never matches a
    # real note. Strip whitespace first, then strip any run of trailing
    # slashes/spaces — order matters, see docs/tomo counterpart.
    base = (daily_path_cfg or "Calendar/301 Daily/").strip().rstrip("/ ")
    return f"{base}/{date}.md"


def _build_daily_update_actions(
    daily_updates: list[dict],
    cfg: dict,
    counter: list[int],
    inbox_path: str,
) -> tuple[list[dict], dict[str, list[str]]]:
    """Emit tracker / log_entry / log_link actions for accepted daily updates.

    Returns (actions, ids_by_origin). `ids_by_origin` maps each origin's
    `_origin_key` (the resolved-path join spec 034 T5.0b established) to the
    ids of every accepted daily action built from that origin, across every
    bucket and day — site 2 of `_build_delete_source_actions` uses this to
    populate `depends_on` on its daily-only deletes (spec 036 T1.2).
    """
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
    ids_by_origin: dict[str, list[str]] = {}

    def _remember(entry: dict, action_id: str) -> None:
        key = _origin_key(resolve_source_path(
            entry.get("source_item_key"), entry.get("source_stem"), inbox_path
        ))
        if key:
            ids_by_origin.setdefault(key, []).append(action_id)

    for day in daily_updates:
        date = day.get("date", "")
        note_path = _resolve_daily_path(daily_path_cfg, date, day.get("daily_note_path"))
        for tr in day.get("trackers", []) or []:
            if not tr.get("accepted"):
                continue
            configured = tracker_fields.get(tr.get("field", "")) or {}
            action_id = _next_id(counter)
            out.append({
                "id": action_id,
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
            _remember(tr, action_id)
        for le in day.get("log_entries", []) or []:
            if not le.get("accepted"):
                continue
            action_id = _next_id(counter)
            out.append({
                "id": action_id,
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
            _remember(le, action_id)
        for ll in day.get("log_links", []) or []:
            if not ll.get("accepted"):
                continue
            action_id = _next_id(counter)
            out.append({
                "id": action_id,
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
            _remember(ll, action_id)
    return out, ids_by_origin
