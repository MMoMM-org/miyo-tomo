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


# Names differing only in case are treated as one destination (CON-6). The
# comparison folds; nothing displayed is ever folded, so the user always reads
# the name they typed and the vault's own spelling of what is in its way.
_CASE_NOTE = (
    "The names differ only in case — the filesystem may treat them as one file."
)

_COUNT_WORDS = {2: "Two", 3: "Three", 4: "Four"}


def _unique_in_order(values: list[str]) -> list[str]:
    """The distinct visible spellings, first spelling kept (NFC/NFD are one)."""
    out: list[str] = []
    for v in values:
        if not any(same_spelling(v, kept) for kept in out):
            out.append(v)
    return out


def make_folder_listing(client_or_lookup):
    """Return ``folder_listing(location) -> {folded destination: vault path}``.

    The ``.md`` view of a ``VaultFolderLookup``: one ``list_dir(folder,
    depth=1)`` per distinct folder, never a per-name ``note_exists`` probe.
    Pass the run's lookup to share its raw listing with every other reader;
    pass a client to get a private one. Pass 2 does not call this: it hands
    ``validate_destinations`` its lookup's ``notes`` view directly. A failed
    listing reads as empty — an error is not a collision.
    """
    lookup = (
        client_or_lookup
        if isinstance(client_or_lookup, VaultFolderLookup)
        else VaultFolderLookup(client_or_lookup)
    )
    return lookup.notes


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
    elif same_spelling(vault_note, claim_dests[0]):
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


def _orphaned_link_targets(actions: list[dict], dropped_ids: set[str]) -> set[str]:
    """The titles of dropped `create_moc` actions, keyed for `target_moc`.

    A `link_to_moc` bullet is written INTO the MOC named by its `target_moc`,
    not by the note that authors it. If the `create_moc` that would have
    created that MOC was dropped, the MOC does not exist — the bullet has
    nowhere to land regardless of how many surviving actions still write it.
    That is why this has no subtraction against survivors, unlike
    `_orphaned_link_titles`: the two rules answer different questions (did
    *this bullet's author* survive vs. did *this bullet's destination*
    survive), and the subtraction correct for one would be wrong for the
    other — a second create_moc of the same title surviving elsewhere does
    not make a dropped one's destination exist.
    """
    orphaned: set[str] = set()
    for action in actions:
        if action.get("action") != "create_moc" or action.get("id") not in dropped_ids:
            continue
        title = sanitize_stem(action.get("title") or "")
        if title:
            orphaned.add(title)
    return orphaned


def _links_for(
    withholding: dict, removed_moc_links: list[dict], claimed_links: set[int]
) -> list[dict]:
    """The share of one run's withdrawn bullets that belongs to one report.

    Both post-passes may withhold in the same run, and each renders its own
    section. A bullet is attributed to the withholding whose dropped moves
    carry its title (`_orphaned_link_titles`'s key) or whose dropped
    `create_moc` it names as `target_moc` (`_orphaned_link_targets`'s key).

    The two keys can both point at the *same* bullet within one run: one
    clash drops the bullet's author, an independent clash drops its target
    MOC. `claimed_links` (keyed by ``id()``, since ``removed_moc_links``
    entries are plain dicts with no identity of their own) accumulates
    across every clash in call order — the same claim-once shape
    `_paired_delete_candidates` uses for `withdrawn_paths` — so the first
    clash able to claim a bullet owns it and no later clash can re-claim it.
    One withdrawal is reported once.
    """
    titles = {
        sanitize_stem(d.get("title") or "")
        for d in withholding.get("dropped") or []
    }
    claimed: list[dict] = []
    for link in removed_moc_links:
        if id(link) in claimed_links:
            continue
        if (
            sanitize_stem(link.get("source_note_title") or "") in titles
            or sanitize_stem(link.get("target_moc") or "") in titles
        ):
            claimed_links.add(id(link))
            claimed.append(link)
    return claimed


