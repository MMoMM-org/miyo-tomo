#!/usr/bin/env python3
"""test_039_t4_5_wire_plan_into_pass_2.py — spec 039 T4.5.

Pass 2 (`instruction-render.py` `main()`) runs on ONE vault folder lookup
(K2) and ONE basename census (K3): the attachment plan (K1) is built from
them once, before the first note is rendered, and `validate_destinations`
reads the note view of that same lookup — so a folder holding both an
attachment target and a note destination is listed once. The two counters
reach the run's cost-history entry when `--cost-history` is given (C1-AC1).

Every `main()` here is called the way the synthesis conductor calls it
(`tomo/dot_claude/agents/synthesis-conductor.md` step 3b): `--suggestions`,
`--output-dir`, `--config`, `--upstream-type`, `--upstream-path`,
`--upstream-body`, `--run-id`. `VaultFolderLookup` and `make_basename_census`
are the REAL ones over a counting fake Kado client — only the client, the
config loader and the template/body/token-render I/O are faked.

Mechanism each test falsifies:
- `test_the_plan_is_built_once_before_the_first_render`: building the plan
  inside the loop or at the `build_actions` call.
- `test_a_folder_shared_by_an_attachment_and_a_note_is_listed_once`:
  `validate_destinations` fed `make_folder_listing(client)` (a second,
  private lookup) instead of the shared lookup's `notes` view.
- `test_a_run_with_no_attachment_spends_no_census_and_no_extra_listing`:
  a census or an asset-folder listing paid for a run with no attachment.
- `test_a_bad_typed_folder_refuses_one_item_and_never_reaches_the_path_shape_guard`:
  a refused typed folder reaching the wire (then `_check_path_shape` aborts
  the whole run with exit 2).
- `test_the_cost_history_entry_carries_the_three_counters`: no entry, or an
  entry without the K2/K3 counters, or counters not read off the shared
  instances.
- `test_garden_audit_and_daily_only_runs_are_byte_identical_to_before`:
  T4.5 changing a run that files no note (fixture recorded at 0e8835a6,
  before T4.5 was implemented).
- `test_validate_destinations_lists_each_folder_once`: the per-folder map
  rebuilt per destination.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
FIXTURE_DIR = TESTS_DIR / "fixtures" / "039-t4-5-unaffected-runs"
sys.path.insert(0, str(SCRIPTS_DIR))

import lib.render_actions as render_actions  # noqa: E402
from lib.cost_history import build_entry  # noqa: E402
from lib.kado_client import KadoNotFoundError  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "instruction_render_t039_t4_5", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render_t039_t4_5"] = ir
_spec.loader.exec_module(ir)

INBOX = "100 Inbox/"
ASSET = "Atlas/290 Assets/295 Attachments"
NOTES = "Atlas/202 Notes"
RUN_ID = "2026-10-12-090000-t45"

_IR_CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSET + "/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
    "callouts.editable": ["NOTE"],
}


def _parent(path: str) -> str:
    return path.rstrip("/").rpartition("/")[0]


class CountingKado:
    """A Kado stand-in that logs every round trip.

    `list_dir` answers from `files` + `existing_folders` (anything else is
    Kado's `Path not found`); `_call_tool("kado-search", byName)` matches
    Kado's lower-cased substring rule over basenames, so the REAL census
    narrows it.
    """

    def __init__(self, files=(), existing_folders=()):
        self.files = list(files)
        self.existing = {f.rstrip("/") for f in existing_folders}
        self.call_count = 0
        self.log: list[list] = []
        self.listed: list[str] = []
        self.byname: list[str] = []

    def _folders(self) -> set[str]:
        found = set(self.existing)
        for path in self.files:
            parts = path.split("/")
            for i in range(1, len(parts)):
                found.add("/".join(parts[:i]))
        return found

    def _record(self, *entry) -> None:
        self.call_count += 1
        self.log.append(list(entry))

    def list_dir(self, folder, depth=1):
        self._record("list_dir", folder, depth)
        name = folder.rstrip("/")
        self.listed.append(name)
        if name not in self._folders():
            raise KadoNotFoundError(f"Path not found: {folder}")
        entries = [{"path": p, "type": "file"} for p in self.files if _parent(p) == name]
        entries += [
            {"path": f, "type": "folder"}
            for f in sorted(self._folders()) if f and _parent(f) == name
        ]
        return entries

    def _call_tool(self, tool, args):
        self._record("_call_tool", tool, args.get("operation"), args.get("query"))
        if tool == "kado-search" and args.get("operation") == "byName":
            self.byname.append(args["query"])
            query = args["query"]
            items = [
                {"path": p} for p in self.files
                if query in p.rsplit("/", 1)[-1].lower()
            ]
            return {"items": items}
        return {"items": []}

    def search_by_name(self, stem):
        self._record("search_by_name", stem)
        return []

    def read_note(self, path):
        self._record("read_note", path)
        return {"content": ""}

    def note_exists(self, path):
        self._record("note_exists", path)
        return True

    def resolve_stem_to_path(self, stem):
        self._record("resolve_stem_to_path", stem)
        return None


def _client_or_refuse(client):
    if client is None:
        raise AssertionError("this run must not construct a Kado client")
    return client


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 12, 9, 0, 0, tzinfo=tz or timezone.utc)


def _item(item_id, title, *, attachments=(), destination=NOTES + "/"):
    return {
        "id": item_id, "action": "create_note", "title": title,
        "template": "templates/atomic.md", "source_path": f"{title}.md",
        "item_key": f"{INBOX}{title}.md",
        "tags": [], "parent_moc": "", "parent_mocs": [],
        "destination": destination, "summary": "",
        "attachments": list(attachments), "candidate_mocs": [],
    }


def _typed(source, *, folder, name):
    return {
        "source": source, "remedy": "rename", "proposed_name": name,
        "name_is_owner_supplied": True,
        "proposed_dir": folder, "dir_is_owner_supplied": True,
    }


def _run_main(monkeypatch, tmp_path, suggestions, client, *,
              upstream_type="suggestions", cost_history=None, cfg=None,
              events=None):
    """Drive `main()` with the conductor's argument list (step 3b)."""
    suggestions_file = tmp_path / "parsed-suggestions.json"
    suggestions_file.write_text(json.dumps(suggestions), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")
    body_file = tmp_path / "upstream-body.md"
    body_file.write_text("# upstream\n", encoding="utf-8")

    monkeypatch.delenv("TOMO_VERSION", raising=False)
    monkeypatch.setattr(ir, "datetime", _FrozenDatetime)
    monkeypatch.setattr(ir, "load_config", lambda _path: dict(cfg or _IR_CFG))
    monkeypatch.setattr(ir, "load_tracker_fields", lambda _path: {})
    monkeypatch.setattr(ir, "KadoClient", lambda: _client_or_refuse(client))
    monkeypatch.setattr(ir, "read_template", lambda _c, _r: "# {{title}}\n{{body}}\n")
    monkeypatch.setattr(ir, "read_note_body", lambda *_a, **_kw: "")

    def _render(*_a, **_kw):
        if events is not None:
            events.append("render")
        return "Map: ![[karte.png]]\n"

    monkeypatch.setattr(ir, "render_via_script", _render)
    out_dir = tmp_path / "rendered"
    argv = [
        "instruction-render.py",
        "--suggestions", str(suggestions_file),
        "--output-dir", str(out_dir),
        "--config", str(cfg_file),
        "--upstream-type", upstream_type,
        "--upstream-path", "100 Inbox/2026-10-12_0900_suggestions.md",
        "--upstream-body", str(body_file),
        "--run-id", RUN_ID,
        "--tag-handler-groups-dir", str(tmp_path / "no-groups"),
        "--shared-ctx", str(tmp_path / "no-shared-ctx.json"),
    ]
    if cost_history is not None:
        argv += ["--cost-history", str(cost_history)]
    monkeypatch.setattr(sys, "argv", argv)
    rc = ir.main()
    return rc, out_dir


def _doc(out_dir: Path) -> dict:
    return json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))


