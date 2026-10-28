#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_links.py — link-member augmentation in _run_pipeline (spec 042 T2.1).

Drives moc-discovery main() in-process with a graph-capable fake Kado client
(no live Kado, no ~/.tomo, no tomo-instance). Fixture vault (miyo profile):

  energy cluster: A, B, C  (3 topic members → highest confidence)
  solar  cluster: D, E     (2 topic members)
  X   linked with A, B, D, E  → link member of both clusters
  Y   linked with A only      → never a link member (threshold 2)
  U   uncached, linked with A, B → counted as skipped_uncached, never proposed
  Daily note linked with A, B → periodic, never proposed, never a bridge
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("moc_discovery_links", SCRIPT_PATH)
_moc_disc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery_links"] = _moc_disc
_spec.loader.exec_module(_moc_disc)

from lib import kado_client as _kado_mod  # noqa: E402
from lib.kado_client import KadoBudgetExhausted, KadoError  # noqa: E402
from lib.topic_signature import compute_topic_signature  # noqa: E402

_BASE = "Atlas/202 Notes/"
A, B, C, D, E = (f"{_BASE}{s}.md" for s in ("alpha", "beta", "gamma", "delta", "epsilon"))
X = f"{_BASE}xenon.md"
Y = f"{_BASE}yttrium.md"
U = f"{_BASE}uncached.md"
DAILY = "Calendar/301 Daily/2026-01-01.md"
MOC_PATH = "Atlas/200 Maps/Gardening MOC.md"

_NOTES = [
    {"path": A, "topics": ["energy", "a1"]},
    {"path": B, "topics": ["energy", "b1"]},
    {"path": C, "topics": ["energy", "c1"]},
    {"path": D, "topics": ["solar", "d1"]},
    {"path": E, "topics": ["solar", "e1"]},
    {"path": X, "topics": ["xenon-topic"]},
    {"path": Y, "topics": ["yttrium-topic"]},
]

_LINKS = {
    A: [X, Y, U, DAILY, B],
    B: [X, U, DAILY, A],
    C: [],
    D: [X],
    E: [X],
}


def _stem(path: str) -> str:
    return path.rsplit("/", 1)[-1].removesuffix(".md")


class _GraphFake:
    """Kado fake: tag search, note reads and a recording `graph`.

    Mirrors KadoClient's budget surface: `attempt_gate` is asked before every
    simulated send; `attempt_count` grows by `attempts_per_call` per lookup.
    """

    def __init__(self, links=None, tag_paths=(A, B, C, D, E), attempts_per_call=1):
        self.links = dict(links if links is not None else _LINKS)
        self.tag_paths = list(tag_paths)
        self.attempts_per_call = attempts_per_call
        self.graph_calls: list[tuple[str, str, object]] = []
        self.attempt_count = 0
        self.attempt_gate = None
        self.min_interval = 0.0

    def graph(self, operation, path, limit=None):
        self.graph_calls.append((operation, path, limit))
        for _ in range(self.attempts_per_call):
            if self.attempt_gate is not None and not self.attempt_gate():
                raise KadoBudgetExhausted("budget")
            self.attempt_count += 1
        return [{"path": p, "relation": "outgoing"} for p in self.links.get(path, [])]

    def search_by_tag(self, query):
        return [{"path": p} for p in self.tag_paths]

    def read_note(self, path):
        return {"content": "# stub\n"}

    def list_dir(self, *_a, **_k):  # pragma: no cover
        return []


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _write_config(tmp_path: Path, *, max_results: int = 5) -> Path:
    cfg = {
        "profile": "miyo",
        "tomo": {
            "moc_proposal": {
                "min_notes": 2,
                "confidence_threshold": 0.10,
                "max_results": max_results,
                "candidate_cap": 200,
            }
        },
    }
    p = tmp_path / "vault-config.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return p


def _write_cache(tmp_path: Path, notes=_NOTES) -> Path:
    entries = [
        {"path": MOC_PATH, "kind": "moc", "title": "Gardening MOC",
         "topics": ["gardening"], "tags": []},
    ]
    for n in notes:
        entries.append({
            "path": n["path"], "kind": "note", "stem": _stem(n["path"]),
            "topics": n["topics"], "tags": n.get("tags", []),
            "up_state": n.get("up_state", "absent"), "up_target": n.get("up_target"),
        })
    cache = {
        "moc_cache_version": 1,
        "last_scan": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ttl_days": 1,
        "scope_paths": [],
        "exclude_paths": [],
        "moc_tag": "type/others/moc",
        "entries": entries,
        "placeholder_links": [],
    }
    p = tmp_path / "moc-structure-cache.yaml"
    p.write_text(yaml.dump(cache, allow_unicode=True), encoding="utf-8")
    return p


