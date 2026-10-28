# version: 0.2.0
"""link_members.py — MOC link members found through the link graph (spec 042).

`/moc-propose` asks `kado-graph` for the neighbours of cluster members; this
module decides, offline, which neighbours are allowed to be proposed
(`NodeEligibility`), runs the lookups under an attempt budget (`LinkLookup`) and
adds every eligible non-member linked from at least two members of a cluster
(`augment_clusters`). Periodic notes (hubs that link everything) and MOCs are
neither members nor bridges.

Eligibility reads only the discovery cache, the profile and vault-config — no
Kado call. Uncached nodes are ineligible (`uncached`) and only counted. Reasons
are fixed tokens, never paths; nothing here prints or logs.

Rationale: docs/tomo/scripts/lib/link_members.md — SDD ADR-3.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lib.kado_client import KadoBudgetExhausted, KadoError
from lib.moc_tags import EXCLUDE_NOTE_TAG
from lib.profile_conventions import moc_suffix

OK = "ok"
NOT_MD = "not-md"
INBOX = "inbox"
PERIODIC = "periodic"
MOC = "moc"
OUT_OF_SCOPE = "out-of-scope"
EXCLUDED_TAG = "excluded-tag"
UNCACHED = "uncached"

LOOKUP_BUDGET = 60  # HTTP attempts per run, retries included (ADR-4)
LOOKUP_PACING_S = 0.3  # minimum seconds between sends
MEMBER_THRESHOLD = 2  # members a node must be linked with

DONE = "done"
SKIPPED_BUDGET = "skipped_budget"
FAILED = "failed"

_EXCLUDE_NOTE_KEY = EXCLUDE_NOTE_TAG.casefold()


def _prefix(value) -> str | None:
    """Normalise a folder value: stripped, trailing '/' — None when blank."""
    if not isinstance(value, str) or not value.strip():
        return None
    p = value.strip()
    return p if p.endswith("/") else p + "/"


def _prefixes(values) -> list[str]:
    out: list[str] = []
    for v in values:
        p = _prefix(v)
        if p and p not in out:
            out.append(p)
    return out


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _calendar_paths(calendar) -> list:
    cal = _dict(calendar)
    paths = [cal.get("base_path")]
    for gran in _dict(cal.get("granularities")).values():
        paths.append(_dict(gran).get("path"))
    return paths


def _atomic_paths(node) -> list:
    """Paths from a scalar, a {path|paths} dict or a {base_path, subdirectories} dict."""
    if isinstance(node, str):
        return [node]
    node = _dict(node)
    paths = [node.get("path"), node.get("base_path")]
    paths += list(node.get("paths") or [])
    paths += [_dict(sd).get("path") for sd in node.get("subdirectories") or []]
    return paths


def _has_exclude_note_tag(tags) -> bool:
    for tag in tags or []:
        if isinstance(tag, str):
            bare = tag[1:] if tag.startswith("#") else tag
            if bare.strip().casefold() == _EXCLUDE_NOTE_KEY:
                return True
    return False


def _cache_entries(cache: dict) -> dict[str, dict]:
    """Discovery-cache entries keyed by vault path."""
    return {
        e["path"]: e
        for e in _dict(cache).get("entries") or []
        if isinstance(e, dict) and isinstance(e.get("path"), str)
    }


class NodeEligibility:
    """Offline eligibility of a vault path as a link member."""

    def __init__(self, cache: dict, profile: dict, vault_cfg: dict):
        cache = _dict(cache)
        profile = _dict(profile)
        cfg = _dict(vault_cfg)
        defaults = _dict(profile.get("concept_defaults"))
        concepts = _dict(cfg.get("concepts"))

        self._entries = _cache_entries(cache)
        self._map_note_paths = {
            m.get("path") for m in cache.get("map_notes") or [] if isinstance(m, dict)
        }

        # User config wins over the profile (layer precedence).
        atomic = concepts.get("atomic_note") or defaults.get("atomic_note")
        self._atomic = _prefixes(_atomic_paths(atomic))
        self._inbox = _prefixes([concepts.get("inbox") or defaults.get("inbox")])

        exclude = _dict(_dict(cfg.get("tomo")).get("moc_structure_cache")).get("exclude_paths")
        self._periodic = _prefixes(
            _calendar_paths(defaults.get("calendar"))
            + _calendar_paths(concepts.get("calendar"))
            + list(exclude or [])
        )

        suffix = moc_suffix(profile)
        self._moc_suffix = suffix.casefold() if isinstance(suffix, str) else ""

    def is_periodic(self, path: str) -> bool:
        return any(path.startswith(p) for p in self._periodic)

    def is_moc(self, path: str) -> bool:
        entry = self._entries.get(path)
        if entry is not None and entry.get("kind") == "moc":
            return True
        if path in self._map_note_paths:
            return True
        stem = path.rsplit("/", 1)[-1]
        if stem.endswith(".md"):
            stem = stem[:-3]
        return bool(self._moc_suffix) and stem.casefold().endswith(self._moc_suffix)

    def check(self, path: str) -> tuple[bool, str]:
        """Return (eligible, reason); the first failing rule names the reason."""
        if not path.endswith(".md"):
            return False, NOT_MD
        if any(path.startswith(p) for p in self._inbox):
            return False, INBOX
        if self.is_periodic(path):
            return False, PERIODIC
        if self.is_moc(path):
            return False, MOC
        if self._atomic and not any(path.startswith(p) for p in self._atomic):
            return False, OUT_OF_SCOPE
        entry = self._entries.get(path)
        if entry is not None and _has_exclude_note_tag(entry.get("tags")):
            return False, EXCLUDED_TAG
        if entry is None:
            return False, UNCACHED
        return True, OK


class LookupFailed:
    """A `neighbors` lookup that raised a Kado error."""


class BudgetExhausted:
    """A `neighbors` lookup the attempt gate refused; nothing was sent."""


class LinkLookup:
    """Memoised `kado-graph neighbors` lookups under an attempt budget.

    Installs the budget as the client's attempt gate and sets its pacing; both
    stay installed for the rest of the run.
    """

    def __init__(self, client, budget: int = LOOKUP_BUDGET):
        self._client = client
        self._budget = budget
        self._base = getattr(client, "attempt_count", 0)
        self._memo: dict[str, list[str] | LookupFailed] = {}
        self.lookups = 0
        self.failed = 0
        client.attempt_gate = lambda: self.remaining() > 0
        client.min_interval = LOOKUP_PACING_S

    @property
    def attempts(self) -> int:
        return getattr(self._client, "attempt_count", 0) - self._base

    def remaining(self) -> int:
        return max(0, self._budget - self.attempts)

    def cached(self, path: str) -> bool:
        return path in self._memo

    def neighbors(self, path: str) -> list[str] | LookupFailed | BudgetExhausted:
        if path in self._memo:
            return self._memo[path]
        self.lookups += 1
        try:
            nodes = self._client.graph("neighbors", path)
        except KadoBudgetExhausted:
            return BudgetExhausted()
        except KadoError:
            self.failed += 1
            self._memo[path] = LookupFailed()
            return self._memo[path]
        result: list[str] = []
        for node in nodes:
            node_path = node.get("path") if isinstance(node, dict) else None
            if isinstance(node_path, str) and node_path != path and node_path not in result:
                result.append(node_path)
        self._memo[path] = result
        return result


@dataclass
class LinkMember:
    stem: str
    path: str
    linked_with: list[str]
    up_state: str
    up_target: str | None


@dataclass
class ClusterLinks:
    status: str
    link_members: list[LinkMember] = field(default_factory=list)


@dataclass
class AugmentResult:
    clusters: dict[str, ClusterLinks]
    stats: dict[str, int]


def _link_member(path: str, linked_with: list[str], entry: dict) -> LinkMember:
    stem = entry.get("stem") or path.rsplit("/", 1)[-1].removesuffix(".md")
    return LinkMember(
        stem=stem,
        path=path,
        linked_with=linked_with,
        up_state=entry.get("up_state") or "absent",
        up_target=entry.get("up_target"),
    )


def _augment_one(
    cluster, stem_to_path, lookup, eligibility, entries, threshold, uncached
) -> ClusterLinks:
    members = [(s, stem_to_path[s]) for s in cluster.get("items") or [] if s in stem_to_path]
    member_paths = {p for _, p in members}
    need = sum(1 for p in member_paths if not lookup.cached(p))
    if need > lookup.remaining():
        return ClusterLinks(SKIPPED_BUDGET)

    hits: dict[str, set[str]] = {}
    for stem, path in members:
        result = lookup.neighbors(path)
        if isinstance(result, (LookupFailed, BudgetExhausted)):
            return ClusterLinks(FAILED)
        for node in result:
            if node in member_paths:
                continue
            ok, reason = eligibility.check(node)
            if ok:
                hits.setdefault(node, set()).add(stem)
            elif reason == UNCACHED:
                uncached.add(node)

    link_members = [
        _link_member(node, sorted(by), entries[node])
        for node, by in hits.items()
        if len(by) >= threshold
    ]
    return ClusterLinks(DONE, sorted(link_members, key=lambda m: m.stem))


def augment_clusters(
    clusters, stem_to_path, lookup, eligibility, cache, threshold=MEMBER_THRESHOLD
) -> AugmentResult:
    """Link members per cluster of the rendered slice, in the given order.

    ``clusters`` is the rendered slice only; the caller marks the rest
    ``not_rendered``. Inputs are not mutated.
    """
    entries = _cache_entries(cache)
    uncached: set[str] = set()
    out: dict[str, ClusterLinks] = {}
    for cluster in clusters:
        out[cluster["cluster_id"]] = _augment_one(
            cluster, stem_to_path, lookup, eligibility, entries, threshold, uncached
        )
    stats = {
        "lookups": lookup.lookups,
        "attempts": lookup.attempts,
        "failed": lookup.failed,
        "clusters_skipped_budget": sum(1 for c in out.values() if c.status == SKIPPED_BUDGET),
        "members_total": sum(len(c.link_members) for c in out.values()),
        "skipped_uncached": len(uncached),
    }
    return AugmentResult(out, stats)
