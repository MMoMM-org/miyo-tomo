#!/usr/bin/env python3
# version: 0.3.1
"""test_attachment_index.py — Tests for lib.attachment_index — spec 031
(Inbox attachment filing), Phase 1.

T1.1 covers extract_attachment_embeds() — PRD Feature 1 (detect embedded
attachments):
  - AC-F1.1: `![[karte.jpg]]` embed is recorded
  - AC-F1.2: note-to-note embed `![[Some Note]]` is NOT recorded
  - AC-F1.3: plain link `[[karte.jpg]]` (no bang) is NOT recorded
  - AC-F1.4: the same embed twice is recorded once, in document order
  - AC-F1.5: no embeds → empty list

Plus the two-step classifier boundary (SDD "Example: Embed extraction"): the
`KNOWN_FILE_EXTENSIONS` frozenset contains `md`, so a naive membership check
would wrongly treat `![[Note.md]]` as an attachment. And PRD Feature 2
criterion 2: a path-qualified embed target keeps its path — unlike
topic-extract.py's `_strip_link_target`, which discards it.

T1.2 covers build_inbox_index() — indexing a Kado listDir result by basename
so basename collisions across folders are representable rather than lost.
`five_file_inbox` is the SDD's worked five-file inbox fixture, reused
verbatim by T1.3's resolution tests.

T1.3 covers resolve_attachments() — resolving each embed target against a
build_inbox_index() index into an AttachmentRef (resolved | unresolved |
ambiguous). `five_file_index` builds on `five_file_inbox` (unchanged from
T1.2) via build_inbox_index() to give resolve_attachments its input directly.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.attachment_index import (  # noqa: E402
    AttachmentRef,
    build_inbox_index,
    extract_attachment_embeds,
    resolve_attachments,
)


def test_embed_with_extension_is_recorded():
    """AC-F1.1: `![[karte.jpg]]` is recorded as an attachment."""
    assert extract_attachment_embeds("![[karte.jpg]]") == ["karte.jpg"]


def test_plain_link_is_not_recorded():
    """AC-F1.3: a plain `[[...]]` link (no bang) is not an attachment."""
    assert extract_attachment_embeds("[[karte.jpg]]") == []


def test_note_embed_without_extension_is_not_recorded():
    """AC-F1.2: `![[Some Note]]` names a note, not a file — not an attachment."""
    assert extract_attachment_embeds("![[Some Note]]") == []


def test_md_embed_is_not_recorded_despite_being_in_known_extensions():
    """The two-step classifier: `md` IS in _KNOWN_FILE_EXTENSIONS, but a note
    embed must still be excluded — a naive membership check would wrongly emit
    a move_asset for a note (Hashi rejects this, CON-3)."""
    assert extract_attachment_embeds("![[Note.md]]") == []


def test_canvas_embed_is_not_recorded():
    assert extract_attachment_embeds("![[Board.canvas]]") == []


def test_base_embed_is_not_recorded():
    assert extract_attachment_embeds("![[Data.base]]") == []


def test_embed_with_alias_is_recorded_without_alias():
    assert extract_attachment_embeds("![[karte.jpg|Karte]]") == ["karte.jpg"]


def test_embed_with_anchor_is_recorded_without_anchor():
    assert extract_attachment_embeds("![[karte.jpg#section]]") == ["karte.jpg"]


def test_path_qualified_embed_keeps_its_path():
    """PRD Feature 2, criterion 2: a path-qualified embed is already an answer
    and must not be discarded — unlike topic-extract.py's _strip_link_target,
    which ends with split("/")[-1]."""
    assert extract_attachment_embeds("![[Images/karte.jpg]]") == ["Images/karte.jpg"]


def test_duplicate_embed_recorded_once_in_document_order():
    """AC-F1.4: the same embed twice is recorded once."""
    body = "See ![[karte.jpg]] here and again ![[karte.jpg]] later, plus ![[other.png]]."
    assert extract_attachment_embeds(body) == ["karte.jpg", "other.png"]


def test_mixed_case_extension_is_recorded():
    """The `.lower()` in _is_attachment_target's extension check is the only
    thing making a mixed-case extension classify as an attachment — nothing
    else tests it, so a refactor dropping it would break case-insensitive
    matching silently. Original casing is preserved in the returned value."""
    assert extract_attachment_embeds("![[FOTO.JPG]]") == ["FOTO.JPG"]


def test_empty_body_returns_empty_list():
    """AC-F1.5: no embeds → empty attachment list."""
    assert extract_attachment_embeds("") == []


def test_body_with_no_embeds_returns_empty_list():
    """AC-F1.5: prose with no wikilinks at all → empty attachment list."""
    assert extract_attachment_embeds("Just plain prose, no links here.") == []


def test_attachment_index_module_stays_pure():
    """Regression guard for the 175→4 module fix: importing lib.attachment_index
    must not pull in lib.render_actions or lib.kado_client. Runs in a subprocess
    so the assertion holds regardless of what other tests have already imported."""
    code = (
        "import sys; sys.path.insert(0, %r); "
        "import lib.attachment_index; "
        "assert 'lib.render_actions' not in sys.modules; "
        "assert 'lib.kado_client' not in sys.modules"
    ) % str(SCRIPTS_DIR)
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


# --- T1.2: build_inbox_index() ---------------------------------------------

@pytest.fixture
def five_file_inbox():
    """SDD's worked five-file inbox, reused verbatim by T1.3.

    Matches the real shape of `KadoClient.list_dir()` — a flat list of item
    dicts, each carrying `path` and `type` ('file' | 'folder') — NOT a dict
    wrapped under an "entries" key (see plan/phase-1.md discrepancy note).
    """
    return [
        {"path": "100 Inbox/Places/Dresden.md", "type": "file"},
        {"path": "100 Inbox/Places/Prag.md", "type": "file"},
        {"path": "100 Inbox/Images/karte.jpg", "type": "file"},
        {"path": "100 Inbox/Images/prag-karte.jpg", "type": "file"},
        {"path": "100 Inbox/Scans/karte.jpg", "type": "file"},
    ]


def test_build_inbox_index_indexes_each_file_by_basename(five_file_inbox):
    index = build_inbox_index(five_file_inbox)
    assert index["Dresden.md"] == ["100 Inbox/Places/Dresden.md"]
    assert index["prag-karte.jpg"] == ["100 Inbox/Images/prag-karte.jpg"]


def test_build_inbox_index_preserves_basename_collisions(five_file_inbox):
    """PRD Business rule 4: collisions are preserved as multiple paths, never
    collapsed to one — karte.jpg exists under both Images/ and Scans/."""
    index = build_inbox_index(five_file_inbox)
    assert index["karte.jpg"] == [
        "100 Inbox/Images/karte.jpg",
        "100 Inbox/Scans/karte.jpg",
    ]


def test_build_inbox_index_excludes_folder_entries():
    result = [
        {"path": "100 Inbox/Images", "type": "folder"},
        {"path": "100 Inbox/Images/karte.jpg", "type": "file"},
    ]
    index = build_inbox_index(result)
    assert "Images" not in index
    assert index["karte.jpg"] == ["100 Inbox/Images/karte.jpg"]


def test_build_inbox_index_indexes_md_files_too():
    """The index describes the inbox as-is — filtering .md notes out is the
    resolver's job (T1.3), not this function's."""
    index = build_inbox_index([{"path": "100 Inbox/Places/Dresden.md", "type": "file"}])
    assert index == {"Dresden.md": ["100 Inbox/Places/Dresden.md"]}


def test_build_inbox_index_skips_file_item_without_path():
    """An item claiming type=='file' but missing 'path' contributes nothing,
    rather than indexing under a bogus key."""
    assert build_inbox_index([{"type": "file"}]) == {}


@pytest.mark.parametrize("empty_result", [None, []])
def test_build_inbox_index_fails_open_on_empty_or_missing_result(empty_result):
    """PRD Business rule 10: an empty index is a valid state, not an
    exception. Both None (a listDir call that failed) and [] (a listDir call
    that returned nothing) hit the early `if not list_dir_result` return —
    they never reach the per-item guard below."""
    assert build_inbox_index(empty_result) == {}


def test_build_inbox_index_fails_open_on_wrapped_dict_result():
    """A truthy non-list container — e.g. a caller mistakenly passing the raw
    {"items": [...]} wrapper instead of the flat list — does NOT hit the
    early-return (a non-empty dict is truthy). It reaches the loop, which
    iterates the dict's keys (plain strings), and the per-item
    `isinstance(item, dict)` guard rejects each one. This is the guard this
    test exercises; the None/[] case above exercises the early return instead."""
    wrapped = {"items": [{"path": "100 Inbox/Images/karte.jpg", "type": "file"}]}
    assert build_inbox_index(wrapped) == {}


# --- T1.3: resolve_attachments() --------------------------------------------

@pytest.fixture
def five_file_index(five_file_inbox):
    """The SDD's worked index, built from the unchanged T1.2 fixture."""
    return build_inbox_index(five_file_inbox)