def _moves(doc: dict, kind: str) -> list[dict]:
    return [a for a in doc["actions"] if a.get("action") == kind]


def _suggestions(items, remedies=(), daily_updates=()):
    return {
        "confirmed_items": list(items), "daily_updates": list(daily_updates),
        "skipped": [], "attachment_conflict_remedies": list(remedies),
    }


# ---------------------------------------------------------------------------
# (1) one plan, before the first render
# ---------------------------------------------------------------------------

def test_the_plan_is_built_once_before_the_first_render(monkeypatch, tmp_path):
    source = f"{INBOX}karte.png"
    client = CountingKado([source], existing_folders=[ASSET, NOTES])
    events: list[str] = []
    real_build = ir.build_attachment_plan

    def _spy(*args, **kwargs):
        events.append("plan")
        return real_build(*args, **kwargs)

    monkeypatch.setattr(ir, "build_attachment_plan", _spy)
    rc, _out = _run_main(
        monkeypatch, tmp_path,
        _suggestions([_item("S01", "Eins", attachments=[source]),
                      _item("S02", "Zwei", attachments=[source])]),
        client, events=events,
    )
    assert rc == 0
    assert events.count("plan") == 1, events
    assert events[0] == "plan", events
    assert events.count("render") == 2, events


# ---------------------------------------------------------------------------
# (2) one list_dir per folder across the asset and note guards
# ---------------------------------------------------------------------------

