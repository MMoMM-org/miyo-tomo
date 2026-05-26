#!/usr/bin/env python3
# version: 0.2.0
"""test_inbox_triage.py — Behavioural tests for inbox-triage.py.

T2.1: discovery, bucketing, approval scanning, FAN detection, caching,
and error handling (steps 1-6 of the SDD algorithm).
T2.2: coverage computation, drift detection, action determination,
routing-plan emission, metrics (steps 7-11).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Fake KadoClient (recording pattern)
# ---------------------------------------------------------------------------

class FakeKadoClient:
    """Minimal KadoClient replacement that returns pre-configured responses."""

    def __init__(
        self,
        *,
        listdir_items: list[dict] | None = None,
        frontmatter_responses: dict[str, list[dict]] | None = None,
        read_note_responses: dict[str, dict] | None = None,
        read_note_errors: dict[str, Exception] | None = None,
    ):
        self._listdir_items = listdir_items or []
        self._frontmatter_responses = frontmatter_responses or {}
        self._read_note_responses = read_note_responses or {}
        self._read_note_errors = read_note_errors or {}
        self.calls: list[tuple[str, dict]] = []

    def list_dir(self, path: str, *, depth: int = None, limit: int = 500) -> list:
        self.calls.append(("list_dir", {"path": path, "depth": depth}))
        return self._listdir_items

    def search_by_frontmatter(
        self, query: str, *, path_prefix: str | None = None, limit: int = 500,
        modified_after: int | None = None,
    ) -> list[dict]:
        self.calls.append(("search_by_frontmatter", {"query": query, "path_prefix": path_prefix}))
        return self._frontmatter_responses.get(query, [])

    def read_note(self, path: str) -> dict:
        self.calls.append(("read_note", {"path": path}))
        if path in self._read_note_errors:
            raise self._read_note_errors[path]
        return self._read_note_responses.get(path, {"content": "", "modified": 0})


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

def _load_module():
    """Load inbox-triage.py as a module."""
    import importlib.util
    script_path = SCRIPTS_DIR / "inbox-triage.py"
    spec = importlib.util.spec_from_file_location("inbox_triage", script_path)
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules so dataclass can resolve annotations
    sys.modules["inbox_triage"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

INBOX_PATH = "100 Inbox/"


def _listdir_item(path: str, item_type: str = "file") -> dict:
    return {"path": path, "type": item_type, "modified": 1716300000000, "size": 100}


def _fm_hit(path: str, doc_type: str, state: str) -> dict:
    return {
        "path": path,
        "modified": 1716300000000,
        "frontmatter": {
            "tomo": {
                "doc_type": doc_type,
                "state": state,
                "run_id": "test-run",
                "updated_at": "2026-05-21T12:00:00Z",
            }
        },
    }


def _suggestions_body(approved: bool, fan_items: list[str] | None = None) -> str:
    """Build a minimal suggestions doc body."""
    mark = "[x]" if approved else "[ ]"
    lines = [
        "---",
        "type: tomo-suggestions",
        "---",
        "",
        "# Inbox Suggestions",
        "",
        f"- {mark} Approved",
        "",
        "## Suggestions",
        "",
    ]
    for i, stem in enumerate(fan_items or [], start=1):
        lines += [
            f"### S{i:02d} — {stem} reflections",
            "",
            f"**Source:** [[{stem}]]",
            "",
            "**Decision (atomic note):**",
            "- [x] Approve",
            "- [x] Force Atomic Note (create/keep a standalone note for this item)",
            "",
        ]
    return "\n".join(lines)


def _moc_proposal_body(accepted: bool) -> str:
    mark = "[x]" if accepted else "[ ]"
    return f"""---
type: tomo-moc-proposal
---

# MOC Proposal — Board Games

- {mark} Accept

