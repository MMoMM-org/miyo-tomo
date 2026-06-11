#!/usr/bin/env python3
# version: 0.1.0
"""test_016_multi_topic_e2e.py — F-41 T6.1: End-to-end multi-topic atomic notes suite.

Tests the deterministic pipeline (reducer → render → parser) with recorded
analyst-output fixtures proving multi-thread input flows correctly.

Pipeline chain under test:
  suggestions-reducer.py  (reads item-result JSONs → suggestions-doc.json)
  suggestions-render.py   (reads suggestions-doc.json → suggestions.md)
  suggestion-parser.py    (reads suggestions.md → parsed JSON with confirmed_items)

The analyst step (inbox-analyst.md) is LLM-driven and is NOT invoked here.
Each test starts from a RECORDED analyst-output fixture (an item-result.json).

For cases requiring instruction-render.py (Kado-dependent for templates),
build_actions() is called directly with kado_client=None so action-count and
action-type assertions are still Kado-free. See per-test comments where this
applies.

Spec: docs/XDD/specs/016-multi-topic-atomic-notes/
Covers: A10 acceptance criteria (9 cases).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ── Repo paths ─────────────────────────────────────────────────────────────────

TESTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

REDUCER = SCRIPTS_DIR / "suggestions-reducer.py"
RENDER = SCRIPTS_DIR / "suggestions-render.py"
PARSER = SCRIPTS_DIR / "suggestion-parser.py"

sys.path.insert(0, str(SCRIPTS_DIR))


# ── Module loaders (reuse conftest pattern) ────────────────────────────────────


def _load_mod(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_ir = _load_mod("instruction_render_016", SCRIPTS_DIR / "instruction-render.py")
_reducer_mod = _load_mod("suggestions_reducer_016", SCRIPTS_DIR / "suggestions-reducer.py")
_render_mod = _load_mod("suggestions_render_016", SCRIPTS_DIR / "suggestions-render.py")


# ── Minimal vault-config for render stage ─────────────────────────────────────

_MINIMAL_CONFIG_YAML = """\
profile: miyo
concepts:
  inbox: "100 Inbox/"
  atomic_note:
    path: "Atlas/202 Notes/"
  map_note:
    path: "Atlas/200 Maps/"
callouts:
  editable: []