def _common_args(tmp_path: Path, config: Path, cache: Path) -> list[str]:
    squelch = tmp_path / "moc-squelch.json"
    if not squelch.exists():
        squelch.write_text(
            json.dumps({"schema_version": "1", "last_run_id": "", "rejections": []}),
            encoding="utf-8",
        )
    return ["--config", str(config), "--cache", str(cache), "--squelch-state", str(squelch)]


def _run(argv: list[str]) -> tuple[int, dict | None]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = _moc_disc.main(argv)
    text = out.getvalue().strip()
    return code, (json.loads(text) if text else None)


def _run_tag(tmp_path, monkeypatch, fake, *, max_results=5, notes=_NOTES):
    config = _write_config(tmp_path, max_results=max_results)
    cache = _write_cache(tmp_path, notes)
    monkeypatch.setattr(_moc_disc, "_build_kado_client", lambda: fake)
    return _run(["--tag", "science", *_common_args(tmp_path, config, cache)])


def _run_phase1_input(tmp_path, candidates, *, max_results=5, notes=_NOTES):
    config = _write_config(tmp_path, max_results=max_results)
    cache = _write_cache(tmp_path, notes)
    payload = {"mode": "tag", "trigger_arg": "science", "profile": "miyo",
               "candidates": candidates}
    p1 = tmp_path / "phase1-in.json"
    p1.write_text(json.dumps(payload), encoding="utf-8")
    return _run(["--phase1-input", str(p1), *_common_args(tmp_path, config, cache)])


def _by_topic(report: dict) -> dict[str, dict]:
    return {c["topic"]: c for c in report["topic_clusters"]}


def _members(cluster: dict) -> dict[str, dict]:
    return {m["stem"]: m for m in cluster["link_members"]}


def _candidates(*paths_topics):
    return [{"stem": _stem(p), "path": p, "topics": t} for p, t in paths_topics]


# ── F1: link members in the real pipeline ────────────────────────────────────


def test_top_cluster_gets_note_linked_with_two_members(tmp_path, monkeypatch):
    """F1-AC1/AC2/AC3: X (linked with alpha+beta) is a link member with linked_with;
    Y (one member) is not; beta (a topic member A links to) is not duplicated."""
    code, report = _run_tag(tmp_path, monkeypatch, _GraphFake())
    assert code in (0, 1)
    top = report["topic_clusters"][0]
    assert top["topic"] == "energy"
    assert top["link_lookup_status"] == "done"
    members = _members(top)
    assert set(members) == {"xenon"}
    assert members["xenon"] == {
        "stem": "xenon", "path": X, "linked_with": ["alpha", "beta"],
        "up_state": "absent", "up_target": None,
    }


def test_note_qualifying_for_two_rendered_clusters_listed_in_each(tmp_path, monkeypatch):
    """F1-AC4: X is linked with two members of each cluster → in both."""
    _, report = _run_tag(tmp_path, monkeypatch, _GraphFake())
    clusters = _by_topic(report)
    assert _members(clusters["energy"])["xenon"]["linked_with"] == ["alpha", "beta"]
    assert _members(clusters["solar"])["xenon"]["linked_with"] == ["delta", "epsilon"]


def test_clusters_beyond_max_results_not_rendered_and_never_looked_up(tmp_path, monkeypatch):
    """ADR-2: only clusters[:max_results] are looked up; the rest get not_rendered."""
    fake = _GraphFake()
    _, report = _run_tag(tmp_path, monkeypatch, fake, max_results=1)
    clusters = _by_topic(report)
    assert report["topic_clusters"][0]["topic"] == "energy"
    assert clusters["energy"]["link_lookup_status"] == "done"
    assert clusters["solar"]["link_lookup_status"] == "not_rendered"
    assert clusters["solar"]["link_members"] == []
    looked_up = {path for _, path, _ in fake.graph_calls}
    assert looked_up == {A, B, C}
    assert all(op == "neighbors" and limit is None for op, _, limit in fake.graph_calls)


