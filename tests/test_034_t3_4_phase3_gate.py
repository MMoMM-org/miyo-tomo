#!/usr/bin/env python3
# version: 0.2.0
"""test_034_t3_4_phase3_gate.py — the Phase 3 validation gate.

Spec 034 (recursive inbox discovery), Phase 3 T3.4.

WHY THIS FILE EXISTS, when four per-task test files already pass:

Phase 3 turned discovery recursive — the change every other phase was
sequenced around. Three of this spec's tasks have already passed both
review gates while their defect stayed live, so a green per-task suite is
not the evidence this phase needs. This file states the three things a
per-task test cannot:

  1. **No regression on a flat inbox.** The golden under
     `tests/fixtures/034-t3-4-flat-golden/suggestions.md` was rendered by
     the pipeline at `ee44cb3` — the commit immediately preceding Phase 1 —
     from the root-only fixture below, driven through real
     `inbox-triage.py` / `state-update.py` / `suggestions-reducer.py` /
     `suggestions-render.py` invocations. It is a recording of the old
     renderer, not a transcription of the spec. The assertion is on the
     WHOLE document string, not on selected fields.

  2. **The listing count is observed, not calculated.** `_count_kado_calls`
     is the thing under test, so it can never also be the evidence. Every
     count here reads the fake client's own record of the calls it
     received.

  3. **A same-name pair survives a full Pass 1.** Two notes sharing a
     filename in different subfolders reach the suggestions document as
     distinct items with distinct `item_key`s, distinct per-item result
     files, and independent run-state entries. Phase 3 is the first phase
     where this collision is reachable at all: before it, `depth=1` meant
     neither note was ever discovered.

The fake client honours `depth` the way Kado does. A fake that ignored it
would let a lingering `depth=1` pass unnoticed, which is exactly the
regression this phase exists to remove — and exactly what the Phase 2 gate
could not see.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
GOLDEN = TESTS_DIR / "fixtures" / "034-t3-4-flat-golden" / "suggestions.md"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.item_key import to_filename  # noqa: E402

INBOX = "100 Inbox/"

# --- The flat golden's fixture: every entry a DIRECT child of the inbox ----
FLAT_RUN_ID = "gate34-flat-golden"
FLAT_FIXTURE = [
    "100 Inbox/Dresden.md",
    "100 Inbox/Hokkaido Trip.md",
    "100 Inbox/Kaffee und Kuchen.md",
    "100 Inbox/diagram.png",   # #93: an attachment, never partitioned as an item
    "100 Inbox/memo.m4a",      # audio paired with the transcript beside it
    "100 Inbox/memo.md",
]
FLAT_TITLES = {
    "100 Inbox/Dresden.md": "Dresden - Frauenkirche",
    "100 Inbox/Hokkaido Trip.md": "Hokkaido powder days",
    "100 Inbox/Kaffee und Kuchen.md": "Kaffee und Kuchen ritual",
    "100 Inbox/memo.md": "Memo transcript takeaway",
}

# --- The collision fixture: two namesakes in different subfolders ----------
NESTED_RUN_ID = "gate34-nested-pass1"
DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
DRESDEN_REISE = "100 Inbox/Reise/Dresden.md"
ROOT_NOTE = "100 Inbox/Root Note.md"
NESTED_FIXTURE = [DRESDEN_PLACES, DRESDEN_REISE, ROOT_NOTE]
NESTED_TITLES = {
    DRESDEN_PLACES: "Dresden - Frauenkirche",
    DRESDEN_REISE: "Dresden - a different note",
    ROOT_NOTE: "Root note takeaway",
}


# ---------------------------------------------------------------------------
# Fake Kado — records every call, and honours `depth`
# ---------------------------------------------------------------------------

class RecordingClient:
    def __init__(self, subtree: list[str]):
        self.calls: list[tuple[str, dict]] = []
        self._subtree = [
            {"path": p, "type": "file", "modified": 1716300000000, "size": 100}
            for p in subtree
        ]

    def _direct_children(self) -> list[dict]:
        return [i for i in self._subtree if "/" not in i["path"][len(INBOX):]]

    def list_dir(self, path, *, depth=None, limit=500):
        self.calls.append(("list_dir", {"path": path, "depth": depth}))
        return self._direct_children() if depth == 1 else list(self._subtree)

    def list_notes(self, path, *, fields=None, depth=None, limit=500):
        self.calls.append(("list_notes", {"path": path, "fields": fields, "depth": depth}))
        return []

    def search_by_frontmatter(self, query, *, path_prefix=None, limit=500,
                              modified_after=None):
        self.calls.append(("search_by_frontmatter", {"query": query}))
        return []

    def read_note(self, path):
        self.calls.append(("read_note", {"path": path}))
        return {"content": "", "modified": 0}

    def read_frontmatter(self, path):
        self.calls.append(("read_frontmatter", {"path": path}))
        return {"content": {}}

    def read_file_bytes(self, path):
        from lib.kado_client import KadoError
        self.calls.append(("read_file_bytes", {"path": path}))
        raise KadoError(f"not found: {path}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_script(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{cmd[1]} failed (exit {result.returncode})\n"
        f"stderr:\n{result.stderr}\nstdout:\n{result.stdout[:2000]}"
    )
    return result


def _item_result(stem: str, path: str, title: str) -> dict:
    return {
        "schema_version": "1",
        "stem": stem,
        "item_key": path,
        "path": path,
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "date_relevance": None,
        "issues": [],
        "duration_ms": 100,
        "force_atomic": False,
        "actions": [
            {
                "kind": "create_atomic_note",
                "source_stem": stem,
                "suggested_title": title,
                "template": "Atomic Note.md",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": [
                    {"path": "Atlas/200 Maps/Travel (MOC).md",
                     "score": 0.8, "pre_check": True},
                ],
                "tags_to_add": ["topic/travel"],
                "atomic_note_worthiness": 0.85,
                "classification": None,
            },
        ],
    }


# The three wall-clock fields in a rendered suggestions document. Every one is
# stamped at render time and carries no information about the pipeline's
# behaviour, so all three are normalised before comparison — and nothing else is.
_NORMALISERS = (
    (re.compile(r"^generated: '[^']*'$", re.MULTILINE), "generated: '<NORMALISED>'"),
    (re.compile(r"^  updated_at: '[^']*'$", re.MULTILINE), "  updated_at: '<NORMALISED>'"),
    (re.compile(r"^# Inbox Suggestions — .*$", re.MULTILINE),
     "# Inbox Suggestions — <NORMALISED>"),
)


def _normalise(document: str) -> str:
    for pattern, replacement in _NORMALISERS:
        document = pattern.sub(replacement, document)
    return document


def _drive_pass1(work: Path, fixture: list[str], titles: dict[str, str],
                 run_id: str) -> dict:
    """Run Pass 1 end to end, deriving the item set from what triage actually
    discovered — a note recursion misses simply never appears downstream."""
    items_dir = work / "items"
    items_dir.mkdir(exist_ok=True)
    state_path = work / "inbox-state.jsonl"

    triage = _load_script(f"inbox_triage_t3_4_{run_id}", "inbox-triage.py")
    client = RecordingClient(fixture)
    rc = triage.main(["--inbox-path", INBOX, "--output-dir", str(work),
                      # T6.1: the cost history defaults cwd-relative, correct for
                      # the instance runtime — keep this run's entry out of the repo.
                      "--cost-history", str(work / "cost-history.jsonl")],
                     client_factory=lambda: client)
    assert rc == 0, f"inbox-triage.main() returned {rc}"

    plan = json.loads((work / "routing-plan.json").read_text(encoding="utf-8"))
    discovered = [s["path"] for s in plan["fresh_sources"]]

    for path in discovered:
        stem = Path(path).stem
        for status in ("pending", "running", "done"):
            _run([
                sys.executable, str(SCRIPTS_DIR / "state-update.py"),
                "--state", str(state_path),
                "--item-key", path, "--stem", stem, "--path", path,
                "--status", status, "--run-id", run_id,
            ])
        (items_dir / to_filename(path)).write_text(
            json.dumps(_item_result(stem, path, titles[path]),
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    doc_path = work / "suggestions-doc.json"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-reducer.py"),
        "--state", str(state_path), "--items-dir", str(items_dir),
        "--run-id", run_id, "--profile", "miyo", "--output", str(doc_path),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--resolved-attachments", str(work / "absent-resolved.json"),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--threshold", "1", "--no-kado",
    ])

    md_path = work / "suggestions.md"
    wire_path = work / "suggestions-wire.json"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-render.py"),
        "--input", str(doc_path), "--output", str(md_path),
        "--json-output", str(wire_path),
    ])

    return {
        "calls": client.calls,
        "routing_plan": plan,
        "discovered": discovered,
        "items_dir": items_dir,
        "state_lines": [
            json.loads(ln) for ln in
            state_path.read_text(encoding="utf-8").splitlines() if ln.strip()
        ],
        "suggestions_doc": json.loads(doc_path.read_text(encoding="utf-8")),
        "markdown": md_path.read_text(encoding="utf-8"),
        "wire": json.loads(wire_path.read_text(encoding="utf-8")),
    }


@pytest.fixture(scope="module")
def flat_run(tmp_path_factory) -> dict:
    return _drive_pass1(tmp_path_factory.mktemp("t3_4_flat"),
                        FLAT_FIXTURE, FLAT_TITLES, FLAT_RUN_ID)


@pytest.fixture(scope="module")
def nested_run(tmp_path_factory) -> dict:
    return _drive_pass1(tmp_path_factory.mktemp("t3_4_nested"),
                        NESTED_FIXTURE, NESTED_TITLES, NESTED_RUN_ID)


# ---------------------------------------------------------------------------
# 1. The flat-inbox golden — the WHOLE document
# ---------------------------------------------------------------------------

class TestFlatInboxGolden:
    def test_rendered_document_matches_the_pre_phase_1_render(self, flat_run):
        """The whole string, not selected fields. The golden was produced by
        the pipeline at ee44cb3 from this same fixture."""
        expected = GOLDEN.read_text(encoding="utf-8")
        actual = _normalise(flat_run["markdown"])
        assert actual == expected, (
            "the flat-inbox suggestions document changed since ee44cb3 — "
            "recursion must change WHERE files are found, never what is rendered"
        )

    def test_the_golden_is_not_trivially_empty(self, flat_run):
        """A normaliser that ate the document would make the comparison
        vacuous. Pin the parts that carry the pipeline's actual output."""
        expected = GOLDEN.read_text(encoding="utf-8")
        assert "### S01 — Dresden - Frauenkirche" in expected
        assert "### S04 — Memo transcript takeaway" in expected
        assert expected.count("**Source:**") == 4

    def test_only_wall_clock_fields_were_normalised(self, flat_run):
        """Every normalised line is a render-time timestamp. If a future
        renderer moves real content onto one of these lines, this fails."""
        for line in _normalise(flat_run["markdown"]).splitlines():
            if "<NORMALISED>" in line:
                assert line in (
                    "generated: '<NORMALISED>'",
                    "  updated_at: '<NORMALISED>'",
                    "# Inbox Suggestions — <NORMALISED>",
                ), f"unexpected normalised line: {line!r}"

    def test_a_root_level_png_is_still_not_an_item(self, flat_run):
        """#93's suffix partition is untouched by recursion."""
        assert "100 Inbox/diagram.png" not in flat_run["discovered"]

    def test_root_audio_pairs_with_the_transcript_beside_it(self, flat_run):
        assert flat_run["routing_plan"]["has_audio"] is False, (
            "a root audio with its sibling .md beside it reported as needing work"
        )


