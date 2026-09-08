#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t6_2_pipeline_integration.py — the Phase 6 integration gate.

Spec 034 (recursive inbox discovery), Phase 6 T6.2.

WHAT THIS FILE OWNS, and what it deliberately does not.

`test_034_t2_8_end_to_end_key_trace.py` already walks this spec end to end,
hop by hop, on BOTH parser paths, for two namesake notes in one-level
subfolders and for a space-and-mixed-case subfolder. It is the authority on
`item_key` identity and on the artefact-to-artefact trace of that identity.
This file does not re-assert either. A second file repeating them doubles the
maintenance and leaves nobody able to say which one is authoritative.

What T2.8's fixture has none of, and what this one is for:

  - a ROOT-LEVEL note and a note nested TWO levels deep, in one run
  - a NAMESAKE PAIR OF ATTACHMENTS — two different files sharing a basename
    in different subfolders, each embedded by its own note (T6.0's `claimed`
    fold plus T5.4's suppression, at the instruction-set boundary)
  - a note with NO EMBED, as a negative control
  - an AUDIO file whose only namesake note lives elsewhere in the tree
    (Feature 5's actual defect surface)

The two namesake notes appear here only as the carriers of the attachment and
audio cases — never as a re-trace of T2.8.

Assertions are made at EVERY artefact boundary, not only at the end: routing
plan, resolved attachments, per-item results, suggestions document, wire,
parsed suggestions (both paths), and the rendered instruction set. A defect
that a later stage papers over is otherwise invisible.

The second half of this file is the flat-inbox instruction-set golden — a
recording of the Pass-2 chain at `ee44cb3`, the commit immediately preceding
Phase 1 — over its own root-level-only fixture. See
`tests/fixtures/034-t6-2-instructions-golden/README.md`.

The third is `FEATURE_COVERAGE`, the PRD-feature-to-test map. Its residual
limit, stated rather than discovered: the walker proves each referenced test
exists and currently passes; it does NOT prove that test still asserts the
claimed feature. Someone gutting a body to `assert True` under an unchanged
name defeats it, and semantic drift stays a review responsibility at the
moment that test is edited.

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
GOLDEN_DIR = TESTS_DIR / "fixtures" / "034-t6-2-instructions-golden"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.item_key import to_filename  # noqa: E402
from lib.kado_client import KadoError  # noqa: E402

INBOX = "100 Inbox/"
RUN_ID = "t6-2-integration"

# --- The fixture inbox ------------------------------------------------------
ROOT_NOTE = "100 Inbox/Root Note.md"                       # depth 0, no embed
DEEP_NOTE = "100 Inbox/Travel/Japan/Hokkaido Trip.md"      # depth 2
DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"             # carries attachment A
DRESDEN_REISE = "100 Inbox/Reise/Dresden.md"               # carries attachment B
ARCHIVE_MEMO = "100 Inbox/Archive/memo.md"                 # the audio's namesake

KARTE_PLACES = "100 Inbox/Places/karte.png"
KARTE_REISE = "100 Inbox/Reise/karte.png"                  # same basename, other file
KARTE_JP = "100 Inbox/Travel/Japan/karte-jp.png"           # unique basename, depth 2
AUDIO = "100 Inbox/memo.m4a"                               # depth 0; namesake at depth 1

NOTES = [ROOT_NOTE, DEEP_NOTE, DRESDEN_PLACES, DRESDEN_REISE, ARCHIVE_MEMO]
FILES = NOTES + [KARTE_PLACES, KARTE_REISE, KARTE_JP, AUDIO]

TITLES = {
    ROOT_NOTE: "Root note takeaway",
    DEEP_NOTE: "Hokkaido powder days",
    DRESDEN_PLACES: "Dresden - Frauenkirche",
    DRESDEN_REISE: "Dresden - a different note",
    ARCHIVE_MEMO: "Archived memo takeaway",
}

# Embeds as Kado's own metadataCache reports them. The two namesake images are
# path-qualified, which is how the vault writes a link to a duplicate basename;
# the unique one is bare, which is how it writes everything else.
EMBEDS = {
    DRESDEN_PLACES: [KARTE_PLACES],
    DRESDEN_REISE: [KARTE_REISE],
    DEEP_NOTE: ["karte-jp.png"],
    ROOT_NOTE: [],
    ARCHIVE_MEMO: [],
}

ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
TRAVEL_MOC = "Atlas/200 Maps/Travel (MOC).md"


# ---------------------------------------------------------------------------
# The fake vault — one client for both passes
# ---------------------------------------------------------------------------

class FakeVault:
    """Honours `depth` the way Kado does, and reports embeds via `list_notes`.

    A fake that ignored `depth` would let a lingering `depth=1` pass unnoticed,
    which is the regression Phase 3 exists to remove.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._files = [
            {"path": p, "type": "file", "modified": 1716300000000, "size": 100}
            for p in FILES
        ]
        self._vault_notes = {
            "Atlas/900 Templates/Atomic Note.md": (
                "---\ntype: note\ntags: [{{tags}}]\nup:: {{up}}\n---\n\n"
                "# {{title}}\n\n{{body}}\n"
            ),
            TRAVEL_MOC: "---\ntype: moc\n---\n\n# Travel (MOC)\n\n"
                        "> [!connect] Connections\n> - [[Somewhere else]]\n",
            **{p: f"---\ntitle: {Path(p).stem}\n---\n\nBody of {p}.\n" for p in NOTES},
        }

    # -- Pass 1 ------------------------------------------------------------
    def list_dir(self, path, *, depth=None, limit=500):
        self.calls.append(("list_dir", {"path": path, "depth": depth}))
        if depth == 1:
            return [f for f in self._files if "/" not in f["path"][len(INBOX):]]
        return list(self._files)

    def list_notes(self, path, *, fields=None, depth=None, limit=500):
        self.calls.append(("list_notes", {"path": path, "fields": fields}))
        return [
            {"path": note,
             "links": [{"kind": "embed", "target": t} for t in EMBEDS[note]]}
            for note in NOTES
        ]

    def search_by_frontmatter(self, query, *, path_prefix=None, limit=500,
                              modified_after=None):
        self.calls.append(("search_by_frontmatter", {"query": query}))
        return []

    def read_frontmatter(self, path):
        self.calls.append(("read_frontmatter", {"path": path}))
        return {"content": {}}

    def read_file_bytes(self, path):
        self.calls.append(("read_file_bytes", {"path": path}))
        raise KadoError(f"not found: {path}")

    # -- Pass 2 ------------------------------------------------------------
    def read_note(self, path):
        self.calls.append(("read_note", {"path": path}))
        if path not in self._vault_notes:
            raise KadoError(f"not found: {path}")
        return {"content": self._vault_notes[path], "modified": 0}

    def search_by_name(self, name):
        self.calls.append(("search_by_name", {"name": name}))
        stem = name.removesuffix(".md")
        return [{"path": p} for p in self._vault_notes
                if p.rsplit("/", 1)[-1].removesuffix(".md") == stem]

    def note_exists(self, path):
        self.calls.append(("note_exists", {"path": path}))
        return path in self._vault_notes

    def resolve_stem_to_path(self, stem):
        hits = self.search_by_name(stem)
        return hits[0]["path"] if hits else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(module_name: str, filename: str, directory: Path = SCRIPTS_DIR):
    spec = importlib.util.spec_from_file_location(module_name, directory / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{cmd[1]} failed (exit {result.returncode})\n"
        f"stderr:\n{result.stderr}\nstdout:\n{result.stdout[:2000]}"
    )
    return result


def _item_result(path: str) -> dict:
    """A recorded analyst result. The analyst never emits attachments (ADR-2) —
    the reducer merges those from triage's deterministic resolution map."""
    stem = Path(path).stem
    return {
        "schema_version": "1",
        "stem": stem,
        "item_key": path,
        "path": path,
        "type": "fleeting_note",
        "type_confidence": 0.9,
        "date_relevance": None,
        "issues": [],
        "duration_ms": 100,
        "force_atomic": False,
        "actions": [{
            "kind": "create_atomic_note",
            "source_stem": stem,
            "suggested_title": TITLES[path],
            "template": "Atomic Note.md",
            "location": "Atlas/202 Notes/",
            "candidate_mocs": [
                {"path": TRAVEL_MOC, "score": 0.8, "pre_check": True},
            ],
            "tags_to_add": ["topic/travel"],
            "atomic_note_worthiness": 0.85,
            "classification": None,
        }],
    }


# ---------------------------------------------------------------------------
# The traced run — driven once, asserted at every boundary
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def run(tmp_path_factory) -> dict:
    work = tmp_path_factory.mktemp("t6_2_integration")
    items_dir = work / "items"
    items_dir.mkdir()
    state_path = work / "inbox-state.jsonl"
    client = FakeVault()

    # ---- Pass 1, boundary 1: triage --------------------------------------
    triage = _load("inbox_triage_t6_2", "inbox-triage.py")
    rc = triage.main(
        ["--inbox-path", INBOX, "--output-dir", str(work),
         "--cost-history", str(work / "cost-history.jsonl")],
        client_factory=lambda: client,
    )
    assert rc == 0, f"inbox-triage.main() returned {rc}"
    routing_plan = json.loads((work / "routing-plan.json").read_text(encoding="utf-8"))
    resolved = json.loads(
        (work / "resolved-attachments.json").read_text(encoding="utf-8")
    )
    discovered = [s["path"] for s in routing_plan["fresh_sources"]]

    # ---- boundary 2: run state -------------------------------------------
    for path in discovered:
        for status in ("pending", "running", "done"):
            _run([
                sys.executable, str(SCRIPTS_DIR / "state-update.py"),
                "--state", str(state_path), "--item-key", path,
                "--stem", Path(path).stem, "--path", path,
                "--status", status, "--run-id", RUN_ID,
            ])

    # ---- boundary 3: per-item results (the analyst, fixtured) ------------
    for path in discovered:
        (items_dir / to_filename(path)).write_text(
            json.dumps(_item_result(path), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- boundary 4: suggestions doc -------------------------------------
    doc_path = work / "suggestions-doc.json"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-reducer.py"),
        "--state", str(state_path), "--items-dir", str(items_dir),
        "--run-id", RUN_ID, "--profile", "miyo", "--output", str(doc_path),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--resolved-attachments", str(work / "resolved-attachments.json"),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--threshold", "1", "--no-kado",
        "--cost-history", str(work / "cost-history.jsonl"),
    ])
    suggestions_doc = json.loads(doc_path.read_text(encoding="utf-8"))

    # ---- boundary 5: rendered document + wire ----------------------------
    md_path = work / "suggestions.md"
    wire_path = work / "suggestions-wire.json"
    _run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-render.py"),
        "--input", str(doc_path), "--output", str(md_path),
        "--json-output", str(wire_path),
    ])
    wire = json.loads(wire_path.read_text(encoding="utf-8"))

    # ---- boundary 6: parsed suggestions, both paths ----------------------
    parser = _load("suggestion_parser_t6_2", "suggestion-parser.py")
    parsed_wire = parser.build_from_wire(wire, moc_template="MOC.md")

    approved_md = work / "suggestions-approved.md"
    approved_md.write_text(
        md_path.read_text(encoding="utf-8").replace(
            "- [ ] Approved", "- [x] Approved", 1),
        encoding="utf-8",
    )
    parsed_md_path = work / "parsed-suggestions.json"
    parsed_md_path.write_text(_run([
        sys.executable, str(SCRIPTS_DIR / "suggestion-parser.py"),
        "--file", str(approved_md), "--suggestions-doc", str(doc_path),
    ]).stdout, encoding="utf-8")
    parsed_md = json.loads(parsed_md_path.read_text(encoding="utf-8"))

    # ---- boundary 7: the instruction set ---------------------------------
    out_dir = work / "rendered"
    ir = _load("instruction_render_t6_2", "instruction-render.py")
    ir.KadoClient = lambda: client
    argv = sys.argv
    sys.argv = [
        "instruction-render.py",
        "--suggestions", str(parsed_md_path),
        "--output-dir", str(out_dir),
        "--config", str(GOLDEN_DIR / "vault-config.yaml"),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--upstream-type", "suggestions",
        "--upstream-path", "100 Inbox/t6-2-integration-suggestions.md",
        "--run-id", RUN_ID,
    ]
    try:
        assert ir.main() in (0, 1)
    finally:
        sys.argv = argv
    instructions = json.loads(
        (out_dir / "instructions.json").read_text(encoding="utf-8")
    )

    return {
        "client": client,
        "routing_plan": routing_plan,
        "resolved": resolved,
        "discovered": discovered,
        "state_lines": [
            json.loads(ln) for ln in
            state_path.read_text(encoding="utf-8").splitlines() if ln.strip()
        ],
        "suggestions_doc": suggestions_doc,
        "markdown": md_path.read_text(encoding="utf-8"),
        "wire": wire,
        "parsed_wire": parsed_wire,
        "parsed_md": parsed_md,
        "instructions": instructions,
        "instructions_md": (out_dir / "instructions.md").read_text(encoding="utf-8"),
    }