def test_resolve_subfolder_target_not_sibling(five_file_index):
    """AC-F2.1: `prag-karte.jpg` lives in Images/, not beside the note in
    Places/ — the sibling assumption would produce a nonexistent
    "100 Inbox/Places/prag-karte.jpg". Basename lookup finds the real file
    regardless of where the embedding note lives."""
    [ref] = resolve_attachments(["prag-karte.jpg"], five_file_index)
    assert ref == AttachmentRef(
        "prag-karte.jpg", "100 Inbox/Images/prag-karte.jpg", "resolved"
    )


def test_resolve_ambiguous_basename_yields_no_path(five_file_index):
    """AC-F2.4: karte.jpg has two index hits (Images/ and Scans/) — ambiguous,
    not a guess. Fails if an implementation returns the first hit instead."""
    [ref] = resolve_attachments(["karte.jpg"], five_file_index)
    assert ref.status == "ambiguous"
    assert ref.resolved_path is None


def test_resolve_path_qualified_target_via_membership_check(five_file_index):
    """AC-F2.2: `Images/karte.jpg` disambiguates the two-hit basename by path.
    resolved_path is the retrieved index path — NOT the target string echoed
    back — so this fails if the membership check is dropped in favour of
    "use the given path as-is" (PRD Rule 2's literal reading; the SDD's
    membership check overrides it, see plan/phase-1.md discrepancy note)."""
    [ref] = resolve_attachments(["Images/karte.jpg"], five_file_index)
    assert ref == AttachmentRef(
        "Images/karte.jpg", "100 Inbox/Images/karte.jpg", "resolved"
    )


