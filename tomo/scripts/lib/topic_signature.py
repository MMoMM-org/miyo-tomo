# topic_signature.py — Stable topic-cluster hash for squelch keying.
# version: 0.1.0
"""Compute a short, stable SHA-1 hash for a topic cluster dict.

Factored out of moc-discovery.py so that both the discovery pipeline and the
squelch-persist helper (T5.2) can share the exact same signature algorithm
without duplication.

Signature shape (per SDD §Implementation Examples / Example 2):

    sha1( "|".join(sorted(lower(topic_keywords)))
          + "::"
          + "|".join(sorted(candidate_stems)[:5]) ).hexdigest()[:16]

Stdlib only — no new dependencies.
"""

from __future__ import annotations

import hashlib


def cluster_topic_set(cluster: dict) -> set[str]:
    """Normalised topic bag from a cluster dict.

    Honours both ``topic_keywords`` (list[str]) and the single-string
    ``topic`` fallback (Phase-3 default in moc-discovery.py).
    """
    out: set[str] = set()
    if isinstance(cluster.get("topic_keywords"), list):
        for t in cluster["topic_keywords"]:
            if t:
                norm = str(t).strip().lower()
                if norm:
                    out.add(norm)
    topic = cluster.get("topic")
    if topic:
        norm = str(topic).strip().lower()
        if norm:
            out.add(norm)
    return out


def candidate_stems(cluster: dict) -> list[str]:
    """Pull per-candidate identifiers from a cluster dict.

    Accepts ``candidate_stems`` (list[str] from DiscoveryReport / proposal-doc
    parse), ``items`` (list[str] section_ids from Phase-3 Cluster), and dicts
    with ``stem``/``path`` keys (forward-compat with T2.7 enrichment).
    """
    # Prefer the explicit candidate_stems field (reducer / proposal-doc path)
    cs = cluster.get("candidate_stems")
    if isinstance(cs, list):
        return [str(s) for s in cs if s]

    # Fallback: items list (Phase-3 Cluster TypedDict)
    items = cluster.get("items") or []
    stems: list[str] = []
    for it in items:
        if isinstance(it, str):
            if it:
                stems.append(it)
        elif isinstance(it, dict):
            stem = it.get("stem") or it.get("path") or ""
            if stem:
                stems.append(stem)
    return stems


def compute_topic_signature(cluster: dict) -> str:
    """Return a 16-char hex SHA-1 for squelch keying.

    Stable across small candidate-set drift (top-5 stems only).
    """
    topics = sorted(cluster_topic_set(cluster))
    stems = sorted(candidate_stems(cluster))[:5]
    payload = "|".join(topics) + "::" + "|".join(stems)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
