#!/usr/bin/env python3
# version: 0.1.0
"""test_inbox_triage_review_skip.py — /inbox skips review documents (spec 045
T1.6, ADR-10; PRD F4-AC6, F5-AC4).

A `/review` document lives in the inbox with `tomo.doc_type: review` and the
states `pending-approval` → `approved`. Kado's byFrontmatter returns
`frontmatter: {}`, so inside those buckets the doc_type comes from the
filename: a stem ending in ` Review` is a review document. inbox-triage must
neither read nor apply it, warn about it, nor count it as a new source, and
the run's call counters must be the same as without it. The periodic note
`/review` writes while its instruction set waits (`rendered-note`,
`pending-move`) must not surface as a new source either.

Mock-at-the-orchestrator: a recording fake Kado client drives `discover()`
and `main()`; no live Kado, no container, no vault.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

INBOX_PATH = "100 Inbox/"
WEEK_REVIEW = INBOX_PATH + "2026-W13 Review.md"
MONTH_REVIEW = INBOX_PATH + "2026-03 Review.md"
BOOK_REVIEW = INBOX_PATH + "Book Review.md"
RENAMED_REVIEW = INBOX_PATH + "Week 13 thoughts.md"
PERIODIC_NOTE = INBOX_PATH + "2026-W13.md"
FRESH_NOTE = INBOX_PATH + "brand-new.md"

ALL_QUERIES = (
    "tomo.state=pending-approval",
    "tomo.state=pending-accept",
    "tomo.state=captured",
    "tomo.doc_type=instructions",
    "tomo.state=approved",
    "tomo.state=accepted",
    "tomo.state=pending-move",
)


def _load_module():
    script_path = SCRIPTS_DIR / "inbox-triage.py"
    spec = importlib.util.spec_from_file_location("inbox_triage", script_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage"] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeKadoClient:
    """Recording fake: pre-configured responses, every call appended to .calls."""

    def __init__(
        self,
        *,
        listdir_items: list[dict] | None = None,
        frontmatter_responses: dict[str, list[dict]] | None = None,
        read_note_responses: dict[str, dict] | None = None,
    ):
        self._listdir_items = listdir_items or []
        self._frontmatter_responses = frontmatter_responses or {}
        self._read_note_responses = read_note_responses or {}
        self.calls: list[tuple[str, dict]] = []

    def list_dir(self, path: str, *, depth: int = None, limit: int = 500) -> list:
        self.calls.append(("list_dir", {"path": path, "depth": depth}))
        return self._listdir_items

    def list_notes(
        self, path: str, *, fields: list[str] | None = None,
        depth: int | None = None, limit: int = 500,
    ) -> list[dict]:
        self.calls.append(("list_notes", {"path": path, "fields": fields}))
        return []

    def search_by_frontmatter(
        self, query: str, *, path_prefix: str | None = None, limit: int = 500,
        modified_after: int | None = None,
    ) -> list[dict]:
        self.calls.append(
            ("search_by_frontmatter", {"query": query, "path_prefix": path_prefix})
        )
        return self._frontmatter_responses.get(query, [])

    def read_note(self, path: str) -> dict:
        self.calls.append(("read_note", {"path": path}))
        return self._read_note_responses.get(path, {"content": "", "modified": 0})

    def read_frontmatter(self, path: str) -> dict:
        self.calls.append(("read_frontmatter", {"path": path}))
        return {"content": {}}

    def read_file_bytes(self, path: str) -> bytes:
        self.calls.append(("read_file_bytes", {"path": path}))
        from lib.kado_client import KadoNotFoundError

        raise KadoNotFoundError(f"not found: {path}")


def _listdir_item(path: str) -> dict:
    return {"path": path, "type": "file", "modified": 1716300000000, "size": 100}


def _bucket_hit(path: str) -> dict:
    """A byFrontmatter hit as Kado really returns it: frontmatter is empty."""
    return {"path": path, "modified": 1716300000000, "frontmatter": {}}


def _stamped_hit(path: str, doc_type: str, state: str) -> dict:
    """A hit carrying the full tomo block (what the review document holds)."""
    return {
        "path": path,
        "modified": 1716300000000,
        "frontmatter": {
            "tomo": {
                "doc_type": doc_type,
                "state": state,
                "run_id": "review-run",
                "updated_at": "2026-03-30T08:00:00Z",
            },
            "period": "2026-W13",
            "kind": "weekly",
        },
    }


def _buckets(**overrides: list[dict]) -> dict[str, list[dict]]:
    responses = {q: [] for q in ALL_QUERIES}
    for key, hits in overrides.items():
        query = {
            "pending_approval": "tomo.state=pending-approval",
            "pending_accept": "tomo.state=pending-accept",
            "approved": "tomo.state=approved",
            "pending_move": "tomo.state=pending-move",
        }[key]
        responses[query] = hits
    return responses


def _read_paths(client: FakeKadoClient) -> list[str]:
    return [args["path"] for name, args in client.calls if name == "read_note"]


def _discover(mod, client, tmp_path, **kwargs):
    empty_registry = tmp_path / "tag-handlers"
    empty_registry.mkdir(parents=True, exist_ok=True)
    return mod.discover(
        client, INBOX_PATH, output_dir=str(tmp_path / "out"),
        registry_dir=str(empty_registry), **kwargs,
    )


def _assert_review_untouched(state, client, err: str, review_path: str) -> None:
    assert review_path not in _read_paths(client), "review document was read"
    assert review_path not in {s["path"] for s in state.new_sources}, (
        "review document surfaced as a new source"
    )
    assert state.pending_approval == [], "review document awaits approval"
    assert state.approved_suggestions == []
    assert state.approved_fan == []
    assert state.approved_moc_proposals == []
    assert state.approved_garden_audits == []
    assert state.drift_indicators == []
    assert review_path.rsplit("/", 1)[-1] not in state.manifest, (
        "review document was cached"
    )
    assert "WARNING" not in err, err


# ---------------------------------------------------------------------------
# _get_doc_type filename rule
# ---------------------------------------------------------------------------

class TestGetDocTypeReviewRule:
    def test_week_review_stem_maps_to_review(self):
        mod = _load_module()
        assert mod._get_doc_type(_bucket_hit(WEEK_REVIEW)) == "review"

    def test_month_review_stem_maps_to_review(self):
        mod = _load_module()
        assert mod._get_doc_type(_bucket_hit(MONTH_REVIEW)) == "review"

    def test_frontmatter_doc_type_still_wins(self):
        mod = _load_module()
        hit = _stamped_hit(WEEK_REVIEW, "review", "pending-approval")
        assert mod._get_doc_type(hit) == "review"

    def test_renamed_review_stem_has_no_doc_type(self):
        mod = _load_module()
        assert mod._get_doc_type(_bucket_hit(RENAMED_REVIEW)) == ""

    @pytest.mark.parametrize("stem", ["2026-W13_Review", "2026-W13Review", "Reviewed"])
    def test_only_the_space_suffix_counts(self, stem):
        mod = _load_module()
        assert mod._get_doc_type(_bucket_hit(INBOX_PATH + stem + ".md")) != "review"


# ---------------------------------------------------------------------------
# pending-approval and approved buckets: neither read, applied nor warned
# ---------------------------------------------------------------------------

class TestReviewDocumentIsSkipped:
    def test_pending_approval_review_is_skipped_silently(self, tmp_path, capsys):
        mod = _load_module()
        client = FakeKadoClient(
            listdir_items=[_listdir_item(WEEK_REVIEW)],
            frontmatter_responses=_buckets(pending_approval=[_bucket_hit(WEEK_REVIEW)]),
            read_note_responses={
                WEEK_REVIEW: {"content": "# 2026-W13 Review\n\n- [x] Approved\n"},
            },
        )
        state = _discover(mod, client, tmp_path)
        err = capsys.readouterr().err
        _assert_review_untouched(state, client, err, WEEK_REVIEW)

    def test_pending_approval_review_with_full_frontmatter_is_skipped(
        self, tmp_path, capsys,
    ):
        mod = _load_module()
        client = FakeKadoClient(
            listdir_items=[_listdir_item(WEEK_REVIEW)],
            frontmatter_responses=_buckets(
                pending_approval=[_stamped_hit(WEEK_REVIEW, "review", "pending-approval")],
            ),
        )
        state = _discover(mod, client, tmp_path)
        err = capsys.readouterr().err
        _assert_review_untouched(state, client, err, WEEK_REVIEW)

    @pytest.mark.parametrize("force_pass2", [False, True])
    def test_approved_review_is_skipped_silently(self, tmp_path, capsys, force_pass2):
        mod = _load_module()
        client = FakeKadoClient(
            listdir_items=[_listdir_item(MONTH_REVIEW)],
            frontmatter_responses=_buckets(approved=[_bucket_hit(MONTH_REVIEW)]),
            read_note_responses={
                MONTH_REVIEW: {"content": "# 2026-03 Review\n\n- [x] Approved\n"},
            },
        )
        state = _discover(mod, client, tmp_path, force_pass2=force_pass2)
        err = capsys.readouterr().err
        _assert_review_untouched(state, client, err, MONTH_REVIEW)

    def test_review_document_does_not_change_the_action(self, tmp_path):
        """With only a pending review document in the inbox, the plan idles."""
        mod = _load_module()
        client = FakeKadoClient(
            listdir_items=[_listdir_item(WEEK_REVIEW)],
            frontmatter_responses=_buckets(pending_approval=[_bucket_hit(WEEK_REVIEW)]),
        )
        empty_registry = tmp_path / "tag-handlers"
        empty_registry.mkdir()
        rc = mod.main(
            ["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path / "out"),
             "--cost-history", str(tmp_path / "cost-history.jsonl"),
             "--registry-dir", str(empty_registry)],
            client_factory=lambda: client,
        )
        assert rc == 0
        plan = json.loads((tmp_path / "out" / "routing-plan.json").read_text("utf-8"))
        assert plan["action"] == "idle"
        assert plan["fresh_sources"] == []
        assert plan["pending_approval"] == []


# ---------------------------------------------------------------------------
# What must NOT be caught by the rule
# ---------------------------------------------------------------------------

class TestRuleBoundaries:
    def test_user_book_review_without_tomo_block_is_a_new_item(self, tmp_path, capsys):
        mod = _load_module()
        client = FakeKadoClient(
            listdir_items=[_listdir_item(BOOK_REVIEW)],
            frontmatter_responses=_buckets(),
        )
        state = _discover(mod, client, tmp_path)
        err = capsys.readouterr().err
        assert {s["path"] for s in state.new_sources} == {BOOK_REVIEW}
        assert "WARNING" not in err, err

    def test_renamed_stamped_review_gives_unknown_doc_type_warning_only(
        self, tmp_path, capsys,
    ):
        mod = _load_module()
        client = FakeKadoClient(
            listdir_items=[_listdir_item(RENAMED_REVIEW)],
            frontmatter_responses=_buckets(pending_approval=[_bucket_hit(RENAMED_REVIEW)]),
        )
        state = _discover(mod, client, tmp_path)
        err = capsys.readouterr().err
        warnings = [line for line in err.splitlines() if "WARNING" in line]
        assert warnings == [
            f"[inbox-triage] WARNING: unknown doc_type for {RENAMED_REVIEW}",
        ]
        assert RENAMED_REVIEW not in _read_paths(client)
        assert state.pending_approval == []
        assert RENAMED_REVIEW not in {s["path"] for s in state.new_sources}

    def test_periodic_note_pending_move_is_not_a_new_source(self, tmp_path, capsys):
        """The note /review wrote while its instruction set waits (F5-AC4)."""
        mod = _load_module()
        client = FakeKadoClient(
            listdir_items=[_listdir_item(PERIODIC_NOTE), _listdir_item(FRESH_NOTE)],
            frontmatter_responses=_buckets(
                pending_move=[_stamped_hit(PERIODIC_NOTE, "rendered-note", "pending-move")],
            ),
        )
        state = _discover(mod, client, tmp_path)
        err = capsys.readouterr().err
        paths = {s["path"] for s in state.new_sources}
        assert PERIODIC_NOTE not in paths
        assert FRESH_NOTE in paths
        assert PERIODIC_NOTE not in _read_paths(client)
        assert "WARNING" not in err, err


# ---------------------------------------------------------------------------
# Call counters: a review document costs nothing
# ---------------------------------------------------------------------------

class TestCallCountersUnchanged:
    def _run(self, mod, tmp_path, *, with_review: bool):
        pending = [_bucket_hit(WEEK_REVIEW)] if with_review else []
        approved = [_bucket_hit(MONTH_REVIEW)] if with_review else []
        items = [_listdir_item(FRESH_NOTE)]
        if with_review:
            items += [_listdir_item(WEEK_REVIEW), _listdir_item(MONTH_REVIEW)]
        client = FakeKadoClient(
            listdir_items=items,
            frontmatter_responses=_buckets(pending_approval=pending, approved=approved),
        )
        state = _discover(
            mod, client, tmp_path / ("with" if with_review else "without"),
            force_pass2=True,
        )
        return client, state

    def test_discover_counters_match_a_run_without_the_review_documents(self, tmp_path):
        mod = _load_module()
        base_client, base_state = self._run(mod, tmp_path, with_review=False)
        client, state = self._run(mod, tmp_path, with_review=True)

        assert [name for name, _ in client.calls] == [name for name, _ in base_client.calls]
        assert state.wire_sibling_reads == base_state.wire_sibling_reads
        assert state.tag_handler_reads == base_state.tag_handler_reads
        assert state.base_kado_calls == base_state.base_kado_calls
        assert state.frontmatter_kado_calls == base_state.frontmatter_kado_calls
        assert {s["path"] for s in state.new_sources} == {FRESH_NOTE}
