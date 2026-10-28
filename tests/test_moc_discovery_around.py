#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_around.py — `--around` resolver and new-MOC builder (spec 042 T3.1).

Drives moc-discovery main() in-process with a graph-capable fake Kado client
(no live Kado, no ~/.tomo, no tomo-instance). Fixture vault (miyo profile):

  knowledge  seed; topics habits/goals; links argon, neon, an uncached note,
             a daily note and a MOC → 2 eligible neighbours
  lonely     links neon, an uncached note, a daily note, a MOC → 1 eligible
  solar      a note AND a MOC with that stem (ambiguous)
  twin       two notes with that stem (ambiguous)
  2026-01-02 a cached daily note (periodic)
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("moc_discovery_around", SCRIPT_PATH)
_moc_disc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery_around"] = _moc_disc
_spec.loader.exec_module(_moc_disc)

from lib.kado_client import KadoBudgetExhausted, KadoError, KadoNotFoundError, KadoToolError  # noqa: E402

_BASE = "Atlas/202 Notes/"
SEED = f"{_BASE}knowledge.md"
LONELY = f"{_BASE}lonely.md"
ARGON = f"{_BASE}argon.md"
NEON = f"{_BASE}neon.md"
UNCACHED = f"{_BASE}uncached.md"
SOLAR_NOTE = f"{_BASE}solar.md"
SOLAR_MOC = "Atlas/200 Maps/solar.md"
TWIN_A = f"{_BASE}twin.md"
TWIN_B = f"{_BASE}2021 Thoughts/twin.md"
MOC_PATH = "Atlas/200 Maps/Gardening (MOC).md"
DAILY_CACHED = "Calendar/301 Daily/2026-01-02.md"
DAILY_UNCACHED = "Calendar/301 Daily/2026-01-01.md"
INBOX_NOTE = "100 Inbox/raw-idea.md"
OUTSIDE_NOTE = "Projects/Elsewhere/stray.md"
EXCLUDED_NOTE = f"{_BASE}secret.md"

_NOTES = [
    {"path": SEED, "topics": ["habits", "goals"]},
    {"path": LONELY, "topics": ["lonely-topic"]},
    {"path": ARGON, "topics": ["argon-topic"]},
    {"path": NEON, "topics": ["neon-topic"], "up_state": "valid",
     "up_target": "Gardening (MOC)"},
    {"path": SOLAR_NOTE, "topics": ["solar"]},
    {"path": TWIN_A, "topics": ["twin"]},
    {"path": TWIN_B, "topics": ["twin"]},
    {"path": DAILY_CACHED, "topics": ["day"]},
    {"path": INBOX_NOTE, "topics": ["raw"]},
    {"path": OUTSIDE_NOTE, "topics": ["stray"]},
    {"path": EXCLUDED_NOTE, "topics": ["secret"], "tags": ["MiYo/Tomo/exclude/note"]},
]

_LINKS = {
    SEED: [ARGON, NEON, UNCACHED, DAILY_UNCACHED, MOC_PATH],
    LONELY: [NEON, UNCACHED, DAILY_UNCACHED, MOC_PATH],
}


def _stem(path: str) -> str:
    return path.rsplit("/", 1)[-1].removesuffix(".md")


class _GraphFake:
    """Kado fake with the graph budget surface KadoClient exposes."""

    def __init__(self, links=None, attempts_per_call=1, graph_error=None):
        self.links = dict(links if links is not None else _LINKS)
        self.attempts_per_call = attempts_per_call
        self.graph_error = graph_error
        self.graph_calls: list[tuple[str, str, object]] = []
        self.read_calls: list[str] = []
        self.attempt_count = 0
        self.attempt_gate = None
        self.min_interval = 0.0

    def graph(self, operation, path, limit=None):
        self.graph_calls.append((operation, path, limit))
        for _ in range(self.attempts_per_call):
            if self.attempt_gate is not None and not self.attempt_gate():
                raise KadoBudgetExhausted("budget")
            self.attempt_count += 1
        if self.graph_error is not None:
            raise self.graph_error
        return [{"path": p, "relation": "outgoing"} for p in self.links.get(path, [])]

    def read_note(self, path):
        self.read_calls.append(path)
        if path == SEED:
            return {"content": "up:: [[Gardening (MOC)]]\n"}
        return {"content": "# stub\n"}

    def search_by_tag(self, *_a, **_k):  # pragma: no cover
        raise AssertionError("around: must not search by tag")

    def list_dir(self, *_a, **_k):  # pragma: no cover
        raise AssertionError("around: must not list folders")


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _write_config(tmp_path: Path) -> Path:
    cfg = {
        "profile": "miyo",
        "tomo": {"moc_proposal": {"min_notes": 2, "max_results": 5, "candidate_cap": 200}},
    }
    p = tmp_path / "vault-config.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return p