def test_resolve_target_absent_from_index_is_unresolved(five_file_index):
    """AC-F2.3: a basename with zero index hits is unresolved, not an error."""
    [ref] = resolve_attachments(["missing.jpg"], five_file_index)
    assert ref == AttachmentRef("missing.jpg", None, "unresolved")


def test_resolve_path_qualified_target_not_in_index_is_unresolved(five_file_index):
    """A plausible-looking but wrong path-qualified target: prag-karte.jpg's
    basename IS in the index (under Images/), but not under Scans/. This is a
    stronger fabrication guard than an absent basename — it fails if the
    membership check is skipped and the given path is returned verbatim,
    since "Scans/prag-karte.jpg" would then wrongly report as resolved."""
    [ref] = resolve_attachments(["Scans/prag-karte.jpg"], five_file_index)
    assert ref == AttachmentRef("Scans/prag-karte.jpg", None, "unresolved")


def test_resolve_against_empty_index_is_unresolved_for_every_target():
    """Empty index (listDir failed or the inbox is empty) degrades every
    target to unresolved rather than raising."""
    targets = ["karte.jpg", "Images/karte.jpg", "anything.png"]
    refs = resolve_attachments(targets, {})
    assert [ref.status for ref in refs] == ["unresolved"] * 3
    assert all(ref.resolved_path is None for ref in refs)


def test_resolve_case_differing_basename_is_unresolved(five_file_index):
    """The index key "karte.jpg" does not match "KARTE.jpg" — exact-case
    lookup only. Fails if the lookup key (or the index key) is lowercased,
    since that would turn this into an ambiguous 2-hit match instead."""
    [ref] = resolve_attachments(["KARTE.jpg"], five_file_index)
    assert ref == AttachmentRef("KARTE.jpg", None, "unresolved")


def test_resolve_no_resolved_path_is_absent_from_the_index(five_file_index):
    """Fabrication-impossible-by-construction check: every non-null
    resolved_path returned for a realistic batch of targets must be one of
    the actual paths the index holds."""
    all_indexed_paths = {path for paths in five_file_index.values() for path in paths}
    targets = ["prag-karte.jpg", "karte.jpg", "Images/karte.jpg", "missing.jpg"]
    refs = resolve_attachments(targets, five_file_index)
    for ref in refs:
        if ref.resolved_path is not None:
            assert ref.resolved_path in all_indexed_paths


def test_resolve_fully_qualified_target_matches_by_exact_path(five_file_index):
    """A target that is ALREADY the full vault-relative path (e.g. an embed
    written as `![[100 Inbox/Images/karte.jpg]]`) hits the `path == target`
    branch, not the `.../` suffix branch — no basename collision is even in
    play here since prag-karte.jpg only has one index entry regardless."""
    target = "100 Inbox/Images/prag-karte.jpg"
    [ref] = resolve_attachments([target], five_file_index)
    assert ref == AttachmentRef(target, target, "resolved")


def test_resolve_duplicate_target_is_not_deduplicated(five_file_index):
    """The same embed target appearing twice in embed_targets produces two
    independent AttachmentRefs, not one — deduplication across the run is
    Phase 2's job (_build_move_asset_actions), not this function's."""
    refs = resolve_attachments(["prag-karte.jpg", "prag-karte.jpg"], five_file_index)
    assert refs == [
        AttachmentRef("prag-karte.jpg", "100 Inbox/Images/prag-karte.jpg", "resolved"),
        AttachmentRef("prag-karte.jpg", "100 Inbox/Images/prag-karte.jpg", "resolved"),
    ]
