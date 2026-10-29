# version: 0.34.0
"""render_actions.py — instruction-set action builders (public facade).

Extracted from instruction-render.py (#42, D-07 Constitution L2 split). Turns the
rendered manifest + confirmed items + daily/skip inputs into the ordered list of
machine-readable actions (create_moc, move_note, link_to_moc, add_relationship,
update_*, delete_source, skip). build_actions() is the entry point and stays
here with the emit-time path and dependency audits; each action kind's builder
lives in a sibling module (#216) and every name is re-exported from here, so
`from lib.render_actions import X` keeps working for every caller. The
skip builder stays here: it resolves an item by item_key in one line.
Pure assembly plus a few Kado reads (passed the client as an argument) for
up:: preservation — no rendering, no post-build resolution (that lives in
render_resolve).
"""
from __future__ import annotations

import re

from lib.kado_client import KadoError  # noqa: F401 — re-exported (#216)
from lib.obsidian_filename import sanitize_stem  # noqa: F401 — re-exported (#216)
from lib.profile_conventions import marker_word  # noqa: F401 — re-exported (#216)
from lib.render_helpers import (  # noqa: F401 — re-exported (spec 039 T4.3, #216)
    _ensure_md_extension,
    _moc_stem,
    _stem,
    exact_stem_paths,
    resolve_sibling_path,
    resolve_source_path,
)
from lib.render_md import bare_stem  # noqa: F401 — re-exported (#216)
from lib.refusal_sentences import withheld_attachment_remedy  # noqa: F401 — re-exported (#216)
from lib.attachment_plan import AttachmentPlan, build_attachment_plan  # noqa: F401 — re-exported (#216)
from lib.vault_folder_lookup import VaultFolderLookup  # noqa: F401 — re-exported (#216)
from lib.vault_paths import _asset_dest_join, _dest_join, path_key, same_spelling  # noqa: F401 — _asset_dest_join/_dest_join re-exported (spec 039 T1.4)
from lib.source_link import colliding_names, qualified_target  # noqa: F401 — re-exported (#216)
from lib.up_parse import up_marker_re as _up_marker_re  # noqa: F401 — re-exported (#216)
from lib.supporting_items import (  # noqa: F401 — re-exported (#216)
    parse_supporting_items as _parse_supporting_items,
    union_supporting_items as _union_supporting_items,
)
from lib.render_emit import (  # noqa: F401 — re-exported (#216)
    _disambiguate_filename,
    _inbox_join,
    _next_id,
    _origin_key,
    _wikilink,
)
from lib.render_up_preservation import (  # noqa: F401 — re-exported (#216)
    _WIKILINK_RE,
    _aggregate_related_actions,
    _build_up_preservation_actions,
    _extract_existing_related,
    _make_add_rel,
    _related_marker_re,
    emit_up_preservation_actions,
    extract_first_up_marker,
)
from lib.render_moc_actions import (  # noqa: F401 — re-exported (#216)
    _build_create_moc_actions,
    _build_link_to_moc_actions,
    _build_moc_extension_actions,
    _link_key,
    _link_to_moc_action,
    _moc_linked_members,
)
from lib.render_garden_actions import (  # noqa: F401 — re-exported (#216)
    UnsupportedShapeError,
    _build_edit_frontmatter_actions,
    _build_edit_note_text_actions,
    _construct_edit_frontmatter_fields,
    build_garden_audit_actions,
)
from lib.render_inbox_actions import (  # noqa: F401 — re-exported (#216)
    _build_daily_update_actions,
    _build_move_asset_actions,
    _build_move_note_actions,
    _resolve_daily_path,
)
from lib.render_source_actions import (  # noqa: F401 — re-exported (#216)
    _build_delete_source_actions,
    _build_insert_under_marker_actions,
    _load_tag_handler_groups,
    _marker_to_anchor_value,
    _tag_handler_group_has_resolvable_target,
    group_id,
)
from lib.render_withhold import (  # noqa: F401 — re-exported (#216)
    _CASE_NOTE,
    _COUNT_WORDS,
    _destination_clash_reason,
    _drop_moves_with_paired_deletes,
    _links_for,
    _orphaned_link_targets,
    _orphaned_link_titles,
    _paired_delete_candidates,
    _unique_in_order,
    make_folder_listing,
    validate_destinations,
    withdraw_unjustified_deletes,
)


