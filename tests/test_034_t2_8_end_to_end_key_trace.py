#!/usr/bin/env python3
# version: 0.2.0
"""test_034_t2_8_end_to_end_key_trace.py — the Phase 2 validation gate.

Spec 034 (recursive inbox discovery), Phase 2 T2.8.

WHY THIS FILE EXISTS, when eight per-task test files already pass:

Spec 031 shipped five phases against a field nothing populated. Every task
passed both review gates because each correctly implemented its own local
contract. The same failure recurred three times inside Phase 2 — most
sharply in T2.7, where correct, symmetric code with a proven RED was
completely inert against real data.

Per-stage unit tests cannot catch that. This file therefore traces ONE
identity — `item_key` — across every artefact boundary of a single run,
asserting the VALUE at each hop, not merely that the field exists:

    routing plan
      -> inbox-state.jsonl        (state-update.py, real invocation)
      -> items/<key>.result.json  (the analyst's contract, fixtured)
      -> suggestions-doc.json     (suggestions-reducer.py, real invocation)
      -> suggestions-wire.json    (suggestions-render.py, real invocation)
      -> confirmed_items[]        (suggestion-parser.build_from_wire)
      -> derive_expected()        (instructions-diff.py coverage audit)
      -> build_actions()          (the CON-4 emission boundary to Hashi)

A field that exists but carries a bare stem at one hop is exactly the
defect this gate is for, so every assertion compares against the verbatim
vault-relative path (ADR-1). The fixture inbox deliberately contains:

  - two notes sharing a filename in different subfolders (the collision
    the whole spec exists to remove), and
  - a path with BOTH a space and mixed case, so a normalising, lowercasing,
    slugging or basename-taking stage fails loudly rather than quietly.

WHICH PATHS THIS PROVES: both. The hop-by-hop trace runs the ADR-026
**wire** path (`build_from_wire`). The **markdown** path that the normal
`synthesis-conductor.md` flow invokes is traced separately in
TestMarkdownPathAlsoCarriesTheKey — it recovers each item's key from the
`--suggestions-doc` sibling rather than from the rendered markdown, which
carries only a bare display stem. Phase 5 T5.1 then closed the DISPLAY half:
two namesakes no longer render the identical `[[Dresden]]`. Identity and
display are asserted separately here — the parsed display value must stay a
bare stem on both paths even though the rendered LINK is now qualified.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"

sys.path.insert(0, str(SCRIPTS_DIR))

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate as json_validate  # noqa: E402

from lib.item_key import to_filename  # noqa: E402


# ---------------------------------------------------------------------------
# The fixture inbox — the traps are in the paths themselves
# ---------------------------------------------------------------------------

INBOX = "100 Inbox/"

# Two namesakes in different subfolders: identical `stem`, distinct `item_key`.
DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
DRESDEN_REISE = "100 Inbox/Reise/Dresden.md"
# A subfolder with a space AND mixed case in both folder and filename.
HOKKAIDO = "100 Inbox/Travel Notes/Hokkaido Trip.md"

# (stem, item_key, atomic title) — titles differ so a collapse is visible.
ITEMS: list[tuple[str, str, str]] = [
    ("Dresden", DRESDEN_PLACES, "Dresden — Frauenkirche"),
    ("Dresden", DRESDEN_REISE, "Dresden — a different note"),
    ("Hokkaido Trip", HOKKAIDO, "Hokkaido powder days"),
]

ALL_KEYS = [key for _stem, key, _title in ITEMS]

RUN_ID = "t2-8-gate-run"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_script(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{cmd[1]} failed (exit {result.returncode})\n"
        f"stderr:\n{result.stderr}\nstdout:\n{result.stdout[:2000]}"
    )
    return result


# ---------------------------------------------------------------------------
# Fake Kado — mirrors tests/integration/test_018_pipeline.py's client
# ---------------------------------------------------------------------------

class FakeKadoClient:
    def __init__(self, *, listdir_items=None, frontmatter_responses=None,
                 read_note_responses=None):
        self._listdir_items = listdir_items or []
        self._frontmatter_responses = frontmatter_responses or {}
        self._read_note_responses = read_note_responses or {}

    def list_dir(self, path: str, *, depth: int = None, limit: int = 500) -> list:
        return self._listdir_items

    def list_notes(self, path: str, *, fields=None, depth=None, limit: int = 500):
        return []

    def search_by_frontmatter(self, query: str, *, path_prefix=None, limit: int = 500,
                              modified_after=None) -> list:
        return self._frontmatter_responses.get(query, [])

    def read_note(self, path: str) -> dict:
        return self._read_note_responses.get(path, {"content": "", "modified": 0})

    def read_frontmatter(self, path: str) -> dict:
        return {"content": {}}

    def read_file_bytes(self, path: str) -> bytes:
        from lib.kado_client import KadoError

        raise KadoError(f"not found: {path}")


def _listdir_item(path: str) -> dict:
    return {"path": path, "type": "file", "modified": 1716300000000, "size": 100}


def _empty_frontmatter() -> dict:
    return {
        "tomo.state=pending-approval": [],
        "tomo.state=pending-accept": [],
        "tomo.state=captured": [],
        "tomo.doc_type=instructions": [],
    }


# ---------------------------------------------------------------------------
# The analyst's output — the one stage that is an LLM and so is fixtured
# ---------------------------------------------------------------------------

def _item_result(stem: str, item_key: str, title: str) -> dict:
    """A recorded analyst result. `item_key` is the note's path, verbatim."""
    return {
        "schema_version": "1",
        "stem": stem,
        "item_key": item_key,
        "path": item_key,
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "date_relevance": None,
        "issues": [],
        "duration_ms": 100,
        "force_atomic": False,
        "actions": [
            {
                "kind": "create_atomic_note",
                "source_stem": stem,
                "suggested_title": title,
                "template": "Atomic Note.md",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": [
                    {"path": "Atlas/200 Maps/Travel (MOC).md",
                     "score": 0.8, "pre_check": True},
                ],
                "tags_to_add": ["topic/travel"],
                "atomic_note_worthiness": 0.85,
                "classification": None,
            },
        ],
    }