def _actions(run: dict, kind: str) -> list[dict]:
    return [a for a in run["instructions"]["actions"] if a.get("action") == kind]


# ---------------------------------------------------------------------------
# Boundary 1 — discovery reaches depth 0 and depth 2 alike
# ---------------------------------------------------------------------------

class TestBoundary1Discovery:
    def test_a_root_level_note_and_a_two_level_note_are_both_discovered(self, run):
        """Feature 1: depth is not visible in the output. T2.8's fixture stops
        at one subfolder, so nothing else proves the recursion is unbounded."""
        assert ROOT_NOTE in run["discovered"]
        assert DEEP_NOTE in run["discovered"]
        assert DEEP_NOTE.count("/") == 3, "the deep fixture stopped being deep"

    def test_every_markdown_note_and_no_attachment_became_a_source(self, run):
        assert sorted(run["discovered"]) == sorted(NOTES)
        for asset in (KARTE_PLACES, KARTE_REISE, KARTE_JP, AUDIO):
            assert asset not in run["discovered"], (
                f"{asset} was partitioned as a source item"
            )

    def test_the_audio_is_not_paired_by_a_namesake_in_another_folder(self, run):
        """Feature 5: `100 Inbox/memo.m4a` has no sibling transcript. The only
        `memo.md` in the tree sits in `100 Inbox/Archive/`, and must not
        satisfy it."""
        assert run["routing_plan"]["has_audio"] is True, (
            "an unrelated namesake note elsewhere satisfied the audio file — "
            "the pairing keyed on the stem alone"
        )


