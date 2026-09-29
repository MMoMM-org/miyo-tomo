#!/usr/bin/env python3
# version: 0.3.1
"""test_037_t3_3_embed_rewrite.py — spec 037 T3.3.

T3.1 made `_build_move_asset_actions` recompute a renamed attachment's
destination. Nothing rewrote the note body that still embeds the OLD name —
the exact 2026-09-15 artifact this spec exists to close (README.md
Context): `Atlas/202 Notes/Kai- ....md` embeds `![[Scans/karte.png]]`,
reaching back into an inbox folder the file has left.

Covers, per `docs/XDD/specs/037-asset-destination-collision-is-a-pass1-
decision/plan/phase-3.md` T3.3. `rewrite_renamed_embeds`
(`tomo/scripts/lib/embed_rewrite.py`) is exercised directly for the per-
mutation unit coverage; the last test is the plan's required end-to-end
anchor through the real `instruction-render.py` render loop.

No embed rewriter existed anywhere in this repo before this file —
`lib/attachment_index.py` only reads `![[...]]` (no write path, no fenced-
code handling). `_EMBED_RE` is reused from there per the plan; every other
behaviour below is new.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.embed_rewrite import rewrite_renamed_embeds  # noqa: E402

SOURCE = "100 Inbox/Scans/karte.png"
PROPOSED_NAME = "karte (2).png"


def _remedy(source, remedy, proposed_name=None) -> dict:
    return {"source": source, "remedy": remedy, "proposed_name": proposed_name}


# ---------------------------------------------------------------------------
# Unit coverage of rewrite_renamed_embeds — one mutation per test, named in
# each docstring per the plan.
# ---------------------------------------------------------------------------

def test_path_prefixed_embed_becomes_bare_new_basename():
    """Owner ruling 2026-09-27, and the literal 2026-09-15 artifact: a
    path-prefixed original embed `![[Scans/karte.png]]` becomes the BARE
    basename `![[karte (2).png]]`. Mutation: keep the original folder
    prefix (`Scans/karte (2).png`) — that still points at a folder the
    file has left."""
    body = "See the map: ![[Scans/karte.png]]\n"
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    result = rewrite_renamed_embeds(body, [SOURCE], remedies)
    assert result == "See the map: ![[karte (2).png]]\n"


def test_full_new_path_is_never_hardcoded_into_the_body():
    """Mutation: emit the full new path (asset-folder-qualified) instead of
    the bare basename — this would hard-code `concepts.asset` into every
    rewritten body, breaking the moment the asset folder configuration
    changes."""
    body = "![[Scans/karte.png]]\n"
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    result = rewrite_renamed_embeds(body, [SOURCE], remedies)
    assert "Atlas" not in result
    assert result == "![[karte (2).png]]\n"


def test_note_embedding_it_twice_has_both_rewritten():
    """Mutation: `str.replace` with `count=1` — only the first of two
    embeds of the same renamed attachment in one note body would change."""
    body = "First: ![[Scans/karte.png]]\nSecond: ![[Scans/karte.png]]\n"
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    result = rewrite_renamed_embeds(body, [SOURCE], remedies)
    assert result == (
        "First: ![[karte (2).png]]\nSecond: ![[karte (2).png]]\n"
    )


def test_an_embed_after_an_unclosed_fence_is_left_alone():
    """Mutation: drop the `|\Z` alternative from `_FENCE_RE`, so a fence is
    only recognised when a CLOSING run of backticks exists. An unclosed fence
    then matches nothing at all and every embed after a dangling ``` is
    rewritten as if it were live body text.

    Measured 2026-09-27 (T3.3 compliance review, then again before this fix):
    under the old regex this exact body came back with the embed rewritten.
    Obsidian renders an unclosed fence as code to the end of the note, so
    leaving it alone is the correct reading, not merely the cautious one."""
    body = "Intro.\n```\ncode\n![[Scans/karte.png]]\n"
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    assert rewrite_renamed_embeds(body, [SOURCE], remedies) == body


