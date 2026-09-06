#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t2_3_reducer_reads_by_key.py — the reducer joins on item_key, renders stem.

Covers T2.3 (XDD 034 Phase 2). Three defects live in `suggestions-reducer.py`
today, and this file pins all three:

  1. The per-item result file is looked up as `items_dir / f"{stem}.result.json"`
     while T2.2 moved the analyst to write under `lib.item_key.to_filename`. The
     reducer therefore reads nothing at all on a live run.
  2. A missing result file is skipped with a bare `continue` — no stderr line, no
     entry in the document. An item vanishes from the run and nothing says so.
  3. `last_state_per_stem` replays `inbox-state.jsonl` into `out[stem]`, so two
     items sharing a filename collapse onto one status (ADR-2). The replacement
     is one shared helper in `lib/`, keyed on `item_key`.

`stem` stays display-only (ADR-2): the guard below asserts no rendered title and
no wikilink in the emitted document carries a path-derived value.

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
REDUCER_PATH = SCRIPTS_DIR / "suggestions-reducer.py"

sys.path.insert(0, str(SCRIPTS_DIR))
from lib.item_key import to_filename  # noqa: E402

_DEPS = "/tmp/claude/py_deps"
_extra = ":".join(p for p in [_DEPS, str(SCRIPTS_DIR)] if os.path.isdir(p))
_ENV = {
    **os.environ,
    "PYTHONPATH": _extra + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
}

RUN_ID = "test-t2-3"
# Every fixture item lives under this prefix, so any path-derived value that
# leaks into a rendered title or link is detectable by substring alone.
INBOX_PREFIX = "100 Inbox/"


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _write_shared_ctx(path: Path) -> None:
    path.write_text(json.dumps({
        "schema_version": "1",
        "run_id": RUN_ID,
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
    }), encoding="utf-8")


def _state_line(*, stem: str, item_key: str, status: str = "done", error: dict | None = None) -> str:
    entry: dict = {
        "run_id": RUN_ID,
        "stem": stem,
        "item_key": item_key,
        "path": item_key,
        "status": status,
        "attempts": 1,
    }
    if error is not None:
        entry["error"] = error
    return json.dumps(entry)


