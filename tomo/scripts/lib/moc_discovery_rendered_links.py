# version: 0.1.0
"""moc_discovery_rendered_links.py — Link-member augmentation of moc-discovery's rendered clusters.

The pure halves around the one `LinkLookup` session: which member paths of the
rendered slice get looked up, and how the lookup result is written back onto
every cluster. The session itself stays in moc-discovery.py, which owns the
Kado client. `moc-discovery.py` re-exports every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_rendered_links.md (issue #216).
"""
from __future__ import annotations

from lib.link_members import UNCACHED
from lib.moc_discovery_common import Candidate, _log


NOT_RENDERED = "not_rendered"


def _item_stem(item) -> str:
    """Cluster item → stem; items are stems, enriched dicts carry `stem`."""
    if isinstance(item, dict):
        return str(item.get("stem") or "")
    return str(item)


def _member_up_fields(member) -> dict:
    """The up:: fields of a member dict; the cached reason only when broken."""
    fields = {"up_state": member.up_state, "up_target": member.up_target}
    if member.up_state == "broken":
        fields["up_broken_reason"] = member.up_broken_reason
    return fields


def plan_link_lookups(
    clusters: list[dict],
    candidates: list[Candidate],
    eligibility,
    max_results: int,
) -> tuple[list[dict], list[dict], dict[str, str], dict[str, str]]:
    """Lookup plan for the rendered slice → (rendered, lookup_clusters, path_map, path_to_stem).

    Only ``clusters[:max_results]`` (already confidence-sorted) are looked up;
    the rest get ``not_rendered`` and cause no call. Lookups are keyed by
    member PATH: a stem expands to every eligible candidate path carrying it,
    and ``linked_with`` is mapped back to stems. Candidate paths that fail
    ``NodeEligibility`` (except ``uncached``) are not looked up.
    """
    paths_by_stem: dict[str, list[str]] = {}
    for cand in candidates:
        if not cand.stem or not cand.path:
            continue
        paths = paths_by_stem.setdefault(cand.stem, [])
        ok, reason = eligibility.check(cand.path)
        if (ok or reason == UNCACHED) and cand.path not in paths:
            paths.append(cand.path)
    path_to_stem = {p: s for s, paths in paths_by_stem.items() for p in paths}
    path_map = {p: p for p in path_to_stem}

    rendered = clusters[: max(0, max_results)]
    lookup_clusters: list[dict] = []
    for cluster in rendered:
        keys: list[str] = []
        for stem in (_item_stem(i) for i in cluster.get("items") or []):
            # An unknown stem stays as a key with no path → augment marks the
            # cluster failed without a call.
            for key in paths_by_stem.get(stem, [stem]):
                if key not in keys:
                    keys.append(key)
        lookup_clusters.append({"cluster_id": cluster["cluster_id"], "items": keys})
    return rendered, lookup_clusters, path_map, path_to_stem


def apply_link_results(
    clusters: list[dict],
    rendered: list[dict],
    result,
    path_to_stem: dict[str, str],
) -> dict[str, int]:
    """Attach `link_members` + `link_lookup_status` to every cluster; return `link_stats`.

    Mutates the clusters in place; never touches items, candidate_stems or
    confidence.
    """
    for cluster in clusters:
        cluster["link_lookup_status"] = NOT_RENDERED
        cluster["link_members"] = []
    for cluster in rendered:
        links = result.clusters[cluster["cluster_id"]]
        cluster["link_lookup_status"] = links.status
        cluster["link_members"] = [
            {
                "stem": m.stem,
                "path": m.path,
                "linked_with": sorted({path_to_stem[p] for p in m.linked_with}),
                **_member_up_fields(m),
            }
            for m in links.link_members
        ]

    stats = dict(result.stats)
    _log(
        f"links: rendered={len(rendered)} not_rendered={len(clusters) - len(rendered)} "
        + " ".join(f"{k}={v}" for k, v in stats.items())
    )
    return stats