# ---------------------------------------------------------------------------
# The traced run — executed once, asserted hop by hop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def traced(tmp_path_factory) -> dict:
    """Drive the chain once with real script invocations; return every artefact."""
    work = tmp_path_factory.mktemp("t2_8_trace")
    items_dir = work / "items"
    items_dir.mkdir()
    state_path = work / "inbox-state.jsonl"

    # ---- Hop 1: routing plan (inbox-triage.py, driven through main()) ------
    triage = _load_script("inbox_triage_t2_8", "inbox-triage.py")
    client = FakeKadoClient(
        listdir_items=[_listdir_item(k) for k in ALL_KEYS],
        frontmatter_responses=_empty_frontmatter(),
    )
    rc = triage.main(
        ["--inbox-path", INBOX, "--output-dir", str(work)],
        client_factory=lambda: client,
    )
    assert rc == 0, f"inbox-triage.main() returned {rc}"
    routing_plan = json.loads((work / "routing-plan.json").read_text(encoding="utf-8"))

    # ---- Hop 2: run state (state-update.py, real CLI, --item-key) ----------
    for stem, key, _title in ITEMS:
        for status in ("pending", "running", "done"):
            _run([
                sys.executable, str(SCRIPTS_DIR / "state-update.py"),
                "--state", str(state_path),
                "--item-key", key,
                "--stem", stem,
                "--path", key,
                "--status", status,
                "--run-id", RUN_ID,
            ])
    state_lines = [
        json.loads(ln) for ln in
        state_path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]

    # ---- Hop 3: per-item results (the analyst contract, fixtured) ----------
    for stem, key, title in ITEMS:
        (items_dir / to_filename(key)).write_text(
            json.dumps(_item_result(stem, key, title), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- Hop 4: suggestions doc (suggestions-reducer.py, real CLI) ---------
    doc_path = work / "suggestions-doc.json"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-reducer.py"),
        "--state", str(state_path),
        "--items-dir", str(items_dir),
        "--run-id", RUN_ID,
        "--profile", "miyo",
        "--output", str(doc_path),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--resolved-attachments", str(work / "absent-resolved.json"),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--threshold", "1",
        "--no-kado",
        # T6.1: the reducer appends this run's cost entry; the history path
        # defaults cwd-relative (instance runtime) — keep it out of the repo.
        "--cost-history", str(work / "cost-history.jsonl"),
    ])
    suggestions_doc = json.loads(doc_path.read_text(encoding="utf-8"))

    # ---- Hop 5: wire + markdown (suggestions-render.py, real CLI) ----------
    md_path = work / "suggestions.md"
    wire_path = work / "suggestions-wire.json"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-render.py"),
        "--input", str(doc_path),
        "--output", str(md_path),
        "--json-output", str(wire_path),
    ])
    wire = json.loads(wire_path.read_text(encoding="utf-8"))

    # ---- Hop 6: parsed suggestions, BOTH paths -----------------------------
    # (a) the ADR-026 wire path — what this gate proves.
    parser = _load_script("suggestion_parser_t2_8", "suggestion-parser.py")
    parsed_wire = parser.build_from_wire(wire, moc_template="MOC.md")

    # (b) the markdown path — what synthesis-conductor.md actually invokes.
    approved_md = work / "suggestions-approved.md"
    approved_md.write_text(
        md_path.read_text(encoding="utf-8").replace("- [ ] Approved", "- [x] Approved", 1),
        encoding="utf-8",
    )
    parsed_md = json.loads(_run([
        sys.executable, str(SCRIPTS_DIR / "suggestion-parser.py"),
        "--file", str(approved_md),
    ]).stdout)

    return {
        "work": work,
        "items_dir": items_dir,
        "routing_plan": routing_plan,
        "state_lines": state_lines,
        "suggestions_doc": suggestions_doc,
        "markdown": md_path.read_text(encoding="utf-8"),
        "wire": wire,
        "parsed_wire": parsed_wire,
        "parsed_md": parsed_md,
    }