def _write_state(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_result(
    items_dir: Path,
    *,
    item_key: str,
    stem: str,
    suggested_title: str | None,
    with_daily: bool = False,
) -> Path:
    """Write a per-item analyst result under the item_key-derived filename.

    `suggested_title=None` deliberately omits the field so the reducer falls
    back to `stem` — that fallback is the display site most likely to leak a
    path-derived value into the vault.
    """
    items_dir.mkdir(parents=True, exist_ok=True)
    atomic: dict = {
        "kind": "create_atomic_note",
        "atomic_note_worthiness": 0.8,
        "template": "t_note_tomo",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "needs_new_moc": False,
        "tags_to_add": [],
        "classification": {"category": "100 Philosophy", "confidence": 0.9},
        "alternatives": [],
    }
    if suggested_title is not None:
        atomic["suggested_title"] = suggested_title
    actions: list[dict] = [atomic]
    if with_daily:
        actions.append({
            "kind": "update_daily",
            "date": "2026-06-11",
            "daily_note_path": "Daily/2026-06-11.md",
            "updates": [{
                "kind": "log_entry",
                "time": "09:00",
                "time_source": "frontmatter",
                "position": "append",
                "content": "did a thing",
                "confidence": 0.8,
                "reason": "noted",
            }],
        })
    result_path = items_dir / to_filename(item_key)
    result_path.write_text(json.dumps({
        "schema_version": "1",
        "stem": stem,
        "item_key": item_key,
        "path": item_key,
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "actions": actions,
    }), encoding="utf-8")
    return result_path


def _run_reducer(tmp_path: Path, state_lines: list[str]) -> tuple[dict, str]:
    """Run the reducer over a prepared tmp workspace; return (doc, stderr)."""
    items_dir = tmp_path / "items"
    items_dir.mkdir(exist_ok=True)
    shared_ctx = tmp_path / "shared-ctx.json"
    state = tmp_path / "state.jsonl"
    output = tmp_path / "doc.json"
    _write_shared_ctx(shared_ctx)
    _write_state(state, state_lines)

    proc = subprocess.run(
        [
            sys.executable, str(REDUCER_PATH),
            "--state", str(state),
            "--items-dir", str(items_dir),
            "--run-id", RUN_ID,
            "--profile", "miyo",
            "--shared-ctx", str(shared_ctx),
            "--output", str(output),
            "--no-kado",
        ],
        capture_output=True, text=True, check=False, env=_ENV,
    )
    assert proc.returncode == 0, f"reducer exit {proc.returncode}\nstderr:\n{proc.stderr}"
    return json.loads(output.read_text(encoding="utf-8")), proc.stderr


# ── Display-site harvesting ──────────────────────────────────────────────────

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


def _rendered_markdown(doc: dict) -> list[str]:
    """Every markdown blob the document carries, wherever it is nested."""
    out: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and (key.endswith("_md") or key == "rendered_md"):
                    out.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(doc)
    return out


def _wikilinks(doc: dict) -> list[str]:
    return [m for blob in _rendered_markdown(doc) for m in _WIKILINK.findall(blob)]


def _rendered_titles(doc: dict) -> list[str]:
    """Titles the document presents to the user, from every site that emits one."""
    titles: list[str] = []
    for section in doc.get("sections", []):
        for action in section.get("actions", []):
            item = action.get("item") or {}
            if isinstance(item.get("title"), str):
                titles.append(item["title"])
    for moc in doc.get("proposed_mocs", []):
        if isinstance(moc.get("name"), str):
            titles.append(moc["name"])
        titles.extend(t for t in (moc.get("note_titles") or []) if isinstance(t, str))
    # `**Suggested name:** <title>` is the markdown projection of the same value.
    for blob in _rendered_markdown(doc):
        titles.extend(re.findall(r"\*\*Suggested name:\*\* (.+)", blob))
    return titles


# ── T2.3 RED tests ───────────────────────────────────────────────────────────


def test_reducer_finds_result_written_under_the_item_key_filename(tmp_path):
    """The read side must use the same encoding the analyst writes with (T2.2)."""
    item_key = f"{INBOX_PREFIX}Places/Dresden.md"
    _write_result(
        tmp_path / "items", item_key=item_key, stem="Dresden",
        suggested_title="Dresden Altstadt",
    )
    doc, _ = _run_reducer(tmp_path, [_state_line(stem="Dresden", item_key=item_key)])

    assert len(doc["sections"]) == 1, (
        "reducer produced no section — it did not find the result file written "
        f"as {to_filename(item_key)}"
    )
    assert doc["sections"][0]["stem"] == "Dresden"
    assert doc["sections"][0]["item_key"] == item_key


def test_missing_result_file_is_reported_not_skipped(tmp_path):
    """A `done` item with no result file must be named, not silently dropped.

    Asserting merely that the run survives would pass against the silent-skip
    bug this test exists to close, so both assertions name the item.
    """
    item_key = f"{INBOX_PREFIX}Places/Dresden.md"
    doc, stderr = _run_reducer(tmp_path, [_state_line(stem="Dresden", item_key=item_key)])

    assert item_key in stderr, (
        f"reducer said nothing about the vanished item on stderr:\n{stderr}"
    )
    reported = [
        entry for entry in doc.get("needs_attention", [])
        if entry.get("item_key") == item_key
    ]
    assert reported, (
        "the missing result file left no trace in the document's needs_attention "
        f"block: {doc.get('needs_attention')}"
    )
    assert reported[0]["stem"] == "Dresden"
    assert "result" in reported[0]["error"].lower()


def test_two_items_sharing_a_filename_read_their_own_result_file(tmp_path):
    """The collision this spec exists for: same stem, different folders."""
    key_places = f"{INBOX_PREFIX}Places/Dresden.md"
    key_reise = f"{INBOX_PREFIX}Reise/Dresden.md"
    items_dir = tmp_path / "items"
    _write_result(
        items_dir, item_key=key_places, stem="Dresden",
        suggested_title="Dresden Altstadt",
    )
    _write_result(
        items_dir, item_key=key_reise, stem="Dresden",
        suggested_title="Dresden Reisebericht",
    )
    doc, _ = _run_reducer(tmp_path, [
        _state_line(stem="Dresden", item_key=key_places),
        _state_line(stem="Dresden", item_key=key_reise),
    ])

    assert len(doc["sections"]) == 2, (
        f"expected one section per item, got {len(doc['sections'])} — the two "
        "namesakes collapsed onto one result file or one state entry"
    )
    assert {s["item_key"] for s in doc["sections"]} == {key_places, key_reise}
    assert {s["stem"] for s in doc["sections"]} == {"Dresden"}, (
        "stem must stay the bare filename for both (ADR-2)"
    )
    titles = _rendered_titles(doc)
    assert "Dresden Altstadt" in titles
    assert "Dresden Reisebericht" in titles


def test_no_rendered_title_or_link_carries_a_path_derived_key(tmp_path):
    """The hazard that reaches the vault: a path in a title or a `[[link]]`.

    Scoped to rendered titles and wikilinks specifically, and asserted as a
    property of the whole document rather than per known site — a leak at a
    site nobody enumerated is caught just the same.

    Two sites in the reducer emit a wikilink that legitimately contains `/`:
    `_location_link` (`[[Atlas/202 Notes/]]`, a folder) and the tag-handler
    group's source-path links. Neither is an item link, and neither is
    exercised by this fixture, so the guard stays unweakened here.
    """
    key_places = f"{INBOX_PREFIX}Places/Dresden.md"
    key_reise = f"{INBOX_PREFIX}Reise/Dresden.md"
    items_dir = tmp_path / "items"
    # One item omits suggested_title so the `or stem` title fallback fires —
    # that is the display site a path-derived value would surface through.
    _write_result(
        items_dir, item_key=key_places, stem="Dresden",
        suggested_title=None, with_daily=True,
    )
    _write_result(
        items_dir, item_key=key_reise, stem="Dresden",
        suggested_title="Dresden Reisebericht", with_daily=True,
    )
    doc, _ = _run_reducer(tmp_path, [
        _state_line(stem="Dresden", item_key=key_places),
        _state_line(stem="Dresden", item_key=key_reise),
    ])

    links = _wikilinks(doc)
    assert links, "fixture rendered no wikilinks — the guard would be vacuous"
    for link in links:
        assert ".md" not in link, f"wikilink carries a filename extension: [[{link}]]"
        assert INBOX_PREFIX not in link, f"wikilink carries a path-derived key: [[{link}]]"

    titles = _rendered_titles(doc)
    assert titles, "fixture rendered no titles — the guard would be vacuous"
    for title in titles:
        assert ".md" not in title, f"rendered title carries a filename extension: {title!r}"
        assert INBOX_PREFIX not in title, f"rendered title carries a path-derived key: {title!r}"

    # The title fallback specifically must have produced the bare filename.
    assert "Dresden" in titles


def test_state_replay_keys_on_item_key_not_stem(tmp_path):
    """One shared helper in lib/, replacing the two divergent copies.

    `suggestions-reducer.py` and `mark-captured.py` each carried their own
    `last_state_per_stem`; two copies of one identity computation is how #165
    happened. T2.5 consumes this helper too.
    """
    from lib.inbox_state import last_state_per_item_key

    key_places = f"{INBOX_PREFIX}Places/Dresden.md"
    key_reise = f"{INBOX_PREFIX}Reise/Dresden.md"
    state = tmp_path / "state.jsonl"
    _write_state(state, [
        _state_line(stem="Dresden", item_key=key_places, status="running"),
        _state_line(stem="Dresden", item_key=key_reise, status="failed",
                    error={"kind": "timeout", "message": "took too long"}),
        _state_line(stem="Dresden", item_key=key_places, status="done"),
    ])

    replayed = last_state_per_item_key(state)

    assert set(replayed) == {key_places, key_reise}, (
        "two entries sharing a stem collapsed onto one key"
    )
    assert replayed[key_places]["status"] == "done", "last write per key must win"
    assert replayed[key_reise]["status"] == "failed", (
        "the namesake's status was masked by the other item's"
    )
    assert replayed[key_reise]["error"]["kind"] == "timeout"


def test_state_replay_tolerates_a_missing_or_malformed_log(tmp_path):
    """The reducer's copy failed open on both; the shared helper must too."""
    from lib.inbox_state import last_state_per_item_key

    assert last_state_per_item_key(tmp_path / "absent.jsonl") == {}

    key = f"{INBOX_PREFIX}Places/Dresden.md"
    state = tmp_path / "state.jsonl"
    state.write_text(
        "\n".join(["", "{not json", _state_line(stem="Dresden", item_key=key), ""]),
        encoding="utf-8",
    )
    assert set(last_state_per_item_key(state)) == {key}