def _write_cache(tmp_path: Path) -> Path:
    entries = [
        {"path": MOC_PATH, "kind": "moc", "title": "Gardening (MOC)",
         "topics": ["gardening"], "tags": []},
        {"path": SOLAR_MOC, "kind": "moc", "title": "solar", "topics": ["solar"], "tags": []},
    ]
    for n in _NOTES:
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


def _run(argv: list[str]) -> tuple[int, dict | None]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = _moc_disc.main(argv)
    text = out.getvalue().strip()
    return code, (json.loads(text) if text else None)


def _run_around(tmp_path, monkeypatch, target, fake=None, extra=()):
    fake = fake if fake is not None else _GraphFake()
    config = _write_config(tmp_path)
    cache = _write_cache(tmp_path)
    squelch = tmp_path / "state" / "moc-squelch.json"
    monkeypatch.setattr(_moc_disc, "_build_kado_client", lambda: fake)
    code, report = _run([
        "--around", target, "--config", str(config), "--cache", str(cache),
        "--squelch-state", str(squelch), *extra,
    ])
    return code, report, fake


# ── Resolution — F2-AC3 ──────────────────────────────────────────────────────


@pytest.mark.parametrize("target", [
    "knowledge", "[[knowledge]]", "[[knowledge|Wissen]]", "knowledge.md",
    SEED, SEED.removesuffix(".md"), "KNOWLEDGE", SEED.lower(),
])
def test_resolution_forms_reach_the_cached_seed(tmp_path, monkeypatch, target):
    """stem, [[stem]], stem.md and a vault path resolve to the cache's own path."""
    _, report, fake = _run_around(tmp_path, monkeypatch, target)
    assert report["abort_reason"] is None
    assert report["around"] == {"kind": "note", "path": SEED, "stem": "knowledge"}
    assert fake.graph_calls == [("neighbors", SEED, None)]


def test_moc_and_note_with_same_name_abort_listing_both(tmp_path, monkeypatch):
    _, report, fake = _run_around(tmp_path, monkeypatch, "solar")
    assert report["abort_reason"] == "around-ambiguous"
    assert SOLAR_NOTE in report["abort_message"] and SOLAR_MOC in report["abort_message"]
    assert report["topic_clusters"] == []
    assert fake.graph_calls == []


def test_two_notes_with_same_stem_abort_listing_both(tmp_path, monkeypatch):
    _, report, fake = _run_around(tmp_path, monkeypatch, "[[twin]]")
    assert report["abort_reason"] == "around-ambiguous"
    assert TWIN_A in report["abort_message"] and TWIN_B in report["abort_message"]
    assert fake.graph_calls == []


def test_ambiguous_name_resolves_when_given_a_path(tmp_path, monkeypatch):
    _, report, _ = _run_around(tmp_path, monkeypatch, TWIN_B)
    assert report["around"] == {"kind": "note", "path": TWIN_B, "stem": "twin"}


@pytest.mark.parametrize("target", ["nothere", UNCACHED])
def test_uncached_target_is_not_found_with_remedy(tmp_path, monkeypatch, target):
    """F2-AC3: no name-search fallback; the message names the argument and the remedy."""
    _, report, fake = _run_around(tmp_path, monkeypatch, target)
    assert report["abort_reason"] == "around-not-found"
    assert report["abort_message"] == (
        f"around: '{target}' not found — rebuild the cache or give a path"
    )
    assert report["around"] is None
    assert report["topic_clusters"] == []
    assert fake.graph_calls == []


# ── Refusals and routing ─────────────────────────────────────────────────────


