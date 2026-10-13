#!/usr/bin/env python3
# version: 0.4.0
"""attachment_plan.py — decide, once per Pass 2 run, what happens to every
attachment the confirmed items embed.

Exists so an attachment's fate is decided in exactly one place: its final
target or the reason it is withheld, whether its folder will be created or
went unchecked, and the exact embed text its owning notes get. The move
builder and the embed rewrite read this plan; neither decides anything of its
own, so a move and the embed pointing at it can never disagree.

Built in two passes. Pass A gives every source an outcome (decision table rows
1–11, first match wins). Pass B, only once every outcome is known, decides each
moved source's embed from the basename census adjusted to the vault after the
run — so a target withheld late in Pass A is never counted, and a target
planned later still is. Rationale: docs/tomo/scripts/lib/attachment_plan.md.
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from lib.refusal_sentences import (
    folder_sentence,
    occupied_target_sentence,
    typed_name_sentence,
)
from lib.render_helpers import _ensure_md_extension, resolve_source_path
from lib.typed_name_check import check_typed_folder, check_typed_name
from lib.vault_paths import _asset_dest_join, path_key


@dataclass(frozen=True)
class AttachmentDecision:
    source: str
    owners: tuple[str, ...]
    target: str | None
    withheld: dict | None
    embed: str | None
    folder_created: bool
    unchecked: bool
    qualified_reason: str | None


@dataclass
class AttachmentPlan:
    decisions: list[AttachmentDecision]
    by_source: dict[str, AttachmentDecision]
    move_ids_by_origin: dict[str, list[str]] = field(default_factory=dict)
    _folder_lookup: object = field(default=None, repr=False)
    _census: object = field(default=None, repr=False)

    @property
    def folder_listing_calls(self) -> int:
        return getattr(self._folder_lookup, "folder_listing_calls", 0)

    @property
    def basename_searches(self) -> int:
        return getattr(self._census, "searches", 0)

    def reports_by_source(self) -> dict[str, dict]:
        """What the instruction document reports about each moved source:
        its target, whether the target went unchecked, whether its folder
        will be created, and why its embed carries a path (or None)."""
        return {
            d.source: {
                "target": d.target,
                "unchecked": d.unchecked,
                "folder_created": d.folder_created,
                "qualified_reason": d.qualified_reason,
            }
            for d in self.decisions if d.target is not None
        }


@dataclass
class _Outcome:
    """Pass A's verdict for one source; Pass B adds the embed."""
    source: str
    owners: list[str]
    target: str | None = None
    withheld: dict | None = None
    folder_created: bool = False
    unchecked: bool = False


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _owner_key(item: dict, inbox_path: str) -> str | None:
    """The very key the move builder's notes carry in `source_inbox_item`."""
    return _ensure_md_extension(
        resolve_source_path(item.get("item_key"), item.get("source_path") or "", inbox_path)
        or None
    )


def _sources_with_owners(confirmed: list[dict], inbox_path: str) -> dict[str, list[str]]:
    """Every distinct source (exact spelling) in first-appearance order, with
    every owning origin key in confirmed order."""
    found: dict[str, list[str]] = {}
    for item in confirmed:
        owner = _owner_key(item, inbox_path)
        for path in item.get("attachments") or []:
            owners = found.setdefault(path, [])
            if owner and owner not in owners:
                owners.append(owner)
    return found


def _withhold(outcome: _Outcome, kind: str, destination: str | None, reason: str,
              refusal_reason: str | None = None) -> _Outcome:
    entry = {"source": outcome.source, "destination": destination, "reason": reason}
    if refusal_reason is not None:
        entry["refusal_reason"] = refusal_reason
    entry["kind"] = kind
    entry["owner_source_items"] = list(outcome.owners)
    outcome.withheld = entry
    return outcome


def _typed_folder(remedy: dict, asset_folder: str) -> str | None:
    """The owner's folder, or None when the configured asset folder applies.

    Not owner-supplied, null, or equal to the asset folder spelled as a folder
    (without the trailing separator the config carries) → the default.
    """
    folder = remedy.get("proposed_dir")
    if folder is None or not remedy.get("dir_is_owner_supplied"):
        return None
    if folder == (asset_folder or "").rstrip("/"):
        return None
    return folder


