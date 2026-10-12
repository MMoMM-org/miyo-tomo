#!/usr/bin/env python3
"""test_039_t2_1_breaks_link_and_unsafe_sequence.py — spec 039 T2.1 (F5-AC1..4, AC7).

`check_typed_name` gains two refusal reasons:
  - `breaks_link`: edge whitespace and any of `# ^ [ ]` (a wikilink cannot
    carry them), phrased as "would break the link", never "Obsidian does not
    allow".
  - `unsafe_sequence`: `{{`, `<%`, or a control character. Before this task
    such a name reached `_check_path_shape` and aborted ALL of Pass 2 (exit 2).

Check order: blank, separator, edge whitespace (breaks_link), `{{`/`<%`
and control chars [\\x00-\\x1f\\x7f] (unsafe_sequence), forbidden, `# ^ [ ]`
(breaks_link). Edge tab is `breaks_link`; `<%` outranks forbidden because `<`
is a FORBIDDEN_CHARS member.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.obsidian_filename import sanitize_stem  # noqa: E402
from lib.render_actions import _typed_name_refusal_reason  # noqa: E402
from lib.typed_name_check import REFUSAL_REASONS, check_typed_name  # noqa: E402


@pytest.mark.parametrize("name", [" a.png", "a.png ", "\ta.png", "a.png\t", "  a.png  "])
def test_edge_whitespace_breaks_link(name):
    v = check_typed_name(name)
    assert (v.ok, v.reason) == (False, "breaks_link")
    assert v.name == name


@pytest.mark.parametrize("ch", ["#", "^", "[", "]"])
@pytest.mark.parametrize("fmt", ["{c}a.png", "a{c}b.png", "a.png{c}"])
def test_link_breaking_characters_anywhere(ch, fmt):
    v = check_typed_name(fmt.format(c=ch))
    assert (v.ok, v.reason) == (False, "breaks_link")


def test_existing_order_is_kept():
    assert check_typed_name("   ").reason == "blank"
    assert check_typed_name("a/b.png").reason == "separator_present"
    assert check_typed_name("a/#b.png").reason == "separator_present"
    assert check_typed_name("a?#b.png").reason == "forbidden_character"
    assert check_typed_name("a?#b.png").reason == "forbidden_character"
    # `<%` outranks forbidden_character ('<' is a FORBIDDEN_CHARS member);
    # every control character, NUL included, outranks forbidden_character.
    assert check_typed_name("a<%b.png").reason == "unsafe_sequence"
    assert check_typed_name("a\x00b.png").reason == "unsafe_sequence"
    assert check_typed_name("a?\x01b.png").reason == "unsafe_sequence"
    # edge whitespace runs before the forbidden-character check.
    assert check_typed_name(" a?.png").reason == "breaks_link"
    assert check_typed_name("\ta\x00.png").reason == "breaks_link"


@pytest.mark.parametrize("name", ["a{{b.png", "{{a.png", "a.png{{", "a<%b.png",
                                  "<%a.png", "a\x01b.png", "a\x7fb.png", "a\nb.png",
                                  "a\x00b.png", "\x01a.png", "a.png\x01",
                                  "\x00a.png", "a.png\x7f"])
def test_unsafe_sequences(name):
    v = check_typed_name(name)
    assert (v.ok, v.reason) == (False, "unsafe_sequence")


def test_single_brace_and_angle_are_not_unsafe():
    # '<' is forbidden by Obsidian already; a lone '{' or '%' is plain.
    assert check_typed_name("a{b}%c.png").ok is True


def test_usable_names_still_accepted_verbatim():
    for n in ("karte.png", "karte münchen.png", "a b.png"):
        v = check_typed_name(n)
        assert v.ok is True and v.name == n


def test_refusal_reasons_is_a_closed_set_of_five():
    assert REFUSAL_REASONS == frozenset({
        "separator_present", "forbidden_character", "blank",
        "breaks_link", "unsafe_sequence",
    })


def test_sanitize_stem_unchanged():
    assert sanitize_stem("C# Notizen") == "C# Notizen"


def test_breaks_link_sentence_says_link_not_obsidian_forbids():
    s = _typed_name_refusal_reason("breaks_link", "a#b.png")
    assert s.startswith("typed name refused: ")
    assert "`a#b.png`" in s
    assert "break the link" in s
    assert "does not allow" not in s and "not allowed" not in s


def test_unsafe_sequence_sentence_is_distinct_and_names_the_name():
    s = _typed_name_refusal_reason("unsafe_sequence", "a{{b.png")
    assert s.startswith("typed name refused: ")
    assert "`a{{b.png`" in s
    assert s != _typed_name_refusal_reason("breaks_link", "a{{b.png")


def test_unsafe_sequence_sentence_shows_control_characters_visibly():
    s = _typed_name_refusal_reason("unsafe_sequence", "a\x01b.png")
    assert "\x01" not in s


# ---------------------------------------------------------------------------
# F5-AC7: end to end through the real instruction-render.py main().
# ---------------------------------------------------------------------------

_spec = importlib.util.spec_from_file_location(
    "instruction_render_t039_t2_1", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec)
sys.modules["instruction_render_t039_t2_1"] = ir
_spec.loader.exec_module(ir)

_CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
    "callouts.editable": ["NOTE"],
}
SOURCE = "100 Inbox/Scans/karte.png"


def _item(item_id, title, source_path, attachments):
    return {
        "id": item_id, "action": None, "title": title,
        "template": "templates/atomic.md", "source_path": source_path,
        "tags": [], "parent_moc": "", "parent_mocs": [],
        "destination": "Atlas/202 Notes/", "summary": "",
        "attachments": attachments, "candidate_mocs": [],
    }


@pytest.mark.parametrize("typed", ["a{{b.png", "a<%b.png", "a\x01b.png"])
def test_unsafe_typed_name_does_not_abort_pass_2(monkeypatch, tmp_path, typed):
    suggestions = {
        "confirmed_items": [
            _item("S01", "Kai", "karte.md", [SOURCE]),
            _item("S02", "Zwei", "zwei.md", []),
        ],
        "daily_updates": [],
        "skipped": [],
        "attachment_conflict_remedies": [{
            "source": SOURCE, "remedy": "rename", "proposed_name": typed,
            "name_is_owner_supplied": True,
        }],
    }
    sf = tmp_path / "suggestions.json"
    sf.write_text(json.dumps(suggestions), encoding="utf-8")
    cf = tmp_path / "vault-config.yaml"
    cf.write_text("", encoding="utf-8")
    monkeypatch.setattr(ir, "load_config", lambda _p: dict(_CFG))
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "read_template", lambda _c, _r: "# {{title}}\n{{body}}\n")
    monkeypatch.setattr(ir, "read_note_body", lambda *_a, **_kw: "")
    monkeypatch.setattr(ir, "render_via_script",
                        lambda *_a, **_kw: "See ![[Scans/karte.png]]\n")
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["instruction-render.py", "--suggestions", str(sf),
                                      "--output-dir", str(out), "--config", str(cf)])
    assert ir.main() == 0

    # Both items rendered; the refused attachment withholds only its own
    # item's move, never the other item's actions.
    assert sorted(p.name.split("_", 2)[2] for p in out.glob("*_*_*.md")) == [
        "kai.md", "zwei.md"]
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert any(m["title"] == "Zwei" for m in manifest), "the other item must survive"
    instr = json.loads((out / "instructions.json").read_text(encoding="utf-8"))
    assert not [a for a in instr["actions"]
                if a["action"] == "move_asset" and a["source"] == SOURCE]