@pytest.mark.parametrize("target", ["2026-01-02", DAILY_CACHED, DAILY_UNCACHED])
def test_periodic_seed_is_refused(tmp_path, monkeypatch, target):
    """A periodic seed is refused — also by path when the daily note is not cached."""
    _, report, fake = _run_around(tmp_path, monkeypatch, target)
    assert report["abort_reason"] == "around-periodic"
    assert report["abort_message"] == "around: periodic notes cannot be a MOC seed"
    assert report["topic_clusters"] == []
    assert fake.graph_calls == []


def test_moc_seed_routes_to_extension_stub(tmp_path, monkeypatch):
    """F3 routing: a MOC seed resolves to kind moc and reaches the Phase 4 stub."""
    _, report, fake = _run_around(tmp_path, monkeypatch, "Gardening (MOC)")
    assert report["around"] == {"kind": "moc", "path": MOC_PATH, "stem": "Gardening (MOC)"}
    assert report["abort_reason"] == "around-moc-pending"
    assert report["topic_clusters"] == []
    assert fake.graph_calls == []


@pytest.mark.parametrize("target, reason", [
    (INBOX_NOTE, "it is still in the inbox"),
    (OUTSIDE_NOTE, "it is outside the atomic-note folders"),
    (EXCLUDED_NOTE, "it is tagged exclude/note"),
], ids=["inbox", "out-of-scope", "excluded-tag"])
def test_ineligible_note_seed_is_refused_with_its_reason(tmp_path, monkeypatch, target, reason):
    """Owner decision A: a seed must pass the same eligibility as a link member."""
    _, report, fake = _run_around(tmp_path, monkeypatch, target)
    stem = _stem(target)
    assert report["abort_reason"] == "around-ineligible"
    assert report["abort_message"] == f"around: '{stem}' cannot seed a MOC — {reason}"
    assert report["topic_clusters"] == []
    assert fake.graph_calls == []


# ── Builder — F2-AC1 ─────────────────────────────────────────────────────────


def test_two_eligible_neighbours_build_one_new_moc_cluster(tmp_path, monkeypatch):
    code, report, _ = _run_around(tmp_path, monkeypatch, "knowledge")
    assert code == 0
    assert report["mode"] == "around"
    assert report["trigger_arg"] == "knowledge"
    assert report["abort_reason"] is None
    [cluster] = report["topic_clusters"]
    assert cluster["cluster_id"] == "MOC01"
    assert cluster["title"] == "knowledge (MOC)"
    assert cluster["items"] == ["knowledge"]
    assert cluster["candidate_stems"] == ["knowledge"]
    assert cluster["link_lookup_status"] == "done"
    assert cluster["link_members"] == [
        {"stem": "argon", "path": ARGON, "linked_with": ["knowledge"],
         "up_state": "absent", "up_target": None},
        {"stem": "neon", "path": NEON, "linked_with": ["knowledge"],
         "up_state": "valid", "up_target": "Gardening (MOC)"},
    ]
    assert cluster["existing_up"] == [
        {"stem": "knowledge", "state": "valid", "target": "Gardening (MOC)"}
    ]
    assert report["candidates"][0]["path"] == SEED


def test_parent_options_come_from_seed_topics_not_its_name(tmp_path, monkeypatch):
    """Seed topics habits/goals → Personal Management; the stem 'knowledge' scores nothing."""
    _, report, _ = _run_around(tmp_path, monkeypatch, "knowledge")
    parents = report["parent_options_per_cluster"]["MOC01"]
    assert [p["moc_stem"] for p in parents] == ["2100 - Personal Management"]


def test_fewer_than_two_eligible_neighbours_abort(tmp_path, monkeypatch):
    """F2-AC2: lonely has one eligible neighbour → no cluster, 'fewer than 3 notes'."""
    _, report, fake = _run_around(tmp_path, monkeypatch, "lonely")
    assert report["abort_reason"] == "fewer-than-3-notes"
    assert "fewer than 3 notes" in report["abort_message"]
    assert report["topic_clusters"] == []
    assert report["around"] == {"kind": "note", "path": LONELY, "stem": "lonely"}
    assert report["link_stats"]["attempts"] == 1
    assert fake.graph_calls == [("neighbors", LONELY, None)]