# ---------------------------------------------------------------------------
# Boundary 2 — the attachment resolution map
# ---------------------------------------------------------------------------

class TestBoundary2ResolvedAttachments:
    def test_each_namesake_note_resolves_to_its_own_file(self, run):
        """Feature 2: two path-qualified embeds of same-named files resolve
        independently; neither is reported ambiguous."""
        assert run["resolved"][DRESDEN_PLACES]["attachments"] == [KARTE_PLACES]
        assert run["resolved"][DRESDEN_REISE]["attachments"] == [KARTE_REISE]
        for key in (DRESDEN_PLACES, DRESDEN_REISE):
            assert run["resolved"][key]["unresolved_embeds"] == []

    def test_a_bare_embed_two_levels_down_resolves_to_its_own_file(self, run):
        assert run["resolved"][DEEP_NOTE]["attachments"] == [KARTE_JP]

    def test_the_note_with_no_embed_is_absent_from_the_map(self, run):
        """The negative control. A resolver that attached something here would
        file an image the note never referenced."""
        assert ROOT_NOTE not in run["resolved"]
        assert ARCHIVE_MEMO not in run["resolved"]


# ---------------------------------------------------------------------------
# Boundary 3/4 — per-item results and the suggestions document
# ---------------------------------------------------------------------------

