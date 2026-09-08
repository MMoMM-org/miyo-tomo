#!/usr/bin/env python3
# version: 0.2.0
"""test_034_t6_1_cost_history.py — XDD 034 T6.1: the run records its own cost.

F9's claim is that recursion made discovery cheaper (3 base calls → 2), and
this task writes that figure into a permanent history. A history whose source
is a constant records the intent, not the behaviour: `_count_kado_calls` used
to return ``2 + 7 + …``, and both literals would keep reporting the same number
through any change that reintroduced a listing or a byFrontmatter query.

Four things are pinned here, in the order they bite:

  1. **The counts are observed, not declared.** Every assertion below drives a
     client that charges a *configurable* number of round trips per request, so
     a literal `2` or `7` in the estimator cannot pass — the expected value
     moves with the client, not with the formula.
  2. **The folder counts cross a process boundary.** They are produced by
     `suggestions-reducer.py` and read by a later process; a number computed and
     never wired raises no error and fails no unit test.
  3. **All five actions record, and no SKILL.md step is involved.** `suggest`
     and `fan-resolve` record inside `suggestions-reducer.py` — the process that
     already runs on both paths and already holds the folder counts; `idle`,
     `synthesize` and `transcribe` record in triage itself. The first cut put the
     two reducer paths behind a line in a SKILL.md, which no test can see: the
     criterion is "accumulates **without anyone remembering**", and that cannot
     live in a step someone has to remember.
  4. **Exactly one entry per run.** The triage-side guard is the one trap here
     that fails loudly rather than silently: without it a `suggest` run writes an
     incomplete entry from triage *and* the real one downstream.

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

INBOX_PATH = "100 Inbox/"
HISTORY_REL = Path("state") / "inbox-cost-history.jsonl"

# The seven fields the SDD's cost_history schema names, in its own order.
SDD_FIELDS = (
    "timestamp", "run_id", "item_count", "base_kado_calls", "total_kado_calls",
    "folder_listing_calls", "distinct_destination_folders",
)
BASE_FIELDS = SDD_FIELDS[:5]
FOLDER_FIELDS = SDD_FIELDS[5:]

# A named destination folder, so the folder-count assertions name a location
# rather than asserting "some positive number".
NOTES = "Atlas/202 Notes"
PEOPLE = "Atlas/203 People"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_triage():
    return _load("inbox_triage_t61", "inbox-triage.py")


def _read_history(root: Path) -> list[dict]:
    path = root / HISTORY_REL
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

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
    mark = "[x]" if approved else "[ ]"
    lines = [
        "---", "type: tomo-suggestions", "---", "",
        "# Inbox Suggestions", "", f"- {mark} Approved", "",
        "## Suggestions", "",
    ]
    for i, stem in enumerate(fan_items or [], start=1):
        lines += [
            f"### S{i:02d} — {stem} reflections", "",
            f"**Source:** [[{stem}]]", "",
            "**Decision (atomic note):**",
            "- [x] Approve",
            "- [x] Force Atomic Note (create/keep a standalone note for this item)",
            "",
        ]
    return "\n".join(lines)


class CountingFakeClient:
    """A fake that reports its own round trips, like the real KadoClient.

    ``cost_per_request`` is the number of round trips ONE public method call
    costs — the real client pages, so one ``list_dir`` can be several. Tests set
    it above 1 precisely so a hardcoded `2` or `7` in the estimator cannot agree
    with the observation by luck.
    """

    def __init__(
        self,
        *,
        listdir_items=None,
        frontmatter_responses=None,
        read_note_responses=None,
        cost_per_request: int = 1,
    ):
        self._listdir_items = listdir_items or []
        self._frontmatter_responses = frontmatter_responses or {}
        self._read_note_responses = read_note_responses or {}
        self._cost = cost_per_request
        self.call_count = 0
        self.calls: list[tuple[str, dict]] = []

    def _charge(self, name: str, **args) -> None:
        self.call_count += self._cost
        self.calls.append((name, args))

    def list_dir(self, path: str, *, depth=None, limit: int = 500) -> list:
        self._charge("list_dir", path=path, depth=depth)
        return self._listdir_items

    def list_notes(self, path: str, *, fields=None, depth=None, limit: int = 500):
        self._charge("list_notes", path=path, fields=fields)
        return []

    def search_by_frontmatter(
        self, query: str, *, path_prefix=None, limit: int = 500, modified_after=None,
    ) -> list:
        self._charge("search_by_frontmatter", query=query)
        return self._frontmatter_responses.get(query, [])

    def read_note(self, path: str) -> dict:
        self._charge("read_note", path=path)
        return self._read_note_responses.get(path, {"content": "", "modified": 0})

    def read_frontmatter(self, path: str) -> dict:
        self._charge("read_frontmatter", path=path)
        return {"content": {}}

    def read_file_bytes(self, path: str) -> bytes:
        from lib.kado_client import KadoError

        self._charge("read_file_bytes", path=path)
        raise KadoError(f"not found: {path}")


def _idle_client(**kw) -> CountingFakeClient:
    """An empty inbox — determine_action returns 'idle'."""
    return CountingFakeClient(listdir_items=[], **kw)


def _notes_client(n: int = 2, **kw) -> CountingFakeClient:
    return CountingFakeClient(
        listdir_items=[_listdir_item(f"{INBOX_PATH}note-{i}.md") for i in range(n)],
        **kw,
    )


def _run_triage(monkeypatch, tmp_path: Path, client, extra_argv=None) -> int:
    """Run the real CLI entry point in a clean cwd, as the instance runs it."""
    mod = _load_triage()
    monkeypatch.chdir(tmp_path)
    argv = [
        "--inbox-path", INBOX_PATH,
        "--output-dir", "tomo-tmp",
        "--registry-dir", str(tmp_path / "config" / "tag-handlers"),
    ] + list(extra_argv or [])
    return mod.main(argv, client_factory=lambda: client)


# ---------------------------------------------------------------------------
# 1. The counts are observed, not declared  (trap 1)
# ---------------------------------------------------------------------------

class TestObservedNotDeclared:
    def test_discover_reports_its_base_and_frontmatter_checkpoints(self, tmp_path):
        """A running total cannot be decomposed afterwards — hence two fields."""
        mod = _load_triage()
        client = _notes_client()
        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        # ADR-3: the ONE recursive listDir + the listNotes embed extraction.
        assert state.base_kado_calls == 2
        # query_frontmatter makes seven unconditional byFrontmatter calls.
        assert state.frontmatter_kado_calls == 7

    def test_base_count_follows_the_client_not_a_literal(self, tmp_path):
        """The mutation the Phase-3 gate ran, expressed as an observation.

        A client that pays two round trips per request makes the base cost 4 and
        the byFrontmatter cost 14. A `2 + 7` formula reports 9 regardless — so
        this test is exactly the one a literal cannot pass.
        """
        mod = _load_triage()
        client = _notes_client(cost_per_request=2)
        state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

        assert state.base_kado_calls == 4
        assert state.frontmatter_kado_calls == 14

    def test_count_kado_calls_matches_the_clients_own_total(self, tmp_path):
        """Parity at a cost the literals could never predict."""
        mod = _load_triage()
        for cost in (1, 2, 3):
            client = _notes_client(cost_per_request=cost)
            state = mod.discover(
                client, INBOX_PATH, output_dir=str(tmp_path / f"c{cost}")
            )
            assert mod._count_kado_calls(state) == client.call_count, (
                f"cost_per_request={cost}: reported "
                f"{mod._count_kado_calls(state)} observed {client.call_count}"
            )

    def test_a_client_that_cannot_count_does_not_crash_the_run(self, tmp_path):
        """Measurement must never fail a run — including for an old fake."""
        mod = _load_triage()

        class _Uncounted(CountingFakeClient):
            def __init__(self):
                super().__init__(listdir_items=[])
                del self.call_count

            def _charge(self, name, **args):
                self.calls.append((name, args))

        state = mod.discover(_Uncounted(), INBOX_PATH, output_dir=str(tmp_path))
        assert state.base_kado_calls == 0
        assert state.frontmatter_kado_calls == 0


# ---------------------------------------------------------------------------
# 2. The history file itself
# ---------------------------------------------------------------------------

class TestHistoryFile:
    def test_a_completed_run_appends_one_entry(self, monkeypatch, tmp_path):
        assert _run_triage(monkeypatch, tmp_path, _idle_client()) == 0

        entries = _read_history(tmp_path)
        assert len(entries) == 1
        entry = entries[0]
        for field in BASE_FIELDS:
            assert field in entry, f"{field} missing from {entry}"
        assert entry["action"] == "idle"
        assert entry["run_id"]
        assert entry["timestamp"].endswith("Z")

    def test_several_runs_accumulate_and_none_is_overwritten(
        self, monkeypatch, tmp_path
    ):
        for _ in range(3):
            assert _run_triage(monkeypatch, tmp_path, _idle_client()) == 0

        entries = _read_history(tmp_path)
        assert len(entries) == 3
        assert len({e["run_id"] for e in entries}) == 3

    def test_clearing_the_working_directory_leaves_earlier_entries(
        self, monkeypatch, tmp_path
    ):
        import shutil

        assert _run_triage(monkeypatch, tmp_path, _idle_client()) == 0
        first = _read_history(tmp_path)
        assert len(first) == 1

        shutil.rmtree(tmp_path / "tomo-tmp")
        assert not (tmp_path / "tomo-tmp").exists()

        assert _run_triage(monkeypatch, tmp_path, _idle_client()) == 0
        entries = _read_history(tmp_path)
        assert len(entries) == 2
        assert entries[0] == first[0]

    def test_an_unwritable_history_warns_and_the_run_continues(
        self, monkeypatch, tmp_path, capsys
    ):
        # `state` occupied by a FILE — the append cannot create the directory.
        (tmp_path / "state").write_text("not a directory", encoding="utf-8")

        assert _run_triage(monkeypatch, tmp_path, _idle_client()) == 0

        assert (tmp_path / "tomo-tmp" / "routing-plan.json").exists(), (
            "the run did not complete"
        )
        err = capsys.readouterr().err
        assert "cost history" in err.lower()

    def test_the_entry_carries_the_observed_counts(self, monkeypatch, tmp_path):
        client = _idle_client(cost_per_request=2)
        assert _run_triage(monkeypatch, tmp_path, client) == 0

        entry = _read_history(tmp_path)[0]
        assert entry["base_kado_calls"] == 4
        assert entry["total_kado_calls"] == client.call_count


# ---------------------------------------------------------------------------
# 3. The folder counts cross the process boundary  (trap 2)
# ---------------------------------------------------------------------------

class _FolderListingFake:
    """Reducer-side Kado fake: answers listDir for named destination folders."""

    def __init__(self, folders: dict[str, list[str]]):
        self._folders = folders
        self.call_count = 0
        self.listed: list[str] = []

    def list_dir(self, path: str, *, depth=None, limit: int = 500) -> list:
        self.call_count += 1
        self.listed.append(path)
        folder = path.rstrip("/")
        return [
            {"path": f"{folder}/{name}", "type": "file"}
            for name in self._folders.get(folder, [])
        ]

    def read_note(self, path: str) -> dict:
        self.call_count += 1
        return {"content": "", "modified": 0}

    def read_frontmatter(self, path: str) -> dict:
        self.call_count += 1
        return {"content": {}}

    def search_by_frontmatter(self, query, *, path_prefix=None, limit=500,
                              modified_after=None) -> list:
        self.call_count += 1
        return []


def _write_item(items_dir: Path, item_key: str, title: str, location: str) -> None:
    from lib.item_key import to_filename

    stem = item_key.rsplit("/", 1)[-1][:-3]
    (items_dir / to_filename(item_key)).write_text(json.dumps({
        "schema_version": "1", "stem": stem, "item_key": item_key,
        "path": item_key, "type": "fleeting_note", "type_confidence": 0.9,
        "issues": [], "force_atomic": False,
        "actions": [{
            "kind": "create_atomic_note", "source_stem": stem,
            "suggested_title": title, "template": "Atomic Note.md",
            "location": location, "candidate_mocs": [], "tags_to_add": [],
            "atomic_note_worthiness": 0.85, "classification": None,
            "force_atomic": False,
        }],
    }, ensure_ascii=False), encoding="utf-8")


def _reducer_argv(
    work: Path, *, run_id: str, output_name: str, fan_resolve: bool,
) -> list[str]:
    """The command line the skills issue, verbatim in shape.

    The output document lands in `tomo-tmp/` beside `routing-plan.json`, which is
    where both skills put it — the reducer derives the routing plan from the
    output's own directory, so the two artefacts of one run stay together with no
    extra flag for anyone to forget.
    """
    return [
        "--state", str(work / "inbox-state.jsonl"),
        "--items-dir", str(work / "items"),
        "--run-id", run_id,
        "--profile", "miyo",
        "--output", str(work / "tomo-tmp" / output_name),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--resolved-attachments", str(work / "absent-resolved.json"),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--threshold", "1",
    ] + (["--fan-resolve"] if fan_resolve else [])


def _run_reducer(
    monkeypatch, work: Path, *, run_id: str, destinations: list[tuple[str, str]],
    kado, output_name: str = "suggestions-doc.json", fan_resolve: bool = False,
) -> dict:
    """Drive the real reducer over one atomic proposal per destination."""
    reducer = _load("suggestions_reducer_t61", "suggestions-reducer.py")
    items_dir = work / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    state_path = work / "inbox-state.jsonl"

    for idx, (title, location) in enumerate(destinations):
        item_key = f"{INBOX_PATH}Sub{idx}/{title}.md"
        stem = f"{title}"
        for status in ("pending", "running", "done"):
            subprocess.run([
                sys.executable, str(SCRIPTS_DIR / "state-update.py"),
                "--state", str(state_path), "--item-key", item_key,
                "--stem", stem, "--path", item_key, "--status", status,
                "--run-id", run_id,
            ], check=True, capture_output=True)
        _write_item(items_dir, item_key, title, location)

    doc_path = work / "tomo-tmp" / output_name
    monkeypatch.setattr(reducer, "KadoClient", lambda: kado)
    monkeypatch.setattr(sys, "argv", ["suggestions-reducer.py"] + _reducer_argv(
        work, run_id=run_id, output_name=output_name, fan_resolve=fan_resolve,
    ))
    assert reducer.main() == 0
    return json.loads(doc_path.read_text(encoding="utf-8"))


class TestFolderCountsReachTheDocument:
    def test_the_document_carries_both_folder_counts(self, monkeypatch, tmp_path):
        kado = _FolderListingFake({NOTES: ["Dresden.md"], PEOPLE: []})
        doc = _run_reducer(
            monkeypatch, tmp_path, run_id="t61-folders",
            destinations=[("Dresden", NOTES), ("Ada", PEOPLE)], kado=kado,
        )

        for field in FOLDER_FIELDS:
            assert field in doc, f"{field} never reached suggestions-doc.json"

    def test_two_distinct_destination_folders_are_reported_as_two(
        self, monkeypatch, tmp_path
    ):
        """A positive value at a named location — not merely 'reported separately'."""
        kado = _FolderListingFake({NOTES: ["Dresden.md"], PEOPLE: []})
        doc = _run_reducer(
            monkeypatch, tmp_path, run_id="t61-two",
            destinations=[("Dresden", NOTES), ("Ada", PEOPLE)], kado=kado,
        )

        assert doc["distinct_destination_folders"] == 2
        assert doc["folder_listing_calls"] == 2
        assert sorted(kado.listed) == sorted([NOTES + "/", PEOPLE + "/"])

    def test_a_second_claim_on_one_folder_costs_no_second_listing(
        self, monkeypatch, tmp_path
    ):
        """The cache is the reason the count is not simply the claim count."""
        kado = _FolderListingFake({NOTES: []})
        doc = _run_reducer(
            monkeypatch, tmp_path, run_id="t61-cached",
            destinations=[("Dresden", NOTES), ("Leipzig", NOTES)], kado=kado,
        )

        assert doc["distinct_destination_folders"] == 1
        assert doc["folder_listing_calls"] == 1

    def test_the_document_still_validates_against_its_schema(
        self, monkeypatch, tmp_path
    ):
        from jsonschema import validate as json_validate

        kado = _FolderListingFake({NOTES: []})
        doc = _run_reducer(
            monkeypatch, tmp_path, run_id="t61-schema",
            destinations=[("Dresden", NOTES)], kado=kado,
        )
        schema = json.loads(
            (REPO_ROOT / "tomo" / "schemas" / "suggestions-doc.schema.json")
            .read_text(encoding="utf-8")
        )
        json_validate(instance=doc, schema=schema)


# ---------------------------------------------------------------------------
# 4. All five actions record  (trap 3)
# ---------------------------------------------------------------------------

class TestEveryActionRecords:
    def test_idle_records_in_triage_without_folder_fields(
        self, monkeypatch, tmp_path
    ):
        assert _run_triage(monkeypatch, tmp_path, _idle_client()) == 0
        entries = _read_history(tmp_path)
        assert len(entries) == 1
        assert entries[0]["action"] == "idle"
        for field in FOLDER_FIELDS:
            assert field not in entries[0], (
                f"{field} present on a path where the reducer never ran — "
                "zero asserts a measurement nobody took"
            )

    def test_synthesize_records_in_triage_without_folder_fields(
        self, monkeypatch, tmp_path
    ):
        assert _run_triage(
            monkeypatch, tmp_path, _notes_client(),
            extra_argv=["--force-pass2", "--force"],
        ) == 0
        entries = _read_history(tmp_path)
        assert len(entries) == 1
        assert entries[0]["action"] == "synthesize"
        assert not any(f in entries[0] for f in FOLDER_FIELDS)

    def test_transcribe_records_in_triage_without_folder_fields(
        self, monkeypatch, tmp_path
    ):
        client = CountingFakeClient(
            listdir_items=[_listdir_item(f"{INBOX_PATH}memo.m4a")]
        )
        assert _run_triage(monkeypatch, tmp_path, client) == 0
        entries = _read_history(tmp_path)
        assert len(entries) == 1
        assert entries[0]["action"] == "transcribe"
        assert not any(f in entries[0] for f in FOLDER_FIELDS)

    def test_suggest_records_in_the_reducer_with_the_folder_fields(
        self, monkeypatch, tmp_path
    ):
        assert _run_triage(
            monkeypatch, tmp_path, _notes_client(), extra_argv=["--force-pass1"],
        ) == 0
        assert _read_history(tmp_path) == [], (
            "triage appended for `suggest` — the folder counts do not exist yet"
        )

        kado = _FolderListingFake({NOTES: [], PEOPLE: []})
        _run_reducer(
            monkeypatch, tmp_path, run_id="t61-suggest",
            destinations=[("Dresden", NOTES), ("Ada", PEOPLE)], kado=kado,
        )

        entries = _read_history(tmp_path)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["action"] == "suggest"
        assert entry["run_id"] == "t61-suggest"
        assert entry["distinct_destination_folders"] == 2
        assert entry["folder_listing_calls"] == 2
        assert entry["base_kado_calls"] == 2

    def test_fan_resolve_records_downstream(self, monkeypatch, tmp_path):
        sugg_path = INBOX_PATH + "2026-05-22_1432_suggestions.md"
        client = CountingFakeClient(
            listdir_items=[
                _listdir_item(sugg_path),
                _listdir_item(INBOX_PATH + "Furano.md"),
            ],
            frontmatter_responses={
                "tomo.state=pending-approval": [
                    _fm_hit(sugg_path, "suggestions", "pending-approval"),
                ],
            },
            read_note_responses={
                sugg_path: {
                    "content": _suggestions_body(approved=True, fan_items=["Furano"]),
                    "modified": 0,
                },
            },
        )
        assert _run_triage(monkeypatch, tmp_path, client) == 0
        plan = json.loads(
            (tmp_path / "tomo-tmp" / "routing-plan.json").read_text(encoding="utf-8")
        )
        assert plan["action"] == "fan-resolve", plan["action"]
        assert _read_history(tmp_path) == [], (
            "triage appended for `fan-resolve` — the downstream step writes it"
        )

        kado = _FolderListingFake({NOTES: []})
        _run_reducer(
            monkeypatch, tmp_path, run_id="t61-fan",
            destinations=[("Dresden", NOTES)], kado=kado,
            output_name="suggestions-fan-doc.json", fan_resolve=True,
        )

        entries = _read_history(tmp_path)
        assert len(entries) == 1
        assert entries[0]["action"] == "fan-resolve"
        assert entries[0]["run_id"] == "t61-fan"

    def test_every_action_is_classified(self):
        """A sixth action must not fall through both branches unrecorded."""
        mod = _load_triage()
        actions = {"suggest", "synthesize", "idle", "transcribe", "fan-resolve"}
        assert mod.DOWNSTREAM_COST_ENTRY_ACTIONS <= actions
        assert mod.DOWNSTREAM_COST_ENTRY_ACTIONS == {"suggest", "fan-resolve"}


# ---------------------------------------------------------------------------
# 5. Exactly one entry per run  (trap 4 — the one that fails loudly)
# ---------------------------------------------------------------------------

class TestExactlyOneEntryPerRun:
    def test_a_suggest_run_produces_one_entry_not_two(self, monkeypatch, tmp_path):
        assert _run_triage(
            monkeypatch, tmp_path, _notes_client(), extra_argv=["--force-pass1"],
        ) == 0
        kado = _FolderListingFake({NOTES: []})
        _run_reducer(
            monkeypatch, tmp_path, run_id="t61-once",
            destinations=[("Dresden", NOTES)], kado=kado,
        )

        entries = _read_history(tmp_path)
        assert len(entries) == 1, (
            f"expected exactly one entry for one run, got {len(entries)}: {entries}"
        )

    def test_a_missing_routing_plan_costs_the_entry_not_the_run(
        self, monkeypatch, tmp_path
    ):
        """Measurement must never fail a run `[ref: SDD/Error Handling]`."""
        monkeypatch.chdir(tmp_path)
        kado = _FolderListingFake({NOTES: []})
        doc = _run_reducer(
            monkeypatch, tmp_path, run_id="t61-noplan",
            destinations=[("Dresden", NOTES)], kado=kado,
        )

        assert doc["sections"], "the reducer did not produce its document"
        assert _read_history(tmp_path) == []


# ---------------------------------------------------------------------------
# 6. No SKILL.md step is involved  (the reason the append moved)
# ---------------------------------------------------------------------------

SKILL_DIR = REPO_ROOT / "tomo" / "dot_claude" / "skills"


class TestNoLLMStepRecordsTheCost:
    def test_the_reducer_cli_alone_records_the_run(self, monkeypatch, tmp_path):
        """The production invocation, as a subprocess — nothing else runs.

        The reducer is driven exactly as the skill's one command line drives it,
        in its own process, with no in-process monkeypatching and no second step.
        If the entry appears, the guarantee holds without anyone remembering.
        """
        assert _run_triage(
            monkeypatch, tmp_path, _notes_client(), extra_argv=["--force-pass1"],
        ) == 0

        items_dir = tmp_path / "items"
        items_dir.mkdir(parents=True, exist_ok=True)
        item_key = f"{INBOX_PATH}Sub0/Dresden.md"
        for status in ("pending", "running", "done"):
            subprocess.run([
                sys.executable, str(SCRIPTS_DIR / "state-update.py"),
                "--state", str(tmp_path / "inbox-state.jsonl"),
                "--item-key", item_key, "--stem", "Dresden", "--path", item_key,
                "--status", status, "--run-id", "t61-cli",
            ], check=True, capture_output=True)
        _write_item(items_dir, item_key, "Dresden", NOTES)

        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "suggestions-reducer.py")]
            + _reducer_argv(
                tmp_path, run_id="t61-cli",
                output_name="suggestions-doc.json", fan_resolve=False,
            )
            + ["--no-kado"],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr

        entries = _read_history(tmp_path)
        assert len(entries) == 1, f"stderr was: {proc.stderr}"
        assert entries[0]["action"] == "suggest"
        assert entries[0]["run_id"] == "t61-cli"
        assert entries[0]["base_kado_calls"] == 2

    def test_no_skill_delegates_the_recording_to_a_separate_step(self):
        """The two skills must not carry a cost-recording command.

        A step in a SKILL.md is executed by an LLM, and pytest cannot see whether
        it ran. This asserts the dependency is gone rather than merely unused.
        """
        for skill in ("suggest-handling", "force-atomic-handling"):
            body = (SKILL_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
            assert "record-run-cost" not in body, (
                f"{skill}/SKILL.md still delegates the cost record to an LLM step"
            )
            assert "cost-history" not in body

    def test_the_retired_wrapper_script_is_gone(self):
        assert not (SCRIPTS_DIR / "record-run-cost.py").exists()