def _drop_moves_with_paired_deletes(
    actions: list[dict], dropped_ids: set[str], withdrawn_paths: set[str]
) -> tuple[list[dict], set[str], list[dict]]:
    """Remove the dropped moves and their links; report the deletes they justified.

    Returns ``(kept, removed_deletes, removed_moc_links)``. `removed_deletes`
    names the deletes that actually existed, not every path a dropped move
    touched: an item the user marked "Keep source files" has no paired delete,
    so listing its origin would have the report and the coverage audit both
    claim a withdrawal that never happened.

    `removed_deletes` is report-only (spec 036 T2.3, ADR-4): this function no
    longer removes a `delete_source` action from `kept` on that basis. The
    actual removal is `withdraw_unjustified_deletes`, run once after every drop
    site (`instruction-render.py`, between `filter_unappliable_relationships`
    and `_validate_action_paths`) — a delete whose `depends_on` names an id
    this pass just dropped is withdrawn there, by id, not here, by path. Path
    equality was a second, independent read of a relationship
    `_build_delete_source_actions` already declares once at build time
    (`depends_on`); keeping two readings in step by discipline rather than by
    construction is the shape that drifted in T5.0c (see
    `docs/tomo/scripts/lib/render_actions.md`). The path-based computation
    stays here only because the report — read by `instructions-diff.py`'s
    coverage audit and rendered to the user — is keyed by path, not by id.

    `removed_moc_links` is the same discipline one action kind over. A
    `link_to_moc` for a note this run refused to file instructs the user to
    add a bullet pointing at a path that will hold nothing — the dead link the
    guard exists to prevent, written by the guard itself. T5.3 shipped with
    "a `link_to_moc` for a dropped note is harmless" as its named unverified
    assumption; the T5.5 document disproved it. Spec 036 T2.2 widened the
    claimant filter to include `create_moc`, which reopened the same risk
    from the other side: a bullet whose `target_moc` names a dropped
    `create_moc` also has nowhere to land (`_orphaned_link_targets`).

    Shared by both post-passes over the built action list
    (``validate_destinations`` and ``suppress_moves_for_unfiled_attachments``).
    They drop moves for different reasons and report them separately, but the
    withdrawal itself is one mechanism — a second copy is what drifted apart in
    T5.0c one module over.
    """
    orphaned_titles = _orphaned_link_titles(actions, dropped_ids)
    orphaned_targets = _orphaned_link_targets(actions, dropped_ids)
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
            # Report-only (spec 036 T2.3): no `continue` here. The action is
            # NOT dropped from `kept` on this basis any more —
            # `withdraw_unjustified_deletes` does that, by id, once after
            # every drop site. See this function's docstring and
            # docs/tomo/scripts/lib/render_actions.md.
            removed_deletes.add(action.get("source_path"))
        if action.get("action") == "link_to_moc" and (
            (action.get("source_note_stem") or "") in orphaned_titles
            or sanitize_stem(action.get("target_moc") or "") in orphaned_targets
        ):
            # Join on the stem (what the vault resolves by), report the title
            # (what the user reads) — spec 034 T6.4b. The record carries the
            # display title only: it is serialised into instructions.json's
            # `tomo` block, and `_links_for` derives the key from it the same
            # way the dropped side does, so both halves agree by construction.
            # The second disjunct is spec 036 T2.2: `target_moc` is the raw
            # title the user approved, not a stem, so it is sanitised here to
            # meet `orphaned_targets` on the same basis.
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
    """Drop every action whose destination is contested; report what was dropped.

    Returns ``(kept_actions, clashes)``. Runs after ``build_actions``, over the
    whole assembled list, so it sees every claim at once (ADR-4).

    ``move_note`` and ``create_moc`` are both claimants (spec 036 T2.2,
    ADR-3): each carries ``destination`` under the same key, so a
    ``create_moc`` and a ``move_note`` targeting one path contest it exactly
    as two ``move_note``s would — one would otherwise ship invisibly and
    silently overwrite the other's destination. The same widening also
    subjects a **lone** ``create_moc`` to ``vault_collision``: a destination
    already occupied in the vault drops it too, with no second claimant.

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

    It takes its ``link_to_moc`` bullets too: those authored by a dropped note
    (``_orphaned_link_titles``) and, since a ``create_moc`` can now be the
    thing dropped, those merely *naming* a dropped ``create_moc`` as
    ``target_moc`` (``_orphaned_link_targets``). Either way the bullet is an
    instruction to write into, or point at, a note that will never exist.

    ``folder_listing`` is the run's ``VaultFolderLookup.notes`` view (or
    ``make_folder_listing``); it is asked once per distinct destination
    folder. ``None`` skips the vault half and leaves the run-internal half
    working.

    The pass holds no state across calls: correcting one name and re-running
    Pass 2 emits both moves, with no memo of the earlier clash.
    """
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for action in actions:
        if action.get("action") not in ("move_note", "create_moc"):
            continue
        destination = action.get("destination") or ""
        if not destination:
            continue
        key = path_key(destination)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(action)

    # One listing per destination folder, only for folders this run writes to.
    vault_holders: dict[str, str] = {}
    if folder_listing is not None:
        folder_maps: dict[str, dict[str, str]] = {}
        for key in order:
            destination = groups[key][0].get("destination") or ""
            folder = destination.rsplit("/", 1)[0] if "/" in destination else ""
            if folder not in folder_maps:
                folder_maps[folder] = folder_listing(folder)
            holder = folder_maps[folder].get(key)
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
                    "action": c.get("action"),
                    "title": c.get("title"),
                    "destination": c.get("destination"),
                    "source_inbox_item": c.get("source_inbox_item"),
                    # `source` is the staging note this claimant moves FROM —
                    # present on both kinds. A move_note also carries the
                    # richer source_inbox_item (the original inbox note it
                    # derived from); a create_moc has no such origin, so the
                    # `origin` fallback below reads this field for a MOC
                    # claimant (spec 036 T2.2). Never repurpose
                    # source_inbox_item to hold a MOC's staging path — the
                    # two keys mean different things and overloading one is
                    # what this spec is fixing.
                    "source": c.get("source"),
                    # The one resolved origin the renderer displays, computed
                    # here rather than in render_md.py: the kind-scoped rule
                    # (`source` for a create_moc, `source_inbox_item`
                    # otherwise) is a domain fact about what each claimant
                    # kind carries, not a rendering choice, and belongs where
                    # the claimant's own fields are built. `None` here reads
                    # as "?" at render time, same as before.
                    "origin": (
                        c.get("source") if c.get("action") == "create_moc"
                        else c.get("source_inbox_item")
                    ),
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
    claimed_links: set[int] = set()
    for clash, candidates in pending:
        clash["withdrawn_deletes"] = [c for c in candidates if c in removed_deletes]
        clash["withdrawn_moc_links"] = _links_for(clash, removed_moc_links, claimed_links)
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


