# version: 0.1.0
"""moc_discovery_around.py — `--around` builders of moc-discovery: seed resolution and proposals.

Resolves the seed against the cache and turns one `neighbors(seed)` result
into either a new-MOC cluster (note seed) or the MOC's missing members (MOC
seed). The lookup itself stays in moc-discovery.py, which owns the Kado client
and the `LinkLookup` session. `moc-discovery.py` re-exports every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_around.md (issue #216).
"""
from __future__ import annotations

from dataclasses import dataclass

from lib.link_members import NodeEligibility
from lib.moc_discovery_common import ABORT_MESSAGES, Candidate, _log, _stem_from_path
from lib.moc_discovery_enrich import _moc_location, _serialise_parents, phase5_resolve_parents
from lib.moc_discovery_rendered_links import _member_up_fields
from lib.moc_discovery_report import candidate_rows
from lib.profile_conventions import ensure_suffix, moc_suffix
from lib.render_md import bare_stem, unwrap_list_repr
from lib.slugify import slugify


# ──────────────────────────────────────────────────────────────────────────────
# --around — one new-MOC proposal from a seed note's links (spec 042 F2)
# ──────────────────────────────────────────────────────────────────────────────

AROUND_CLUSTER_ID = "MOC01"
AROUND_MIN_NEIGHBOURS = 2  # seed + 2 neighbours = the 3-note floor
# Why a note seed fails member eligibility, in user terms (owner decision A).
AROUND_INELIGIBLE_REASONS = {
    "not-md": "it is not a Markdown note",
    "inbox": "it is still in the inbox",
    "out-of-scope": "it is outside the atomic-note folders",
    "excluded-tag": "it is tagged exclude/note",
}


@dataclass
class AroundSeed:
    """The resolved `--around` target."""

    kind: str  # "note" | "moc"
    path: str
    stem: str
    topics: list[str]


def _around_key(arg: str) -> tuple[str, bool]:
    """`--around` argument → (match key, is_path).

    `[[stem]]` / `[[stem|alias]]` unwrap to the stem; anything with a `/` is a
    vault path (`.md` added when missing); otherwise a trailing `.md` is dropped.
    """
    key = arg.strip()
    if key.startswith("[[") and key.endswith("]]"):
        key = key[2:-2].split("|", 1)[0].strip()
    if "/" in key:
        return (key if key.endswith(".md") else f"{key}.md"), True
    return key.removesuffix(".md"), False


def resolve_around_seed(
    arg: str, cache: dict, eligibility: NodeEligibility
) -> tuple[AroundSeed | None, str | None, str | None]:
    """Resolve `arg` against the cache → (seed, abort_reason, abort_message).

    Case-insensitive match on entry paths (path argument) or stems (name).
    Refusal order: periodic path argument → ambiguous → not found → periodic →
    (note seeds only) member eligibility.
    """
    key, is_path = _around_key(arg)
    if is_path and eligibility.is_periodic(key):
        return None, "around-periodic", ABORT_MESSAGES["around-periodic"]

    folded = key.casefold()
    matches: dict[str, dict] = {}
    for entry in list(cache.get("entries") or []) + list(cache.get("map_notes") or []):
        path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(path, str):
            continue
        name = path if is_path else _stem_from_path(path)
        if name.casefold() == folded:
            matches.setdefault(path, entry)

    if len(matches) > 1:
        listed = ", ".join(sorted(matches))
        return None, "around-ambiguous", (
            f"around: '{arg}' matches several notes — give a path: {listed}"
        )
    if not matches:
        return None, "around-not-found", (
            f"around: '{arg}' not found — rebuild the cache or give a path"
        )

    path, entry = next(iter(matches.items()))
    if eligibility.is_periodic(path):
        return None, "around-periodic", ABORT_MESSAGES["around-periodic"]
    kind = "moc" if eligibility.is_moc(path) else "note"
    if kind == "note":
        eligible, why = eligibility.check(path)
        if not eligible:
            reason_text = AROUND_INELIGIBLE_REASONS.get(why, f"it is not eligible ({why})")
            return None, "around-ineligible", (
                f"around: '{_stem_from_path(path)}' cannot seed a MOC — {reason_text}"
            )
    topics = [str(t) for t in entry.get("topics") or [] if t]
    return AroundSeed(kind, path, _stem_from_path(path), topics), None, None