def test_link_stats_count_lookups_attempts_members_and_uncached(tmp_path, monkeypatch):
    """F5/F7 counters: 5 member lookups, 1 attempt each, X in two clusters, U uncached."""
    _, report = _run_tag(tmp_path, monkeypatch, _GraphFake())
    assert report["link_stats"] == {
        "lookups": 5, "attempts": 5, "failed": 0,
        "clusters_skipped_budget": 0, "members_total": 2, "skipped_uncached": 1,
    }


def test_budget_exhausted_cluster_is_skipped_and_counted(tmp_path, monkeypatch):
    """F5-AC1: three 20-attempt lookups spend the 60 budget; solar is skipped_budget,
    proposals are still written and the exit code is unchanged."""
    (tmp_path / "base").mkdir()
    (tmp_path / "budget").mkdir()
    code_base, _ = _run_tag(tmp_path / "base", monkeypatch, _GraphFake(links={}))
    fake = _GraphFake(attempts_per_call=20)
    code, report = _run_tag(tmp_path / "budget", monkeypatch, fake)
    clusters = _by_topic(report)
    assert clusters["energy"]["link_lookup_status"] == "done"
    assert clusters["solar"]["link_lookup_status"] == "skipped_budget"
    assert clusters["solar"]["link_members"] == []
    assert report["link_stats"]["clusters_skipped_budget"] == 1
    assert report["link_stats"]["attempts"] == 60
    assert code == code_base


def test_failed_lookup_marks_only_that_cluster(tmp_path, monkeypatch):
    """F5-AC4: a Kado error on delta fails solar; energy keeps its link members."""

    class _FailOnDelta(_GraphFake):
        def graph(self, operation, path, limit=None):
            if path == D:
                self.graph_calls.append((operation, path, limit))
                self.attempt_count += 1
                raise KadoError("boom")
            return super().graph(operation, path, limit)

    _, report = _run_tag(tmp_path, monkeypatch, _FailOnDelta())
    clusters = _by_topic(report)
    assert clusters["solar"]["link_lookup_status"] == "failed"
    assert clusters["solar"]["link_members"] == []
    assert set(_members(clusters["energy"])) == {"xenon"}
    assert report["link_stats"]["failed"] == 1


# ── Two-pass flow and degraded Kado ──────────────────────────────────────────


def test_emit_phase1_makes_no_graph_call(tmp_path, monkeypatch):
    """`--emit-phase1` exits after Phase 1: the fake records zero graph calls."""
    config = _write_config(tmp_path)
    cache = _write_cache(tmp_path)
    fake = _GraphFake()
    monkeypatch.setattr(_moc_disc, "_build_kado_client", lambda: fake)
    out = tmp_path / "phase1.json"
    code, _ = _run(["--tag", "science", *_common_args(tmp_path, config, cache),
                    "--emit-phase1", str(out)])
    assert code == 0 and out.exists()
    assert fake.graph_calls == []


def test_null_kado_client_fails_every_rendered_cluster_exit_unchanged(tmp_path, monkeypatch):
    """No Kado: `_NullKadoClient.graph` raises → every rendered cluster failed,
    proposals still emitted, exit code identical to a run with a working graph."""
    cands = _candidates((A, ["energy"]), (B, ["energy"]), (C, ["energy"]),
                        (D, ["solar"]), (E, ["solar"]))
    (tmp_path / "ok").mkdir()
    monkeypatch.setattr(_moc_disc, "_build_kado_client", lambda: _GraphFake())
    code_ok, _ = _run_phase1_input(tmp_path / "ok", cands)

    def _no_kado(*_a, **_k):
        raise KadoError("no kado in tests")

    monkeypatch.undo()
    monkeypatch.setattr(_kado_mod, "KadoClient", _no_kado)
    (tmp_path / "null").mkdir()
    code, report = _run_phase1_input(tmp_path / "null", cands)
    assert code == code_ok
    assert len(report["topic_clusters"]) == 2
    for cluster in report["topic_clusters"]:
        assert cluster["link_lookup_status"] == "failed"
        assert cluster["link_members"] == []
    assert report["link_stats"]["clusters_skipped_budget"] == 0
    assert report["link_stats"]["members_total"] == 0