# Path-shape contract (Hashi-driven, 2026-04-26 handoff): every path field
# emitted into instructions.json must be vault-relative, absolute within the
# vault, forward-slash separated, control-char free, and free of plugin
# aliases. Hashi's executor refuses non-conforming paths with cryptic
# `Path escapes vault root` / `path-symlink-escape` errors; catching them at
# emit time produces actionable Tomo-side diagnostics instead.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


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


def assert_no_dangling_dependencies(actions: list[dict]) -> list[str]:
    """Audit that every id a `delete_source` names in `depends_on` exists in
    this same action set (spec 036 Feature 5, PRD F5-AC4).

    Producer-side tripwire, not a live filter: under ADR-1,
    `withdraw_unjustified_deletes` already withdraws any `delete_source` whose
    `depends_on` is missing/``None`` or names an id absent from the surviving
    set (SDD Error Handling Criteria), so this audit is expected to be vacuous
    on every real run — a violation here means an unknown-shaped bug upstream
    (ADR-6), and the caller is expected to abort rather than ship.

    Scoped to `delete_source` ONLY (Feature 5 and its ACs are delete-scoped;
    no builder populates `depends_on` on any other action kind today). A
    missing `depends_on` key (or an explicit ``None``) is a violation of equal
    severity to, but distinguishable wording from, a dangling id — mirroring
    `withdraw_unjustified_deletes`' own missing-vs-empty-list distinction.
    ``depends_on: []`` is a positive assertion ("nothing conditions this
    delete") and is never a violation.

    Existence only — not well-formedness. A `depends_on` naming its own
    delete's id, or forming a cycle, is not checked (deliberate non-goal).

    Returns a list of violation messages (one per offending `delete_source`;
    empty means the invariant holds), each self-contained like
    `_validate_action_paths`'s: it names both the offending delete's id and
    the fault. Caller is expected to abort on a non-empty result.
    """
    existing_ids = {a.get("id") for a in actions if a.get("id")}
    violations: list[str] = []
    for action in actions:
        if action.get("action") != "delete_source":
            continue
        action_id = action.get("id", "<no-id>")
        if "depends_on" not in action or action.get("depends_on") is None:
            violations.append(
                f"{action_id} (delete_source): missing required 'depends_on' "
                f"field — a delete_source must declare the id(s) that justify it"
            )
            continue
        missing = sorted({d for d in action["depends_on"] if d not in existing_ids})
        if missing:
            violations.append(
                f"{action_id} (delete_source): depends_on names unknown id(s) "
                f"{missing!r} — not present in this action set"
            )
    return violations