# ---------------------------------------------------------------------------
# Hop 1 — routing plan
# ---------------------------------------------------------------------------

class TestHop1RoutingPlan:
    def test_routing_plan_validates_against_its_schema(self, traced):
        json_validate(instance=traced["routing_plan"],
                      schema=_schema("routing-plan.schema.json"))

    def test_fresh_source_paths_are_the_verbatim_vault_paths(self, traced):
        """`fresh_sources[].path` IS the item key for the suggest flow — ADR-1's
        `derive()` is the identity function, so the path handed to the analyst
        must survive triage untouched."""
        paths = sorted(s["path"] for s in traced["routing_plan"]["fresh_sources"])
        assert paths == sorted(ALL_KEYS), (
            "triage did not carry the vault-relative paths through verbatim"
        )

    def test_namesakes_stay_two_distinct_sources(self, traced):
        paths = [s["path"] for s in traced["routing_plan"]["fresh_sources"]]
        assert DRESDEN_PLACES in paths and DRESDEN_REISE in paths, (
            "the two same-named notes collapsed into one fresh source"
        )

    def test_space_and_mixed_case_survive_triage(self, traced):
        paths = [s["path"] for s in traced["routing_plan"]["fresh_sources"]]
        assert HOKKAIDO in paths
        assert " " in HOKKAIDO and HOKKAIDO != HOKKAIDO.lower()


# ---------------------------------------------------------------------------
# Hop 2 — run state
# ---------------------------------------------------------------------------

class TestHop2RunState:
    def test_every_state_line_carries_the_verbatim_key(self, traced):
        schema = _schema("state-entry.schema.json")
        for entry in traced["state_lines"]:
            json_validate(instance=entry, schema=schema)
            assert entry["item_key"] in ALL_KEYS, (
                f"state line carries {entry['item_key']!r}, not a verbatim vault path"
            )

    def test_state_key_is_never_the_bare_stem(self, traced):
        for entry in traced["state_lines"]:
            assert "/" in entry["item_key"], (
                f"item_key {entry['item_key']!r} lost its folder — a basename was taken"
            )
            assert entry["item_key"] != entry["stem"]

    def test_namesakes_hold_separate_state(self, traced):
        keys = {e["item_key"] for e in traced["state_lines"]}
        assert {DRESDEN_PLACES, DRESDEN_REISE} <= keys
        for key in (DRESDEN_PLACES, DRESDEN_REISE):
            statuses = [e["status"] for e in traced["state_lines"] if e["item_key"] == key]
            assert statuses == ["pending", "running", "done"], (
                f"{key} did not keep its own status history"
            )


# ---------------------------------------------------------------------------
# Hop 3 — per-item result files
# ---------------------------------------------------------------------------

class TestHop3ItemResults:
    def test_each_key_owns_a_distinct_result_file(self, traced):
        names = {p.name for p in traced["items_dir"].iterdir()}
        assert len(names) == len(ALL_KEYS), (
            f"expected {len(ALL_KEYS)} result files, found {sorted(names)} — "
            "two items shared a filename"
        )
        assert names == {to_filename(k) for k in ALL_KEYS}

    def test_result_payload_carries_the_verbatim_key(self, traced):
        schema = _schema("item-result.schema.json")
        for key in ALL_KEYS:
            payload = json.loads(
                (traced["items_dir"] / to_filename(key)).read_text(encoding="utf-8")
            )
            json_validate(instance=payload, schema=schema)
            assert payload["item_key"] == key


# ---------------------------------------------------------------------------
# Hop 4 — suggestions doc
# ---------------------------------------------------------------------------