## Cluster: Board Games
"""


# ---------------------------------------------------------------------------
# Test 1: partition audio and md
# ---------------------------------------------------------------------------

class TestPartitionAudioAndMd:
    def test_mixed_file_types_partitioned_correctly(self, tmp_path):
        mod = _load_module()

        items = [
            _listdir_item(INBOX_PATH + "note-a.md"),
            _listdir_item(INBOX_PATH + "note-b.md"),
            _listdir_item(INBOX_PATH + "recording.m4a"),
            _listdir_item(INBOX_PATH + "podcast.mp3"),
            _listdir_item(INBOX_PATH + "voice.wav"),
            _listdir_item(INBOX_PATH + "clip.ogg"),
            _listdir_item(INBOX_PATH + "video.mp4"),
            _listdir_item(INBOX_PATH + "other.json"),
            _listdir_item(INBOX_PATH + "subfolder", "folder"),
        ]

        client = FakeKadoClient(
            listdir_items=items,
            frontmatter_responses={},
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        md_paths = {f["path"] for f in state.md_files}
        audio_paths = {f["path"] for f in state.audio_files}

        assert md_paths == {
            INBOX_PATH + "note-a.md",
            INBOX_PATH + "note-b.md",
        }
        assert audio_paths == {
            INBOX_PATH + "recording.m4a",
            INBOX_PATH + "podcast.mp3",
            INBOX_PATH + "voice.wav",
            INBOX_PATH + "clip.ogg",
            INBOX_PATH + "video.mp4",
        }
        # Folders and .json excluded from both
        all_paths = md_paths | audio_paths
        assert INBOX_PATH + "subfolder" not in all_paths
        assert INBOX_PATH + "other.json" not in all_paths


# ---------------------------------------------------------------------------
# Test 2: four frontmatter queries
# ---------------------------------------------------------------------------

class TestFourFrontmatterQueries:
    def test_correct_bucket_assignments(self, tmp_path):
        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        moc_path = INBOX_PATH + "2026-05-22_1832_moc-proposal-board-games.md"
        cap_path = INBOX_PATH + "note-captured.md"
        instr_path = INBOX_PATH + "2026-05-24_0900_instructions.md"

        client = FakeKadoClient(
            listdir_items=[
                _listdir_item(sugg_path),
                _listdir_item(moc_path),
                _listdir_item(cap_path),
                _listdir_item(instr_path),
            ],
            frontmatter_responses={
                "tomo.state=pending-approval": [_fm_hit(sugg_path, "suggestions", "pending-approval")],
                "tomo.state=pending-accept": [_fm_hit(moc_path, "moc-proposal", "pending-accept")],
                "tomo.state=captured": [_fm_hit(cap_path, "source", "captured")],
                "tomo.doc_type=instructions": [_fm_hit(instr_path, "instructions", "pending-apply")],
            },
            read_note_responses={
                sugg_path: {"content": _suggestions_body(approved=False), "modified": 0},
                moc_path: {"content": _moc_proposal_body(accepted=False), "modified": 0},
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert len(state.pending_approval_hits) == 1
        assert state.pending_approval_hits[0]["path"] == sugg_path
        assert len(state.pending_accept_hits) == 1
        assert state.pending_accept_hits[0]["path"] == moc_path
        assert len(state.captured_hits) == 1
        assert len(state.instructions_hits) == 1


# ---------------------------------------------------------------------------
# Test 3: new_sources excludes known paths
# ---------------------------------------------------------------------------

class TestNewSourcesExcludesKnownPaths:
    def test_untagged_md_files_detected_as_new(self, tmp_path):
        mod = _load_module()

        known_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        new_path = INBOX_PATH + "fresh-note.md"

        client = FakeKadoClient(
            listdir_items=[
                _listdir_item(known_path),
                _listdir_item(new_path),
            ],
            frontmatter_responses={
                "tomo.state=pending-approval": [_fm_hit(known_path, "suggestions", "pending-approval")],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                known_path: {"content": _suggestions_body(approved=False), "modified": 0},
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        new_paths = [f["path"] for f in state.new_sources]
        assert new_path in new_paths
        assert known_path not in new_paths


# ---------------------------------------------------------------------------
# Test 4: approval scan — suggestions approved
# ---------------------------------------------------------------------------

class TestApprovalScanSuggestionsApproved:
    def test_approved_suggestions_detected(self, tmp_path):
        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"

        client = FakeKadoClient(
            listdir_items=[_listdir_item(sugg_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [_fm_hit(sugg_path, "suggestions", "pending-approval")],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_path: {"content": _suggestions_body(approved=True), "modified": 0},
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert len(state.approved_suggestions) == 1
        assert state.approved_suggestions[0]["path"] == sugg_path
        assert len(state.pending_approval) == 0


# ---------------------------------------------------------------------------
# Test 5: approval scan — suggestions NOT approved
# ---------------------------------------------------------------------------

class TestApprovalScanSuggestionsNotApproved:
    def test_unapproved_suggestions_in_pending(self, tmp_path):
        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"

        client = FakeKadoClient(
            listdir_items=[_listdir_item(sugg_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [_fm_hit(sugg_path, "suggestions", "pending-approval")],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_path: {"content": _suggestions_body(approved=False), "modified": 0},
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert len(state.approved_suggestions) == 0
        assert len(state.pending_approval) == 1
        assert state.pending_approval[0]["path"] == sugg_path


# ---------------------------------------------------------------------------
# Test 6: approval scan — moc-proposal accepted
# ---------------------------------------------------------------------------

class TestApprovalScanMocProposalAccepted:
    def test_accepted_moc_proposal_detected(self, tmp_path):
        mod = _load_module()

        moc_path = INBOX_PATH + "2026-05-22_1832_moc-proposal-board-games.md"

        client = FakeKadoClient(
            listdir_items=[_listdir_item(moc_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [],
                "tomo.state=pending-accept": [_fm_hit(moc_path, "moc-proposal", "pending-accept")],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                moc_path: {"content": _moc_proposal_body(accepted=True), "modified": 0},
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert len(state.approved_moc_proposals) == 1
        assert state.approved_moc_proposals[0]["path"] == moc_path
        assert len(state.pending_approval) == 0


# ---------------------------------------------------------------------------
# Test 7: force atomic note detection
# ---------------------------------------------------------------------------

class TestForceAtomicNoteDetection:
    def test_fan_items_extracted_from_approved_suggestions(self, tmp_path):
        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        body = _suggestions_body(approved=True, fan_items=["Furano", "Niseko"])

        client = FakeKadoClient(
            listdir_items=[_listdir_item(sugg_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [_fm_hit(sugg_path, "suggestions", "pending-approval")],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_path: {"content": body, "modified": 0},
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert len(state.force_atomic_items) == 2
        stems = [item["stem"] for item in state.force_atomic_items]
        assert "Furano" in stems
        assert "Niseko" in stems
        for item in state.force_atomic_items:
            assert item["source_path"] == sugg_path

    def test_fan_in_daily_notes_updates_section(self, tmp_path):
        """FAN in daily-notes-updates (log entry sub-bullet) is also detected."""
        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        body = "\n".join([
            "---",
            "type: tomo-suggestions",
            "---",
            "",
            "# Inbox Suggestions",
            "",
            "- [x] Approved",
            "",
            "## Daily Notes Updates",
            "",
            "### [[2026-04-17]]",
            "",
            "**Possible Log Entries (inline text):**",
            "- after_last_line — Furano content here",
            "  - Reason: Short descriptive note",
            "  - Source: [[Furano]]",
            "  - [ ] Accept",
            "  - [x] Force Atomic Note (create/keep a standalone note for this item)",
            "",
            "## Suggestions",
            "",
        ])

        client = FakeKadoClient(
            listdir_items=[_listdir_item(sugg_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [_fm_hit(sugg_path, "suggestions", "pending-approval")],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_path: {"content": body, "modified": 0},
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert len(state.force_atomic_items) == 1
        assert state.force_atomic_items[0]["stem"] == "Furano"
        assert state.force_atomic_items[0]["source_path"] == sugg_path


# ---------------------------------------------------------------------------
# Test 8: cache writes body and manifest
# ---------------------------------------------------------------------------

class TestCacheWritesBodyAndManifest:
    def test_cached_files_exist_with_correct_content(self, tmp_path):
        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        body_content = _suggestions_body(approved=True)

        client = FakeKadoClient(
            listdir_items=[_listdir_item(sugg_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [_fm_hit(sugg_path, "suggestions", "pending-approval")],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_responses={
                sugg_path: {"content": body_content, "modified": 0},
            },
        )

        mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        cache_dir = tmp_path / "inbox-cache"
        assert cache_dir.is_dir()

        cached_file = cache_dir / "2026-05-22_1432_suggestions.md"
        assert cached_file.exists()
        assert cached_file.read_text(encoding="utf-8") == body_content

        manifest_path = cache_dir / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = manifest["2026-05-22_1432_suggestions.md"]
        assert entry["vault_path"] == sugg_path
        expected_checksum = "sha256:" + hashlib.sha256(body_content.encode("utf-8")).hexdigest()
        assert entry["checksum"] == expected_checksum
        assert "cached_at" in entry


# ---------------------------------------------------------------------------
# Test 9: has_audio true when uncached
# ---------------------------------------------------------------------------

class TestHasAudioTrueWhenUncached:
    def test_audio_without_sibling_md(self, tmp_path):
        mod = _load_module()

        audio_path = INBOX_PATH + "recording.m4a"

        client = FakeKadoClient(
            listdir_items=[_listdir_item(audio_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert state.has_audio is True


# ---------------------------------------------------------------------------
# Test 10: has_audio false when all cached
# ---------------------------------------------------------------------------

class TestHasAudioFalseWhenAllCached:
    def test_audio_with_sibling_md(self, tmp_path):
        mod = _load_module()

        audio_path = INBOX_PATH + "recording.m4a"
        md_path = INBOX_PATH + "recording.md"

        client = FakeKadoClient(
            listdir_items=[
                _listdir_item(audio_path),
                _listdir_item(md_path),
            ],
            frontmatter_responses={
                "tomo.state=pending-approval": [],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert state.has_audio is False


# ---------------------------------------------------------------------------
# Test 11: kado unreachable exits 1
# ---------------------------------------------------------------------------

class TestKadoUnreachableExits1:
    def test_connection_error_exits_1(self, tmp_path):
        from lib.kado_client import KadoConnectionError

        mod = _load_module()

        # Patch KadoClient constructor to raise connection error
        def _raise_connection_error(*args, **kwargs):
            raise KadoConnectionError("Cannot reach Kado")

        with pytest.raises(SystemExit) as exc_info:
            mod.main(["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path)],
                     client_factory=_raise_connection_error)

        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Test: kado-read failure skips doc, adds drift indicator
# ---------------------------------------------------------------------------

class TestKadoReadFailureSkipsDoc:
    def test_read_failure_adds_drift_indicator(self, tmp_path):
        from lib.kado_client import KadoToolError

        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"

        client = FakeKadoClient(
            listdir_items=[_listdir_item(sugg_path)],
            frontmatter_responses={
                "tomo.state=pending-approval": [_fm_hit(sugg_path, "suggestions", "pending-approval")],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
            read_note_errors={
                sugg_path: KadoToolError("kado-read: internal error"),
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert len(state.approved_suggestions) == 0
        assert len(state.drift_indicators) == 1
        assert state.drift_indicators[0]["path"] == sugg_path
        assert state.drift_indicators[0]["type"] == "missing_source"


# ---------------------------------------------------------------------------
# Test: empty inbox produces empty state
# ---------------------------------------------------------------------------

class TestEmptyInbox:
    def test_empty_inbox_all_lists_empty(self, tmp_path):
        mod = _load_module()

        client = FakeKadoClient(
            listdir_items=[],
            frontmatter_responses={
                "tomo.state=pending-approval": [],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
        )

        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert state.md_files == []
        assert state.audio_files == []
        assert state.new_sources == []
        assert state.pending_approval_hits == []
        assert state.pending_accept_hits == []
        assert state.captured_hits == []
        assert state.instructions_hits == []
        assert state.approved_suggestions == []
        assert state.approved_fan == []
        assert state.approved_moc_proposals == []
        assert state.force_atomic_items == []
        assert state.pending_approval == []
        assert state.has_audio is False


# ===========================================================================
# T2.2 — Coverage computation, drift, action, routing-plan (steps 7-11)
# ===========================================================================


def _instructions_hit(
    path: str, sources: list[dict] | None = None,
) -> dict:
    """Build a frontmatter hit for an instructions doc with sources[]."""
    return {
        "path": path,
        "modified": 1716300000000,
        "frontmatter": {
            "tomo": {
                "doc_type": "instructions",
                "state": "pending-apply",
                "run_id": "test-run",
                "updated_at": "2026-05-21T12:00:00Z",
                "sources": sources or [],
            },
        },
    }


# ---------------------------------------------------------------------------
# Coverage computation (step 7)
# ---------------------------------------------------------------------------


class TestCoverageComputation:
    def test_excludes_already_covered_docs(self, tmp_path):
        """Approved doc whose path appears in instructions.sources is
        excluded from to_process."""
        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        instr_path = INBOX_PATH + "2026-05-24_0900_instructions.md"

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            approved_suggestions=[{
                "path": sugg_path,
                "modified": "1716300000000",
                "cache_path": str(tmp_path / "inbox-cache" / "suggestions.md"),
            }],
            instructions_hits=[_instructions_hit(
                instr_path,
                sources=[{"path": sugg_path, "checksum": "sha256:abc"}],
            )],
        )

        covered, to_process = mod.compute_coverage(state)

        assert sugg_path in covered
        assert len(to_process) == 0

    def test_partial_processing(self, tmp_path):
        """When some approved docs are covered and some are not, only
        uncovered go to to_process."""
        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        fan_path = INBOX_PATH + "2026-05-23_1328_suggestions-fan.md"
        moc_path = INBOX_PATH + "2026-05-22_1832_moc-proposal-board-games.md"
        instr_path = INBOX_PATH + "2026-05-24_0900_instructions.md"

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            approved_suggestions=[{
                "path": sugg_path,
                "modified": "1716300000000",
                "cache_path": str(tmp_path / "s.md"),
            }],
            approved_fan=[{
                "path": fan_path,
                "modified": "1716300000000",
                "cache_path": str(tmp_path / "f.md"),
            }],
            approved_moc_proposals=[{
                "path": moc_path,
                "modified": "1716300000000",
                "cache_path": str(tmp_path / "m.md"),
            }],
            instructions_hits=[_instructions_hit(
                instr_path,
                sources=[{"path": sugg_path, "checksum": "sha256:abc"}],
            )],
        )

        covered, to_process = mod.compute_coverage(state)

        assert sugg_path in covered
        assert fan_path in to_process
        assert moc_path in to_process
        assert sugg_path not in to_process
        assert len(to_process) == 2

    def test_no_instructions_means_all_approved_to_process(self):
        """When no instructions exist, all approved docs go to to_process."""
        mod = _load_module()

        sugg_path = INBOX_PATH + "suggestions.md"

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            approved_suggestions=[{"path": sugg_path, "modified": "", "cache_path": ""}],
            instructions_hits=[],
        )

        covered, to_process = mod.compute_coverage(state)

        assert len(covered) == 0
        assert sugg_path in to_process


# ---------------------------------------------------------------------------
# Drift detection (step 8)
# ---------------------------------------------------------------------------


class TestDriftDetection:
    def test_detects_checksum_mismatch(self, tmp_path):
        """When cached body hash differs from sources[].checksum,
        drift_indicators has a checksum_mismatch entry."""
        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        instr_path = INBOX_PATH + "2026-05-24_0900_instructions.md"
        body_content = "# Current body content\n"

        # Cache the body locally
        cache_dir = tmp_path / "inbox-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "2026-05-22_1432_suggestions.md"
        cache_file.write_text(body_content, encoding="utf-8")

        manifest = {
            "2026-05-22_1432_suggestions.md": {
                "vault_path": sugg_path,
                "checksum": mod._compute_checksum(body_content),
                "cached_at": "2026-05-26T10:00:00Z",
            },
        }

        # Instructions reference this source but with old checksum
        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            instructions_hits=[_instructions_hit(
                instr_path,
                sources=[{"path": sugg_path, "checksum": "sha256:0000000000000000000000000000000000000000000000000000000000000000"}],
            )],
            manifest=manifest,
        )

        drift = mod.detect_drift(state, manifest, cache_dir)

        assert len(drift) == 1
        assert drift[0]["path"] == sugg_path
        assert drift[0]["type"] == "checksum_mismatch"

    def test_no_drift_when_checksums_match(self, tmp_path):
        """When cached body checksum matches sources[].checksum,
        no drift indicator is produced."""
        mod = _load_module()

        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        instr_path = INBOX_PATH + "instructions.md"
        body_content = "# Current body content\n"

        cache_dir = tmp_path / "inbox-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "2026-05-22_1432_suggestions.md"
        cache_file.write_text(body_content, encoding="utf-8")

        correct_checksum = mod._compute_checksum(body_content)
        manifest = {
            "2026-05-22_1432_suggestions.md": {
                "vault_path": sugg_path,
                "checksum": correct_checksum,
                "cached_at": "2026-05-26T10:00:00Z",
            },
        }

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            instructions_hits=[_instructions_hit(
                instr_path,
                sources=[{"path": sugg_path, "checksum": correct_checksum}],
            )],
            manifest=manifest,
        )

        drift = mod.detect_drift(state, manifest, cache_dir)

        assert len(drift) == 0

    def test_drift_skips_sources_without_checksum(self, tmp_path):
        """Sources without a checksum field are silently skipped."""
        mod = _load_module()

        sugg_path = INBOX_PATH + "suggestions.md"
        instr_path = INBOX_PATH + "instructions.md"

        cache_dir = tmp_path / "inbox-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "suggestions.md").write_text("body", encoding="utf-8")

        manifest = {
            "suggestions.md": {
                "vault_path": sugg_path,
                "checksum": mod._compute_checksum("body"),
                "cached_at": "2026-05-26T10:00:00Z",
            },
        }

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            instructions_hits=[_instructions_hit(
                instr_path,
                sources=[{"path": sugg_path}],  # no checksum
            )],
            manifest=manifest,
        )

        drift = mod.detect_drift(state, manifest, cache_dir)

        assert len(drift) == 0


# ---------------------------------------------------------------------------
# Action determination (step 9) — priority order
# ---------------------------------------------------------------------------


class TestActionDetermination:
    def test_force_pass1(self):
        """force_pass1=True overrides everything → 'suggest'."""
        mod = _load_module()

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            force_pass1=True,
            has_audio=True,  # would normally trigger transcribe
            new_sources=[{"path": "a.md"}],
        )

        action, idle_reasons = mod.determine_action(state, to_process=set())
        assert action == "suggest"
        assert idle_reasons == []

    def test_force_pass2(self):
        """force_pass2=True → 'synthesize' (even if nothing approved)."""
        mod = _load_module()

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            force_pass2=True,
            has_audio=True,
        )

        action, idle_reasons = mod.determine_action(state, to_process=set())
        assert action == "synthesize"
        assert idle_reasons == []

    def test_transcribe(self):
        """has_audio=True → 'transcribe'."""
        mod = _load_module()

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            has_audio=True,
        )

        action, idle_reasons = mod.determine_action(state, to_process=set())
        assert action == "transcribe"

    def test_fan_resolve(self):
        """force_atomic_items present + no fan doc → 'fan-resolve'."""
        mod = _load_module()

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            force_atomic_items=[{"stem": "Furano", "source_path": "s.md"}],
            approved_fan=[],  # no fan doc exists
        )

        action, idle_reasons = mod.determine_action(state, to_process=set())
        assert action == "fan-resolve"

    def test_fan_resolve_skipped_when_approved_fan_doc_exists(self):
        """force_atomic_items present BUT approved fan doc exists → skip."""
        mod = _load_module()

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            force_atomic_items=[{"stem": "Furano", "source_path": "s.md"}],
            approved_fan=[{"path": "fan.md", "modified": "", "cache_path": ""}],
            new_sources=[{"path": "a.md"}],  # triggers suggest
        )

        action, idle_reasons = mod.determine_action(state, to_process=set())
        # fan-resolve skipped; next matching rule is suggest (new_sources)
        assert action == "suggest"

    def test_fan_resolve_skipped_when_pending_fan_doc_exists(self):
        """force_atomic_items present BUT pending fan doc exists → skip."""
        mod = _load_module()

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            force_atomic_items=[{"stem": "Furano", "source_path": "s.md"}],
            approved_fan=[],
            pending_approval=[{
                "path": "fan.md",
                "doc_type": "suggestions-fan",
                "message": "Awaiting user approval",
            }],
            new_sources=[{"path": "a.md"}],
        )

        action, idle_reasons = mod.determine_action(state, to_process=set())
        assert action == "suggest"

    def test_synthesize(self):
        """to_process non-empty → 'synthesize'."""
        mod = _load_module()

        state = mod.TriageState(inbox_path=INBOX_PATH)
        to_process = {"100 Inbox/approved.md"}

        action, idle_reasons = mod.determine_action(state, to_process=to_process)
        assert action == "synthesize"

    def test_recover(self):
        """recover=True + captured_hits → 'suggest'."""
        mod = _load_module()

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            recover=True,
            captured_hits=[_fm_hit(INBOX_PATH + "note.md", "source", "captured")],
        )

        action, idle_reasons = mod.determine_action(state, to_process=set())
        assert action == "suggest"

    def test_suggest_new_sources(self):
        """new_sources present → 'suggest'."""
        mod = _load_module()

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            new_sources=[{"path": "100 Inbox/fresh.md"}],
        )

        action, idle_reasons = mod.determine_action(state, to_process=set())
        assert action == "suggest"

    def test_idle(self):
        """Nothing to do → 'idle' with reasons."""
        mod = _load_module()

        state = mod.TriageState(inbox_path=INBOX_PATH)

        action, idle_reasons = mod.determine_action(state, to_process=set())
        assert action == "idle"
        assert len(idle_reasons) > 0

    def test_idle_reasons_content(self):
        """Idle reasons cover key conditions."""
        mod = _load_module()

        state = mod.TriageState(inbox_path=INBOX_PATH)

        _, idle_reasons = mod.determine_action(state, to_process=set())
        reasons_text = " ".join(idle_reasons).lower()
        assert "source" in reasons_text


# ---------------------------------------------------------------------------
# Routing plan (step 10)
# ---------------------------------------------------------------------------


_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)


class TestRoutingPlan:
    def test_validates_against_schema(self, tmp_path):
        """build_routing_plan output passes routing-plan.schema.json validation."""
        from jsonschema import validate as json_validate

        mod = _load_module()

        schema_path = REPO_ROOT / "tomo" / "schemas" / "routing-plan.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        state = mod.TriageState(
            inbox_path=INBOX_PATH,
            new_sources=[{"path": INBOX_PATH + "fresh.md", "modified": "1716300000000"}],
            approved_suggestions=[{
                "path": INBOX_PATH + "sug.md",
                "modified": "1716300000000",
                "cache_path": str(tmp_path / "sug.md"),
            }],
        )
        metrics = {
            "total_ms": 18.0,
            "discover_ms": 10.0,
            "kado_calls": 5,
            "docs_cached": 1,
        }

        plan = mod.build_routing_plan(
            state=state,
            action="suggest",
            to_process=set(),
            drift_indicators=[],
            idle_reasons=[],
            metrics=metrics,
        )

        json_validate(instance=plan, schema=schema)

    def test_idle_action_includes_idle_reasons(self):
        """When action=idle, routing plan has non-empty idle_reasons."""
        mod = _load_module()

        state = mod.TriageState(inbox_path=INBOX_PATH)
        idle_reasons = [
            "No new source files in inbox",
            "All approved items already covered by existing instructions",
        ]

        plan = mod.build_routing_plan(
            state=state,
            action="idle",
            to_process=set(),
            drift_indicators=[],
            idle_reasons=idle_reasons,
            metrics={
                "total_ms": 0, "discover_ms": 0,
                "kado_calls": 0, "docs_cached": 0,
            },
        )

        assert plan["action"] == "idle"
        assert len(plan["idle_reasons"]) == 2

    def test_drift_indicators_included(self, tmp_path):
        """Drift indicators are included in the routing plan."""
        mod = _load_module()

        state = mod.TriageState(inbox_path=INBOX_PATH)
        drift = [
            {"path": INBOX_PATH + "old.md", "type": "checksum_mismatch", "detail": "hash differs"},
        ]

        plan = mod.build_routing_plan(
            state=state,
            action="idle",
            to_process=set(),
            drift_indicators=drift,
            idle_reasons=["nothing"],
            metrics={
                "total_ms": 0, "discover_ms": 0,
                "kado_calls": 0, "docs_cached": 0,
            },
        )

        assert len(plan["drift_indicators"]) == 1
        assert plan["drift_indicators"][0]["type"] == "checksum_mismatch"


# ---------------------------------------------------------------------------
# End-to-end: main() writes routing-plan.json (step 11)
# ---------------------------------------------------------------------------


class TestMainWritesRoutingPlan:
    def test_routing_plan_written_to_file(self, tmp_path):
        """main() writes routing-plan.json to output dir."""
        mod = _load_module()

        new_note = INBOX_PATH + "fresh-note.md"

        client = FakeKadoClient(
            listdir_items=[_listdir_item(new_note)],
            frontmatter_responses={
                "tomo.state=pending-approval": [],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
        )

        rc = mod.main(
            ["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path)],
            client_factory=lambda: client,
        )

        assert rc == 0
        plan_path = tmp_path / "routing-plan.json"
        assert plan_path.exists()

        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan["action"] == "suggest"
        assert plan["inbox_path"] == INBOX_PATH

    def test_schema_validation_failure_exits_2(self, tmp_path, monkeypatch):
        """When schema validation fails, main() exits 2."""
        mod = _load_module()

        client = FakeKadoClient(
            listdir_items=[],
            frontmatter_responses={
                "tomo.state=pending-approval": [],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
        )

        # Monkey-patch build_routing_plan to produce invalid output
        original_build = mod.build_routing_plan

        def _bad_plan(*args, **kwargs):
            plan = original_build(*args, **kwargs)
            plan["bad_field"] = "should fail validation"
            return plan

        monkeypatch.setattr(mod, "build_routing_plan", _bad_plan)

        with pytest.raises(SystemExit) as exc_info:
            mod.main(
                ["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path)],
                client_factory=lambda: client,
            )

        assert exc_info.value.code == 2

    def test_metrics_in_routing_plan(self, tmp_path):
        """Routing plan includes timing metrics."""
        mod = _load_module()

        client = FakeKadoClient(
            listdir_items=[],
            frontmatter_responses={
                "tomo.state=pending-approval": [],
                "tomo.state=pending-accept": [],
                "tomo.state=captured": [],
                "tomo.doc_type=instructions": [],
            },
        )

        mod.main(
            ["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path)],
            client_factory=lambda: client,
        )

        plan = json.loads((tmp_path / "routing-plan.json").read_text(encoding="utf-8"))
        assert "metrics" in plan
        assert "total_ms" in plan["metrics"]
        assert "kado_calls" in plan["metrics"]
        assert "docs_cached" in plan["metrics"]
