#!/usr/bin/env python3
"""pass2_harness.py: the shared Pass-2 test harness.

Loads `instruction-render.py` as a module and drives its `main()` with the
conductor's argument list over a Kado stand-in that logs every round trip
(`CountingKado`), plus the two parser-output comparison folds the
paths-converge tests share. Lives in tests/ (never a production path, and
tomo/ is synced into the instance); not named `test_*`, so pytest does not
collect it. Spec 039 T4.5, T4.6, T6.3.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

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


def _suggestions(items, remedies=(), daily_updates=()):
    return {
        "confirmed_items": list(items), "daily_updates": list(daily_updates),
        "skipped": [], "attachment_conflict_remedies": list(remedies),
    }



def strip_provenance(parsed: dict) -> dict:
    """`parsed` with both provenance flags dropped from every remedy, and a
    `proposed_dir` that is NOT owner-supplied read as `None`.

    The folder half mirrors the one equality rule both paths converge on
    downstream (spec 039 SDD, Pass 2 wire path step 2): a folder that is not
    owner-supplied resolves to the configured asset folder, whatever text it
    carries. The markdown path reports the rendered folder verbatim there and
    the wire path reports `null`; both mean the same folder."""
    out = dict(parsed)
    out["attachment_conflict_remedies"] = [
        {
            **{
                k: v for k, v in r.items()
                if k not in ("name_is_owner_supplied", "dir_is_owner_supplied")
            },
            "proposed_dir": r["proposed_dir"] if r["dir_is_owner_supplied"] else None,
        }
        for r in parsed["attachment_conflict_remedies"]
    ]
    return out


def strip_provenance_and_default_folder(parsed: dict) -> dict:
    """`strip_provenance`, plus K1's equality rule: an owner-supplied folder
    spelled exactly as the asset folder is the default (`None`)."""
    out = strip_provenance(parsed)
    out["attachment_conflict_remedies"] = [
        {**r, "proposed_dir": None if r["proposed_dir"] == ASSET else r["proposed_dir"]}
        for r in out["attachment_conflict_remedies"]
    ]
    return out
