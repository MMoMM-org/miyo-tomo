#!/usr/bin/env python3
# version: 0.1.0
"""test_note_triage_interplay.py — /note deliveries and inbox triage (spec 044 T2.6).

The files note-instructions.py deliver writes, and the source it marks, are fed
into triage's own frontmatter buckets (query_frontmatter), new-source logic
(compute_new_sources) and orphan check (detect_orphaned_state):
- the delivered note (rendered-note/pending-move), the MD peer
  (doc_type: instructions) and the marked source (captured) yield no new item
- the marked source with its MD peer beside it raises no orphan warning
- --recover treats the marked source as fresh (F9-AC2)

Runs in tmp_path with an in-memory vault; never a live vault.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

import note_fake_vault as nfv  # noqa: E402

INBOX = "100 Inbox/"
SOURCE = "100 Inbox/Meeting raw.md"
DRAFT = "---\ntitle: Design review\n---\n# Notes\nAll fine\n"
CONFIG = 'profile: "miyo"\nconcepts:\n  inbox: "100 Inbox/"\n  atomic_note: "Atlas/202 Notes/"\n'


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # dataclasses look their module up here
    spec.loader.exec_module(mod)
    return mod


ni = _load("note_instructions", "note-instructions.py")
triage = _load("inbox_triage", "inbox-triage.py")


def _main(argv, capsys) -> dict:
    assert ni.main(argv) == 0
    return json.loads(capsys.readouterr()[0].splitlines()[-1])


@pytest.fixture
def delivered(tmp_path, monkeypatch, capsys):
    """A vault after one successful /note delivery from SOURCE."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "vault-config.yaml").write_text(CONFIG, encoding="utf-8")
    vault = nfv.NoteFakeVault({SOURCE: "raw meeting text\n"})
    monkeypatch.setattr(ni, "KadoClient", vault)
    stem = _main(["new", "--template", "Templates/t_meeting.md", "--source", SOURCE],
                 capsys)["stem"]
    (tmp_path / "tomo-tmp" / "note" / stem / "draft.md").write_text(DRAFT, encoding="utf-8")
    _main(["stage", "--stem", stem, "--title", "Design review"], capsys)
    assert _main(["deliver", "--stem", stem], capsys)["status"] == "delivered"
    return vault


def _state(vault, recover=False):
    _all, _audio, md_files = triage.discover_files(vault, INBOX)
    (pending_approval, pending_accept, captured, instructions,
     approved, accepted, rendered) = triage.query_frontmatter(vault, INBOX)
    new_sources = triage.compute_new_sources(
        md_files, pending_approval, pending_accept, captured, instructions,
        approved, accepted, rendered=rendered)
    return triage.TriageState(
        inbox_path=INBOX, md_files=md_files, pending_approval_hits=pending_approval,
        pending_accept_hits=pending_accept, captured_hits=captured,
        instructions_hits=instructions, new_sources=new_sources, recover=recover)


def test_delivered_files_and_marked_source_are_no_new_item(delivered):
    state = _state(delivered)
    assert len(state.md_files) == 3          # note, MD peer, source; the JSON is not a note
    assert state.new_sources == []
    assert [h["path"] for h in state.captured_hits] == [SOURCE]


def test_marked_source_beside_its_peer_raises_no_orphan_warning(delivered):
    state = _state(delivered)
    assert len(state.instructions_hits) == 1
    assert triage.detect_orphaned_state(state) == []


def test_recover_treats_the_marked_source_as_fresh(delivered):
    state = _state(delivered, recover=True)
    assert triage.determine_action(state, set())[0] == "suggest"
    plan = triage.build_routing_plan(state, "suggest", set(), [], [], {})
    assert [s["path"] for s in plan["fresh_sources"]] == [SOURCE]