def withdraw_unjustified_deletes(
    actions: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Drop every delete whose declared justification did not survive the guards.

    Runs ONCE, after every drop site (spec 036 T2.1; wiring into build is
    T2.3, not this function). A single pass is sufficient because a
    ``delete_source`` never justifies another action — nothing declares a
    dependency on a delete, so removing one cannot orphan anything else. If a
    future action kind ever declares a dependency on a delete, this becomes a
    fixpoint loop; ``test_no_cascade_needed_single_pass_semantics`` is the
    tripwire that must change first.

    Only ``delete_source`` actions are governed — every other action, even one
    carrying its own (irrelevant) ``depends_on``, passes through untouched.

    ``depends_on: []`` and a missing ``depends_on`` key are NOT the same
    reading (spec 036 T2.3, owner decision 2026-09-17 — fail closed). A
    destructive action must justify itself; ``[]`` is a positive assertion
    that nothing conditions this delete ("perform it unconditionally"), while
    an absent key declares nothing at all. Reading the absence the same way
    as the assertion is fail-**open** on a delete: it tells the executor to
    remove a note whose justification cannot be established. This also
    matches T1.3's stance — a delete whose partner id could not be resolved
    is withheld, not shipped.

    - ``depends_on: []`` → kept unconditionally.
    - ``depends_on`` missing, or explicitly ``None`` → withdrawn. ``None`` is
      treated identically to a missing key: both mean "nothing declared",
      not "nothing required".
    - ``depends_on: [ids...]`` → kept only if every named id survived
      (AND semantics); withdrawn, naming the missing ones, otherwise.

    Pure: no I/O, does not mutate ``actions`` or any action dict in it.
    """
    surviving = {a.get("id") for a in actions if a.get("id")}
    kept: list[dict] = []
    withdrawn: list[dict] = []
    for action in actions:
        if action.get("action") != "delete_source":
            kept.append(action)
            continue
        if action.get("depends_on") is None:
            withdrawn.append({
                "id": action.get("id"),
                "source_path": action.get("source_path"),
                "reason": action.get("reason"),
                "missing_dependencies": None,
                "depends_on_declared": False,
            })
            continue
        missing = [d for d in action["depends_on"] if d not in surviving]
        if missing:
            withdrawn.append({
                "id": action.get("id"),
                "source_path": action.get("source_path"),
                "reason": action.get("reason"),
                "missing_dependencies": missing,
                "depends_on_declared": True,
            })
            continue
        kept.append(action)
    return kept, withdrawn


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