"""

_CFG_DICT = {
    "profile": "miyo",
    "concepts.inbox": "100 Inbox/",
    "concepts.atomic_note.path": "Atlas/202 Notes/",
    "concepts.map_note.path": "Atlas/200 Maps/",
    "callouts.editable": [],
}


# ── Item-result fixture factories ──────────────────────────────────────────────


def _make_item_result(
    stem: str,
    *,
    actions: list[dict],
    force_atomic: bool = False,
) -> dict:
    """Build a minimal item-result.json conforming to item-result.schema.json."""
    r: dict = {
        "schema_version": "1",
        "stem": stem,
        "path": f"100 Inbox/{stem}.md",
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "date_relevance": None,
        "issues": [],
        "duration_ms": 100,
        "actions": actions,
    }
    if force_atomic:
        r["force_atomic"] = True
    return r


def _atomic_action(
    title: str,
    *,
    stem: str,
    worthiness: float = 0.8,
    candidate_mocs: list[dict] | None = None,
    needs_new_moc: bool = False,
    proposed_moc_topic: str = "",
    tags: list[str] | None = None,
) -> dict:
    """Build a create_atomic_note action conforming to the schema."""
    a: dict = {
        "kind": "create_atomic_note",
        "source_stem": stem,
        "suggested_title": title,
        "template": "Atomic Note.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": candidate_mocs or [
            {"path": "Atlas/200 Maps/Home (MOC).md", "score": 0.6, "pre_check": False}
        ],
        "tags_to_add": tags or [],
        "atomic_note_worthiness": worthiness,
        "classification": None,
    }
    if needs_new_moc:
        a["needs_new_moc"] = True
        a["proposed_moc_topic"] = proposed_moc_topic
        a["classification"] = {"category": "100 Philosophy", "confidence": 0.7}
    return a


def _daily_action(stem: str, *, content: str = "Log entry text.") -> dict:
    """Build a minimal update_daily action."""
    return {
        "kind": "update_daily",
        "date": "2026-06-11",
        "daily_note_path": "Calendar/301 Daily/2026-06-11.md",
        "daily_note_stem": "2026-06-11",
        "updates": [
            {
                "kind": "log_entry",
                "content": content,
                "reason": "noteworthy event",
                "confidence": 0.9,
                "position": "after_last_line",
                "time": "09:00",
                "time_source": "frontmatter",
            }
        ],
    }


# ── State file factory ─────────────────────────────────────────────────────────


def _write_state(tmp_path: Path, stems: list[str]) -> Path:
    """Write a minimal JSONL state file marking each stem as done."""
    state_path = tmp_path / "state.jsonl"
    lines = []
    for stem in stems:
        lines.append(json.dumps({
            "stem": stem,
            "status": "done",
            "started_at": "2026-06-11T09:00:00Z",
            "finished_at": "2026-06-11T09:00:01Z",
        }))
    state_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return state_path


def _write_shared_ctx(tmp_path: Path) -> Path:
    """Write a minimal shared-ctx.json."""
    ctx = {"field_sections": {}}
    p = tmp_path / "shared-ctx.json"
    p.write_text(json.dumps(ctx), encoding="utf-8")
    return p


def _write_config(tmp_path: Path) -> Path:
    """Write the minimal vault-config.yaml for the render and instruction stage."""
    cfg_path = tmp_path / "vault-config.yaml"
    cfg_path.write_text(_MINIMAL_CONFIG_YAML, encoding="utf-8")
    return cfg_path


# ── Pipeline runners ───────────────────────────────────────────────────────────


def _run_reducer(
    tmp_path: Path,
    items_dir: Path,
    state_path: Path,
    shared_ctx_path: Path,
    *,
    fan_resolve: bool = False,
) -> Path:
    """Run suggestions-reducer.py and return path to suggestions-doc.json."""
    out_path = tmp_path / "suggestions-doc.json"
    cmd = [
        sys.executable, str(REDUCER),
        "--state", str(state_path),
        "--items-dir", str(items_dir),
        "--run-id", "e2e-test-run",
        "--profile", "miyo",
        "--output", str(out_path),
        "--shared-ctx", str(shared_ctx_path),
    ]
    if fan_resolve:
        cmd.append("--fan-resolve")
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"suggestions-reducer failed (exit {result.returncode}):\n"
        f"stderr: {result.stderr}\nstdout: {result.stdout}"
    )
    assert out_path.exists(), "suggestions-doc.json not written by reducer"
    return out_path


def _run_render(tmp_path: Path, doc_path: Path) -> Path:
    """Run suggestions-render.py and return path to suggestions.md."""
    md_path = tmp_path / "suggestions.md"
    cmd = [
        sys.executable, str(RENDER),
        "--input", str(doc_path),
        "--output", str(md_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"suggestions-render failed (exit {result.returncode}):\n"
        f"stderr: {result.stderr}"
    )
    assert md_path.exists(), "suggestions.md not written by renderer"
    return md_path


def _run_parser(md_path: Path, *, fan_resolve_path: Path | None = None) -> dict:
    """Run suggestion-parser.py and return the parsed JSON dict."""
    cmd = [sys.executable, str(PARSER), "--file", str(md_path)]
    if fan_resolve_path:
        cmd += ["--fan-resolve-file", str(fan_resolve_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"suggestion-parser failed (exit {result.returncode}):\n"
        f"stderr: {result.stderr}\nstdout: {result.stdout[:500]}"
    )
    return json.loads(result.stdout)


def _full_pipeline(
    tmp_path: Path,
    item_results: dict[str, dict],
    *,
    fan_resolve: bool = False,
) -> dict:
    """Drive the full reducer → render → parser chain.

    item_results: mapping from stem → item-result dict.
    Returns the parsed JSON from suggestion-parser.py.
    """
    items_dir = tmp_path / "items"
    items_dir.mkdir()

    for stem, result in item_results.items():
        item_path = items_dir / f"{stem}.result.json"
        item_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")

    state_path = _write_state(tmp_path, list(item_results.keys()))
    shared_ctx_path = _write_shared_ctx(tmp_path)

    doc_path = _run_reducer(
        tmp_path, items_dir, state_path, shared_ctx_path, fan_resolve=fan_resolve
    )
    md_path = _run_render(tmp_path, doc_path)

    # For the pipeline tests we mark the doc as approved so the parser
    # processes confirmed items (the user's "Approved" checkbox is ticked).
    md_text = md_path.read_text(encoding="utf-8")
    md_text = md_text.replace(
        "- [ ] Approved", "- [x] Approved", 1
    )
    md_path.write_text(md_text, encoding="utf-8")

    return _run_parser(md_path)


def _stem_of(src: str | None) -> str:
    """Lowercase stem from source_path (handles paths + .md + wikilinks)."""
    if not src:
        return ""
    bare = src.rsplit("/", 1)[-1]
    if bare.endswith(".md"):
        bare = bare[:-3]
    return bare.strip().lower().strip("[]")


# ── Case 1 ─────────────────────────────────────────────────────────────────────


def test_single_thread_no_regression(tmp_path):
    """Single-thread item → exactly 1 create_atomic_note rendered → 1 confirmed.

    CON-2 regression guard: single-thread output must not be altered by the
    multi-thread pathway. The confirmed item carries the correct source stem
    and has no suffix (id == "S01", not "S01#1").
    """
    stem = "solo-note"
    result = _make_item_result(stem, actions=[
        _atomic_action("Only Topic", stem=stem, worthiness=0.8),
    ])
    parsed = _full_pipeline(tmp_path, {stem: result})

    atomics = [
        c for c in parsed["confirmed_items"]
        if _stem_of(c.get("source_path")) == stem
    ]
    assert len(atomics) == 1, (
        f"single-thread must yield exactly 1 confirmed atomic; got {atomics}"
    )
    assert atomics[0]["title"] == "Only Topic"
    # CON-2: id must be bare S01, not S01#1
    assert atomics[0]["id"] == "S01", (
        f"single-thread id must be 'S01', got {atomics[0]['id']!r}"
    )


# ── Case 2 ─────────────────────────────────────────────────────────────────────


def test_two_thread_two_atomics(tmp_path):
    """One source with 2 atomics (distinct titles, shared source_stem) → 2 confirmed.

    Verifies: both distinct titles survive, both share the same source stem,
    ids are S01 and S01#1, and the resulting note filenames are distinct.
    """
    stem = "two-topic-memo"
    result = _make_item_result(stem, actions=[
        _atomic_action("First Topic", stem=stem, worthiness=0.8),
        _atomic_action("Second Topic", stem=stem, worthiness=0.7),
    ])
    parsed = _full_pipeline(tmp_path, {stem: result})

    atomics = [
        c for c in parsed["confirmed_items"]
        if _stem_of(c.get("source_path")) == stem
    ]
    assert len(atomics) == 2, (
        f"two-thread source must yield 2 confirmed atomics; got {atomics}"
    )
    titles = {c["title"] for c in atomics}
    assert titles == {"First Topic", "Second Topic"}, (
        f"both titles must survive; got {titles}"
    )
    ids = {c["id"] for c in atomics}
    assert "S01" in ids, f"first block id must be S01; got {ids}"
    assert "S01#1" in ids, f"second block id must be S01#1; got {ids}"

    # Both share the same source stem
    for c in atomics:
        assert _stem_of(c.get("source_path")) == stem, (
            f"source_path must resolve to {stem!r}; got {c.get('source_path')!r}"
        )


# ── Case 3 ─────────────────────────────────────────────────────────────────────


def test_five_thread_stress(tmp_path):
    """5 atomics from one source → 5 distinct confirmed items with distinct titles."""
    stem = "five-topic-note"
    actions = [
        _atomic_action(f"Topic {i}", stem=stem, worthiness=0.7 + i * 0.02)
        for i in range(1, 6)
    ]
    result = _make_item_result(stem, actions=actions)
    parsed = _full_pipeline(tmp_path, {stem: result})

    atomics = [
        c for c in parsed["confirmed_items"]
        if _stem_of(c.get("source_path")) == stem
    ]
    assert len(atomics) == 5, (
        f"5-thread source must yield 5 confirmed atomics; got {len(atomics)}: {atomics}"
    )
    titles = {c["title"] for c in atomics}
    assert len(titles) == 5, f"all 5 titles must be distinct; got {titles}"
    # Ids: S01, S01#1, S01#2, S01#3, S01#4
    ids = {c["id"] for c in atomics}
    assert "S01" in ids
    assert "S01#1" in ids
    assert "S01#4" in ids


# ── Case 4 ─────────────────────────────────────────────────────────────────────


def test_sub_worthy_multi_thread_no_atomics(tmp_path):
    """Multi-thread item where all threads are sub-worthy → 0 atomics, 1 update_daily.

    The _enforce_coexistence logic drops both sub-worthy atomics, preserves the
    log_entry, and the daily update should appear in the rendered doc.
    """
    stem = "sub-worthy-memo"
    result = _make_item_result(stem, actions=[
        _atomic_action("Weak Thread A", stem=stem, worthiness=0.2),
        _atomic_action("Weak Thread B", stem=stem, worthiness=0.3),
        _daily_action(stem, content="Brief log entry for sub-worthy content."),
    ])
    parsed = _full_pipeline(tmp_path, {stem: result})

    atomics = [
        c for c in parsed["confirmed_items"]
        if _stem_of(c.get("source_path")) == stem
        and c.get("action") not in ("create_moc",)
        and c.get("template")
    ]
    assert atomics == [], (
        f"sub-worthy threads must produce 0 atomics; got {atomics}"
    )

    # The daily updates must appear in the doc (carried through reducer → render)
    doc = json.loads(
        (tmp_path / "suggestions-doc.json").read_text(encoding="utf-8")
    )
    daily_updates = doc.get("daily_notes_updates", [])
    assert len(daily_updates) >= 1, (
        "sub-worthy item with daily must produce at least 1 daily_notes_update entry"
    )
    # At least one log_entry for the stem
    log_entries = [
        e for d in daily_updates for e in d.get("log_entries", [])
        if e.get("source_stem") == stem
    ]
    assert len(log_entries) >= 1, (
        f"expected a log_entry for stem {stem!r}; updates: {daily_updates}"
    )


# ── Case 5 ─────────────────────────────────────────────────────────────────────


def test_mixed_worthiness_one_atomic_one_daily(tmp_path):
    """1 worthy thread + 1 sub-worthy thread + daily → 1 atomic + daily preserved.

    _enforce_coexistence: the sub-worthy thread is dropped, the worthy thread
    survives, and the log_entry converts to a log_link pointing at the survivor.
    """
    stem = "mixed-worthy-memo"
    result = _make_item_result(stem, actions=[
        _atomic_action("Worthy Thread", stem=stem, worthiness=0.8),
        _atomic_action("Sub-worthy Thread", stem=stem, worthiness=0.25),
        _daily_action(stem, content="I went to the gym today."),
    ])
    parsed = _full_pipeline(tmp_path, {stem: result})

    atomics = [
        c for c in parsed["confirmed_items"]
        if _stem_of(c.get("source_path")) == stem and c.get("template")
    ]
    assert len(atomics) == 1, (
        f"mixed-worthy source must yield exactly 1 atomic; got {atomics}"
    )
    assert atomics[0]["title"] == "Worthy Thread"

    # The daily log_link or log_entry must still be present in the doc JSON
    doc = json.loads(
        (tmp_path / "suggestions-doc.json").read_text(encoding="utf-8")
    )
    daily_updates = doc.get("daily_notes_updates", [])
    # After coexistence enforcement the log_entry is converted to a log_link
    # pointing at the survivor — either log_links or log_entries must have an
    # entry for this stem.
    has_daily = any(
        e.get("source_stem") == stem
        for d in daily_updates
        for bucket in ("log_links", "log_entries")
        for e in d.get(bucket, [])
    )
    assert has_daily, (
        f"daily entry for stem {stem!r} must be preserved; daily_updates={daily_updates}"
    )


# ── Case 6 ─────────────────────────────────────────────────────────────────────


def test_voice_multi_thread_atomics_with_audio_ref(tmp_path):
    """Voice-sourced multi-thread → 2 atomics, each carrying the source stem.

    Scope: reducer → render → parser (deterministic pipeline only).
    Audio-reference persistence through instruction-render is Kado-dependent
    (template read) and is out of scope for this test tier. What we assert:
    both confirmed items carry the correct source_path back to the voice stem.

    Note on audio ref: the audio link is an analyst-supplied field in the
    item-result (source_stem == voice stem); the rendered note body pulls the
    source body from Kado at instruction-render time — that Kado call is NOT
    exercised here. This test proves the source stem survives to confirmed_items.
    """
    stem = "voice-memo-2026-06-11"
    result = _make_item_result(stem, actions=[
        _atomic_action("PKM Architecture Insight", stem=stem, worthiness=0.85),
        _atomic_action("Stoic Philosophy Note", stem=stem, worthiness=0.75),
    ])
    parsed = _full_pipeline(tmp_path, {stem: result})

    atomics = [
        c for c in parsed["confirmed_items"]
        if _stem_of(c.get("source_path")) == stem
    ]
    assert len(atomics) == 2, (
        f"voice multi-thread must yield 2 atomics; got {atomics}"
    )
    # Both atomics must carry the audio (voice) source stem
    for c in atomics:
        assert _stem_of(c.get("source_path")) == stem, (
            f"audio ref must survive to confirmed_item; got source_path={c.get('source_path')!r}"
        )


# ── Case 7 ─────────────────────────────────────────────────────────────────────


def test_fan_ticked_multi_thread_resolve_doc(tmp_path):
    """Force-Atomic-ticked multi-thread → fan-resolve doc with 2 proposals.

    Exercises the parser's FAN resolve N-entry path shipped in Phase 4 / T4.2.
    Reuses the fixture shape from test_suggestion_parser_multi_atomic.py.

    Scope: parser only (the FAN resolve path starts with a pre-rendered
    suggestions markdown built from two unapproved atomic blocks + a Daily Notes
    Updates Force-Atomic tick). The full chain (reducer → render → parser) is not
    used here because the fan-resolve doc shape is most honestly built by
    reproducing the exact markdown shape the reducer/renderer emits, which is
    what the existing parser unit tests do. We feed the same synthetic markdown
    through the actual parser subprocess.

    NOTE: this case is scoped to the parser stage because the fan-resolve flow
    is triggered by a specific daily-notes tick (Force Atomic Note) that the
    production agent injects AFTER the primary reducer run — it is not driven by
    the item-result fixture directly. Testing it at the full chain level would
    require faking the agent-side tick injection, which would be coverage theater.
    """
    # Build a fan-resolve doc with 2 unapproved atomic blocks (same shape as
    # the fixture in test_suggestion_parser_multi_atomic._two_atomic_fan_doc).
    doc_lines = [
        "---",
        "type: tomo-suggestions",
        "generated: 2026-06-11T09:00:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 1",
        "run_id: 2026-06-11T09-00-00Z-fan-test",
        "doc_variant: fan-resolve",
        "---",
        "",
        "# Inbox Suggestions — Force-Atomic Resolve — 2026-06-11",
        "",
        "- [x] Approved — check this box when you have finished reviewing, then run `/inbox` for Pass 2",
        "",
        "## Daily Notes Updates",
        "",
        "### [[2026-06-11]]",
        "",
        "**Possible Log Entries (inline text):**",
        "- after_last_line — Multi-topic voice memo about two distinct concepts.",
        "  - Reason: worthiness 0.3 — inline log entry",
        "  - Source: [[fan-voice-memo]]",
        "  - [ ] Accept",
        "  - [x] Force Atomic Note (create/keep a standalone note for this item)",
        "",
        "## Suggestions",
        "",
        "### S01 — fan-voice-memo split",
        "",
        "**Source:** [[fan-voice-memo]]",
        "**Suggested name:** PKM Insight Alpha",
        "**Type:** fleeting_note",
        "**Template:** Atomic Note.md",
        "**Destination:** Atlas/202 Notes/",
        "",
        "**Decision (atomic note):**",
        "- [ ] Approve",
        "- [ ] Keep in inbox",
        "- [ ] Skip (keep in inbox)",
        "- [ ] Delete source",
        "",
        "**Source:** [[fan-voice-memo]]",
        "**Suggested name:** PKM Insight Beta",
        "**Type:** fleeting_note",
        "**Template:** Atomic Note.md",
        "**Destination:** Atlas/202 Notes/",
        "",
        "**Decision (atomic note):**",
        "- [ ] Approve",
        "- [ ] Keep in inbox",
        "- [ ] Skip (keep in inbox)",
        "- [ ] Delete source",
        "",
    ]
    md_path = tmp_path / "fan-resolve-suggestions.md"
    md_path.write_text("\n".join(doc_lines), encoding="utf-8")

    parsed = _run_parser(md_path)

    # Force-Atomic promotes both unapproved blocks
    fan_items = [
        c for c in parsed["confirmed_items"]
        if _stem_of(c.get("source_path")) == "fan-voice-memo"
    ]
    assert len(fan_items) == 2, (
        f"FAN resolve doc must promote both unapproved blocks; got {fan_items}"
    )
    titles = {c["title"] for c in fan_items}
    assert titles == {"PKM Insight Alpha", "PKM Insight Beta"}, (
        f"both FAN proposals must have distinct titles; got {titles}"
    )
    for c in fan_items:
        assert c.get("force_atomic") is True, (
            f"FAN-promoted item must carry force_atomic=True; got {c}"
        )


# ── Case 8 ─────────────────────────────────────────────────────────────────────


def test_overlapping_topics_moc_dedup(tmp_path):
    """_build_link_to_moc_actions deduplicates repeated parent_mocs on one item.

    Primary assertion (non-vacuous): a single confirmed item whose parent_mocs
    list contains the SAME MOC path twice produces exactly ONE link_to_moc
    action — proving the `seen` set in _build_link_to_moc_actions fires on the
    second duplicate entry and suppresses it.

    The assertion WOULD FAIL if the `seen` set were removed from production
    code: without it both iterations of `for parent in parents` would call
    _emit(), which would append two identical actions (the early-return guard
    `if key in seen` is the only thing preventing that).

    Secondary assertion: two DIFFERENT atomics each referencing the same MOC
    produce two distinct (source_note_title, target_moc) pairs — i.e. cross-item
    links are NOT deduped away, only per-item duplicate entries are.

    Scope: _build_link_to_moc_actions directly (Kado-free, cfg-free).
    build_actions() requires concepts.calendar.granularities.daily.path in cfg
    even when daily_updates=[]; calling the targeted helper directly is more
    honest and avoids a config stub that doesn't reflect production shape.
    """
    # ── Primary: per-item duplicate MOC dedup triggers `seen` set ─────────────
    # One item with the same MOC listed twice in parent_mocs.
    dup_item = {
        "title": "Duplicate MOC Note",
        "parent_mocs": ["Home (MOC)", "Home (MOC)"],
    }
    counter = [0]
    actions_dup = _ir._build_link_to_moc_actions([dup_item], counter)

    assert len(actions_dup) == 1, (
        f"duplicate parent_mocs entry must produce exactly 1 link_to_moc "
        f"(seen-set dedup); got {len(actions_dup)}: {actions_dup}"
    )
    assert actions_dup[0].get("target_moc") == "Home (MOC)", (
        f"deduped action must target the shared MOC; got {actions_dup[0]}"
    )

    # ── Secondary: cross-item, distinct source → links preserved ──────────────
    # Two atomics referencing the same MOC must each emit their own link action.
    stem = "overlapping-moc-memo"
    shared_moc = {"path": "Atlas/200 Maps/Home (MOC).md", "score": 0.85, "pre_check": True}
    result = _make_item_result(stem, actions=[
        _atomic_action("Thread Alpha", stem=stem, worthiness=0.8,
                       candidate_mocs=[shared_moc]),
        _atomic_action("Thread Beta", stem=stem, worthiness=0.75,
                       candidate_mocs=[shared_moc]),
    ])
    parsed = _full_pipeline(tmp_path, {stem: result})

    atomics = [
        c for c in parsed["confirmed_items"]
        if _stem_of(c.get("source_path")) == stem
    ]
    assert len(atomics) == 2, (
        f"overlapping-moc source must yield 2 atomics; got {atomics}"
    )

    counter2 = [0]
    link_actions = _ir._build_link_to_moc_actions(atomics, counter2)

    # Both atomics have different source titles → 2 distinct (source, moc) pairs.
    pairs = [
        (a.get("source_note_title", ""), a.get("target_moc", ""))
        for a in link_actions
    ]
    assert len(pairs) == len(set(pairs)), (
        f"link_to_moc pairs must be unique (no duplicates); got {pairs}"
    )
    assert len(link_actions) >= 2, (
        f"two distinct atomics referencing the same MOC must each produce a "
        f"link_to_moc action (cross-item links are preserved); got {link_actions}"
    )


# ── Case 9 ─────────────────────────────────────────────────────────────────────


def test_apothekerpfaedchen_success_signal(tmp_path):
    """SYNTHETIC fixture shaped like the 2026-05-01 Apothekerpfaedchen voice memo.

    The real memo contains:
      - One daily-log thread (medical appointment walk)
      - One atomic thread (PKM architecture insight)

    This test uses a SYNTHETIC representative fixture, NOT the real vault
    artifact. The actual re-run against the live vault is a manual sign-off
    (documented in docs/XDD/specs/016-multi-topic-atomic-notes/).

    Asserts:
      - Exactly 1 confirmed create_atomic_note (the PKM insight)
      - At least 1 daily_notes_update entry (the medical appointment log)
      - Both are linked to the same source stem
    """
    stem = "apothekerpfaedchen-2026-05-01"  # synthetic stem, not the real vault path

    result = _make_item_result(stem, actions=[
        # Thread 1: worthy atomic (PKM architecture insight)
        _atomic_action(
            "PKM Architecture — Connecting Fleeting Notes to Structure",
            stem=stem,
            worthiness=0.82,
        ),
        # Thread 2: daily log (medical appointment walk) — sub-worthy as atomic
        _daily_action(
            stem,
            content="Walked the Apothekerpfaedchen path, noticed how structure emerges from walking.",
        ),
    ])

    parsed = _full_pipeline(tmp_path, {stem: result})

    # 1 atomic confirmed
    atomics = [
        c for c in parsed["confirmed_items"]
        if _stem_of(c.get("source_path")) == stem and c.get("template")
    ]
    assert len(atomics) == 1, (
        f"Apothekerpfaedchen: expected 1 atomic (PKM insight); got {atomics}"
    )
    assert "PKM" in atomics[0]["title"], (
        f"atomic title should reference PKM insight; got {atomics[0]['title']!r}"
    )

    # Daily entry preserved in the suggestions-doc
    doc = json.loads(
        (tmp_path / "suggestions-doc.json").read_text(encoding="utf-8")
    )
    daily_updates = doc.get("daily_notes_updates", [])
    assert len(daily_updates) >= 1, (
        "Apothekerpfaedchen: daily log thread must produce at least 1 daily_notes_update"
    )
    log_entries_for_stem = [
        e for d in daily_updates
        for e in d.get("log_entries", [])
        if e.get("source_stem") == stem
    ]
    # After coexistence enforcement with 1 worthy atomic, the log_entry converts
    # to a log_link; check either bucket.
    log_links_for_stem = [
        e for d in daily_updates
        for e in d.get("log_links", [])
        if e.get("source_stem") == stem
    ]
    has_daily_entry = bool(log_entries_for_stem or log_links_for_stem)
    assert has_daily_entry, (
        f"Apothekerpfaedchen: daily log for stem {stem!r} must be preserved; "
        f"daily_updates={daily_updates}"
    )

    # Coexistence: 1 atomic + 1 daily → the log must be a log_link (not raw log_entry)
    # because the worthy atomic converts the log_entry.
    assert len(log_links_for_stem) >= 1, (
        f"With 1 worthy atomic, the log_entry must convert to a log_link; "
        f"log_entries={log_entries_for_stem}, log_links={log_links_for_stem}"
    )