class TestBoundary3ItemResults:
    def test_a_two_level_path_round_trips_through_the_result_filename(self, run):
        """T2.8 proves one-level keys survive `to_filename`. Depth is this
        file's half: a filename encoder that dropped a separator would give the
        deep note the same file as a one-level namesake."""
        encoded = to_filename(DEEP_NOTE)
        assert encoded != to_filename("100 Inbox/Japan/Hokkaido Trip.md"), (
            f"two different depths encode to the same result filename: {encoded}"
        )
        assert "/" not in encoded, f"{encoded} is not a flat filename"


class TestBoundary4SuggestionsDocument:
    def test_every_discovered_note_reached_the_document(self, run):
        sections = run["suggestions_doc"]["sections"]
        assert len(sections) == len(NOTES), (
            f"{len(sections)} sections for {len(NOTES)} notes — one was dropped"
        )

    def test_the_attachment_list_reached_the_document_per_note(self, run):
        """The map is joined on the item's own path. A join on the display stem
        would give both Dresdens the same list."""
        by_key = {s["item_key"]: s for s in run["suggestions_doc"]["sections"]}
        got = {
            key: [a["item"].get("attachments") for a in by_key[key]["actions"]]
            for key in (DRESDEN_PLACES, DRESDEN_REISE, DEEP_NOTE, ROOT_NOTE)
        }
        assert got[DRESDEN_PLACES] == [[KARTE_PLACES]]
        assert got[DRESDEN_REISE] == [[KARTE_REISE]]
        assert got[DEEP_NOTE] == [[KARTE_JP]]
        assert got[ROOT_NOTE] == [[]], "the no-embed control acquired an attachment"

    def test_the_root_and_the_deep_note_are_rendered_the_same_way(self, run):
        """Feature 1: depth is not visible in the output. A note two folders
        down reads exactly as a root-level one does — its source link is the
        bare filename, because nothing else in this run shares it."""
        md = run["markdown"]
        assert "**Source:** [[Root Note]]" in md
        assert "**Source:** [[Hokkaido Trip]]" in md
        # T5.1 qualifies a source link ONLY where a filename repeats in the
        # run, so the qualified ones must be exactly the namesake pair — the
        # deep note is two folders down and still renders bare. Attachment
        # lines are excluded: they name files, and a file path belongs there.
        qualified = sorted(
            ln for ln in md.splitlines()
            if ln.startswith("**Source:**") and "100 Inbox/" in ln
        )
        assert qualified == [
            "**Source:** [[100 Inbox/Places/Dresden|Dresden]]",
            "**Source:** [[100 Inbox/Reise/Dresden|Dresden]]",
        ], f"location was added where nothing needed disambiguating: {qualified}"