def test_untouched_attachment_in_the_same_note_is_left_verbatim():
    """A note embedding two attachments, one renamed and one not, keeps the
    untouched one verbatim. Mutation: rewrite every embed in the body
    rather than only the matched target — the untouched embed would be
    corrupted too (e.g. by matching indiscriminately)."""
    other_source = "100 Inbox/Scans/other.png"
    body = "![[Scans/karte.png]] and ![[Scans/other.png]]"
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    result = rewrite_renamed_embeds(body, [SOURCE, other_source], remedies)
    assert result == "![[karte (2).png]] and ![[Scans/other.png]]"


def test_matches_by_basename_not_by_the_full_resolved_path():
    """`item["attachments"]` holds resolved paths while the body holds
    whatever the owner typed. `inbox-triage.py` keeps `embed_target` only
    for UNRESOLVED refs — a resolved one carries no as-typed text at all, so
    a bare `![[karte.png]]` in the body has no path component to compare.
    Mutation: match on the full resolved path (`100 Inbox/Scans/karte.png`)
    — that finds nothing for a bare embed."""
    body = "![[karte.png]]"
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    result = rewrite_renamed_embeds(body, [SOURCE], remedies)
    assert result == "![[karte (2).png]]"


def test_alias_and_anchor_survive_the_rewrite():
    """An embed carrying an alias and an anchor survives with both intact.
    Mutation: replace the whole `![[...]]` span rather than only its target
    portion — the alias/anchor text would be lost."""
    body = "![[Scans/karte.png|Site Map#Legend]]"
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    result = rewrite_renamed_embeds(body, [SOURCE], remedies)
    assert result == "![[karte (2).png|Site Map#Legend]]"


def test_embed_inside_a_fenced_code_block_is_left_alone():
    """Mutation: rewrite without the fence guard — a `![[...]]` shown as
    example text inside a fenced code block would be rewritten as if it
    were a real dependency of the note."""
    body = (
        "Before the fence: ![[Scans/karte.png]]\n"
        "```\n"
        "Example embed syntax: ![[Scans/karte.png]]\n"
        "```\n"
    )
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    result = rewrite_renamed_embeds(body, [SOURCE], remedies)
    assert result == (
        "Before the fence: ![[karte (2).png]]\n"
        "```\n"
        "Example embed syntax: ![[Scans/karte.png]]\n"
        "```\n"
    )


def test_plain_link_without_the_bang_is_left_alone():
    """A plain `[[...]]` link is a deliberate reference, not an embed.
    Mutation: drop the `!` from the match — `attachment_index.py`'s
    `_EMBED_RE` is the shape reused here; this is regression insurance on
    borrowed reader logic, not coverage of new rewrite behaviour."""
    body = "See [[Scans/karte.png]] for details."
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    result = rewrite_renamed_embeds(body, [SOURCE], remedies)
    assert result == body


def test_non_rename_remedies_leave_the_body_unchanged():
    """`keep_in_inbox` and `ignore` never change the attachment's filed
    name, so neither must touch the body. Covers both remedies in one test
    since both routes share the same "leave body alone" outcome."""
    body = "![[Scans/karte.png]]"
    for remedy in ("keep_in_inbox", "ignore"):
        remedies = {SOURCE: _remedy(SOURCE, remedy)}
        assert rewrite_renamed_embeds(body, [SOURCE], remedies) == body