def _around_abort(report: dict, reason: str, message: str) -> dict:
    report["abort_reason"] = reason
    report["abort_message"] = message
    _log(f"around: abort → {reason!r}")
    return report


def _ref_stem(ref) -> str:
    """Bare stem of one parent ref: `[[ ]]`, alias, heading, folder and `.md` stripped."""
    s = str(ref).strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2]
    return bare_stem(s.split("|", 1)[0].split("#", 1)[0])


def _up_targets_stem(entry: dict, stem: str) -> bool:
    """True when a cache entry's `up_target` or any `up_value` element names `stem`."""
    targets: list = []
    for raw in (entry.get("up_target"), entry.get("up_value")):
        value = unwrap_list_repr(raw)
        targets.extend(value if isinstance(value, (list, tuple)) else [value])
    folded = stem.casefold()
    return any(t is not None and _ref_stem(t).casefold() == folded for t in targets)


def apply_around_extension(
    report: dict, seed: AroundSeed, cache: dict, links
) -> dict:
    """around:<MOC> — neighbours without cached up:: to the MOC → report.extension."""
    entries = {e.get("path"): e for e in cache.get("entries") or [] if isinstance(e, dict)}
    missing = [
        m for m in links.link_members if not _up_targets_stem(entries[m.path], seed.stem)
    ]
    report["link_stats"]["members_total"] = len(missing)
    if not missing:
        return _around_abort(
            report, "no-missing-members",
            f"around: '{seed.stem}' has no missing members — every eligible "
            f"linked note already has up:: to it",
        )
    report["extension"] = {
        "moc_stem": seed.stem,
        "moc_path": seed.path,
        "members": [
            {
                "stem": m.stem,
                "path": m.path,
                "linked_with": [seed.stem],
                **_member_up_fields(m),
            }
            for m in missing
        ],
    }
    return report


def around_too_few(report: dict, seed: AroundSeed, links) -> dict | None:
    """around:<note> — abort when the seed has fewer than the 3-note floor, else None."""
    if len(links.link_members) < AROUND_MIN_NEIGHBOURS:
        return _around_abort(
            report, "fewer-than-3-notes",
            f"around: fewer than 3 notes — '{seed.stem}' has "
            f"{len(links.link_members)} eligible linked note(s), "
            f"{AROUND_MIN_NEIGHBOURS} are needed",
        )
    return None


def build_around_cluster(
    seed: AroundSeed, links, profile_dict: dict, cache: dict
) -> tuple[dict, list]:
    """around:<note> — the one new-MOC cluster and its parent options."""
    title = ensure_suffix(seed.stem, moc_suffix(profile_dict))
    parents = phase5_resolve_parents({"topic_keywords": seed.topics}, profile_dict, cache)
    cluster = {
        "topic": seed.stem,
        "items": [seed.stem],
        "parent": None,
        "tags": [],
        "cluster_id": AROUND_CLUSTER_ID,
        "title": title,
        "confidence": 1.0,  # topic formula: 1 member / 1 candidate
        "candidate_stems": [seed.stem],
        "topic_keywords": list(seed.topics),
        "location": _moc_location(profile_dict),
        "template": "t_moc_tomo",
        "slug": slugify(title),
        "existing_up": [],
        "link_lookup_status": links.status,
        "link_members": [
            {
                "stem": m.stem,
                "path": m.path,
                "linked_with": [seed.stem],
                **_member_up_fields(m),
            }
            for m in links.link_members
        ],
    }
    return cluster, parents


def fill_around_note_report(
    report: dict, candidate: Candidate, clusters: list[dict], parents: list
) -> dict:
    """around:<note> — write the seed candidate, cluster and parents into the report."""
    report.update({
        "candidates_total": 1,
        "candidates_after_prefilter": 1,
        "candidates": candidate_rows([candidate]),
        "topic_clusters": clusters,
        "parent_options_per_cluster": {AROUND_CLUSTER_ID: _serialise_parents(parents)},
    })
    return report