# ---------------------------------------------------------------------------
# Boundary 5/6 — the wire and both parser paths
# ---------------------------------------------------------------------------

class TestBoundary6BothParserPaths:
    def test_both_paths_carry_every_note(self, run):
        for label, parsed in (("wire", run["parsed_wire"]), ("md", run["parsed_md"])):
            confirmed = [c for c in parsed["confirmed_items"]
                         if c.get("action") != "create_moc"]
            assert len(confirmed) == len(NOTES), (
                f"the {label} path parsed {len(confirmed)} items, expected {len(NOTES)}"
            )

    def test_both_paths_agree_on_each_note_s_attachments(self, run):
        """The attachment list is what the suppression pass keys on. A path
        that loses it turns a clash into a silent double-file."""
        def by_title(parsed):
            return {
                c["title"]: sorted(c.get("attachments") or [])
                for c in parsed["confirmed_items"] if c.get("title")
            }
        assert by_title(run["parsed_wire"]) == by_title(run["parsed_md"])
        assert by_title(run["parsed_md"])["Dresden - Frauenkirche"] == [KARTE_PLACES]
        assert by_title(run["parsed_md"])["Dresden - a different note"] == [KARTE_REISE]
        assert by_title(run["parsed_md"])["Root note takeaway"] == []


# ---------------------------------------------------------------------------
# Boundary 7 — the instruction set
# ---------------------------------------------------------------------------