def test_a_rename_with_null_proposed_name_leaves_the_body_unchanged():
    """A `rename` whose `proposed_name` is `None` (the markdown/JSON desync
    route, T3.1) degrades to `keep_in_inbox` at the move-action layer — the
    attachment is never actually renamed, so the body must not be either.

    Mutation: remove BOTH the early `if not new_name: continue` guard and
    `_replace`'s `if new_basename is None` check — the embed then becomes the
    literal `![[None]]`.

    Both, deliberately, because neither alone bites *for this body*: measured
    2026-09-27, each guard is covered by the other here, so removing either one
    on its own leaves this assertion green.

    Neither is redundant, and the late check is the more load-bearing of the
    two — an earlier version of this docstring called it protection for "a map
    built by some future caller", which undersells it. `renames.get(...)`
    returns `None` for any embed whose basename is not in the map at all, which
    is the ORDINARY case of a note embedding one renamed attachment and one
    untouched one. Measured with the late check removed and two attachments,
    one renamed:

        '![[karte (2).png]] and ![[None]]'

    So the late check guards today's multi-attachment path, and the early guard
    keeps the rename map's declared `dict[str, str]` type honest. Recorded so
    the next reader does not "simplify" either one on the evidence of a green
    suite — and `test_untouched_attachment_in_the_same_note_is_left_verbatim`
    is the test that actually fails when the late check goes."""
    body = "![[Scans/karte.png]]"
    remedies = {SOURCE: _remedy(SOURCE, "rename", proposed_name=None)}
    assert rewrite_renamed_embeds(body, [SOURCE], remedies) == body


def test_no_matching_remedy_at_all_leaves_the_body_unchanged():
    """A source with no remedy record at all (conflict gone by Pass 2, or
    never existed) must not perturb an unrelated embed."""
    body = "![[Scans/karte.png]]"
    assert rewrite_renamed_embeds(body, [SOURCE], {}) == body


# ---------------------------------------------------------------------------
# End-to-end anchor (plan T3.3 bullet 4): render a fixture whose item embeds
# a renamed attachment through the REAL instruction-render.py render loop,
# read the WRITTEN file back off disk, and cross-check its embed against the
# emitted move_asset action's destination basename — not against the test's
# own re-typed expectation of proposed_name.
# ---------------------------------------------------------------------------

_spec = importlib.util.spec_from_file_location(
    "instruction_render_t037_t3_3", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render_t037_t3_3"] = ir
_spec.loader.exec_module(ir)

_IR_CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
    "callouts.editable": ["NOTE"],
}


def test_end_to_end_written_file_agrees_with_the_emitted_move_asset(
    monkeypatch, tmp_path
):
    """Render a real confirmed item whose attachment is renamed by remedy,
    through the real `instruction-render.py` loop (real `build_actions`,
    unmocked). Read the file the loop actually wrote to disk and assert its
    embed's basename equals the `move_asset` action's destination basename
    — the success condition the plan states: no rendered note references a
    name the run did not file, asserted against the emitted actions rather
    than against a literal re-typed from `proposed_name`.

    Mutation this anchors against: emitting the move without the rewrite —
    the written file would still embed `Scans/karte.png`, a path the move
    has just vacated, while the emitted action moves the file elsewhere."""
    confirmed_items = [{
        "id": "S01",
        "action": None,
        "title": "Kai",
        "template": "templates/atomic.md",
        "source_path": "karte.md",
        "tags": [],
        "parent_moc": "",
        "parent_mocs": [],
        "destination": "Atlas/202 Notes/",
        "summary": "",
        "attachments": [SOURCE],
        "candidate_mocs": [],
    }]
    suggestions = {
        "confirmed_items": confirmed_items,
        "daily_updates": [],
        "skipped": [],
        "attachment_conflict_remedies": [
            {"source": SOURCE, "remedy": "rename", "proposed_name": PROPOSED_NAME},
        ],
    }
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps(suggestions), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(ir, "load_config", lambda _path: dict(_IR_CFG))
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "read_template", lambda _client, _ref: "# {{title}}\n{{body}}\n")
    monkeypatch.setattr(ir, "read_note_body", lambda *_a, **_kw: "")
    monkeypatch.setattr(
        ir, "render_via_script",
        lambda *_a, **_kw: "# Kai\n\nSee the map: ![[Scans/karte.png]]\n",
    )

    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys, "argv",
        [
            "instruction-render.py",
            "--suggestions", str(suggestions_file),
            "--output-dir", str(out_dir),
            "--config", str(cfg_file),
        ],
    )
    rc = ir.main()
    assert rc == 0

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 1
    rendered_file = manifest[0]["rendered_file"]
    written = (out_dir / rendered_file).read_text(encoding="utf-8")

    instructions = json.loads(
        (out_dir / "instructions.json").read_text(encoding="utf-8")
    )
    move_asset_actions = [
        a for a in instructions["actions"]
        if a["action"] == "move_asset" and a["source"] == SOURCE
    ]
    assert len(move_asset_actions) == 1
    emitted_basename = move_asset_actions[0]["destination"].rsplit("/", 1)[-1]

    assert f"![[{emitted_basename}]]" in written, (
        f"written note does not embed the basename the run actually filed "
        f"the attachment under ({emitted_basename!r}): {written!r}"
    )
    assert "Scans/karte.png" not in written, (
        f"written note still references the vacated inbox path: {written!r}"
    )


