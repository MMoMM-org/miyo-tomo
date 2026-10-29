# version: 0.1.0
"""render_moc_actions.py — create_moc, link_to_moc and extend_moc action builders.

Split out of render_actions.py (#216, Constitution L2 file size). Owns every
action that creates a MOC or writes a bullet into one: create_moc from the
rendered manifest, link_to_moc from parent_mocs / supporting_items, and the
extend_moc expansion (add_relationship + link_to_moc per member, with one
Kado `outgoing` read to skip members the MOC already links).
"""
from __future__ import annotations

from lib.kado_client import KadoError
from lib.obsidian_filename import sanitize_stem
from lib.render_emit import _inbox_join, _next_id, _wikilink
from lib.render_helpers import _moc_stem, _stem, exact_stem_paths
from lib.render_up_preservation import emit_up_preservation_actions
from lib.supporting_items import (
    parse_supporting_items as _parse_supporting_items,
    union_supporting_items as _union_supporting_items,
)
from lib.vault_paths import _dest_join, path_key


def _link_key(text: str) -> str:
    """Normalise a wikilink target or vault path for comparison, as Obsidian does."""
    key = text.split("|", 1)[0].split("#", 1)[0].strip()
    if key.lower().endswith(".md"):
        key = key[:-3]
    return key.casefold()


def _build_create_moc_actions(
    manifest: list[dict],
    inbox_path: str,
    counter: list[int],
) -> list[dict]:
    """Emit create_moc actions for rendered MOCs. MUST run before move_note and
    link_to_moc so IDs for new MOCs precede anything that links into them.
    """
    out: list[dict] = []
    # path_key(destination) (NFC + case) -> the action that claimed it (T6.0,
    # W7). The key normalises; the action it holds keeps its author's spelling.
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
        # Compared by path_key, NFC + case (CON-6, spec 034 T6.0, 039 W7):
        # `Travel (MOC)` and `travel (MOC)` — or an NFC/NFD pair — are one file
        # on this filesystem, and the parser's by-Name merge is exact so such a
        # pair reaches here intact.
        existing = by_dest.get(path_key(destination))
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
        by_dest[path_key(destination)] = action
        out.append(action)
    return out


def _link_to_moc_action(
    counter: list[int], target_moc: str, source_title: str,
    anchor: dict | None = None,
) -> dict:
    """One link_to_moc action: a `- [[source_title]]` bullet into `target_moc`."""
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
    return {
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
    }


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
        out.append(_link_to_moc_action(counter, target_moc, source_title, anchor))

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


def _moc_linked_members(kado_client, moc_path: str | None, members: list[str]) -> list[str] | None:
    """Members the MOC links, from one `outgoing(moc)` call; None when it could not be asked."""
    if not moc_path:
        return None
    try:
        nodes = kado_client.graph("outgoing", moc_path)
    except KadoError:
        return None
    keys: set[str] = set()
    for node in nodes:
        resolved = _link_key(node.get("path", ""))
        keys.update({resolved, resolved.rsplit("/", 1)[-1]})
    return [m for m in members if _link_key(m) in keys]


def _build_moc_extension_actions(
    confirmed: list[dict],
    kado_client,
    counter: list[int],
    reports: list[dict],
    parent_marker: str = "up::",
    peer_marker: str = "related::",
) -> list[dict]:
    """Expand each extend_moc item into add_relationship + link_to_moc actions.

    Per ticked member: emit_up_preservation_actions(member, moc, override).
    Per member the MOC does not already link: one `- [[member]]` link_to_moc.
    Appends one record per extension to `reports`.
    """
    if kado_client is None:
        return []
    out: list[dict] = []
    for item in confirmed:
        if item.get("action") != "extend_moc":
            continue
        moc = _moc_stem(item.get("target_moc") or "")
        members = []
        seen: set[str] = set()
        for m in _parse_supporting_items(item.get("supporting_items")):
            if m.casefold() not in seen:
                seen.add(m.casefold())
                members.append(m)
        if not moc or not members:
            continue
        override = bool(item.get("override_preserve_existing_up", False))
        no_relationship: list[dict] = []
        for member in members:
            emitted = emit_up_preservation_actions(
                member, moc, override, kado_client, counter,
                parent_marker=parent_marker, peer_marker=peer_marker,
            )
            if not emitted:
                no_relationship.append({"member": member, "cause": "up-already-points-to-moc"})
            elif emitted[0].get("error"):
                no_relationship.append({"member": member, "cause": emitted[0]["error"]})
            out.extend(emitted)
        moc_path = item.get("target_moc_path")
        if not moc_path:
            try:
                paths = exact_stem_paths(kado_client.search_by_name(moc), moc)
            except KadoError:
                paths = []
            moc_path = paths[0] if len(paths) == 1 else None
        linked = _moc_linked_members(kado_client, moc_path, members)
        for member in members:
            if linked is None or member not in linked:
                link = _link_to_moc_action(counter, moc, member)
                link["target_moc_path"] = moc_path
                out.append(link)
        reports.append({
            "id": item.get("id"),
            "target_moc": moc,
            "target_moc_path": moc_path,
            "members": members,
            "already_linked": linked or [],
            "outgoing_checked": linked is not None,
            "no_relationship": no_relationship,
        })
    return out