class TestBoundary7InstructionSet:
    def test_the_two_namesake_attachments_do_not_both_get_filed(self, run):
        """Feature 8 / T6.0's `claimed` fold: the destination folder is flat, so
        `karte.png` can be filed once. The second is not filed."""
        moved = [a["source"] for a in _actions(run, "move_asset")]
        assert sorted(moved) == sorted([KARTE_JP, KARTE_PLACES]), (
            f"both namesake attachments were filed, or neither was: {moved}"
        )

    def test_the_second_namesake_s_own_move_is_suppressed_with_it(self, run):
        """T5.4: filing the note while its image stays behind is the inbox
        residue the attachment feature exists to eliminate. The note whose
        attachment lost the clash keeps its note in the inbox too."""
        moved_titles = {a.get("title") for a in _actions(run, "move_note")}
        assert "Dresden - Frauenkirche" in moved_titles
        assert "Dresden - a different note" not in moved_titles, (
            "the losing namesake's note was filed without its attachment"
        )

    def test_the_other_notes_are_unaffected_by_that_clash(self, run):
        """One note's clash does not hold up another's."""
        moved_titles = {a.get("title") for a in _actions(run, "move_note")}
        assert {"Root note takeaway", "Hokkaido powder days",
                "Archived memo takeaway"} <= moved_titles

    def test_the_losing_note_is_not_deleted_from_the_inbox_either(self, run):
        """The residue guarantee has two halves: the note is not moved, AND its
        source is not deleted. Deleting it while its move was suppressed would
        destroy the note outright."""
        deleted = {a.get("source_path") for a in _actions(run, "delete_source")}
        assert "Dresden" in deleted or DRESDEN_PLACES in deleted, (
            "the winning namesake's source was not cleaned up at all"
        )
        assert len(_actions(run, "delete_source")) == len(NOTES) - 1, (
            "the suppressed note's source was still queued for deletion"
        )

    def test_the_clash_is_reported_in_the_document_the_user_reads(self, run):
        """CON-2: the user approves on what the document says. A suppression
        the document does not mention is a silent skip."""
        md = run["instructions_md"]
        assert "## Skipped — un-appliable actions" in md, (
            "the suppressed attachment is not surfaced to the user at all"
        )
        assert KARTE_REISE in md, f"the skipped file is not named: {md[-800:]}"
        assert ASSET_FOLDER + "karte.png" in md, (
            "the report does not say which destination the two files collided on"
        )

    def test_no_path_leaks_into_a_stem_emitted_to_hashi(self, run):
        """CON-4: whatever identity this design introduces internally, the
        emitted stems stay bare filenames."""
        for action in run["instructions"]["actions"]:
            for field in ("source_stem", "target_stem", "daily_note_stem"):
                value = action.get(field)
                if isinstance(value, str) and value:
                    assert "/" not in value, (
                        f"{action.get('id')} emitted {field}={value!r}"
                    )

    def test_item_key_is_never_emitted_to_hashi(self, run):
        assert "item_key" not in json.dumps(run["instructions"])


# ---------------------------------------------------------------------------
# The flat-inbox instruction-set golden
# ---------------------------------------------------------------------------

# Every line on which today's Pass 2 differs from `ee44cb3`'s for the flat
# fixture, each attributed. The golden is a recording of the OLD document, so
# this list is the whole claim under review: anything diverging that is not
# named here fails, and re-recording at HEAD would destroy the evidence.
DELIBERATE_DELTAS: tuple[tuple[re.Pattern[str], re.Pattern[str], str], ...] = (
    (re.compile(r"^### I\d+ — Delete source note \(content captured in daily note\)$"),
     re.compile(r"^### I\d+ — Delete source note: .+$"),
     "T5.5 (e3aefec): the old heading stated ONE of the five causes "
     "`delete_source` is emitted for, and contradicted the Action line "
     "beneath it for the other four. The heading now names the note."),
)


