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

import json
import logging
import re
import sys
from pathlib import Path

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

logger = logging.getLogger(__name__)

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
