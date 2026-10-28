# version: 0.1.0
"""link_members.py — Which linked notes may become MOC link members (spec 042).

`/moc-propose` asks `kado-graph` for the neighbours of cluster members; this
module decides, offline, which neighbours are allowed to be proposed. Periodic
notes (hubs that link everything) and MOCs are neither members nor bridges.

Eligibility reads only the discovery cache, the profile and vault-config — no
Kado call. Uncached nodes are ineligible (`uncached`) and left to the caller to
count. Reasons are fixed tokens, never paths; nothing here prints or logs.

Rationale: docs/tomo/scripts/lib/link_members.md — SDD ADR-3.
"""
from __future__ import annotations

from lib.moc_tags import EXCLUDE_NOTE_TAG

OK = "ok"
NOT_MD = "not-md"
INBOX = "inbox"
PERIODIC = "periodic"
MOC = "moc"
OUT_OF_SCOPE = "out-of-scope"
EXCLUDED_TAG = "excluded-tag"
UNCACHED = "uncached"

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


class NodeEligibility:
    """Offline eligibility of a vault path as a link member."""

    def __init__(self, cache: dict, profile: dict, vault_cfg: dict):
        cache = _dict(cache)
        profile = _dict(profile)
        cfg = _dict(vault_cfg)
        defaults = _dict(profile.get("concept_defaults"))
        concepts = _dict(cfg.get("concepts"))

        self._entries = {
            e["path"]: e
            for e in cache.get("entries") or []
            if isinstance(e, dict) and isinstance(e.get("path"), str)
        }
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

        suffix = _dict(concepts.get("map_note")).get("name_suffix")
        if suffix is None:
            suffix = _dict(defaults.get("map_note")).get("name_suffix")
        self._moc_suffix = suffix.casefold() if isinstance(suffix, str) and suffix else ""

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