def test_two_confirmed_items_embedding_one_renamed_attachment_are_both_rewritten(
    monkeypatch, tmp_path
):
    """Two DIFFERENT confirmed items in one run, both embedding the same
    renamed attachment — both written bodies must name the new basename.

    Mutation: hoist the `rewrite_renamed_embeds(...)` call out of the
    per-item loop so it runs once, on the first item only. The second note
    is then written with the vacated `Scans/karte.png` still in it.

    This test replaces an earlier one that called `rewrite_renamed_embeds`
    twice with two separate bodies and asserted both came back rewritten.
    That could not fail: the function is stateless and rebuilds its rename
    map from its arguments on every call, so "rewrite only the first owner"
    is not expressible against it — the named mutation could never bite.
    Measured 2026-09-27. The plan bullet is a property of the RENDER LOOP
    (`owner_source_items`, `render_actions.py:720`, is a list because several
    confirmed items can embed one attachment), so it is asserted here,
    through the loop, against both files on disk.
    """
    def _item(item_id, title, source_path):
        return {
            "id": item_id, "action": None, "title": title,
            "template": "templates/atomic.md", "source_path": source_path,
            "tags": [], "parent_moc": "", "parent_mocs": [],
            "destination": "Atlas/202 Notes/", "summary": "",
            "attachments": [SOURCE], "candidate_mocs": [],
        }

    suggestions = {
        "confirmed_items": [
            _item("S01", "Kai", "kai.md"),
            _item("S02", "Zwei", "zwei.md"),
        ],
        "daily_updates": [],
        "skipped": [],
        "attachment_conflict_remedies": [
            {"source": SOURCE, "remedy": "rename", "proposed_name": PROPOSED_NAME},
        ],
    }
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps(suggestions), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(ir, "load_config", lambda _path: dict(_IR_CFG))
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "read_template", lambda _c, _r: "# {{title}}\n{{body}}\n")
    monkeypatch.setattr(ir, "read_note_body", lambda *_a, **_kw: "")
    monkeypatch.setattr(
        ir, "render_via_script",
        lambda *_a, **_kw: "Both notes embed it: ![[Scans/karte.png]]\n",
    )

    out_dir = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "instruction-render.py",
        "--suggestions", str(suggestions_file),
        "--output-dir", str(out_dir),
        "--config", str(cfg_file),
    ])
    assert ir.main() == 0

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 2, f"both items must render: {manifest}"

    for entry in manifest:
        written = (out_dir / entry["rendered_file"]).read_text(encoding="utf-8")
        assert f"![[{PROPOSED_NAME}]]" in written, (
            f"{entry['rendered_file']} was not rewritten: {written!r}"
        )
        assert "Scans/karte.png" not in written, (
            f"{entry['rendered_file']} still names the vacated path: {written!r}"
        )


