#!/usr/bin/env python3
# version: 0.2.0
"""test_034_t4_1_dispatcher_real_path.py — the FAN dispatcher uses the item's real path.

Covers T4.1 (XDD 034 Phase 4). Two defects close together here:

  1. `force-atomic-handling/SKILL.md` reconstructed the note path as
     `<inbox_path>/<stem>.md`, which names a file that does not exist for ANY
     subfolder note — with or without a name clash `[ref: PRD/Feature 4]`.
  2. T2.1 had to set `force_atomic_items[*].item_key` to the REVIEW DOCUMENT's
     path, because no note path was available at the extraction sites. Two FAN
     items in one document therefore shared one key.

Both are fixed by carrying the item's own vault-relative path. Where the
reference is genuinely ambiguous — two inbox notes share the filename a bare
`Source: [[stem]]` names — the pipeline declines rather than guessing
`[ref: PRD/Business Rule 7]`, and says so on stderr.

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate as json_validate  # noqa: E402

SKILL_PATH = (
    REPO_ROOT / "tomo" / "dot_claude" / "skills" / "force-atomic-handling" / "SKILL.md"
)

INBOX_PATH = "100 Inbox/"
DOC_PATH = INBOX_PATH + "2026-05-22_1432_suggestions.md"

# The two same-stem notes the spec's worked example uses.
DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
DRESDEN_REISE = "100 Inbox/Reise/Dresden.md"

# Subfolder + space + mixed case: a normalising, lowercasing or slugging
# implementation collapses this into something else (ADR-1 trap).
SUBFOLDER_SPACE_MIXED_CASE = "100 Inbox/Places/Dresden Impressionen.md"

ROOT_LEVEL_NOTE = "100 Inbox/Furano.md"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "inbox_triage", SCRIPTS_DIR / "inbox-triage.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_schema() -> dict:
    return json.loads(
        (REPO_ROOT / "tomo" / "schemas" / "routing-plan.schema.json").read_text(
            encoding="utf-8"
        )
    )


# ---------------------------------------------------------------------------
# Fakes (same shape as test_034_t2_1_triage_emits_item_key.py)
# ---------------------------------------------------------------------------

class FakeKadoClient:
    def __init__(
        self,
        *,
        listdir_items=None,
        frontmatter_responses=None,
        read_note_responses=None,
    ):
        self._listdir_items = listdir_items or []
        self._frontmatter_responses = frontmatter_responses or {}
        self._read_note_responses = read_note_responses or {}

    def list_dir(self, path: str, *, depth: int = None, limit: int = 500) -> list:
        return self._listdir_items

    def list_notes(self, path: str, *, fields=None, depth=None, limit: int = 500):
        return []

    def search_by_frontmatter(
        self, query: str, *, path_prefix=None, limit: int = 500, modified_after=None,
    ) -> list:
        return self._frontmatter_responses.get(query, [])

    def read_note(self, path: str) -> dict:
        return self._read_note_responses.get(path, {"content": "", "modified": 0})

    def read_frontmatter(self, path: str) -> dict:
        return {"content": {}}

    def read_file_bytes(self, path: str) -> bytes:
        from lib.kado_client import KadoError

        raise KadoError(f"not found: {path}")


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


def _empty_frontmatter() -> dict:
    return {
        "tomo.state=pending-approval": [],
        "tomo.state=pending-accept": [],
        "tomo.state=captured": [],
        "tomo.doc_type=instructions": [],
    }


def _suggestions_body(fan_stems: list[str]) -> str:
    """An approved suggestions doc with one ticked FAN checkbox per stem."""
    lines = [
        "---", "type: tomo-suggestions", "---", "",
        "# Inbox Suggestions", "", "- [x] Approved", "",
        "## Suggestions", "",
    ]
    for i, stem in enumerate(fan_stems, start=1):
        lines += [
            f"### S{i:02d} — {stem} reflections", "",
            f"**Source:** [[{stem}]]", "",
            "**Decision (atomic note):**",
            "- [x] Approve",
            "- [x] Force Atomic Note (create/keep a standalone note for this item)",
            "",
        ]
    return "\n".join(lines)


def _index(*paths: str) -> dict[str, list[str]]:
    """The run's inbox listing indexed by basename, as discover() builds it."""
    from lib.attachment_index import build_inbox_index

    return build_inbox_index([_listdir_item(p) for p in paths])


def _client(doc_body: str, note_paths: list[str]) -> FakeKadoClient:
    return FakeKadoClient(
        listdir_items=[_listdir_item(DOC_PATH)]
        + [_listdir_item(p) for p in note_paths],
        frontmatter_responses={
            **_empty_frontmatter(),
            "tomo.state=pending-approval": [
                _fm_hit(DOC_PATH, "suggestions", "pending-approval"),
            ],
        },
        read_note_responses={DOC_PATH: {"content": doc_body, "modified": 0}},
    )


