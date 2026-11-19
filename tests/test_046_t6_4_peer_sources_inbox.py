#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t6_4_peer_sources_inbox.py — a peer's `tomo.sources` never lists a path outside the inbox (spec 046 T6.4).

Hashi's cleanup trashes every `sources[].path` after a full apply. A review document path comes from `meta.json`
(or `--doc-path`), so a wrong one must never reach the list: `peer_sources(plan, meta, inbox=...)` drops a path that
is not strictly inside the configured inbox folder (dropped, not refused: the delivery goes on and the file is
simply never trashed). Mechanisms each test falsifies:

- the guard removed: ``test_a_path_outside_the_inbox_is_not_listed`` (Calendar, parent hops, absolute, backslash,
  the inbox folder itself, a name sharing only the inbox prefix, non-canonical spellings)
- the guard dropping everything: ``test_inbox_paths_are_listed``
- the new-note copy skipping the guard: ``test_the_new_note_copy_is_guarded_too``
- `set_md` not passing the inbox on: ``test_set_md_writes_only_inbox_sources``
- an unconfigured (empty) inbox listing anything: ``test_an_empty_inbox_lists_nothing``

Spec: docs/XDD/specs/046-review-template-sections/plan/phase-6.md (T6.1 "Open for T6.4")
Ref: Constitution L1 (privacy / permission rules: authorization and rejection both covered)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import frontmatter  # noqa: E402

from lib import review_actions as ra  # noqa: E402
from lib import review_delivery as rdl  # noqa: E402

INBOX = "100 Inbox/"
TARGET = "Calendar/2026-W13.md"


def _plan(note_path=None):
    plan = ra.ReviewPlan(ra.NEW_NOTE if note_path else ra.INSERT, TARGET, False, [], {})
    plan.note_path = note_path
    return plan


def _meta(doc_path):
    return rdl.ReviewMeta({"run_id": "r", "generated": "2026-11-19T08:00:00Z", "doc_path": doc_path})


@pytest.mark.parametrize("inbox", ["100 Inbox/", "100 Inbox", "/100 Inbox/", "Deep/Inbox"])
def test_inbox_paths_are_listed(inbox):
    doc = f"{inbox.strip('/')}/2026-W13 Review.md"
    assert rdl.peer_sources(_plan(), _meta(doc), inbox=inbox) == [{"path": doc}]


@pytest.mark.parametrize("bad", [
    "Calendar/2026-W13 Review.md",
    "../x.md",
    "100 Inbox/../Calendar/x.md",
    "/100 Inbox/x.md",
    "/etc/passwd",
    "100 Inbox Archive/x.md",
    "100 Inboxx.md",
    "100 Inbox",
    "100 Inbox/",
    "100 Inbox\\x.md",
    "100 Inbox/./x.md",
    "100 Inbox//x.md",
    "100 inbox/x.md",
], ids=["calendar", "dotdot", "hop-out", "absolute-inbox", "absolute", "prefix-sibling", "prefix-file",
        "the-folder", "the-folder-slash", "backslash", "dot-segment", "double-slash", "case"])
def test_a_path_outside_the_inbox_is_not_listed(bad):
    assert rdl.peer_sources(_plan(), _meta(bad), inbox=INBOX) == []


def test_the_new_note_copy_is_guarded_too():
    plan = _plan("Calendar/elsewhere.md")
    assert rdl.peer_sources(plan, _meta("100 Inbox/doc.md"), inbox=INBOX) == [{"path": "100 Inbox/doc.md"}]
    plan = _plan("100 Inbox/2026-03.md")
    assert rdl.peer_sources(plan, _meta("Calendar/doc.md"), inbox=INBOX) == [{"path": "100 Inbox/2026-03.md"}]


@pytest.mark.parametrize("inbox", ["", "  ", "/", ".", "..", "a/../.."])
def test_an_empty_inbox_lists_nothing(inbox):
    assert rdl.peer_sources(_plan(), _meta("100 Inbox/doc.md"), inbox=inbox) == []


def test_set_md_writes_only_inbox_sources():
    plan = _plan("Calendar/elsewhere.md")
    block = frontmatter(rdl.set_md(plan, _meta("100 Inbox/doc.md"), None, inbox=INBOX))["tomo"]
    assert block["sources"] == [{"path": "100 Inbox/doc.md"}]
    block = frontmatter(rdl.set_md(plan, _meta("Calendar/doc.md"), None, inbox=INBOX))["tomo"]
    assert block["sources"] == []