# ---------------------------------------------------------------------------
# 2. The call count — observed, never calculated
# ---------------------------------------------------------------------------

class TestObservedCallCount:
    def test_exactly_one_inbox_listing_per_run(self, flat_run):
        listings = [c for c in flat_run["calls"] if c[0] == "list_dir"]
        assert len(listings) == 1, (
            f"expected ONE listDir, the fake client recorded {len(listings)}: {listings}"
        )

    def test_that_listing_is_depth_unbounded(self, flat_run):
        listing = next(c for c in flat_run["calls"] if c[0] == "list_dir")
        assert listing[1]["depth"] is None, (
            f"the inbox listing asked for depth={listing[1]['depth']!r} — "
            "a depth limit hides subfolder notes"
        )
        assert listing[1]["path"] == INBOX

    def test_base_calls_are_two(self, flat_run):
        """ADR-3: base = the one recursive listDir + the listNotes embed
        extraction. Counted from the fake's own record, never from
        `_count_kado_calls` — the estimator is the thing under test."""
        base = [c for c in flat_run["calls"] if c[0] in ("list_dir", "list_notes")]
        assert len(base) == 2, f"base calls: {base}"
        assert [c[0] for c in base] == ["list_dir", "list_notes"]

    def test_the_count_does_not_grow_with_subfolders(self, nested_run):
        base = [c for c in nested_run["calls"] if c[0] in ("list_dir", "list_notes")]
        assert len(base) == 2, (
            f"a nested inbox cost more base calls than a flat one: {base}"
        )


