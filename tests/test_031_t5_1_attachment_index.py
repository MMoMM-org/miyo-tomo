#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t5_1_attachment_index.py — spec 031 T5.1 inbox attachment index
and attachment extraction/resolution (ADR-1 + corrected ADR-2).

Covers `build_attachment_index` (inbox-triage.py) and its wiring into
`discover()`:
  - the recursive listDir is requested exactly once per run, independent of
    note count (CON-4 / PRD business rule 9)
  - the recursive call targets the inbox path, not the vault root (PRD
    business rule 3 — only inbox paths can ever appear in the index)
  - a KadoError on the recursive call degrades to an empty index and the run
    continues (no exception escapes) — PRD business rule 10
  - a subtree of 600+ entries is fully indexed, none dropped
  - the existing depth=1 partition (`discover_files`, the #93 decision) is
    untouched by adding the second, recursive call

ADR-2 correction: the original design deferred `listNotes(fields=["links"])`
extraction in favour of a body-scanning regex, on the premise that "the
regex runs on bodies the pipeline already has." That premise is false —
`inbox-triage.py` never reads a fresh source's body (only the analyst
subagent does, invisible to this script). `attachment_index.py`'s regex-based
`extract_attachment_embeds` stays in the library (tested, correct, the right
tool if a body-bearing path ever exists) but this pipeline does not call it.
Instead `resolve_inbox_attachments` uses `list_notes(fields=["links"])` —
Kado's own metadataCache, authoritative on what an embed is (no
fenced-code-block false positives, unlike the regex) — and resolves each
`kind=='embed'` file target against the SAME recursive index via Phase 1's
`resolve_attachments`. `attachment-index.json` is dropped: the basename
index is purely internal now, consumed by resolution within the same
`discover()` call.

The resolution result is persisted to `<output_dir>/resolved-attachments.json`
(keyed by source path) — NOT joined into `routing-plan.json`'s
`fresh_sources[]`. The reducer (`suggestions-reducer.py`) never reads the
routing plan (it takes `--state`/`--items-dir`/`--shared-ctx`) and runs as a
separate, later process after the per-item analysts, so nothing held on
`fresh_sources[]` would ever reach it; `fresh_sources`' membership also
tracks newness, not attachment presence, so it is the wrong population
regardless. T5.3's `[triage]`-prefixed stderr reporting for unresolved/
ambiguous embeds lives inside `resolve_inbox_attachments` itself, since
resolution happens there.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

INBOX_PATH = "100 Inbox/"