# Default asset folder — single source of truth for both the fallback used
# when a caller's cfg dict lacks "concepts.asset" (build_actions, below) and
# instruction-render.py's CONFIG_DEFAULTS entry for the same key.
DEFAULT_ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"


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

    The head names the attachment and why it was withheld; the remedy is
    `lib.refusal_sentences.withheld_attachment_remedy` for the entry's kind —
    the same remedy the "Attachments still in the inbox" bullet and the shell
    relay carry, so one item never reads two different fixes (owner ruling
    2026-10-12). A destination clash (`collision`) names the claimed
    destination; every other kind's head is the entry's own `reason`, phrased
    by `lib.refusal_sentences` (or the plan, for `no_basename`).
    `vault_collision_held` never reaches this function at all (excluded in
    `suppress_moves_for_unfiled_attachments`, below).
    """
    source = entry.get("source") or "?"
    kind = entry.get("kind")
    if kind == "collision":
        head = (
            f"`{source}` cannot be filed — another file of that name already "
            f"claims `{entry.get('destination')}`"
        )
    else:
        head = f"`{source}` cannot be filed — {entry.get('reason') or 'no filename'}"
    remedy = withheld_attachment_remedy(kind, entry.get("destination"))
    tail = (
        "the note that embeds it is not filed either"
        if note_count == 1
        else f"the {note_count} notes that embed it are not filed either"
    )
    return f"{head} — {tail}. {remedy}."


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

    `kind: vault_collision_held` (spec 037) is excluded from this pass: the
    owner chose *keep in inbox* for the attachment, not for the note, and
    holding the note anyway would silently widen that choice. See
    docs/tomo/scripts/lib/render_actions.md for why this needed an explicit
    exclusion rather than following from the shape above.

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
        if entry.get("kind") == "vault_collision_held":
            # The owner's remedy — spec 037 T3.1. Only the file stays behind.
            continue
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
    claimed_links: set[int] = set()
    for suppression, candidates in pending:
        suppression["withdrawn_deletes"] = [
            c for c in candidates if c in removed_deletes
        ]
        suppression["withdrawn_moc_links"] = _links_for(
            suppression, removed_moc_links, claimed_links
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
    attachment_plan: AttachmentPlan | None = None,
    extension_reports: list[dict] | None = None,
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
         moc extension      — per extend_moc: add_relationship, then link_to_moc
      3. move_note          — atomic notes
      4. move_asset         — attachments named on the manifest, deduplicated globally
      5. link_to_moc        — parent_mocs up-links + supporting_items down-links
      6. update_tracker / update_log_entry / update_log_link
      7. insert_under_marker — approved tag-handler group blocks (spec 024 T4.1)
      8. delete_source      — incl. approved tag-handler group sources (after their insert)
      9. skip

    `attachment_plan` (spec 039 K1) decides every attachment; the move
    builder projects it and this function stores the projection's
    `move_ids_by_origin` back on the plan. A manifest that carries attachments
    requires one (ValueError otherwise); one without attachments needs none.

    `extension_reports`, when given, receives one record per extend_moc item.
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
    out.extend(_build_moc_extension_actions(
        confirmed, kado_client, counter,
        extension_reports if extension_reports is not None else [],
        parent_marker=parent_marker, peer_marker=peer_marker,
    ))
    move_notes = _build_move_note_actions(manifest, inbox_path, counter)
    out.extend(move_notes)
    if attachment_plan is None:
        if any(item.get("attachments") for item in manifest):
            raise ValueError(
                "attachment_plan is required when the manifest carries attachments"
            )
        attachment_plan = build_attachment_plan(
            manifest, None, asset_folder=asset_folder, inbox_path=inbox_path,
            folder_lookup=None, census=None,
        )
    move_assets, skipped_assets, move_ids_by_origin = _build_move_asset_actions(
        manifest, attachment_plan, counter, inbox_path,
    )
    attachment_plan.move_ids_by_origin = move_ids_by_origin
    out.extend(move_assets)
    out.extend(_build_link_to_moc_actions(confirmed, counter))
    daily_actions, daily_action_ids_by_origin = _build_daily_update_actions(
        daily_updates, cfg, counter, inbox_path
    )
    out.extend(daily_actions)
    insert_actions, insert_action_ids_by_group = _build_insert_under_marker_actions(
        tag_handler_groups or [], approved_tag_handler_group_ids or [], counter,
    )
    out.extend(insert_actions)
    out.extend(_build_delete_source_actions(
        confirmed, move_notes, daily_updates, skipped, inbox_path, counter,
        tag_handler_groups=tag_handler_groups or [],
        approved_tag_handler_group_ids=approved_tag_handler_group_ids or [],
        keep_source_group_ids=tag_handler_keep_source_group_ids or [],
        daily_action_ids_by_origin=daily_action_ids_by_origin,
        insert_action_ids_by_group=insert_action_ids_by_group,
        move_ids_by_origin=move_ids_by_origin,
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