class TestHop4SuggestionsDoc:
    def test_doc_validates_against_its_schema(self, traced):
        json_validate(instance=traced["suggestions_doc"],
                      schema=_schema("suggestions-doc.schema.json"))

    def test_every_section_carries_the_verbatim_key(self, traced):
        sections = traced["suggestions_doc"]["sections"]
        assert len(sections) == len(ALL_KEYS), (
            f"reducer emitted {len(sections)} sections for {len(ALL_KEYS)} items — "
            "an item was dropped or two were merged"
        )
        assert sorted(s["item_key"] for s in sections) == sorted(ALL_KEYS)

    def test_section_stem_stays_a_bare_filename(self, traced):
        """ADR-2: `stem` is display-only. A path here reaches note titles and
        wikilinks, which is a user-visible break."""
        for section in traced["suggestions_doc"]["sections"]:
            assert "/" not in section["stem"], (
                f"a path leaked into the display stem: {section['stem']!r}"
            )

    def test_namesakes_keep_their_own_titles(self, traced):
        by_key = {s["item_key"]: s for s in traced["suggestions_doc"]["sections"]}
        titles = {
            key: [a["item"]["title"] for a in by_key[key]["actions"]
                  if a.get("kind") == "create_atomic_note"]
            for key in (DRESDEN_PLACES, DRESDEN_REISE)
        }
        assert titles[DRESDEN_PLACES] == ["Dresden — Frauenkirche"]
        assert titles[DRESDEN_REISE] == ["Dresden — a different note"], (
            "one namesake's analyst result was read for the other"
        )


# ---------------------------------------------------------------------------
# Hop 5 — the wire
# ---------------------------------------------------------------------------

class TestHop5Wire:
    def test_wire_validates_against_its_schema(self, traced):
        json_validate(instance=traced["wire"],
                      schema=_schema("suggestions-wire.schema.json"))

    def test_every_wire_suggestion_carries_the_verbatim_key(self, traced):
        keys = sorted(s["item_key"] for s in traced["wire"]["suggestions"])
        assert keys == sorted(ALL_KEYS)

    def test_wire_stem_stays_bare_for_hashi(self, traced):
        """CON-4: `stem` is what Hashi joins on. It must stay a bare filename."""
        for suggestion in traced["wire"]["suggestions"]:
            assert "/" not in suggestion["stem"]
            assert not suggestion["stem"].endswith(".md")


# ---------------------------------------------------------------------------
# Hop 6 — parsed suggestions, wire path
# ---------------------------------------------------------------------------

class TestHop6ParsedSuggestionsWirePath:
    def test_confirmed_items_carry_the_verbatim_key(self, traced):
        confirmed = [
            c for c in traced["parsed_wire"]["confirmed_items"]
            if c.get("action") != "create_moc"
        ]
        assert sorted(c["item_key"] for c in confirmed) == sorted(ALL_KEYS)

    def test_source_path_stays_the_bare_display_stem(self, traced):
        """ADR-2: `item_key` carries identity so `source_path` can stay display
        text. Overwriting source_path with a path is the failure mode T2.3b
        was written to avoid."""
        for item in traced["parsed_wire"]["confirmed_items"]:
            if item.get("action") == "create_moc":
                continue
            assert item["source_path"] == "Dresden" or "/" not in item["source_path"]

    def test_namesakes_remain_two_confirmed_items(self, traced):
        keys = [c.get("item_key") for c in traced["parsed_wire"]["confirmed_items"]]
        assert keys.count(DRESDEN_PLACES) == 1
        assert keys.count(DRESDEN_REISE) == 1


# ---------------------------------------------------------------------------
# Hop 7 — the coverage audit keys on the same identity
# ---------------------------------------------------------------------------

class TestHop7CoverageAudit:
    def test_derive_expected_keys_on_the_verbatim_path(self, traced):
        diff = _load_script("instructions_diff_t2_8", "instructions-diff.py")
        expected = diff.derive_expected(traced["parsed_wire"])
        keys = sorted(
            v["item_key"] for v in expected["by_item"].values()
            if v.get("kind") == "move_note"
        )
        assert keys == sorted(ALL_KEYS), (
            "the coverage audit did not inherit the wire's identity — a missing "
            "action for one namesake can hide behind the other"
        )


# ---------------------------------------------------------------------------
# Hop 8 — CON-4: the emission boundary to Hashi
# ---------------------------------------------------------------------------

_CON4_CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}

_STEM_FIELDS = ("source_stem", "target_stem", "daily_note_stem")