class TestFlatInboxInstructionGolden:
    """Its own fixture — plain root-level notes, no collisions — recorded from
    the Pass-2 chain at `ee44cb3` by `record.py` beside it.

    Recursion must change WHERE notes are found, never what Pass 2 instructs
    for a flat inbox. One thing in this spec DOES deliberately change a flat
    inbox's instruction document — T5.5's delete-source heading — so the claim
    is not "byte-identical" but "identical except for the deltas named in
    `DELIBERATE_DELTAS`". That distinction is the point: an unnamed change
    fails here even though it is one line, and a named one is reviewed once,
    in this list, rather than absorbed into a re-recorded golden.
    """

    @pytest.fixture(scope="class")
    def replayed(self, tmp_path_factory) -> str:
        record = _load("t6_2_record", "record.py", GOLDEN_DIR)
        return record.normalise(
            record.run_pass2(SCRIPTS_DIR, tmp_path_factory.mktemp("t6_2_golden"))
        )

    @pytest.fixture(scope="class")
    def golden(self) -> str:
        return (GOLDEN_DIR / "instructions.md").read_text(encoding="utf-8")

    def _differing(self, golden: str, replayed: str) -> list[tuple[str, str]]:
        old_lines, new_lines = golden.splitlines(), replayed.splitlines()
        assert len(old_lines) == len(new_lines), (
            f"the instruction document changed length: {len(old_lines)} lines at "
            f"ee44cb3, {len(new_lines)} today — an action was added or dropped"
        )
        return [(a, b) for a, b in zip(old_lines, new_lines) if a != b]

    def test_todays_pass_2_differs_only_where_this_spec_meant_it_to(
        self, golden, replayed,
    ):
        for old, new in self._differing(golden, replayed):
            assert any(
                old_pat.match(old) and new_pat.match(new)
                for old_pat, new_pat, _why in DELIBERATE_DELTAS
            ), (
                "the flat-inbox instruction set changed in a way this spec did "
                "not intend — recursion must change WHERE notes are found, "
                f"never what Pass 2 instructs for a flat inbox.\n"
                f"  ee44cb3: {old!r}\n  today:   {new!r}"
            )

    def test_exactly_the_three_delete_headings_moved(self, golden, replayed):
        """One per `delete_source` action in this fixture. Pinning the count
        stops a fourth, unrelated divergence from hiding behind a delta pattern
        it happens to match."""
        assert len(self._differing(golden, replayed)) == 3

    def test_the_golden_is_not_trivially_empty(self, golden):
        """A normaliser that ate the document would make the comparison
        vacuous. Pin the parts that carry the pipeline's actual output."""
        assert "action_count: 9" in golden
        assert golden.count("- [ ] Applied") == 9
        assert "## New Files" in golden and "## MOC Links" in golden

    def test_only_render_time_stamps_were_normalised(self, replayed):
        """Every placeholder stands for a value minted at render time. If a
        future renderer moves real content onto one of these, this fails."""
        for line in replayed.splitlines():
            if "<NORMALISED>" in line:
                assert line in ("generated: <NORMALISED>",
                                "  updated_at: '<NORMALISED>'"), line
            if "<STAMP>" in line:
                assert "<STAMP>_" in line, line


# ---------------------------------------------------------------------------
# The PRD-feature coverage map
# ---------------------------------------------------------------------------