# ---------------------------------------------------------------------------
# 3. The same-name pair survives a full Pass 1
# ---------------------------------------------------------------------------

class TestSameNamePairSurvivesPass1:
    def test_both_namesakes_are_discovered(self, nested_run):
        assert sorted(nested_run["discovered"]) == sorted(NESTED_FIXTURE), (
            "recursive discovery did not reach both subfolder notes"
        )

    def test_each_namesake_owns_a_distinct_result_file(self, nested_run):
        names = {p.name for p in nested_run["items_dir"].iterdir()}
        assert names == {to_filename(p) for p in NESTED_FIXTURE}
        assert to_filename(DRESDEN_PLACES) != to_filename(DRESDEN_REISE)

    def test_each_namesake_holds_its_own_run_state(self, nested_run):
        for key in (DRESDEN_PLACES, DRESDEN_REISE):
            statuses = [e["status"] for e in nested_run["state_lines"]
                        if e["item_key"] == key]
            assert statuses == ["pending", "running", "done"], (
                f"{key} did not keep its own status history"
            )

    def test_both_reach_the_suggestions_document_as_distinct_sections(self, nested_run):
        sections = nested_run["suggestions_doc"]["sections"]
        assert len(sections) == len(NESTED_FIXTURE), (
            f"reducer emitted {len(sections)} sections for {len(NESTED_FIXTURE)} items"
        )
        by_key = {s["item_key"]: s for s in sections}
        assert {DRESDEN_PLACES, DRESDEN_REISE} <= set(by_key)
        titles = {
            key: by_key[key]["actions"][0]["item"]["title"]
            for key in (DRESDEN_PLACES, DRESDEN_REISE)
        }
        assert titles[DRESDEN_PLACES] != titles[DRESDEN_REISE], (
            f"the two namesakes collapsed onto one title: {titles}"
        )

    def test_the_wire_carries_both_keys(self, nested_run):
        keys = [s["item_key"] for s in nested_run["wire"]["suggestions"]]
        assert DRESDEN_PLACES in keys and DRESDEN_REISE in keys

    def test_the_rendered_document_shows_both(self, nested_run):
        md = nested_run["markdown"]
        assert "Dresden - Frauenkirche" in md
        assert "Dresden - a different note" in md