def test_null_kado_client_graph_raises_kado_error():
    """The stand-in exposes the budget surface LinkLookup reads, and graph raises."""

    def _no_kado(*_a, **_k):
        raise KadoError("no kado")

    orig = _kado_mod.KadoClient
    _kado_mod.KadoClient = _no_kado
    try:
        client = _moc_disc._build_kado_client()
    finally:
        _kado_mod.KadoClient = orig
    assert client.attempt_count == 0
    assert client.attempt_gate is None
    assert client.min_interval == 0.0
    try:
        client.graph("neighbors", A)
    except KadoError:
        pass
    else:  # pragma: no cover
        raise AssertionError("graph must raise KadoError")


# ── Topic-only invariants ────────────────────────────────────────────────────


def test_squelch_signature_and_confidence_unchanged_by_link_members(tmp_path, monkeypatch):
    """ADR-2: squelch signature, confidence, items and candidate_stems are the same
    with and without link members."""
    (tmp_path / "plain").mkdir()
    (tmp_path / "linked").mkdir()
    _, plain = _run_tag(tmp_path / "plain", monkeypatch, _GraphFake(links={}))
    _, linked = _run_tag(tmp_path / "linked", monkeypatch, _GraphFake())
    p, lnk = _by_topic(plain)["energy"], _by_topic(linked)["energy"]
    assert p["link_members"] == [] and lnk["link_members"]
    assert compute_topic_signature(p) == compute_topic_signature(lnk)
    for key in ("confidence", "items", "candidate_stems", "cluster_id"):
        assert p[key] == lnk[key], key


# ── Pass 2 member re-check and stem collisions ───────────────────────────────


def test_phase1_input_members_rechecked_by_eligibility(tmp_path, monkeypatch):
    """Pass 2 trusts --phase1-input: a periodic note smuggled in as a topic member
    is not looked up and cannot bridge (Y linked with alpha + the daily → no member)."""
    links = {A: [Y], B: [], C: [], DAILY: [Y]}
    fake = _GraphFake(links=links)
    monkeypatch.setattr(_moc_disc, "_build_kado_client", lambda: fake)
    cands = _candidates((A, ["energy"]), (B, ["energy"]), (C, ["energy"]),
                        (DAILY, ["energy"]))
    _, report = _run_phase1_input(tmp_path, cands)
    energy = _by_topic(report)["energy"]
    assert "2026-01-01" in energy["items"]
    assert energy["link_lookup_status"] == "done"
    assert DAILY not in {path for _, path, _ in fake.graph_calls}
    assert energy["link_members"] == []


def test_stem_collision_builds_lookup_map_by_path(tmp_path, monkeypatch):
    """Two candidates share the stem 'alpha'. Both paths are looked up, and the
    one the other members link to is a topic member, not a link member."""
    a2 = f"{_BASE}2021 Thoughts/alpha.md"
    notes = [*_NOTES, {"path": a2, "topics": ["energy", "a2"]}]
    links = {A: [], a2: [X], B: [A, X], C: [A]}
    fake = _GraphFake(links=links)
    monkeypatch.setattr(_moc_disc, "_build_kado_client", lambda: fake)
    cands = _candidates((A, ["energy"]), (a2, ["energy"]), (B, ["energy"]),
                        (C, ["energy"]))
    _, report = _run_phase1_input(tmp_path, cands, notes=notes)
    energy = _by_topic(report)["energy"]
    assert {path for _, path, _ in fake.graph_calls} == {A, a2, B, C}
    members = _members(energy)
    assert "alpha" not in members
    assert members["xenon"]["linked_with"] == ["alpha", "beta"]


def test_colliding_stems_count_by_path_and_render_shared_name_once(tmp_path, monkeypatch):
    """Owner decision O4: two notes named `alpha` that both link X make X a link
    member (2 distinct member paths); the reason shows `alpha` once."""
    a2 = f"{_BASE}2021 Thoughts/alpha.md"
    notes = [*_NOTES, {"path": a2, "topics": ["energy", "a2"]}]
    links = {A: [X], a2: [X], B: [], C: []}
    fake = _GraphFake(links=links)
    monkeypatch.setattr(_moc_disc, "_build_kado_client", lambda: fake)
    cands = _candidates((A, ["energy"]), (a2, ["energy"]), (B, ["energy"]),
                        (C, ["energy"]))
    _, report = _run_phase1_input(tmp_path, cands, notes=notes)
    members = _members(_by_topic(report)["energy"])
    assert members["xenon"]["linked_with"] == ["alpha"]
