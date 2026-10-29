# version: 0.1.0
"""render_withhold.py — the destination guard and the delete-withdrawal pass.

Split out of render_actions.py (#216, Constitution L2 file size). Post-passes
over the built action list that withhold what must not ship: every claimant
of a contested destination (validate_destinations), the paired deletes and
MOC bullets a dropped move takes with it (shared with the attachment guard),
and every delete_source whose declared justification did not survive
(withdraw_unjustified_deletes).
"""
from __future__ import annotations

from lib.obsidian_filename import sanitize_stem
from lib.vault_folder_lookup import VaultFolderLookup
from lib.vault_paths import path_key, same_spelling


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
