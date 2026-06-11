#!/usr/bin/env python3
# version: 0.2.0
"""test_suggestions_reducer_multi_atomic.py — F-41 T3.1 + T1.

Covers the two silent-collapse fixes in suggestions-reducer.py that let N
atomic notes from a single source coexist (C1) and keep distinct titles (C2):

  C1 — _enforce_coexistence partitions atomics by worthiness/force_atomic:
        survivors (>=0.5 or force_atomic) are kept, sub-worthy are dropped
        individually, and the daily log_entry converts to a log_link only
        when at least one survivor remains.
  C2 — per-atomic keying so N atomics in one section keep distinct titles
        through build_topic_clusters → _enrich_proposed_mocs, while the
        single-thread case stays byte-identical (CON-2).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "suggestions-reducer.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load suggestions-reducer.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("suggestions_reducer", SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["suggestions_reducer"] = _mod
_spec.loader.exec_module(_mod)

_enforce_coexistence = _mod._enforce_coexistence  # type: ignore[attr-defined]
_enrich_proposed_mocs = _mod._enrich_proposed_mocs  # type: ignore[attr-defined]
_atomic_id = _mod._atomic_id  # type: ignore[attr-defined]
build_topic_clusters = _mod.build_topic_clusters  # type: ignore[attr-defined]
ClusterCandidate = _mod.ClusterCandidate  # type: ignore[attr-defined]


# ── Factories ────────────────────────────────────────────────────────────────


def make_atomic(
    *,
    title: str,
    worthiness: float,
    stem: str = "src-note",
    force_atomic: bool | None = None,
    needs_new_moc: bool = False,
    topic: str = "",
    tags: list[str] | None = None,
) -> dict:
    a: dict = {
        "kind": "create_atomic_note",
        "suggested_title": title,
        "atomic_note_worthiness": worthiness,
        "stem": stem,
    }
    if force_atomic is not None:
        a["force_atomic"] = force_atomic
    if needs_new_moc:
        a["needs_new_moc"] = True
        a["proposed_moc_topic"] = topic
        a["classification"] = {"category": "100 Philosophy"}
        a["tags_to_add"] = tags or []
    return a


def make_update_daily(
    *,
    content: str = "did a thing",
    time: str = "09:00",
) -> dict:
    return {
        "kind": "update_daily",
        "daily_note_path": "Daily/2026-06-11.md",
        "updates": [
            {
                "kind": "log_entry",
                "time": time,
                "time_source": "frontmatter",
                "position": "append",
                "content": content,
                "reason": "logged",
            }
        ],
    }


def _log_links(actions: list[dict]) -> list[dict]:
    out: list[dict] = []
    for a in actions:
        if a.get("kind") != "update_daily":
            continue
        for u in a.get("updates") or []:
            if u.get("kind") == "log_link":
                out.append(u)
    return out


def _log_entries(actions: list[dict]) -> list[dict]:
    out: list[dict] = []
    for a in actions:
        if a.get("kind") != "update_daily":
            continue
        for u in a.get("updates") or []:
            if u.get("kind") == "log_entry":
                out.append(u)
    return out


def _atomics(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("kind") == "create_atomic_note"]


# ── C1 — _enforce_coexistence ────────────────────────────────────────────────


def test_two_survivors_both_kept_log_converted():
    """Test 1: 2 atomics (0.7, 0.6) + daily log_entry → both kept, log→link."""
    actions = [
        make_atomic(title="Alpha", worthiness=0.7),
        make_atomic(title="Beta", worthiness=0.6),
        make_update_daily(),
    ]
    out = _enforce_coexistence(actions)

    kept = _atomics(out)
    assert {a["suggested_title"] for a in kept} == {"Alpha", "Beta"}

    links = _log_links(out)
    assert len(links) == 1
    assert links[0]["target_stem"] == "Alpha"  # first survivor's title
    assert _log_entries(out) == []


def test_mixed_worthiness_drops_subworthy_keeps_survivor():
    """Test 2: atomic 0.7 + atomic 0.3 + log_entry → 0.7 kept, 0.3 dropped."""
    actions = [
        make_atomic(title="Keep", worthiness=0.7),
        make_atomic(title="Drop", worthiness=0.3),
        make_update_daily(),
    ]
    out = _enforce_coexistence(actions)

    kept = _atomics(out)
    assert [a["suggested_title"] for a in kept] == ["Keep"]

    links = _log_links(out)
    assert len(links) == 1
    assert links[0]["target_stem"] == "Keep"
    assert _log_entries(out) == []


def test_all_subworthy_drops_atomics_keeps_log_entry():
    """Test 3: atomic 0.3 + atomic 0.4 + log_entry → both dropped, log kept."""
    actions = [
        make_atomic(title="A", worthiness=0.3),
        make_atomic(title="B", worthiness=0.4),
        make_update_daily(),
    ]
    out = _enforce_coexistence(actions)

    assert _atomics(out) == []
    assert _log_links(out) == []
    entries = _log_entries(out)
    assert len(entries) == 1
    assert entries[0]["content"] == "did a thing"


def test_force_atomic_survivor_overrides_subworthiness():
    """force_atomic truthy keeps a sub-worthy atomic as a survivor."""
    actions = [
        make_atomic(title="Forced", worthiness=0.2, force_atomic=True),
        make_update_daily(),
    ]
    out = _enforce_coexistence(actions)

    kept = _atomics(out)
    assert [a["suggested_title"] for a in kept] == ["Forced"]
    links = _log_links(out)
    assert len(links) == 1
    assert links[0]["target_stem"] == "Forced"


# ── C1 — CON-2 single-thread regression ──────────────────────────────────────


def test_single_thread_coexistence_byte_identical():
    """Test 5a: 1 atomic + log_entry → exact legacy log_link shape (CON-2)."""
    actions = [
        make_atomic(title="Solo", worthiness=0.8, stem="src"),
        make_update_daily(time="07:30"),
    ]
    out = _enforce_coexistence(actions)

    assert [a["suggested_title"] for a in _atomics(out)] == ["Solo"]
    links = _log_links(out)
    assert links == [
        {
            "kind": "log_link",
            "target_stem": "Solo",
            "time": "07:30",
            "time_source": "frontmatter",
            "position": "append",
            "reason": "logged",
        }
    ]


def test_single_subworthy_atomic_dropped_log_kept():
    """Single sub-worthy atomic + log_entry → atomic dropped, log kept (legacy)."""
    actions = [
        make_atomic(title="Weak", worthiness=0.3),
        make_update_daily(),
    ]
    out = _enforce_coexistence(actions)
    assert _atomics(out) == []
    assert len(_log_entries(out)) == 1
    assert _log_links(out) == []


def test_no_log_entry_returns_actions_unchanged():
    """Early return: atomic present but no log_entry → actions untouched."""
    actions = [make_atomic(title="X", worthiness=0.9)]
    out = _enforce_coexistence(actions)
    assert out == actions


# ── C2 — per-atomic titles survive into proposed-MOC note_titles ──────────────


def _build_clusters_like_loop(atomics_per_section: dict[str, list[dict]]):
    """Mirror the reducer action-loop's keying of cluster_candidates and
    section_titles, then run the same post-processing the reducer runs.

    atomics_per_section maps section_id (e.g. "S01") → ordered list of atomic
    action dicts (each carrying needs_new_moc/proposed_moc_topic/tags).
    Returns the enriched proposed_mocs list.
    """
    cluster_candidates = []
    section_titles: dict[str, str] = {}
    for section_id, atomics in atomics_per_section.items():
        atomic_idx = 0
        for action in atomics:
            stem = action.get("stem", "")
            # Key exactly as the reducer loop does (production helper).
            atomic_id = _atomic_id(section_id, atomic_idx)
            if action.get("needs_new_moc"):
                topic_raw = (action.get("proposed_moc_topic") or "").strip()
                if topic_raw:
                    cls = action.get("classification") or {}
                    parent = cls.get("category") or ""
                    item_tags = [t for t in (action.get("tags_to_add") or []) if t]
                    cluster_candidates.append(
                        ClusterCandidate(
                            section_id=atomic_id,
                            topic=topic_raw,
                            parent=parent,
                            tags=item_tags,
                        )
                    )
            title = (action.get("suggested_title") or "").strip() or stem
            section_titles[atomic_id] = title
            atomic_idx += 1

    proposed_mocs = list(build_topic_clusters(cluster_candidates, threshold=1))
    _enrich_proposed_mocs(proposed_mocs, section_titles)
    return proposed_mocs


def test_two_atomics_same_section_distinct_titles_survive():
    """Test 4: two distinct-topic needs_new_moc atomics in ONE source → both
    titles survive into their proposed-MOC note_titles (no overwrite)."""
    atomics = [
        make_atomic(
            title="Stoicism Note", worthiness=0.8, needs_new_moc=True,
            topic="Stoicism", tags=["#philosophy"],
        ),
        make_atomic(
            title="Epicureanism Note", worthiness=0.8, needs_new_moc=True,
            topic="Epicureanism", tags=["#philosophy"],
        ),
    ]
    proposed = _build_clusters_like_loop({"S01": atomics})

    titles_by_topic = {pm["topic"]: pm["note_titles"] for pm in proposed}
    assert titles_by_topic["Stoicism"] == ["Stoicism Note"]
    assert titles_by_topic["Epicureanism"] == ["Epicureanism Note"]


def test_single_atomic_proposed_moc_byte_identical_keying():
    """Test 5b: single atomic → note_titles resolves via the bare S01 key,
    byte-identical to legacy single-thread behaviour (CON-2)."""
    atomics = [
        make_atomic(
            title="Lone Topic Note", worthiness=0.8, needs_new_moc=True,
            topic="Lone Topic", tags=["#x"],
        ),
    ]
    proposed = _build_clusters_like_loop({"S01": atomics})
    assert len(proposed) == 1
    assert proposed[0]["topic"] == "Lone Topic"
    assert proposed[0]["note_titles"] == ["Lone Topic Note"]
    # The cluster item key must be the bare section id for single-thread.
    assert proposed[0]["items"] == ["S01"]


# ── T1 — flat per-atomic suggestion_id (F-41 reversal of OQ5) ────────────────
#
# These integration tests run the full reducer via subprocess so that the
# emitted suggestions-doc.json is inspected exactly as the renderer (T2)
# and parser (T3) will consume it.  Style mirrors test_suggestions_reducer_fan_resolve.py.

REPO_ROOT_T1 = TESTS_DIR.parent
REDUCER_PATH = REPO_ROOT_T1 / "tomo" / "scripts" / "suggestions-reducer.py"
SCHEMA_PATH = REPO_ROOT_T1 / "tomo" / "schemas" / "suggestions-doc.schema.json"

_DEPS = "/tmp/claude/py_deps"
_SCRIPTS_DIR = str(REPO_ROOT_T1 / "tomo" / "scripts")
_extra = ":".join(p for p in [_DEPS, _SCRIPTS_DIR] if os.path.isdir(p))
_ENV_T1 = {
    **os.environ,
    "PYTHONPATH": _extra + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
}


def _write_shared_ctx(path: Path) -> None:
    path.write_text(json.dumps({
        "schema_version": "1",
        "run_id": "test-t1",
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
    }), encoding="utf-8")


def _write_state(path: Path, stems: list[str]) -> None:
    lines = [
        json.dumps({
            "stem": s,
            "path": f"100 Inbox/{s}.md",
            "status": "done",
            "run_id": "test-t1",
            "ts": "2026-06-11T10:00:00Z",
        })
        for s in stems
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_result_atomic(
    items_dir: Path,
    stem: str,
    atomics: list[dict],
    daily_content: str | None = None,
) -> None:
    """Write a result.json with N atomic actions plus an optional log_entry."""
    items_dir.mkdir(parents=True, exist_ok=True)
    actions: list[dict] = []
    for a in atomics:
        actions.append({
            "kind": "create_atomic_note",
            "suggested_title": a["title"],
            "atomic_note_worthiness": a.get("worthiness", 0.8),
            "template": "t_note_tomo",
            "location": "Atlas/202 Notes/",
            "candidate_mocs": [],
            "needs_new_moc": False,
            "tags_to_add": [],
            "classification": {"category": "100 Philosophy", "confidence": 0.9},
            "alternatives": [],
        })
    if daily_content is not None:
        actions.append({
            "kind": "update_daily",
            "date": "2026-06-11",
            "daily_note_path": "Daily/2026-06-11.md",
            "updates": [{
                "kind": "log_entry",
                "time": "09:00",
                "time_source": "frontmatter",
                "position": "append",
                "content": daily_content,
                "confidence": 0.8,
                "reason": "noted",
            }],
        })
    (items_dir / f"{stem}.result.json").write_text(json.dumps({
        "schema_version": "1",
        "stem": stem,
        "path": f"100 Inbox/{stem}.md",
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "force_atomic": False,
        "actions": actions,
        "candidate_mocs": [],
        "classification": {"category": "100 Philosophy", "confidence": 0.9},
        "needs_new_moc": False,
        "proposed_moc_topic": None,
        "tags_to_add": [],
        "atomic_note_worthiness": 0.8,
        "alternatives": [],
        "issues": [],
        "duration_ms": 0,
    }, ensure_ascii=False), encoding="utf-8")


def _write_result_daily_only(items_dir: Path, stem: str) -> None:
    """Write a result.json with only a log_entry (no atomics — daily-only)."""
    items_dir.mkdir(parents=True, exist_ok=True)
    (items_dir / f"{stem}.result.json").write_text(json.dumps({
        "schema_version": "1",
        "stem": stem,
        "path": f"100 Inbox/{stem}.md",
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "force_atomic": False,
        "actions": [{
            "kind": "update_daily",
            "date": "2026-06-11",
            "daily_note_path": "Daily/2026-06-11.md",
            "updates": [{
                "kind": "log_entry",
                "time": "08:00",
                "time_source": "frontmatter",
                "position": "append",
                "content": "daily only content",
                "confidence": 0.8,
                "reason": "noted",
            }],
        }],
        "candidate_mocs": [],
        "classification": {"category": "100 Philosophy", "confidence": 0.9},
        "needs_new_moc": False,
        "proposed_moc_topic": None,
        "tags_to_add": [],
        "atomic_note_worthiness": 0.0,
        "alternatives": [],
        "issues": [],
        "duration_ms": 0,
    }, ensure_ascii=False), encoding="utf-8")


def _run_reducer(tmp_path: Path, stems: list[str]) -> dict:
    items_dir = tmp_path / "items"
    items_dir.mkdir(exist_ok=True)
    shared_ctx = tmp_path / "shared-ctx.json"
    state = tmp_path / "state.jsonl"
    output = tmp_path / "doc.json"
    _write_shared_ctx(shared_ctx)
    _write_state(state, stems)

    result = subprocess.run(
        [
            sys.executable, str(REDUCER_PATH),
            "--state", str(state),
            "--items-dir", str(items_dir),
            "--run-id", "test-t1",
            "--profile", "miyo",
            "--shared-ctx", str(shared_ctx),
            "--output", str(output),
        ],
        capture_output=True, text=True, check=False, env=_ENV_T1,
    )
    assert result.returncode == 0, (
        f"reducer exit {result.returncode};\nstderr:\n{result.stderr}"
    )
    return json.loads(output.read_text(encoding="utf-8"))


def _atomic_actions_from_doc(doc: dict) -> list[dict]:
    """Extract all {kind, rendered_md, ...} action dicts for create_atomic_note."""
    out = []
    for section in doc.get("sections", []):
        for action in section.get("actions", []):
            if action.get("kind") == "create_atomic_note":
                out.append(action)
    return out


def _log_links_from_doc(doc: dict) -> list[dict]:
    out = []
    for group in doc.get("daily_notes_updates", []):
        out.extend(group.get("log_links", []))
    return out


# ── T1 RED tests ──────────────────────────────────────────────────────────────


def test_t1_two_sources_flat_suggestion_ids(tmp_path):
    """Source A (2 atomics) + Source B (1 atomic) → S01, S02, S03.

    Each create_atomic_note action in sections[].actions[] carries a flat
    `suggestion_id` sequenced globally across all sources.
    """
    _write_result_atomic(tmp_path / "items", "src-a",
                         [{"title": "Alpha"}, {"title": "Beta"}])
    _write_result_atomic(tmp_path / "items", "src-b",
                         [{"title": "Gamma"}])

    # Need items dir to exist before _run_reducer creates it — already created above.
    doc = _run_reducer(tmp_path, ["src-a", "src-b"])

    atomic_actions = _atomic_actions_from_doc(doc)
    ids = [a.get("suggestion_id") for a in atomic_actions]
    assert ids == ["S01", "S02", "S03"], (
        f"Expected flat global suggestion_ids ['S01','S02','S03'], got {ids}"
    )


def test_t1_daily_only_item_does_not_increment_counter(tmp_path):
    """Source A (2 atomics) → S01, S02; daily-only item in between → no id;
    Source B (1 atomic) thereafter → S03 (NOT S02)."""
    # Alphabetically: src-a, src-b-daily-only, src-c
    _write_result_atomic(tmp_path / "items", "src-a",
                         [{"title": "Alpha"}, {"title": "Beta"}])
    _write_result_daily_only(tmp_path / "items", "src-b-daily-only")
    _write_result_atomic(tmp_path / "items", "src-c",
                         [{"title": "Gamma"}])

    doc = _run_reducer(tmp_path, ["src-a", "src-b-daily-only", "src-c"])

    atomic_actions = _atomic_actions_from_doc(doc)
    ids = [a.get("suggestion_id") for a in atomic_actions]
    assert ids == ["S01", "S02", "S03"], (
        f"Daily-only item must not increment counter; got {ids}"
    )


def test_t1_each_atomic_action_carries_suggestion_id(tmp_path):
    """Every create_atomic_note action dict in sections[].actions[] has suggestion_id."""
    _write_result_atomic(tmp_path / "items", "src-x",
                         [{"title": "Note One"}, {"title": "Note Two"}])

    doc = _run_reducer(tmp_path, ["src-x"])

    atomic_actions = _atomic_actions_from_doc(doc)
    assert len(atomic_actions) == 2
    for action in atomic_actions:
        assert "suggestion_id" in action, (
            f"create_atomic_note action missing suggestion_id: {action}"
        )
        assert action["suggestion_id"].startswith("S"), action["suggestion_id"]


def test_t1_log_link_source_section_matches_flat_suggestion_id(tmp_path):
    """log_link.source_section == flat suggestion_id of the atomic that drove it.

    Cross-source setup forces section_id != suggestion_id for src-b:
      src-a: 2 atomics (no daily)  → section_id=S01, suggestion_ids S01, S02
      src-b: 1 atomic + daily      → section_id=S02, suggestion_id=S03

    src-b's log_link targets "Gamma" (its only atomic, suggestion_id=S03).
    Old per-source behavior: source_section == section_id == "S02"  [WRONG]
    New flat behavior:       source_section == suggestion_id == "S03" [CORRECT]
    This test WOULD FAIL with the old fallback (title_to_suggestion_id.get(target, section_id)).
    """
    # src-a: 2 atomics, no daily — occupies global suggestion_id slots S01 and S02.
    _write_result_atomic(tmp_path / "items", "src-a",
                         [{"title": "Alpha"}, {"title": "Beta"}])
    # src-b: 1 atomic + daily — section_id=S02, but atomic gets suggestion_id=S03.
    _write_result_atomic(tmp_path / "items", "src-b",
                         [{"title": "Gamma"}],
                         daily_content="worked on philosophy")

    # Alphabetical order: src-a (idx=1 → section_id=S01), src-b (idx=2 → section_id=S02).
    doc = _run_reducer(tmp_path, ["src-a", "src-b"])

    # Verify the flat suggestion_ids are as expected.
    atomic_actions = _atomic_actions_from_doc(doc)
    ids = [a.get("suggestion_id") for a in atomic_actions]
    assert ids == ["S01", "S02", "S03"], (
        f"Expected flat suggestion_ids ['S01','S02','S03'], got {ids}"
    )

    # The log_link from src-b targets "Gamma" (suggestion_id=S03, section_id=S02).
    log_links = _log_links_from_doc(doc)
    assert len(log_links) == 1, f"Expected exactly 1 log_link, got {log_links}"
    ll = log_links[0]
    assert ll["target_stem"] == "Gamma", ll

    # DISCRIMINATING ASSERTION: source_section must be the flat suggestion_id
    # "S03", NOT the per-source section_id "S02".
    # Old per-source behavior would return "S02" here → this assert would FAIL.
    assert ll["source_section"] == "S03", (
        f"source_section is {ll['source_section']!r}; expected 'S03' (flat suggestion_id). "
        f"'S02' means old per-source section_id was used — the fix is not in effect."
    )


def test_t1_single_atomic_regression(tmp_path):
    """Single-atomic source → exactly one action with suggestion_id 'S01' (CON-2)."""
    _write_result_atomic(tmp_path / "items", "solo",
                         [{"title": "Solo Note"}])

    doc = _run_reducer(tmp_path, ["solo"])

    atomic_actions = _atomic_actions_from_doc(doc)
    assert len(atomic_actions) == 1
    assert atomic_actions[0].get("suggestion_id") == "S01", atomic_actions[0]


def test_t1_schema_validation_with_suggestion_id_field(tmp_path):
    """suggestion_id survives schema validation — not stripped by additionalProperties.

    This test imports jsonschema directly and validates the emitted doc against
    the suggestions-doc.schema.json to catch the three-way spec/schema/consumer
    drift described in the task brief.
    """
    try:
        import jsonschema
    except ImportError:
        import pytest as _pytest
        _pytest.skip("jsonschema not available")

    _write_result_atomic(tmp_path / "items", "src-a",
                         [{"title": "Alpha"}, {"title": "Beta"}])
    doc = _run_reducer(tmp_path, ["src-a"])

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    # If schema strips suggestion_id (additionalProperties:false), validate
    # would NOT raise — but we'd find no suggestion_id in the atomic actions.
    # Validate must not raise on a doc that contains suggestion_id.
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        raise AssertionError(
            f"Schema validation failed — suggestion_id may not be declared in schema: {exc.message}"
        ) from exc

    # Confirm field is present even after a round-trip through JSON (no stripping).
    atomic_actions = _atomic_actions_from_doc(doc)
    ids = [a.get("suggestion_id") for a in atomic_actions]
    assert all(sid is not None for sid in ids), (
        f"suggestion_id stripped from actions after schema validation round-trip: {ids}"
    )