class TestHop8EmissionBoundaryStaysBareForHashi:
    def _actions(self, traced):
        from lib.render_actions import build_actions  # noqa: PLC0415 — script-dir import

        confirmed = traced["parsed_wire"]["confirmed_items"]
        manifest = [
            {
                "id": c["id"],
                "path": f"Atlas/202 Notes/{c.get('title') or ''}.md",
                "source_path": c.get("source_path"),
                "attachments": [],
            }
            for c in confirmed if c.get("template")
        ]
        actions, _skipped = build_actions(
            manifest, confirmed, traced["parsed_wire"].get("daily_updates", []),
            traced["parsed_wire"].get("skipped", []), dict(_CON4_CFG),
        )
        return actions

    def test_no_path_leaks_into_an_emitted_stem(self, traced):
        """CON-4 is a cross-repo contract with a separate repository: whatever
        identity this design introduces internally, the emitted stems stay bare
        filenames."""
        for action in self._actions(traced):
            for field in _STEM_FIELDS:
                value = action.get(field)
                if isinstance(value, str) and value:
                    assert "/" not in value, (
                        f"action {action.get('id')} emitted {field}={value!r} — "
                        "a path leaked across the Hashi boundary"
                    )

    def test_item_key_is_never_emitted_to_hashi(self, traced):
        """`item_key` is internal. It must not appear in the instruction set."""
        emitted = json.dumps(self._actions(traced))
        assert "item_key" not in emitted


# ---------------------------------------------------------------------------
# The known limit — stated, not discovered
# ---------------------------------------------------------------------------

class TestMarkdownPathAlsoCarriesTheKey:
    """Was a known-limit assertion; now a positive trace, as it required.

    `suggestion-parser.main()` — what `synthesis-conductor.md` invokes in the
    normal flow — used to mint no `item_key`, on the premise that the rendered
    markdown carries only a bare display stem. That premise held for the
    markdown FILE and not for the markdown PATH: the same invocation passes
    `--suggestions-doc`, and that document carries `sections[].item_key` keyed
    by the id the heading shows. The key is joined back from there.

    Note this is NOT what T5.1 does — T5.1 path-qualifies source links only for
    same-filename groups, so a globally unique subfolder note would have kept
    its bare link and stayed unrecoverable.
    """

    def test_markdown_path_confirmed_items_carry_their_own_key(self, traced):
        confirmed = traced["parsed_md"]["confirmed_items"]
        assert confirmed, "the markdown path parsed no confirmed items at all"
        keys = {c["title"]: c.get("item_key") for c in confirmed}
        assert keys == {
            "Dresden — Frauenkirche": DRESDEN_PLACES,
            "Dresden — a different note": DRESDEN_REISE,
            "Hokkaido powder days": HOKKAIDO,
        }, f"markdown path bound the wrong keys: {keys}"

    def test_the_two_namesakes_do_not_collapse_onto_one_key(self, traced):
        """The whole point: identical display stems, distinct identities."""
        confirmed = traced["parsed_md"]["confirmed_items"]
        dresdens = [c for c in confirmed if c["source_path"] == "Dresden"]
        assert len(dresdens) == 2
        assert len({c["item_key"] for c in dresdens}) == 2, (
            f"both namesakes bound the same key: {dresdens}"
        )

    def test_display_stems_stay_bare_on_the_markdown_path(self, traced):
        """ADR-2 still holds — recovering identity must not put a path into
        the display text the note title is derived from."""
        confirmed = traced["parsed_md"]["confirmed_items"]
        assert all("/" not in (c["source_path"] or "") for c in confirmed)

    def test_the_two_source_links_are_now_distinguishable(self, traced):
        """Was `test_markdown_still_renders_bare_source_links`, which pinned the
        gap T5.1 then closed: both namesakes used to render the identical
        `[[Dresden]]`, so the USER could not tell them apart in the document
        they approve. T5.1 path-qualifies a source link on collision. The
        identity assertions above are unchanged — they are what this class is
        for, and they must keep holding through the display change."""
        md = traced["markdown"]
        assert md.count("**Source:** [[Dresden]]") == 0, (
            "a colliding namesake still renders a bare, ambiguous source link"
        )
        links = re.findall(r"^\*\*Source:\*\* \[\[([^\]]+)\]\]", md, re.MULTILINE)
        dresden = [ln for ln in links if ln.endswith("|Dresden")]
        assert len(dresden) == 2 and len(set(dresden)) == 2, (
            f"the two namesakes do not carry distinct source links: {links}"
        )
        for ln in dresden:
            target, alias = ln.split("|", 1)
            assert alias == "Dresden", (
                f"the alias must keep the display text bare (ADR-2): {ln}"
            )
            assert f"{target}.md" in (DRESDEN_PLACES, DRESDEN_REISE), (
                f"the qualified link does not name a real namesake: {ln}"
            )