def _decide(outcome: _Outcome, remedy: dict | None, *, asset_folder: str,
            inbox_path: str, claimed: dict[str, str], folder_lookup) -> _Outcome:
    """Pass A, rows 1–11 of the decision table for one source."""
    path = outcome.source
    try:
        default_target = _asset_dest_join(asset_folder, path)
    except ValueError as exc:  # row 1
        print(f"  [warn] skipping attachment — {exc}", file=sys.stderr)
        return _withhold(outcome, "no_basename", None, "the inbox path has no filename")

    kind = remedy["remedy"] if remedy else None
    if kind == "keep_in_inbox":  # row 2
        return _withhold(
            outcome, "vault_collision_held", default_target,
            f"kept in inbox: the owner chose not to file it over "
            f"the occupied destination `{default_target}`",
        )

    target = default_target
    if kind == "rename":
        folder = _typed_folder(remedy, asset_folder)
        if folder is not None:  # row 3
            verdict = check_typed_folder(folder, inbox_path=inbox_path)
            if not verdict.ok:
                return _withhold(outcome, "typed_folder_refused", None,
                                 folder_sentence(verdict.reason, folder), verdict.reason)
        name = remedy.get("proposed_name")
        if not name:
            if folder is not None:  # row 4 (F1-AC11)
                return _withhold(outcome, "typed_name_refused", None,
                                 typed_name_sentence("blank", name or ""), "blank")
            return _withhold(  # row 5
                outcome, "vault_collision_held", default_target,
                f"kept in inbox: it was to be filed under a new name "
                f"beside the occupied destination `{default_target}`, and "
                f"that name is no longer available to this run — it "
                f"stays in the inbox rather than being filed under a "
                f"name the owner did not choose",
            )
        if remedy.get("name_is_owner_supplied"):  # row 6
            verdict = check_typed_name(name)
            if not verdict.ok:
                return _withhold(outcome, "typed_name_refused", None,
                                 typed_name_sentence(verdict.reason, name), verdict.reason)
        target = _asset_dest_join(folder if folder is not None else asset_folder, name)

    claimant = claimed.get(path_key(target))
    if claimant is not None:  # row 7
        reason = (
            f"destination collision: it also resolves to "
            f"`{target}`, already claimed by `{claimant}`"
        )
        print(f"  [warn] {reason} — skipping {path!r}", file=sys.stderr)
        return _withhold(outcome, "collision", target, reason)

    target_folder = target.rpartition("/")[0]
    state = folder_lookup.state(target_folder)
    if kind != "ignore" and state == "listed":  # row 8
        key = path_key(target)
        occupier = folder_lookup.assets(target_folder).get(key)
        if occupier is not None or key in folder_lookup.occupied_by_folder(target_folder):
            # no file occupier but the key is taken: a folder holds the name
            return _withhold(
                outcome, "vault_occupied", target,
                occupied_target_sentence(target, occupier,
                                         occupier_is_folder=occupier is None),
            )

    claimed[path_key(target)] = path
    outcome.target = target
    outcome.unchecked = state == "unanswered"  # row 9
    outcome.folder_created = state == "absent"  # row 10
    return outcome  # row 11


def _embed(outcome: _Outcome, census, moved_sources: Counter,
           moved_targets: Counter) -> tuple[str | None, str | None]:
    """Pass B: the embed for one moved source, judged on the vault after the run."""
    final = _basename(outcome.target)
    key = path_key(final)
    hits = census.count(final)
    if hits is None:
        return outcome.target, "unanswered"
    others = max(hits - moved_sources[key], 0) + (moved_targets[key] - 1)
    if others >= 1:
        return outcome.target, "ambiguous"
    return (final if final != _basename(outcome.source) else None), None


def build_attachment_plan(confirmed, remedies_by_source, *, asset_folder,
                          inbox_path, folder_lookup, census) -> AttachmentPlan:
    """One decision per distinct attachment source in `confirmed`.

    `remedies_by_source` maps a source to its remedy record
    (`suggestion-parser.py`); a source without one is a plain attachment.
    `inbox_path` is the vault-relative inbox (`concepts.inbox`).
    `folder_lookup` is K2 (`VaultFolderLookup`), `census` is K3.
    Prints the same `[warn]` lines the move builder printed for `no_basename`
    and `collision`; a projection of this plan must not print them again.
    """
    remedies = remedies_by_source or {}
    claimed: dict[str, str] = {}
    outcomes = [
        _decide(_Outcome(source, owners), remedies.get(source),
                asset_folder=asset_folder, inbox_path=inbox_path,
                claimed=claimed, folder_lookup=folder_lookup)
        for source, owners in _sources_with_owners(confirmed, inbox_path).items()
    ]

    moved = [o for o in outcomes if o.target is not None]
    moved_sources = Counter(path_key(_basename(o.source)) for o in moved)
    moved_targets = Counter(path_key(_basename(o.target)) for o in moved)

    decisions: list[AttachmentDecision] = []
    for o in outcomes:
        embed, qualified = (
            _embed(o, census, moved_sources, moved_targets)
            if o.target is not None else (None, None)
        )
        decisions.append(AttachmentDecision(
            source=o.source, owners=tuple(o.owners), target=o.target,
            withheld=o.withheld, embed=embed, folder_created=o.folder_created,
            unchecked=o.unchecked, qualified_reason=qualified,
        ))
    return AttachmentPlan(
        decisions=decisions,
        by_source={d.source: d for d in decisions},
        _folder_lookup=folder_lookup,
        _census=census,
    )