# ---------------------------------------------------------------------------
# 1. Two FAN items sharing a stem must not share an item_key
# ---------------------------------------------------------------------------

class TestSameStemDistinctPaths:
    def test_two_fan_items_same_stem_distinct_paths_get_distinct_item_keys(self):
        """The wire names each item's own path — two Dresdens stay two items.

        Order-sensitive equality, not a bare inequality: a join that resolved
        both stems but swapped the two paths would satisfy `!=`.
        """
        mod = _load_module()
        wire = {
            "schema_version": "1",
            "suggestions": [
                {"id": "S01", "stem": "Dresden", "item_key": DRESDEN_PLACES,
                 "suppressed": True, "force_atomic": True},
                {"id": "S02", "stem": "Dresden", "item_key": DRESDEN_REISE,
                 "suppressed": True, "force_atomic": True},
            ],
            "daily_updates": [],
        }

        items = mod._extract_fan_items_from_wire(
            wire, DOC_PATH, inbox_index=_index(DRESDEN_PLACES, DRESDEN_REISE),
        )

        assert len(items) == 2, "same-stem items were deduplicated into one"
        keys = [i["item_key"] for i in items]
        assert keys[0] != keys[1]
        assert keys == [DRESDEN_PLACES, DRESDEN_REISE]
        assert [i["stem"] for i in items] == ["Dresden", "Dresden"]

    def test_markdown_same_stem_is_ambiguous_and_declines(self, capsys):
        """A bare `Source: [[Dresden]]` cannot say WHICH Dresden.

        Business Rule 7: decline rather than choose. The decline is announced,
        naming the document and the reference, so it is never silent.
        """
        mod = _load_module()
        body = _suggestions_body(["Dresden", "Dresden"])

        items = mod._extract_fan_items(
            body, DOC_PATH, inbox_index=_index(DRESDEN_PLACES, DRESDEN_REISE),
        )

        assert items == []
        err = capsys.readouterr().err
        assert "Dresden" in err
        assert DOC_PATH in err
        assert "declined" in err.lower()


# ---------------------------------------------------------------------------
# 2. A subfolder note dispatches with its real path
# ---------------------------------------------------------------------------

