"""Spec 042 T1.2/T1.3 — NodeEligibility, LinkLookup and augment_clusters.

Eligibility tests start from ONE eligible cached note and change exactly one
thing, so each rule is falsified on its own (PRD F6-AC1, F6-AC2, F6-AC4).
Lookup/augment tests run against a graph fake that counts attempts and honours
the client's attempt gate like KadoClient does (PRD F1, F5-AC1, F5-AC4, F6-AC3).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tomo" / "scripts"))

from lib.kado_client import KadoBudgetExhausted, KadoError  # noqa: E402
from lib.link_members import (  # noqa: E402
    LinkLookup,
    LinkMember,
    NodeEligibility,
    augment_clusters,
)

GOOD = "Vault/Notes/Idea.md"

PROFILE = {
    "concept_defaults": {
        "inbox": "Vault/Inbox/",
        "atomic_note": {
            "base_path": "Vault/Notes/",
            "subdirectories": [{"path": "Vault/Notes/Sub/"}],
        },
        "map_note": {"name_suffix": " (MOC)"},
        "calendar": {
            "base_path": "Vault/Cal/",
            "granularities": {
                "daily": {"enabled": True, "path": "Vault/Cal/Days/"},
                "weekly": {"enabled": True, "path": "Vault/Cal/Weeks/"},
                "yearly": {"enabled": False, "path": None},
            },
        },
    }
}

VAULT_CFG = {
    "concepts": {
        "calendar": {"granularities": {"daily": {"path": "Vault/Notes/Journal/ "}}},
    },
    "tomo": {"moc_structure_cache": {"exclude_paths": ["Vault/Notes/Private/"]}},
}


def _entry(path, kind="note", tags=None):
    return {"path": path, "kind": kind, "tags": tags or []}


def _make(extra_entries=(), profile=PROFILE, vault_cfg=VAULT_CFG):
    entries = [_entry(GOOD)] + list(extra_entries)
    cache = {
        "entries": entries,
        "map_notes": [e for e in entries if e["kind"] == "moc"],
    }
    return NodeEligibility(cache, copy.deepcopy(profile), copy.deepcopy(vault_cfg))


class TestEligibility:
    def test_cached_atomic_note_is_eligible(self):
        assert _make().check(GOOD) == (True, "ok")

    def test_non_md_path(self):
        e = _make([_entry("Vault/Notes/pic.png")])
        assert e.check("Vault/Notes/pic.png") == (False, "not-md")

    def test_outside_atomic_note_paths(self):
        p = "Elsewhere/Idea.md"
        assert _make([_entry(p)]).check(p) == (False, "out-of-scope")

    def test_atomic_subdirectory_is_in_scope(self):
        p = "Vault/Notes/Sub/Deep.md"
        assert _make([_entry(p)]).check(p) == (True, "ok")

    def test_sibling_prefix_is_not_in_scope(self):
        p = "Vault/Notes2/Idea.md"
        assert _make([_entry(p)]).check(p) == (False, "out-of-scope")

    def test_inbox_path(self):
        profile = copy.deepcopy(PROFILE)
        profile["concept_defaults"]["atomic_note"]["base_path"] = "Vault/"
        p = "Vault/Inbox/Draft.md"
        e = _make([_entry(p)], profile=profile)
        assert e.check(p) == (False, "inbox")

    def test_inbox_from_vault_config_overrides_profile(self):
        cfg = copy.deepcopy(VAULT_CFG)
        cfg["concepts"]["inbox"] = "Vault/Notes/Landing/"
        p = "Vault/Notes/Landing/Draft.md"
        assert _make([_entry(p)], vault_cfg=cfg).check(p) == (False, "inbox")

    @pytest.mark.parametrize(
        "path",
        [
            "Vault/Cal/2026-10-01.md",  # profile calendar base_path
            "Vault/Cal/Days/2026-10-01.md",  # profile granularity
            "Vault/Cal/Weeks/2026-W40.md",  # profile granularity
            "Vault/Notes/Journal/2026-10-01.md",  # vault-config, trailing space
            "Vault/Notes/Private/Secret.md",  # exclude_paths
        ],
    )
    def test_periodic_path(self, path):
        profile = copy.deepcopy(PROFILE)
        profile["concept_defaults"]["atomic_note"]["base_path"] = "Vault/"
        e = _make([_entry(path)], profile=profile)
        assert e.check(path) == (False, "periodic")
        assert e.is_periodic(path)
        assert not e.is_periodic(GOOD)

    def test_vault_config_calendar_base_path(self):
        cfg = copy.deepcopy(VAULT_CFG)
        cfg["concepts"]["calendar"]["base_path"] = "Vault/Notes/Cal2/"
        p = "Vault/Notes/Cal2/x.md"
        e = _make([_entry(p)], vault_cfg=cfg)
        assert e.check(p) == (False, "periodic")

    def test_real_profile_and_trailing_space_daily(self):
        profile = yaml.safe_load((REPO_ROOT / "tomo/profiles/miyo.yaml").read_text())
        cfg = {
            "concepts": {
                "calendar": {
                    "base_path": "Calendar/",
                    "granularities": {"daily": {"path": "Calendar/301 Daily/ "}},
                }
            }
        }
        note = "Atlas/202 Notes/2021 Thoughts/Idea.md"
        daily = "Calendar/301 Daily/2026-10-01.md"
        e = NodeEligibility(
            {"entries": [_entry(note), _entry(daily)], "map_notes": []}, profile, cfg
        )
        assert e.check(note) == (True, "ok")
        assert e.check(daily) == (False, "periodic")

    def test_moc_by_cache_kind(self):
        p = "Vault/Notes/Hub.md"
        e = _make([_entry(p, kind="moc")])
        assert e.check(p) == (False, "moc")
        assert e.is_moc(p) and not e.is_moc(GOOD)

    def test_moc_by_map_notes(self):
        p = "Vault/Notes/Hub.md"
        cache = {"entries": [_entry(GOOD), _entry(p)], "map_notes": [{"path": p}]}
        e = NodeEligibility(cache, PROFILE, VAULT_CFG)
        assert e.check(p) == (False, "moc")

    def test_moc_by_name_suffix(self):
        p = "Vault/Notes/Cooking (MOC).md"
        e = _make([_entry(p)])
        assert e.check(p) == (False, "moc")

    @pytest.mark.parametrize("tag", ["MiYo/Tomo/exclude/note", "#MiYo/Tomo/exclude/note"])
    def test_exclude_note_tag(self, tag):
        p = "Vault/Notes/Hidden.md"
        e = _make([_entry(p, tags=["topic/x", tag])])
        assert e.check(p) == (False, "excluded-tag")

    def test_exclude_moc_tag_does_not_exclude_a_note(self):
        p = "Vault/Notes/Other.md"
        e = _make([_entry(p, tags=["MiYo/Tomo/exclude/moc"])])
        assert e.check(p) == (True, "ok")

    def test_uncached_path(self):
        assert _make().check("Vault/Notes/New.md") == (False, "uncached")

    def test_periodic_and_uncached_reports_periodic(self):
        assert _make().check("Vault/Cal/Days/2026-10-02.md") == (False, "periodic")

    def test_missing_config_sections_do_not_raise(self):
        e = NodeEligibility({"entries": [_entry(GOOD)]}, {}, {})
        assert e.check(GOOD) == (True, "ok")

    def test_module_never_prints_or_logs(self, capsys):
        e = _make()
        for p in (GOOD, "Elsewhere/x.md", "Vault/Notes/New.md"):
            e.check(p)
        out = capsys.readouterr()
        assert out.out == "" and out.err == ""


# ── T1.3: LinkLookup and augment_clusters ─────────────────────────────────────

N = "Vault/Notes/"
DAILY = "Vault/Cal/Days/2025-06-04.md"


class FakeGraphClient:
    """kado-graph `neighbors` over a fixed adjacency, shaped like Kado's nodes.

    Copied in spirit from tests/test_instruction_render_up_preservation.py.
    Each call spends ``attempts[path]`` HTTP attempts (default 1, i.e. retries
    when > 1); the attempt gate is consulted before every attempt, as in
    KadoClient._call_tool. Paths in ``fail`` raise KadoError after sending.
    """

    def __init__(self, adjacency, attempts=None, fail=()):
        self._adj = adjacency
        self._attempts = dict(attempts or {})
        self._fail = set(fail)
        self.graph_calls: list[tuple[str, str, object]] = []
        self.attempt_count = 0
        self.attempt_gate = None
        self.min_interval = 0.0

    def graph(self, operation: str, path: str, limit: int | None = None) -> list[dict]:
        self.graph_calls.append((operation, path, limit))
        for _ in range(self._attempts.get(path, 1)):
            if self.attempt_gate is not None and not self.attempt_gate():
                raise KadoBudgetExhausted("budget")
            self.attempt_count += 1
        if path in self._fail:
            raise KadoError("HTTP 500 from Kado")
        assert operation == "neighbors"
        return [{"path": p, "relation": "outgoing"} for p in self._adj.get(path, [])]


def _note(stem, kind="note", up_state="absent", up_target=None, folder=N):
    return {
        "path": f"{folder}{stem}.md",
        "stem": stem,
        "kind": kind,
        "tags": [],
        "up_state": up_state,
        "up_target": up_target,
    }


def _world(adjacency, notes=(), **client_kw):
    """Cache with A..Y as plain notes plus `notes`; adjacency keyed by stem."""
    entries = [_note(s) for s in ("A", "B", "C", "D", "E", "F", "X", "Y", "W")]
    entries.append(_note("Z", kind="moc"))
    entries.append(_note("2025-06-04", folder="Vault/Cal/Days/"))
    entries += list(notes)
    cache = {"entries": entries, "map_notes": [e for e in entries if e["kind"] == "moc"]}
    stem_to_path = {e["stem"]: e["path"] for e in entries}

    def p(stem):
        return stem_to_path.get(stem, f"{N}{stem}.md")

    adj = {p(k): [p(v) for v in vs] for k, vs in adjacency.items()}
    client = FakeGraphClient(adj, **{
        k: ({p(s): n for s, n in v.items()} if k == "attempts" else {p(s) for s in v})
        for k, v in client_kw.items()
    })
    elig = NodeEligibility(cache, PROFILE, VAULT_CFG)
    return client, cache, stem_to_path, elig


def _cluster(cid, *stems):
    return {"cluster_id": cid, "items": list(stems)}


def _run(clusters, adjacency, budget=60, notes=(), **client_kw):
    client, cache, stem_to_path, elig = _world(adjacency, notes, **client_kw)
    lookup = LinkLookup(client, budget=budget)
    result = augment_clusters(clusters, stem_to_path, lookup, elig, cache)
    return result, client, lookup


def _stems(result, cid):
    return [m.stem for m in result.clusters[cid].link_members]


class TestLookup:
    def test_neighbors_returns_paths_and_never_passes_limit(self):
        client, _, s2p, _ = _world({"A": ["X", "Y"]})
        lookup = LinkLookup(client)
        assert lookup.neighbors(s2p["A"]) == [s2p["X"], s2p["Y"]]
        assert client.graph_calls == [("neighbors", s2p["A"], None)]

    def test_memoised_across_clusters(self):
        adjacency = {"A": ["X"], "B": ["X"], "C": ["X"]}
        result, client, lookup = _run(
            [_cluster("c1", "A", "B"), _cluster("c2", "A", "C")], adjacency
        )
        called = [c[1] for c in client.graph_calls]
        assert called.count(f"{N}A.md") == 1
        assert len(called) == 3
        assert lookup.cached(f"{N}A.md")

    def test_installs_gate_and_pacing_and_counts_attempts(self):
        client, _, s2p, _ = _world({"A": ["X"]}, attempts={"A": 3})
        lookup = LinkLookup(client, budget=10)
        lookup.__enter__()
        assert client.min_interval == 0.3
        assert client.attempt_gate is not None
        lookup.neighbors(s2p["A"])
        assert lookup.attempts == 3
        assert lookup.remaining() == 7

    def test_attempts_are_counted_from_construction(self):
        client, _, s2p, _ = _world({"A": ["X"]})
        client.attempt_count = 5
        lookup = LinkLookup(client, budget=10)
        lookup.neighbors(s2p["A"])
        assert lookup.attempts == 1 and lookup.remaining() == 9

    def test_gate_refuses_send_past_budget(self):
        client, _, s2p, _ = _world({"A": ["X"]}, attempts={"A": 3})
        lookup = LinkLookup(client, budget=2)
        result = lookup.neighbors(s2p["A"])
        assert not isinstance(result, list)
        assert client.attempt_count == 2
        assert lookup.remaining() == 0

    def test_failed_lookup_is_counted_and_memoised(self):
        client, _, s2p, _ = _world({}, fail={"A"})
        lookup = LinkLookup(client)
        first = lookup.neighbors(s2p["A"])
        second = lookup.neighbors(s2p["A"])
        assert not isinstance(first, list) and not isinstance(second, list)
        assert lookup.failed == 1
        assert len(client.graph_calls) == 1

    def test_close_restores_previous_gate_and_pacing(self):
        client, _, _, _ = _world({})
        prev_gate = lambda: True  # noqa: E731
        client.attempt_gate = prev_gate
        client.min_interval = 0.05
        lookup = LinkLookup(client)
        lookup.__enter__()
        assert client.attempt_gate is not prev_gate
        assert client.min_interval == 0.3
        lookup.close()
        lookup.close()
        assert client.attempt_gate is prev_gate
        assert client.min_interval == 0.05

    def test_with_block_restores_on_exit_and_on_error(self):
        client, _, _, _ = _world({})
        with LinkLookup(client) as lookup:
            assert isinstance(lookup, LinkLookup)
            assert client.min_interval == 0.3
        assert client.attempt_gate is None and client.min_interval == 0.0
        with pytest.raises(RuntimeError):
            with LinkLookup(client):
                raise RuntimeError("boom")
        assert client.attempt_gate is None and client.min_interval == 0.0


class TestLookupCounting:
    def test_gate_refused_lookup_is_not_counted(self):
        client, _, s2p, _ = _world({"A": ["X"]})
        with LinkLookup(client, budget=0) as lookup:
            lookup.neighbors(s2p["A"])
            assert lookup.lookups == 0

    def test_successful_and_kado_error_lookups_are_counted(self):
        client, _, s2p, _ = _world({"A": ["X"]}, fail={"B"})
        with LinkLookup(client) as lookup:
            lookup.neighbors(s2p["A"])
            assert lookup.lookups == 1
            lookup.neighbors(s2p["B"])
            assert lookup.lookups == 2

    def test_construction_alone_leaves_client_untouched(self):
        client, _, _, _ = _world({})
        LinkLookup(client)
        assert client.attempt_gate is None and client.min_interval == 0.0

    def test_unentered_neighbors_is_still_gated_and_close_restores(self):
        client, _, s2p, _ = _world({"A": ["X"]}, attempts={"A": 3})
        lookup = LinkLookup(client, budget=2)
        assert not isinstance(lookup.neighbors(s2p["A"]), list)
        assert client.attempt_count == 2
        lookup.close()
        assert client.attempt_gate is None and client.min_interval == 0.0

    @pytest.mark.parametrize(
        "payload",
        [
            [{"path": "n/B.md"}, "junk", None, 7, {"path": 5}, {"relation": "x"},
             {"path": "n/B.md"}, {"path": "n/A.md"}, {"path": "n/C.md"}],
        ],
    )
    def test_malformed_neighbors_payload_keeps_only_valid_unique_non_self(self, payload):
        client, _, _, _ = _world({})
        client.graph = lambda op, path, limit=None: payload
        with LinkLookup(client) as lookup:
            assert lookup.neighbors("n/A.md") == ["n/B.md", "n/C.md"]


class TestAugment:
    def test_unmapped_stem_fails_cluster_without_graph_calls(self):
        client, cache, s2p, elig = _world({"A": ["X"], "B": ["X"], "C": ["Y"], "D": ["Y"]})
        lookup = LinkLookup(client)
        result = augment_clusters(
            [_cluster("bad", "A", "Nope"), _cluster("ok", "C", "D")],
            s2p, lookup, elig, cache,
        )
        assert result.clusters["bad"].status == "failed"
        assert result.clusters["bad"].link_members == []
        assert result.clusters["ok"].status == "done"
        called = {c[1] for c in client.graph_calls}
        assert f"{N}A.md" not in called
        assert called == {f"{N}C.md", f"{N}D.md"}

    def test_traced_example(self):
        # SDD traced example: C=[A,B,D]; X hits {A,B}, Y hits {A,D};
        # the daily and MOC Z are never counted.
        adjacency = {"A": ["X", "2025-06-04", "Y"], "B": ["X", "2025-06-04"], "D": ["Y", "Z"]}
        result, client, _ = _run(
            [_cluster("c1", "A", "B", "D"), _cluster("c2", "A", "E")], adjacency
        )
        c1 = result.clusters["c1"]
        assert c1.status == "done"
        assert c1.link_members == [
            LinkMember(stem="X", path=f"{N}X.md", linked_with=["A", "B"],
                       up_state="absent", up_target=None),
            LinkMember(stem="Y", path=f"{N}Y.md", linked_with=["A", "D"],
                       up_state="absent", up_target=None),
        ]
        called = [c[1] for c in client.graph_calls]
        assert called == [f"{N}A.md", f"{N}B.md", f"{N}D.md", f"{N}E.md"]

    def test_linked_with_is_sorted_and_up_state_from_cache(self):
        w = _note("W", up_state="valid", up_target="Cooking (MOC)")
        adjacency = {"F": ["W"], "B": ["W"]}
        result, _, _ = _run([_cluster("c1", "F", "B")], adjacency, notes=[w])
        (m,) = result.clusters["c1"].link_members
        assert m.linked_with == ["B", "F"]
        assert (m.up_state, m.up_target) == ("valid", "Cooking (MOC)")

    def test_node_in_one_member_list_is_not_added(self):  # F1-AC2
        adjacency = {"A": ["X"], "B": ["Y"]}
        result, _, _ = _run([_cluster("c1", "A", "B")], adjacency)
        assert result.clusters["c1"].status == "done"
        assert _stems(result, "c1") == []

    def test_existing_member_is_not_added(self):  # F1-AC3
        adjacency = {"A": ["B"], "B": ["A"], "D": ["A", "B"]}
        result, _, _ = _run([_cluster("c1", "A", "B", "D")], adjacency)
        assert _stems(result, "c1") == []

    def test_node_qualifying_in_two_clusters_is_in_both(self):  # F1-AC4
        adjacency = {"A": ["X"], "B": ["X"], "D": ["X"], "E": ["X"]}
        result, _, _ = _run(
            [_cluster("c1", "A", "B"), _cluster("c2", "D", "E")], adjacency
        )
        assert _stems(result, "c1") == ["X"]
        assert _stems(result, "c2") == ["X"]

    def test_periodic_hub_never_counts(self):  # F6-AC3
        adjacency = {"A": ["2025-06-04"], "B": ["2025-06-04"]}
        result, _, _ = _run([_cluster("c1", "A", "B")], adjacency)
        assert result.clusters["c1"].status == "done"
        assert _stems(result, "c1") == []

    def test_moc_hub_never_counts(self):  # F6-AC3
        adjacency = {"A": ["Z"], "B": ["Z"]}
        result, _, _ = _run([_cluster("c1", "A", "B")], adjacency)
        assert _stems(result, "c1") == []

    def test_uncached_neighbours_are_counted_not_added(self):
        adjacency = {"A": ["New"], "B": ["New"]}
        result, _, _ = _run([_cluster("c1", "A", "B")], adjacency)
        assert _stems(result, "c1") == []
        assert result.stats["skipped_uncached"] == 1

    def test_budget_skips_whole_cluster_then_smaller_runs(self):  # F5-AC1
        adjacency = {"A": ["X"], "B": ["X"], "C": ["X"], "D": ["Y"], "E": ["Y"]}
        result, client, lookup = _run(
            [_cluster("big", "A", "B", "C"), _cluster("small", "D", "E")],
            adjacency,
            budget=2,
        )
        assert result.clusters["big"].status == "skipped_budget"
        assert result.clusters["big"].link_members == []
        assert result.clusters["small"].status == "done"
        assert _stems(result, "small") == ["Y"]
        assert [c[1] for c in client.graph_calls] == [f"{N}D.md", f"{N}E.md"]
        assert result.stats["clusters_skipped_budget"] == 1

    def test_cached_lookups_need_no_budget(self):
        adjacency = {"A": ["X"], "B": ["X"]}
        result, client, _ = _run(
            [_cluster("c1", "A", "B"), _cluster("c2", "B", "A")], adjacency, budget=2
        )
        assert result.clusters["c2"].status == "done"
        assert _stems(result, "c2") == ["X"]
        assert len(client.graph_calls) == 2

    def test_budget_refused_mid_cluster_is_skipped_budget_and_counted(self):
        adjacency = {"A": ["X"], "B": ["X"]}
        result, client, lookup = _run(
            [_cluster("c1", "A", "B")], adjacency, budget=3, attempts={"A": 3}
        )
        assert result.clusters["c1"].status == "skipped_budget"
        assert result.clusters["c1"].link_members == []
        assert result.stats["clusters_skipped_budget"] == 1
        assert result.stats["failed"] == 0
        assert client.attempt_count == 3

    def test_kado_error_lookup_is_failed_not_skipped_budget(self):
        result, _, _ = _run([_cluster("c1", "A", "B")], {"A": ["X"]}, fail={"B"})
        assert result.clusters["c1"].status == "failed"
        assert result.stats["clusters_skipped_budget"] == 0

    def test_failed_lookup_fails_only_its_cluster(self):  # F5-AC4
        adjacency = {"A": ["X"], "B": ["X"], "D": ["Y"], "E": ["Y"]}
        result, _, _ = _run(
            [_cluster("c1", "A", "B"), _cluster("c2", "D", "E")], adjacency, fail={"B"}
        )
        assert result.clusters["c1"].status == "failed"
        assert result.clusters["c1"].link_members == []
        assert result.clusters["c2"].status == "done"
        assert _stems(result, "c2") == ["Y"]
        assert result.stats["failed"] == 1

    def test_stats(self):
        adjacency = {"A": ["X"], "B": ["X", "Y"], "D": ["Y"]}
        result, _, _ = _run([_cluster("c1", "A", "B", "D")], adjacency, attempts={"D": 2})
        assert result.stats == {
            "lookups": 3,
            "attempts": 4,
            "failed": 0,
            "clusters_skipped_budget": 0,
            "members_total": 2,
            "skipped_uncached": 0,
        }

    def test_input_clusters_are_not_mutated(self):
        clusters = [_cluster("c1", "A", "B")]
        before = copy.deepcopy(clusters)
        _run(clusters, {"A": ["X"], "B": ["X"]})
        assert clusters == before

    def test_never_prints(self, capsys):
        _run([_cluster("c1", "A", "B")], {"A": ["X"], "B": ["X"]}, fail={"A"})
        out = capsys.readouterr()
        assert out.out == "" and out.err == ""