def _load_module():
    script_path = SCRIPTS_DIR / "inbox-triage.py"
    spec = importlib.util.spec_from_file_location("inbox_triage_t51", script_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage_t51"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _listdir_item(path: str, item_type: str = "file") -> dict:
    return {"path": path, "type": item_type, "modified": 1716300000000, "size": 100}


class _FakeClient:
    """Minimal fake covering every Kado method discover() may call.

    depth1_items and recursive_items are independently configurable so tests
    can distinguish the existing depth=1 partition call from the new
    recursive call. recursive_error, when set, is raised ONLY on the
    depth=None (recursive) call — the depth=1 call always succeeds, proving
    a recursive-call failure cannot take the existing partition down with it.
    """

    def __init__(
        self, depth1_items=None, recursive_items=None, recursive_error=None,
        notes=None, list_notes_error=None,
    ):
        self.calls: list[tuple[str, dict]] = []
        self._depth1_items = depth1_items or []
        self._recursive_items = (
            recursive_items if recursive_items is not None else list(self._depth1_items)
        )
        self._recursive_error = recursive_error
        self._notes = notes or []
        self._list_notes_error = list_notes_error

    def list_dir(self, path, *, depth=None, limit=500):
        self.calls.append(("list_dir", {"path": path, "depth": depth}))
        if depth is None:
            if self._recursive_error is not None:
                raise self._recursive_error
            return self._recursive_items
        return self._depth1_items

    def list_notes(self, path, *, fields=None, depth=None, limit=500):
        self.calls.append(("list_notes", {"path": path, "fields": fields}))
        if self._list_notes_error is not None:
            raise self._list_notes_error
        return self._notes

    def search_by_frontmatter(self, query, *, path_prefix=None, limit=500, modified_after=None):
        self.calls.append(("search_by_frontmatter", {"query": query}))
        return []

    def read_note(self, path):
        self.calls.append(("read_note", {"path": path}))
        return {"content": "", "modified": 0}

    def read_frontmatter(self, path):
        self.calls.append(("read_frontmatter", {"path": path}))
        return {"content": {}}

    def read_file_bytes(self, path):
        self.calls.append(("read_file_bytes", {"path": path}))
        from lib.kado_client import KadoError
        raise KadoError(f"not found: {path}")


def _list_dir_calls(client) -> list[dict]:
    return [args for name, args in client.calls if name == "list_dir"]


# ---------------------------------------------------------------------------
# Constant cost (CON-4 / business rule 9)
# ---------------------------------------------------------------------------

def test_recursive_listing_requested_exactly_once_per_run(tmp_path):
    mod = _load_module()
    client = _FakeClient(depth1_items=[_listdir_item(INBOX_PATH + "note.md")])

    mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    recursive_calls = [c for c in _list_dir_calls(client) if c["depth"] is None]
    assert len(recursive_calls) == 1, (
        f"expected exactly 1 recursive list_dir call, got {len(recursive_calls)}: "
        f"{_list_dir_calls(client)}"
    )


def test_recursive_listing_count_independent_of_note_count(tmp_path):
    """The defining CON-4 guard: 1 note and 20 notes issue the SAME number of
    recursive list_dir calls (one)."""
    mod = _load_module()

    def _run(n_notes: int, out: Path) -> int:
        items = [_listdir_item(f"{INBOX_PATH}note-{i}.md") for i in range(n_notes)]
        client = _FakeClient(depth1_items=items)
        mod.discover(client, INBOX_PATH, output_dir=str(out))
        return len([c for c in _list_dir_calls(client) if c["depth"] is None])

    one_note_calls = _run(1, tmp_path / "one")
    twenty_note_calls = _run(20, tmp_path / "twenty")
    assert one_note_calls == 1
    assert twenty_note_calls == 1
    assert one_note_calls == twenty_note_calls


def test_recursive_call_targets_inbox_path_not_vault_root(tmp_path):
    """Business rule 3 — only inbox paths can be resolved. Guards against a
    future `client.list_dir()` call that defaults to the vault root."""
    mod = _load_module()
    client = _FakeClient(depth1_items=[])

    mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    recursive_calls = [c for c in _list_dir_calls(client) if c["depth"] is None]
    assert len(recursive_calls) == 1
    assert recursive_calls[0]["path"] == INBOX_PATH


# ---------------------------------------------------------------------------
# Fail open (PRD business rule 10)
# ---------------------------------------------------------------------------

def test_kado_error_on_recursive_call_yields_empty_index(tmp_path):
    from lib.kado_client import KadoError

    mod = _load_module()
    client = _FakeClient(
        depth1_items=[_listdir_item(INBOX_PATH + "note.md")],
        recursive_error=KadoError("recursive listDir unavailable"),
    )

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    assert state.attachment_index == {}


def test_kado_error_on_recursive_call_does_not_abort_the_run(tmp_path):
    """The run continues past the failure — no exception escapes, and the
    depth=1 partition (which happens first) is completely unaffected."""
    from lib.kado_client import KadoError

    mod = _load_module()
    client = _FakeClient(
        depth1_items=[_listdir_item(INBOX_PATH + "note.md")],
        recursive_error=KadoError("recursive listDir unavailable"),
    )

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    # No exception escaped discover() (implicit — reaching this line proves
    # it), AND the run produced normal, non-degraded triage output.
    assert [f["path"] for f in state.md_files] == [INBOX_PATH + "note.md"]
    assert state.attachment_index == {}


# ---------------------------------------------------------------------------
# Index construction + persistence for downstream resolution
# ---------------------------------------------------------------------------

def test_index_is_built_from_the_recursive_listing(tmp_path):
    mod = _load_module()
    items = [
        _listdir_item(INBOX_PATH + "Places/Dresden.md"),
        _listdir_item(INBOX_PATH + "Images/karte.jpg"),
        _listdir_item(INBOX_PATH + "Scans/karte.jpg"),
        _listdir_item(INBOX_PATH + "Places", "folder"),
    ]
    client = _FakeClient(depth1_items=[], recursive_items=items)

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    assert state.attachment_index["Dresden.md"] == [INBOX_PATH + "Places/Dresden.md"]
    assert set(state.attachment_index["karte.jpg"]) == {
        INBOX_PATH + "Images/karte.jpg", INBOX_PATH + "Scans/karte.jpg",
    }
    # Folder entries never enter the index.
    assert "Places" not in state.attachment_index


def test_no_attachment_index_file_is_written(tmp_path):
    """Regression guard for the dropped artifact: the index is purely
    internal now (resolution consumes it within the same discover() call),
    so no <output_dir>/attachment-index.json should ever appear again."""
    mod = _load_module()
    items = [_listdir_item(INBOX_PATH + "Images/karte.jpg")]
    client = _FakeClient(depth1_items=[], recursive_items=items)

    mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    assert not (tmp_path / "attachment-index.json").exists()


# ---------------------------------------------------------------------------
# Pagination / scale (kado_client.py:597-617 assembles pages transparently;
# this proves OUR indexing code handles the fully-assembled result without
# dropping anything)
# ---------------------------------------------------------------------------

def test_large_subtree_is_fully_indexed(tmp_path):
    mod = _load_module()
    n = 600
    items = [_listdir_item(f"{INBOX_PATH}Images/photo-{i}.jpg") for i in range(n)]
    client = _FakeClient(depth1_items=[], recursive_items=items)

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    assert len(state.attachment_index) == n
    assert state.attachment_index["photo-0.jpg"] == [INBOX_PATH + "Images/photo-0.jpg"]
    assert state.attachment_index[f"photo-{n - 1}.jpg"] == [
        INBOX_PATH + f"Images/photo-{n - 1}.jpg"
    ]


# ---------------------------------------------------------------------------
# #93 partition regression guard — the existing depth=1 call is untouched
# ---------------------------------------------------------------------------

def test_93_partition_unchanged_by_the_new_recursive_call(tmp_path):
    """A .png at the inbox root is still not partitioned as an item (#93),
    even though the SAME recursive call now also sees it and indexes it as
    an attachment candidate — two independent concerns over the same file."""
    mod = _load_module()
    items = [
        _listdir_item(INBOX_PATH + "note.md"),
        _listdir_item(INBOX_PATH + "photo.png"),
    ]
    client = _FakeClient(depth1_items=items, recursive_items=items)

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    all_partitioned = {f["path"] for f in state.md_files} | {
        f["path"] for f in state.audio_files
    }
    assert INBOX_PATH + "photo.png" not in all_partitioned
    assert INBOX_PATH + "note.md" in {f["path"] for f in state.md_files}
    # The attachment index, meanwhile, DOES see the .png — the two mechanisms
    # are independent (index build must not feed back into partitioning).
    assert "photo.png" in state.attachment_index


# ---------------------------------------------------------------------------
# Extraction + resolution (ADR-2, corrected): one listNotes(fields=["links"])
# call per run, resolved against the SAME recursive index.
# ---------------------------------------------------------------------------

def _note_link(target: str, kind: str) -> dict:
    return {"target": target, "kind": kind}


def _note_entry(path: str, links: list[dict] | None = None) -> dict:
    entry = {"path": path}
    if links is not None:
        entry["links"] = links
    return entry


def _list_notes_calls(client) -> list[dict]:
    return [args for name, args in client.calls if name == "list_notes"]


def test_list_notes_requested_exactly_once_per_run(tmp_path):
    mod = _load_module()
    client = _FakeClient(depth1_items=[_listdir_item(INBOX_PATH + "note.md")])

    mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    calls = _list_notes_calls(client)
    assert len(calls) == 1, f"expected exactly 1 list_notes call, got {len(calls)}: {calls}"


def test_list_notes_count_independent_of_note_count(tmp_path):
    """CON-4 for the extraction call too: 1 note and 20 notes issue the same
    single list_notes call."""
    mod = _load_module()

    def _run(n_notes: int, out: Path) -> int:
        items = [_listdir_item(f"{INBOX_PATH}note-{i}.md") for i in range(n_notes)]
        client = _FakeClient(depth1_items=items)
        mod.discover(client, INBOX_PATH, output_dir=str(out))
        return len(_list_notes_calls(client))

    assert _run(1, tmp_path / "one") == 1
    assert _run(20, tmp_path / "twenty") == 1


def test_list_notes_requests_links_field_and_inbox_path(tmp_path):
    mod = _load_module()
    client = _FakeClient(depth1_items=[])

    mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    calls = _list_notes_calls(client)
    assert len(calls) == 1
    assert calls[0]["path"] == INBOX_PATH
    assert calls[0]["fields"] == ["links"]


# ---------------------------------------------------------------------------
# resolve_inbox_attachments — unit-level (no discover() plumbing needed)
# ---------------------------------------------------------------------------

def test_resolved_attachment_keyed_by_source_path(tmp_path):
    trip_path = INBOX_PATH + "trip.md"
    attachment_path = INBOX_PATH + "Images/karte.jpg"
    mod = _load_module()
    client = _FakeClient(
        notes=[_note_entry(trip_path, [_note_link("karte.jpg", "embed")])],
    )
    index = {"karte.jpg": [attachment_path]}

    result = mod.resolve_inbox_attachments(client, INBOX_PATH, index)

    assert result[trip_path]["attachments"] == [attachment_path]
    assert result[trip_path]["unresolved_embeds"] == []


def test_ambiguous_embed_reported_with_candidate_count(tmp_path, capsys):
    trip_path = INBOX_PATH + "trip.md"
    mod = _load_module()
    client = _FakeClient(
        notes=[_note_entry(trip_path, [_note_link("karte.jpg", "embed")])],
    )
    index = {"karte.jpg": [INBOX_PATH + "Images/karte.jpg", INBOX_PATH + "Scans/karte.jpg"]}

    result = mod.resolve_inbox_attachments(client, INBOX_PATH, index)

    assert result[trip_path]["attachments"] == []
    assert result[trip_path]["unresolved_embeds"] == [
        {"embed_target": "karte.jpg", "status": "ambiguous", "candidate_count": 2},
    ]
    err = capsys.readouterr().err
    assert "[triage]" in err
    assert trip_path in err
    assert "karte.jpg" in err
    assert "2 candidates" in err


def test_unresolved_embed_reported_without_candidate_count(tmp_path, capsys):
    trip_path = INBOX_PATH + "trip.md"
    mod = _load_module()
    client = _FakeClient(
        notes=[_note_entry(trip_path, [_note_link("karte.jpg", "embed")])],
    )

    result = mod.resolve_inbox_attachments(client, INBOX_PATH, index={})  # karte.jpg not indexed

    assert result[trip_path]["attachments"] == []
    assert result[trip_path]["unresolved_embeds"] == [
        {"embed_target": "karte.jpg", "status": "unresolved"},
    ]
    err = capsys.readouterr().err
    assert "[triage]" in err
    assert trip_path in err
    assert "karte.jpg" in err


def test_link_kind_is_never_treated_as_an_embed(tmp_path):
    """A plain [[karte.jpg]] LINK (kind=='link') must never contribute an
    attachment or an unresolved-embed entry — only ![[...]] (kind=='embed')
    is a dependency. The target deliberately names a real, resolvable file
    (not a bare note name) so the kind filter is the ONLY thing excluding
    it — a note-name target would already be excluded by
    _is_attachment_target regardless of kind, which would let this test
    pass even with the kind filter removed."""
    trip_path = INBOX_PATH + "trip.md"
    attachment_path = INBOX_PATH + "Images/karte.jpg"
    mod = _load_module()
    client = _FakeClient(
        notes=[_note_entry(trip_path, [_note_link("karte.jpg", "link")])],
    )
    index = {"karte.jpg": [attachment_path]}

    result = mod.resolve_inbox_attachments(client, INBOX_PATH, index)

    assert trip_path not in result  # no embed targets at all -> note absent


def test_note_embed_excluded_via_is_attachment_target(tmp_path):
    """![[Other Note.md]] is an embed, but a NOTE embed, not a file — must
    never appear in attachments or unresolved_embeds (Phase 1's
    _is_attachment_target boundary)."""
    trip_path = INBOX_PATH + "trip.md"
    mod = _load_module()
    client = _FakeClient(
        notes=[_note_entry(trip_path, [_note_link("Other Note.md", "embed")])],
    )
    index = {"Other Note.md": [INBOX_PATH + "Other Note.md"]}

    result = mod.resolve_inbox_attachments(client, INBOX_PATH, index)

    assert trip_path not in result


def test_note_with_no_links_gets_no_entry(tmp_path):
    trip_path = INBOX_PATH + "trip.md"
    mod = _load_module()
    client = _FakeClient(notes=[_note_entry(trip_path)])  # no "links" key at all

    result = mod.resolve_inbox_attachments(client, INBOX_PATH, index={})

    assert trip_path not in result


def test_note_embedding_the_same_attachment_twice_records_it_once(tmp_path):
    """PRD F1-AC4: a note embedding the same attachment twice records it
    once — mirrors attachment_index.extract_attachment_embeds' own `seen`
    dedup, which resolve_inbox_attachments must replicate since it replaced
    that function as the pipeline's embed source (ADR-2, corrected)."""
    trip_path = INBOX_PATH + "trip.md"
    attachment_path = INBOX_PATH + "Images/karte.jpg"
    mod = _load_module()
    client = _FakeClient(
        notes=[_note_entry(trip_path, [_note_link("karte.jpg", "embed"), _note_link("karte.jpg", "embed")])],
    )
    index = {"karte.jpg": [attachment_path]}

    result = mod.resolve_inbox_attachments(client, INBOX_PATH, index)

    assert result[trip_path]["attachments"] == [attachment_path]


def test_same_target_different_alias_or_anchor_collapses_to_one(tmp_path):
    """The near-miss a naive dedup-before-stripping would catch backwards:
    ![[karte.jpg|A]] and ![[karte.jpg#top]] are different RAW forms but
    strip to the same target — they must still collapse to one entry, so
    dedup has to happen on the post-strip target, not the raw string."""
    trip_path = INBOX_PATH + "trip.md"
    attachment_path = INBOX_PATH + "Images/karte.jpg"
    mod = _load_module()
    client = _FakeClient(
        notes=[_note_entry(trip_path, [_note_link("karte.jpg|A", "embed"), _note_link("karte.jpg#top", "embed")])],
    )
    index = {"karte.jpg": [attachment_path]}

    result = mod.resolve_inbox_attachments(client, INBOX_PATH, index)

    assert result[trip_path]["attachments"] == [attachment_path]


def test_list_notes_kado_error_fails_open(tmp_path):
    """A KadoError on list_notes yields {} rather than raising — every
    source's attachments/unresolved_embeds default to empty downstream, and
    the run continues (PRD business rule 10)."""
    from lib.kado_client import KadoError

    trip_path = INBOX_PATH + "trip.md"
    mod = _load_module()
    client = _FakeClient(
        depth1_items=[_listdir_item(trip_path)],
        recursive_items=[_listdir_item(trip_path), _listdir_item(INBOX_PATH + "Images/karte.jpg")],
        list_notes_error=KadoError("listNotes unavailable"),
    )

    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    assert [f["path"] for f in state.md_files] == [trip_path]  # run continued normally


def test_fully_resolving_run_emits_no_triage_lines(capsys):
    """A fully-resolving run emits no [triage] unresolved/ambiguous lines."""
    trip_path = INBOX_PATH + "trip.md"
    attachment_path = INBOX_PATH + "Images/karte.jpg"
    mod = _load_module()
    client = _FakeClient(
        notes=[_note_entry(trip_path, [_note_link("karte.jpg", "embed")])],
    )
    index = {"karte.jpg": [attachment_path]}

    mod.resolve_inbox_attachments(client, INBOX_PATH, index)

    err = capsys.readouterr().err
    assert "[triage]" not in err


# ---------------------------------------------------------------------------
# Persistence: resolved-attachments.json — the cross-process hand-off to the
# reducer (a separate, later process that never reads routing-plan.json)
# ---------------------------------------------------------------------------

def test_resolved_attachments_persisted_to_json(tmp_path):
    import json as _json

    trip_path = INBOX_PATH + "trip.md"
    attachment_path = INBOX_PATH + "Images/karte.jpg"
    mod = _load_module()
    client = _FakeClient(
        depth1_items=[_listdir_item(trip_path)],
        recursive_items=[_listdir_item(trip_path), _listdir_item(attachment_path)],
        notes=[_note_entry(trip_path, [_note_link("karte.jpg", "embed")])],
    )

    mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    on_disk = _json.loads((tmp_path / "resolved-attachments.json").read_text(encoding="utf-8"))
    assert on_disk[trip_path]["attachments"] == [attachment_path]
    assert on_disk[trip_path]["unresolved_embeds"] == []


def test_fresh_sources_do_not_carry_attachment_fields(tmp_path):
    """routing-plan.json's fresh_sources[] is the wrong join point (the
    reducer never reads it, and its membership tracks newness, not
    attachment presence) — confirm no attachment fields leak in there."""
    import json as _json

    trip_path = INBOX_PATH + "trip.md"
    mod = _load_module()
    client = _FakeClient(
        depth1_items=[_listdir_item(trip_path)],
        notes=[_note_entry(trip_path, [_note_link("karte.jpg", "embed")])],
    )

    rc = mod.main(
        ["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path)],
        client_factory=lambda: client,
    )
    assert rc == 0

    plan = _json.loads((tmp_path / "routing-plan.json").read_text(encoding="utf-8"))
    entry = next(s for s in plan["fresh_sources"] if s["path"] == trip_path)
    assert set(entry.keys()) == {"path", "modified"}


# ---------------------------------------------------------------------------
# T5.4 headline assertion: the constant-cost claim in its final form, all
# three attachment-related calls together (CON-4).
# ---------------------------------------------------------------------------

def test_constant_cost_claim_1_note_and_20_notes_issue_the_same_three_calls(tmp_path):
    """1 note and 20 notes issue the SAME number of attachment-related Kado
    calls: the depth=1 partition listDir, the recursive attachment-index
    listDir, and the listNotes(fields=["links"]) extraction call — three
    total, regardless of note count."""
    mod = _load_module()

    def _run(n_notes: int, out: Path) -> tuple[int, int, int]:
        items = [_listdir_item(f"{INBOX_PATH}note-{i}.md") for i in range(n_notes)]
        client = _FakeClient(depth1_items=items)
        mod.discover(client, INBOX_PATH, output_dir=str(out))
        list_dir_calls = len(_list_dir_calls(client))
        list_notes_calls = len(_list_notes_calls(client))
        return list_dir_calls, list_notes_calls, list_dir_calls + list_notes_calls

    one_note = _run(1, tmp_path / "one")
    twenty_notes = _run(20, tmp_path / "twenty")

    assert one_note == (2, 1, 3)
    assert twenty_notes == (2, 1, 3)
    assert one_note == twenty_notes