def test_a_folder_shared_by_an_attachment_and_a_note_is_listed_once(
    monkeypatch, tmp_path
):
    """The owner files the attachment into the note's own folder: the plan's
    occupancy check and the destination guard both read `Atlas/202 Notes`.
    Mutation: `validate_destinations(actions, make_folder_listing(client))`
    (v0.65.0) — that folder is listed twice."""
    source = f"{INBOX}karte.png"
    client = CountingKado([source], existing_folders=[ASSET, NOTES])
    rc, out_dir = _run_main(
        monkeypatch, tmp_path,
        _suggestions(
            [_item("S01", "Eins", attachments=[source])],
            [_typed(source, folder=NOTES, name="karte-neu.png")],
        ),
        client,
    )
    assert rc == 0
    doc = _doc(out_dir)
    assert [m["destination"] for m in _moves(doc, "move_asset")] == [
        f"{NOTES}/karte-neu.png"
    ]
    assert _moves(doc, "move_note"), doc["actions"]
    counts = Counter(client.listed)
    assert counts[NOTES] == 1, client.listed
    assert all(n == 1 for n in counts.values()), client.listed


# ---------------------------------------------------------------------------
# (3) no attachment → no census, no extra listing (F3-AC7)
# ---------------------------------------------------------------------------

def test_a_run_with_no_attachment_spends_no_census_and_no_extra_listing(
    monkeypatch, tmp_path
):
    client = CountingKado([], existing_folders=[ASSET, NOTES])
    history = tmp_path / "state" / "inbox-cost-history.jsonl"
    rc, _out = _run_main(
        monkeypatch, tmp_path,
        _suggestions([_item("S01", "Eins"), _item("S02", "Zwei")]),
        client, cost_history=history,
    )
    assert rc == 0
    assert client.byname == [], client.byname
    # Only the note guard's one listing of the notes' own folder — no asset
    # folder, no second listing of the note folder.
    assert client.listed == [NOTES], client.listed
    entry = json.loads(history.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["basename_searches"] == 0
    assert entry["basename_pages"] == 0
    assert entry["folder_listing_calls"] == 1


# ---------------------------------------------------------------------------
# (4) a bad typed folder refuses one item, the run goes on (F2-AC7)
# ---------------------------------------------------------------------------

def test_a_bad_typed_folder_refuses_one_item_and_never_reaches_the_path_shape_guard(
    monkeypatch, tmp_path
):
    bad, good = f"{INBOX}karte.png", f"{INBOX}foto.png"
    client = CountingKado([bad, good], existing_folders=[ASSET, NOTES])
    shaped: list[str] = []
    real_shape = render_actions._check_path_shape

    def _spy_shape(value):
        shaped.append(value)
        return real_shape(value)

    monkeypatch.setattr(render_actions, "_check_path_shape", _spy_shape)
    rc, out_dir = _run_main(
        monkeypatch, tmp_path,
        _suggestions(
            [_item("S01", "Eins", attachments=[bad]),
             _item("S02", "Zwei", attachments=[good])],
            [_typed(bad, folder="../Ausserhalb", name="karte.png")],
        ),
        client,
    )
    assert rc == 0
    doc = _doc(out_dir)
    assert [m["source"] for m in _moves(doc, "move_asset")] == [good]
    assert [m["title"] for m in _moves(doc, "move_note")] == ["Zwei"]
    refused = doc["tomo"]["skipped_assets"]
    assert [(s["source"], s["kind"]) for s in refused] == [
        (bad, "typed_folder_refused")
    ]
    assert shaped, "the path-shape guard must still run over the surviving actions"
    assert not [v for v in shaped if "Ausserhalb" in v], shaped


# ---------------------------------------------------------------------------
# (5) the cost-history entry (C1-AC1)
# ---------------------------------------------------------------------------

def test_the_cost_history_entry_carries_the_three_counters(monkeypatch, tmp_path):
    source = f"{INBOX}karte.png"
    client = CountingKado(
        [source, "Archive/karte.png"], existing_folders=[ASSET, NOTES]
    )
    history = tmp_path / "state" / "inbox-cost-history.jsonl"
    rc, _out = _run_main(
        monkeypatch, tmp_path,
        _suggestions([_item("S01", "Eins", attachments=[source])]),
        client, cost_history=history,
    )
    assert rc == 0
    lines = history.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, lines
    entry = json.loads(lines[0])
    reducer_shape = set(build_entry(
        run_id="r", action="suggest", item_count=0, base_kado_calls=0,
        total_kado_calls=0, folder_listing_calls=0,
        distinct_destination_folders=0,
    ))
    assert set(entry) == reducer_shape | {"basename_searches", "basename_pages"}
    assert entry["run_id"] == RUN_ID
    assert entry["action"] == "render"
    assert entry["item_count"] == 1
    assert entry["folder_listing_calls"] == len(client.listed) == 2
    assert entry["distinct_destination_folders"] == 2
    assert entry["basename_searches"] == len(client.byname) == 1
    assert entry["basename_pages"] == len(client.byname)
    assert entry["total_kado_calls"] == client.call_count
    assert entry["base_kado_calls"] == 0


def test_no_cost_history_entry_without_the_flag(monkeypatch, tmp_path):
    client = CountingKado([], existing_folders=[NOTES])
    monkeypatch.chdir(tmp_path)
    rc, _out = _run_main(
        monkeypatch, tmp_path, _suggestions([_item("S01", "Eins")]), client,
    )
    assert rc == 0
    assert not (tmp_path / "state").exists()


# ---------------------------------------------------------------------------
# (6) runs that file no note are unaffected
# ---------------------------------------------------------------------------

GARDEN_ITEMS = [
    {
        "id": "F01", "garden_check": "orphan", "garden_action": "file_note",
        "path": "Atlas/202 Notes/Waldweg.md", "stem": "Waldweg",
        "target_moc": "Rivers (MOC)", "target_moc_path": "Atlas/201 MOCs/Rivers (MOC).md",
    },
]

DAILY_UPDATES = [{
    "date": "2026-10-11",
    "daily_note_path": "Calendar/301 Daily/2026-10-11.md",
    "trackers": [{"field": "Sleep", "value": "23:00", "accepted": True}],
}]


# `updated_at` is stamped by the tomo-block builder from its own clock, not
# `main()`'s; it is the only field normalised, so nothing else can hide.
_UPDATED_AT = (
    (re.compile(r'"updated_at": "[^"]*"'), '"updated_at": "<NORMALISED>"'),
    (re.compile(r"updated_at: '[^']*'"), "updated_at: '<NORMALISED>'"),
)


def _outputs(out_dir: Path) -> dict:
    found = {}
    for name in ("instructions.json", "instructions.md", "manifest.json"):
        text = (out_dir / name).read_text(encoding="utf-8")
        for pattern, replacement in _UPDATED_AT:
            text = pattern.sub(replacement, text)
        found[name] = text
    return found


def unaffected_runs(monkeypatch, tmp_path) -> dict[str, dict]:
    """The outputs of a garden-audit run and a daily-only run (client None).

    Shared with the fixture recorder (`FIXTURE_DIR/record.py`), so the
    recording and the replay are one harness.
    """
    results: dict[str, dict] = {}
    garden_client = CountingKado([], existing_folders=[NOTES])
    garden_dir = tmp_path / "garden"
    garden_dir.mkdir()
    rc, out = _run_main(
        monkeypatch, garden_dir,
        {"confirmed_items": GARDEN_ITEMS, "daily_updates": [], "skipped": []},
        garden_client, upstream_type="garden-audit",
    )
    results["garden-audit"] = {"rc": rc, **_outputs(out), "kado_log": garden_client.log}

    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    rc, out = _run_main(
        monkeypatch, daily_dir,
        _suggestions([], daily_updates=DAILY_UPDATES), None,
    )
    results["daily-only"] = {"rc": rc, **_outputs(out), "kado_log": []}
    return results


def test_garden_audit_and_daily_only_runs_are_byte_identical_to_before(
    monkeypatch, tmp_path
):
    expected = json.loads(
        (FIXTURE_DIR / "expected.json").read_text(encoding="utf-8")
    )
    actual = json.loads(json.dumps(unaffected_runs(monkeypatch, tmp_path)))
    for run in ("garden-audit", "daily-only"):
        for key in ("rc", "instructions.json", "instructions.md",
                    "manifest.json", "kado_log"):
            assert actual[run][key] == expected[run][key], (run, key)


# ---------------------------------------------------------------------------
# (7) validate_destinations memoises the per-folder map
# ---------------------------------------------------------------------------

def test_validate_destinations_lists_each_folder_once():
    """Three moves into one folder, one into another: the folder view is asked
    once per folder. Mutation: calling `folder_listing(folder)` per
    destination (v0.28.1) — `Atlas/202 Notes` is asked three times."""
    asked: list[str] = []

    def _listing(folder):
        asked.append(folder)
        return {}

    actions = [
        {"id": f"A{i}", "action": "move_note", "title": t,
         "destination": f"{folder}/{t}.md", "source": f"{INBOX}{t}.md"}
        for i, (folder, t) in enumerate([
            (NOTES, "Eins"), (NOTES, "Zwei"), ("Atlas/203 Other", "Drei"),
            (NOTES, "Vier"),
        ])
    ]
    kept, clashes = render_actions.validate_destinations(actions, _listing)
    assert clashes == []
    assert len(kept) == 4
    assert sorted(asked) == sorted([NOTES, "Atlas/203 Other"]), asked


# ---------------------------------------------------------------------------
# (8) the entry on a run with no client, and on an aborted run
# ---------------------------------------------------------------------------

def test_a_daily_only_run_records_measured_zeros_without_a_client(
    monkeypatch, tmp_path
):
    """No client means no lookup and no census could have run: the entry
    carries measured zeros. Mutation: dropping the `if client` /
    `if folder_lookup` / `if census` guard on the matching counter in
    `main()` raises on `None`."""
    history = tmp_path / "state" / "inbox-cost-history.jsonl"
    rc, _out = _run_main(
        monkeypatch, tmp_path,
        _suggestions([], daily_updates=DAILY_UPDATES), None,
        cost_history=history,
    )
    assert rc == 0
    lines = history.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, lines
    entry = json.loads(lines[0])
    assert entry["action"] == "render"
    assert entry["item_count"] == 0
    for key in ("folder_listing_calls", "basename_searches", "basename_pages",
                "total_kado_calls"):
        assert entry[key] == 0, (key, entry)


def test_an_aborted_render_records_no_cost_entry(monkeypatch, tmp_path):
    """A destination with a `..` segment reaches `_validate_action_paths`,
    which aborts the run with exit 2 before any artefact is written.
    Mutation: appending the entry before the abort guards."""
    client = CountingKado([], existing_folders=[NOTES])
    history = tmp_path / "state" / "inbox-cost-history.jsonl"
    rc, out_dir = _run_main(
        monkeypatch, tmp_path,
        _suggestions([_item("S01", "Eins", destination="../Ausserhalb/")]),
        client, cost_history=history,
    )
    assert rc == 2
    assert not (out_dir / "instructions.md").exists()
    assert not history.exists()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