@pytest.mark.parametrize("fake_kwargs", [
    {"graph_error": KadoError("boom")},
    {"attempts_per_call": 61},
])
def test_seed_lookup_failure_is_reported_not_as_too_few(tmp_path, monkeypatch, fake_kwargs):
    """F5-AC5: a failed (or budget-refused) seed lookup never reads 'fewer than 3 notes'."""
    _, report, _ = _run_around(tmp_path, monkeypatch, "knowledge", _GraphFake(**fake_kwargs))
    assert report["abort_reason"] == "seed-lookup-failed"
    assert "seed lookup failed" in report["abort_message"]
    assert "fewer than 3" not in report["abort_message"]
    assert report["topic_clusters"] == []


@pytest.mark.parametrize("error", [KadoNotFoundError("gone"), KadoToolError("denied")])
def test_cached_seed_that_kado_refuses_is_a_seed_lookup_failure(tmp_path, monkeypatch, error):
    """Owner decision W1: a cached seed Kado refuses is not 'not found'; it names the seed."""
    _, report, _ = _run_around(tmp_path, monkeypatch, "knowledge", _GraphFake(graph_error=error))
    assert report["abort_reason"] == "seed-lookup-failed"
    assert "knowledge" in report["abort_message"]
    assert report["topic_clusters"] == []


def test_healthy_seed_costs_exactly_one_attempt(tmp_path, monkeypatch):
    _, report, fake = _run_around(tmp_path, monkeypatch, "knowledge")
    assert fake.graph_calls == [("neighbors", SEED, None)]
    assert report["link_stats"] == {
        "lookups": 1, "attempts": 1, "failed": 0,
        "clusters_skipped_budget": 0, "members_total": 2, "skipped_uncached": 1,
    }
    assert fake.attempt_gate is None  # LinkLookup restored the client


def test_around_never_reads_or_writes_the_squelch_registry(tmp_path, monkeypatch):
    def _forbidden(*_a, **_k):
        raise AssertionError("around: touched the squelch registry")

    for name in ("_squelch_load_registry", "_squelch_decrement_all",
                 "_squelch_save_registry_atomic"):
        monkeypatch.setattr(_moc_disc, name, _forbidden)
    _, report, _ = _run_around(tmp_path, monkeypatch, "knowledge")
    assert len(report["topic_clusters"]) == 1
    assert report["squelched"] == []
    assert not (tmp_path / "state" / "moc-squelch.json").exists()


# ── CLI surface ──────────────────────────────────────────────────────────────


def _ns(**overrides) -> Namespace:
    base = dict(tag=None, folder=None, klass=None, title=None, around=None, free_text=None)
    base.update(overrides)
    return Namespace(**base)


def test_route_input_maps_around_flag():
    assert _moc_disc.route_input(_ns(around="knowledge")) == ("around", "knowledge")


def test_route_input_rejects_empty_around():
    with pytest.raises(ValueError):
        _moc_disc.route_input(_ns(around=""))


def test_route_input_leaves_around_prefix_in_free_text_alone():
    """The `around:` prefix is routed by the agent prose; the script sees --around only."""
    assert _moc_disc.route_input(_ns(free_text="around:knowledge")) == (
        "free-text", "around:knowledge",
    )


def test_around_excludes_other_scope_flags():
    with pytest.raises(SystemExit):
        _moc_disc.build_parser().parse_args(["--around", "x", "--tag", "y"])


@pytest.mark.parametrize("flag", ["--emit-phase1", "--phase1-input", "--check-moc-uplinks"])
def test_around_with_two_pass_or_check_flags_is_fatal(tmp_path, monkeypatch, flag):
    """Single pass: combining --around with Pass 1/2 or the uplink check exits 2, writes nothing."""
    p1 = tmp_path / "phase1.json"
    extra = [flag] if flag == "--check-moc-uplinks" else [flag, str(p1)]
    code, report, fake = _run_around(tmp_path, monkeypatch, "knowledge", extra=extra)
    assert code == 2
    assert report is None
    assert not p1.exists()
    assert fake.graph_calls == []


def test_empty_report_has_around_none():
    assert _moc_disc.empty_report("scan", "", "miyo")["around"] is None