class TestSubfolderNoteCarriesRealPath:
    def test_extract_fan_items_resolves_subfolder_note(self):
        mod = _load_module()
        body = _suggestions_body(["Dresden Impressionen"])

        items = mod._extract_fan_items(
            body, DOC_PATH, inbox_index=_index(SUBFOLDER_SPACE_MIXED_CASE),
        )

        assert len(items) == 1
        assert items[0]["item_key"] == SUBFOLDER_SPACE_MIXED_CASE
        assert items[0]["stem"] == "Dresden Impressionen"
        # source_path keeps its own meaning: the document the box was ticked in.
        assert items[0]["source_path"] == DOC_PATH

    def test_subfolder_note_routing_plan_carries_real_path(self, tmp_path):
        """End-to-end: routing-plan.json names the note, not the review doc."""
        mod = _load_module()
        client = _client(
            _suggestions_body(["Dresden Impressionen"]), [SUBFOLDER_SPACE_MIXED_CASE],
        )

        rc = mod.main(
            ["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path)],
            client_factory=lambda: client,
        )
        assert rc == 0

        plan = json.loads((tmp_path / "routing-plan.json").read_text(encoding="utf-8"))
        assert plan["action"] == "fan-resolve"
        assert len(plan["force_atomic_items"]) == 1
        item = plan["force_atomic_items"][0]
        # Character-for-character: subfolder kept, space kept, case kept.
        assert item["item_key"] == SUBFOLDER_SPACE_MIXED_CASE
        assert item["item_key"] != DOC_PATH
        json_validate(instance=plan, schema=_load_schema())

    def test_daily_log_entry_resolves_to_its_own_note(self):
        """The daily-notes-updates FAN checkbox path resolves too (#165)."""
        mod = _load_module()
        wire = {
            "schema_version": "1",
            "suggestions": [],
            "daily_updates": [
                {"date": "2026-04-17", "log_entries": [
                    {"source_stem": "Dresden Impressionen", "force_atomic_note": True},
                ]},
            ],
        }

        items = mod._extract_fan_items_from_wire(
            wire, DOC_PATH, inbox_index=_index(SUBFOLDER_SPACE_MIXED_CASE),
        )

        assert len(items) == 1
        assert items[0]["item_key"] == SUBFOLDER_SPACE_MIXED_CASE


# ---------------------------------------------------------------------------
# 3. A root-level note behaves exactly as before
# ---------------------------------------------------------------------------

class TestRootLevelNoteUnchanged:
    def test_root_level_note_entry_unchanged(self, tmp_path):
        mod = _load_module()
        client = _client(_suggestions_body(["Furano"]), [ROOT_LEVEL_NOTE])

        rc = mod.main(
            ["--inbox-path", INBOX_PATH, "--output-dir", str(tmp_path)],
            client_factory=lambda: client,
        )
        assert rc == 0

        plan = json.loads((tmp_path / "routing-plan.json").read_text(encoding="utf-8"))
        assert plan["action"] == "fan-resolve"
        assert plan["force_atomic_items"] == [
            {
                "stem": "Furano",
                "item_key": ROOT_LEVEL_NOTE,
                "source_path": DOC_PATH,
            }
        ]
        json_validate(instance=plan, schema=_load_schema())


# ---------------------------------------------------------------------------
# 4. The runtime instruction: no reconstruction survives
# ---------------------------------------------------------------------------

def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _dispatch_step() -> str:
    """The `### 3. Fan-out dispatch` step only.

    A whole-file substring check is how a wrong value survived a green scan
    earlier in this spec — every assertion below is made against the step that
    actually carries the instruction.
    """
    text = _skill_text()
    start = text.index("### 3. Fan-out dispatch")
    end = text.index("\n### ", start + 1)
    return text[start:end]


class TestSkillFileInstruction:
    def test_no_reconstruction_pattern_in_skill_file(self):
        """`<inbox_path>/<stem>.md` is gone — not widened, gone."""
        text = _skill_text()
        assert "<inbox_path>/<stem>" not in text
        # Any composition of inbox_path with a per-item placeholder is a
        # reconstruction, whatever the second half is called.
        recon = re.findall(r"<inbox_path>/<[a-z_]+>", text)
        assert recon == [], f"surviving reconstruction(s): {recon}"

    def test_dispatch_step_passes_the_carried_path(self):
        """Both `path` and `item_key` read the item's carried value."""
        step = _dispatch_step()
        assert re.search(r"^\s*path\s*=\s*\"<item_key>\"", step, re.MULTILINE)
        assert re.search(r"^\s*item_key\s*=\s*\"<item_key>\"", step, re.MULTILINE)

    def test_strict_block_present_with_review_document_hazard(self):
        """The guard survives the change: source_path is the review document."""
        step = _dispatch_step()
        strict_lines = [ln for ln in step.splitlines() if ln.startswith("# STRICT")]
        assert strict_lines, "the STRICT block was removed from the dispatch step"
        joined = "\n".join(
            ln for ln in step.splitlines() if ln.startswith("#")
        )
        assert "source_path" in joined
        assert "NEVER use it as path" in joined
        assert "Why:" in joined


# ---------------------------------------------------------------------------
# 5. One narrowing rule, three call sites (PRD Business Rule 9)
# ---------------------------------------------------------------------------

# The rule — strip alias/anchors, match by basename, narrow by path suffix —
# was hand-copied three times. It drifted immediately: the FAN copy stripped
# `|` and `#` but not `^`, so a block-anchored reference failed to resolve
# against an index that plainly contained it. All three sites now route
# through lib.attachment_index.narrow_candidates.

AGREEMENT_INDEX = {
    "Dresden.md": ["100 Inbox/Places/Dresden.md", "100 Inbox/Reise/Dresden.md"],
    "Furano.md": ["100 Inbox/Furano.md"],
}

# (reference, the single path it must resolve to)
AGREEING_REFERENCES = [
    ("Furano.md", "100 Inbox/Furano.md"),                        # bare
    ("Furano.md|Furano", "100 Inbox/Furano.md"),                 # alias
    ("Furano.md#Trip notes", "100 Inbox/Furano.md"),             # heading anchor
    ("Furano.md^a1b2c3", "100 Inbox/Furano.md"),                 # block anchor
    ("Places/Dresden.md", "100 Inbox/Places/Dresden.md"),        # path-qualified
    ("Reise/Dresden.md|Dresden", "100 Inbox/Reise/Dresden.md"),  # both
]


class TestOneNarrowingRule:
    def test_block_anchor_reference_resolves(self):
        """`^block` is an anchor, not part of the filename — the FAN copy's gap."""
        mod = _load_module()

        note_path, count = mod._resolve_fan_note(
            "Dresden Impressionen^a1b2c3", _index(SUBFOLDER_SPACE_MIXED_CASE),
        )

        assert note_path == SUBFOLDER_SPACE_MIXED_CASE
        assert count == 1

    def test_all_three_sites_agree_on_the_same_reference(self):
        """resolve_attachments, _candidate_count and _resolve_fan_note agree.

        Three call sites, one rule. Each adapts the shared result to its own
        return shape; none re-implements the narrowing.
        """
        mod = _load_module()
        from lib.attachment_index import resolve_attachments

        for reference, expected in AGREEING_REFERENCES:
            refs = resolve_attachments([reference], AGREEMENT_INDEX)
            assert refs[0].status == "resolved", reference
            assert refs[0].resolved_path == expected, reference

            assert mod._candidate_count(reference, AGREEMENT_INDEX) == 1, reference

            note_path, count = mod._resolve_fan_note(reference, AGREEMENT_INDEX)
            assert note_path == expected, reference
            assert count == 1, reference

    def test_all_three_sites_agree_that_a_reference_is_ambiguous(self):
        """Agreement has to hold on the failing side too, not just the happy one."""
        mod = _load_module()
        from lib.attachment_index import resolve_attachments

        refs = resolve_attachments(["Dresden.md"], AGREEMENT_INDEX)
        assert refs[0].status == "ambiguous"
        assert refs[0].resolved_path is None
        assert mod._candidate_count("Dresden.md", AGREEMENT_INDEX) == 2
        assert mod._resolve_fan_note("Dresden.md", AGREEMENT_INDEX) == (None, 2)

    def test_fan_site_supplies_the_note_extension_a_wikilink_omits(self):
        """The only difference the FAN site is allowed to carry: `[[Furano]]`
        names a note, so `.md` is appended — after stripping, never before."""
        mod = _load_module()

        assert mod._resolve_fan_note("Furano", AGREEMENT_INDEX) == (
            "100 Inbox/Furano.md", 1,
        )
        # Strip-then-append: appending first would search for "Furano|x.md".
        assert mod._resolve_fan_note("Furano|Nice trip", AGREEMENT_INDEX) == (
            "100 Inbox/Furano.md", 1,
        )


# ---------------------------------------------------------------------------
# 6. The remaining decline branches
# ---------------------------------------------------------------------------

class TestDeclineBranches:
    def test_wire_daily_entry_with_no_resolvable_note_declines(self, capsys):
        """The wire fallback: a daily entry whose stem matches no suggestion
        and no inbox note (`_add_by_stem`'s resolution branch)."""
        mod = _load_module()
        wire = {
            "schema_version": "1",
            "suggestions": [],
            "daily_updates": [
                {"date": "2026-04-17", "log_entries": [
                    {"source_stem": "Vanished", "force_atomic_note": True},
                ]},
            ],
        }

        items = mod._extract_fan_items_from_wire(
            wire, DOC_PATH, inbox_index=_index(ROOT_LEVEL_NOTE),
        )

        assert items == []
        err = capsys.readouterr().err
        assert "Vanished" in err
        assert "declined" in err.lower()

    def test_wire_daily_entry_ambiguous_between_two_suggestions_declines(self, capsys):
        """Two suggestions share the stem, so the daily entry's `source_stem`
        cannot say which note it belongs to — and the listing cannot either."""
        mod = _load_module()
        wire = {
            "schema_version": "1",
            "suggestions": [
                {"id": "S01", "stem": "Dresden", "item_key": DRESDEN_PLACES,
                 "suppressed": False, "force_atomic": False},
                {"id": "S02", "stem": "Dresden", "item_key": DRESDEN_REISE,
                 "suppressed": False, "force_atomic": False},
            ],
            "daily_updates": [
                {"date": "2026-04-17", "log_entries": [
                    {"source_stem": "Dresden", "force_atomic_note": True},
                ]},
            ],
        }

        items = mod._extract_fan_items_from_wire(
            wire, DOC_PATH, inbox_index=_index(DRESDEN_PLACES, DRESDEN_REISE),
        )

        assert items == []
        assert "declined" in capsys.readouterr().err.lower()

    def test_markdown_note_no_longer_in_inbox_declines(self, capsys):
        """Zero candidates: the note was moved, renamed or already consumed."""
        mod = _load_module()
        body = _suggestions_body(["Vanished"])

        items = mod._extract_fan_items(
            body, DOC_PATH, inbox_index=_index(ROOT_LEVEL_NOTE),
        )

        assert items == []
        err = capsys.readouterr().err
        assert "Vanished" in err
        assert "no inbox note of that name" in err

    def test_zero_candidate_decline_names_a_different_cause_than_ambiguity(self, capsys):
        """The two declines are not interchangeable — the user's next action
        differs (find the note vs. disambiguate two)."""
        mod = _load_module()

        mod._report_fan_decline("Gone", DOC_PATH, 0)
        missing = capsys.readouterr().err
        mod._report_fan_decline("Dresden", DOC_PATH, 2)
        ambiguous = capsys.readouterr().err

        assert "no inbox note of that name" in missing
        assert "share that filename" in ambiguous
        assert missing != ambiguous