# ---------------------------------------------------------------------------
# Fence faults the original single-regex guard had. All three measured against
# the old `_FENCE_RE` on 2026-09-27 (T3.3 code-quality review) before the line
# scanner replaced it.
# ---------------------------------------------------------------------------

def test_a_shorter_closing_run_does_not_end_a_longer_fence():
    """Mutation: close a fence on the first run of 3+ backticks regardless of
    the opening run's length — i.e. the single-regex guard this replaced.

    A 4-backtick fence containing a bare 3-backtick line (how a PKM note
    *about* markdown is written) then ended early, and the real embed still
    inside the outer fence was REWRITTEN. Measured under the old regex:
    `![[karte (2).png]]` came back inside the code block. That is the inverse
    of the defect T3.3 exists to fix — not a stale reference surviving, but a
    fenced example silently corrupted. CommonMark closes a fence only on a run
    of the same character at least as long as the opening one, which is why
    this is a line scan and not a pattern (`re` has no variable-length
    backreference comparison)."""
    body = "Doc example:\n````\n```\n![[Scans/karte.png]]\n````\nEnd.\n"
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    assert rewrite_renamed_embeds(body, [SOURCE], remedies) == body


def test_a_crlf_closing_fence_still_closes_the_fence():
    """Mutation: anchor the closing-fence match on `[ \\t]*$` against the raw
    line, so a `\\r\\n` line ending defeats it.

    The fence then never closed, the unclosed-fence fallback swallowed the
    rest of the note, and a real embed AFTER the code block was silently left
    alone — a missed rewrite rather than a corruption, but the same class.
    Measured under the old regex: the trailing embed was not rewritten."""
    body = "Intro.\r\n```\r\ncode\r\n```\r\nAfter ![[Scans/karte.png]]\r\n"
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    result = rewrite_renamed_embeds(body, [SOURCE], remedies)
    assert "![[karte (2).png]]" in result, (
        f"an embed after a CRLF-closed fence must still be rewritten: {result!r}"
    )


def test_a_tilde_fence_is_recognised_too():
    """Mutation: match only backtick fences. CommonMark allows `~~~`, and a
    note discussing backtick syntax is precisely where one is used — so the
    embed inside would be rewritten as if it were a live dependency."""
    body = "~~~\n![[Scans/karte.png]]\n~~~\n"
    remedies = {SOURCE: _remedy(SOURCE, "rename", PROPOSED_NAME)}
    assert rewrite_renamed_embeds(body, [SOURCE], remedies) == body


def test_a_non_rename_remedy_carrying_a_proposed_name_changes_nothing():
    """Mutation: drop the `remedy != "rename"` filter (`embed_rewrite.py`),
    keeping only the falsy-`proposed_name` guard.

    This is the case that filter exists for, and nothing tested it before
    2026-09-27. `_join_attachment_conflict_remedies` (`suggestion-parser.py`)
    joins `proposed_name` onto EVERY remedy record from the structured doc,
    not only renames — so `{remedy: "keep_in_inbox", proposed_name: "karte
    (2).png"}` is the ordinary production shape, not a contrived one. The
    owner said keep it in the inbox; the name Pass 1 *would* have used is
    still carried alongside. Rewriting the body to it would point the note at
    a file the run deliberately did not file.

    Measured: with both this and `test_a_rename_with_null_proposed_name_...`
    as they stood before, removing either guard left every assertion green —
    each was covered by the other guard downstream."""
    remedies = {SOURCE: _remedy(SOURCE, "keep_in_inbox", PROPOSED_NAME)}
    body = "![[Scans/karte.png]]"
    assert rewrite_renamed_embeds(body, [SOURCE], remedies) == body

    remedies_ignore = {SOURCE: _remedy(SOURCE, "ignore", PROPOSED_NAME)}
    assert rewrite_renamed_embeds(body, [SOURCE], remedies_ignore) == body