# (feature_id, description, test_module, test_name). A row whose honest answer
# is "not covered by a test" carries None plus a one-line reason — that is a
# fact, not a claim, and needs no proof. Every other row is walked below and
# its test RUN, not merely collected: a row pointing at a since-xfailed test
# collects cleanly and proves nothing.
FEATURE_COVERAGE: list[tuple[int, str, str | None, str | None]] = [
    (1, "Notes in inbox subfolders are discovered and triaged",
     "tests/test_034_t6_2_pipeline_integration.py",
     "TestBoundary1Discovery::"
     "test_a_root_level_note_and_a_two_level_note_are_both_discovered"),
    (2, "Two notes sharing a filename are handled independently",
     "tests/test_034_t2_8_end_to_end_key_trace.py",
     "TestHop4SuggestionsDoc::test_namesakes_keep_their_own_titles"),
    (3, "Marking a source note as captured targets the right note",
     "tests/test_034_t2_5_captured_mark_targets_right_note.py",
     "test_collision_marks_the_approved_note_and_leaves_the_namesake_untouched"),
    (4, "Force Atomic works for a note in a subfolder",
     "tests/test_034_t4_1_dispatcher_real_path.py",
     "TestSubfolderNoteCarriesRealPath::test_extract_fan_items_resolves_subfolder_note"),
    (5, "Audio files match their transcript by note, not by name alone",
     "tests/test_034_t6_2_pipeline_integration.py",
     "TestBoundary1Discovery::"
     "test_the_audio_is_not_paired_by_a_namesake_in_another_folder"),
    (6, "Every run records how much it cost",
     "tests/test_034_t6_1_cost_history.py",
     "TestHistoryFile::test_several_runs_accumulate_and_none_is_overwritten"),
    (7, "Two notes cannot silently claim the same destination",
     "tests/test_034_t5_2_destination_clash_proposal.py",
     "test_second_claimant_on_one_destination_gets_a_distinct_name"),
    (8, "A note whose attachment cannot be filed stays with it",
     "tests/test_034_t6_2_pipeline_integration.py",
     "TestBoundary7InstructionSet::"
     "test_the_second_namesake_s_own_move_is_suppressed_with_it"),
    # Feature 9 is a call-count claim, not a fixture-boundary assertion: the
    # only honest evidence is a client that records the calls it received, and
    # T3.4 already owns that fake. Pointed there rather than restated weakly here.
    (9, "Discovery does not cost an extra vault listing",
     "tests/test_034_t3_4_phase3_gate.py",
     "TestObservedCallCount::test_exactly_one_inbox_listing_per_run"),
    # Feature 10 is agreement between two predicates on inputs Kado never
    # sends. No end-to-end fixture can produce such an input, so it is pointed
    # at the table-driven agreement test T3.1 shipped for exactly this.
    (10, "The two file-type checks agree",
     "tests/test_034_t3_1_one_file_filter.py",
     "test_discover_files_and_build_inbox_index_agree"),
]


def _resolve_rows() -> list[tuple[int, str, str]]:
    """The rows that claim a test, as pytest node ids."""
    rows = []
    for feature_id, description, module, name in FEATURE_COVERAGE:
        if module is None:
            continue
        rows.append((feature_id, description,
                     f"{module}::{name}" if name else module))
    return rows


def test_every_prd_feature_has_a_row():
    ids = [row[0] for row in FEATURE_COVERAGE]
    assert ids == list(range(1, 11)), f"the map skips or repeats a feature: {ids}"


def test_a_row_without_a_test_states_why():
    """Today every feature is covered, so this guard has nothing to iterate —
    which is stated rather than left to look like a passing check. It fires the
    moment a future row is dropped to None without a reason beside it."""
    uncovered = [row for row in FEATURE_COVERAGE if row[2] is None]
    assert uncovered == [], (
        "a feature lost its test — keep the row, set the module to None, and "
        f"give the reason in the fourth field: {uncovered}"
    )
    for feature_id, _description, _module, name in uncovered:
        assert name and name.startswith("NOT COVERED"), (
            f"feature {feature_id} claims nothing and explains nothing"
        )


def test_every_referenced_module_exists():
    """A typo'd module name reaches the walker as a pytest usage error buried
    in captured stdout. Name it here instead."""
    for feature_id, _description, module, _name in FEATURE_COVERAGE:
        if module is None:
            continue
        assert (REPO_ROOT / module).is_file(), (
            f"feature {feature_id} points at {module}, which does not exist"
        )


@pytest.mark.parametrize(
    ("feature_id", "description", "node_id"),
    _resolve_rows(),
    ids=[f"F{row[0]}" for row in _resolve_rows()],
)
def test_the_referenced_test_currently_passes(feature_id, description, node_id):
    """Run the referenced node, do not merely collect it.

    Collectibility alone would accept a row pointing at a test since marked
    `xfail` or `skip`, which collects cleanly and proves nothing. What this
    does NOT prove is stated in the module docstring.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", node_id, "-q", "-p", "no:cacheprovider",
         "--no-header", "-x"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"Feature {feature_id} ({description}) points at {node_id}, "
        f"which does not currently pass:\n{result.stdout[-3000:]}"
    )
    assert " passed" in result.stdout, (
        f"Feature {feature_id} points at {node_id}, which ran nothing:\n"
        f"{result.stdout[-2000:]}"
    )
