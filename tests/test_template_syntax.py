#!/usr/bin/env python3
# version: 0.1.3
"""test_template_syntax.py — Behavioural tests for lib.template_syntax.

Spec 044 T1.2: one module gives the template outline its points and the
filled-note check its verdict (PRD F3; SDD F3-AC1, F3-AC7; ADR-4). The
fixtures are real template shapes: frontmatter with Templater values, a
callout, fenced code that carries {{x}}, an escaped \\{{x}}, <% %> and <%* %>
spans, a template whose first line is a tp.file.include, and headings with and
without a body.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import template_syntax as ts  # noqa: E402

MEETING_TEMPLATE = """---
UUID: <% tp.date.now("YYYYMMDDHHmmss") %>
DateStamp: {{datestamp}}
title: "{{title}}"
tags:
  - type/note/meeting
aliases:
Summary: {{summary}}
---

> [!connect] Your way around
> up:: {{up}}

# [[{{title}}]]

## Attendees

## Agenda
{{agenda}}

<%*
let d = tp.date.now("YYYY")
%>
## Example
```markdown
{{not_a_token}}
## Not a heading
```
Write \\{{literal}} here, source {{source_link}}, made {{uuid}}.
### Notes
"""

INCLUDE_FIRST_TEMPLATE = """<% await tp.file.include("[[x_frontmatter]]") %>
title: "{{title}}"
---

# {{title}}
"""

CLEAN_NOTE = """---
title: "Weekly sync"
tags:
  - type/note/meeting
---

# [[Weekly sync]]

## Agenda
Budget review.

```text
{{kept_inside_fence}}
```
Escaped \\{{literal}} stays.
"""


def _lines(text: str) -> list[str]:
    return text.splitlines()


# ──────────────────────────────────────────────────────────────────────────────
# Leading block
# ──────────────────────────────────────────────────────────────────────────────

def test_leading_block_found_returns_the_lines_between_the_fences():
    block = ts.leading_block(MEETING_TEMPLATE)
    assert block.status == "ok"
    assert block.start_line == 1
    assert block.end_line == 9
    assert block.lines[0] == 'UUID: <% tp.date.now("YYYYMMDDHHmmss") %>'
    assert block.lines[-1] == "Summary: {{summary}}"


def test_leading_block_unclosed_when_the_opening_fence_never_closes():
    block = ts.leading_block("---\ntitle: x\n\n# Heading\n")
    assert block.status == "unclosed"
    assert block.lines == []


def test_leading_block_missing_when_a_templater_include_is_line_one():
    block = ts.leading_block(INCLUDE_FIRST_TEMPLATE)
    assert block.status == "missing"


def test_leading_block_missing_on_empty_text():
    assert ts.leading_block("").status == "missing"


def test_frontmatter_ok_is_true_only_for_a_closed_leading_block():
    assert ts.frontmatter_ok(MEETING_TEMPLATE) is True
    assert ts.frontmatter_ok("---\ntitle: x\n") is False
    assert ts.frontmatter_ok(INCLUDE_FIRST_TEMPLATE) is False


# ──────────────────────────────────────────────────────────────────────────────
# Frontmatter keys
# ──────────────────────────────────────────────────────────────────────────────

def test_frontmatter_keys_list_top_level_keys_with_value_and_line():
    keys = ts.frontmatter_keys(MEETING_TEMPLATE)
    assert keys == [
        {"key": "UUID", "has_value": True, "line": 2},
        {"key": "DateStamp", "has_value": True, "line": 3},
        {"key": "title", "has_value": True, "line": 4},
        {"key": "tags", "has_value": True, "line": 5},
        {"key": "aliases", "has_value": False, "line": 7},
        {"key": "Summary", "has_value": True, "line": 8},
    ]


def test_frontmatter_key_with_an_indented_list_has_a_value():
    keys = ts.frontmatter_keys("---\ntags:\n  - a\ntitle: x\n---\n")
    assert keys[0] == {"key": "tags", "has_value": True, "line": 2}


def test_frontmatter_key_with_a_column_zero_list_has_a_value():
    keys = ts.frontmatter_keys("---\ntags:\n- a\n- b\ntitle: x\n---\n")
    assert keys == [
        {"key": "tags", "has_value": True, "line": 2},
        {"key": "title", "has_value": True, "line": 5},
    ]


def test_frontmatter_key_with_a_column_zero_list_before_the_closing_fence():
    keys = ts.frontmatter_keys("---\ntitle: x\ntags:\n- a\n---\n")
    assert keys[-1] == {"key": "tags", "has_value": True, "line": 3}


def test_frontmatter_empty_key_followed_by_another_key_has_no_value():
    keys = ts.frontmatter_keys("---\naliases:\ntitle: x\n---\n")
    assert keys[0] == {"key": "aliases", "has_value": False, "line": 2}


def test_frontmatter_empty_key_before_the_closing_fence_has_no_value():
    keys = ts.frontmatter_keys("---\ntitle: x\naliases:\n---\n- not frontmatter\n")
    assert keys[-1] == {"key": "aliases", "has_value": False, "line": 3}


def test_frontmatter_keys_empty_when_the_block_is_missing():
    assert ts.frontmatter_keys(INCLUDE_FIRST_TEMPLATE) == []


# ──────────────────────────────────────────────────────────────────────────────
# Tokens
# ──────────────────────────────────────────────────────────────────────────────

def test_tokens_listed_with_line_outside_fences_templater_and_escapes():
    names = [(t["name"], t["line"]) for t in ts.tokens(MEETING_TEMPLATE)]
    assert names == [
        ("datestamp", 3),
        ("title", 4),
        ("summary", 8),
        ("up", 12),
        ("title", 14),
        ("agenda", 19),
        ("source_link", 29),
        ("uuid", 29),
    ]


def test_tokens_never_include_a_fenced_or_escaped_token():
    names = {t["name"] for t in ts.tokens(MEETING_TEMPLATE)}
    assert "not_a_token" not in names
    assert "literal" not in names


def test_tokens_inside_a_templater_span_are_not_points():
    text = '<% tp.user.fmt("{{inner}}") %>\n{{outer}}\n'
    assert [t["name"] for t in ts.tokens(text)] == ["outer"]


def test_tokens_inside_a_tilde_fence_are_skipped():
    text = "~~~\n{{hidden}}\n~~~\n{{shown}}\n"
    assert [t["name"] for t in ts.tokens(text)] == ["shown"]


@pytest.mark.parametrize("name", ["uuid", "datestamp", "updated", "date_iso",
                                  "locale", "vault", "vault_version", "profile"])
def test_generated_and_config_tokens_are_prefilled(name):
    [token] = ts.tokens("{{" + name + "}}")
    assert token["prefilled"] is True


@pytest.mark.parametrize("name", ["title", "tags", "body", "up", "summary",
                                  "aliases", "classification", "my_custom"])
def test_every_other_token_known_or_not_is_a_point(name):
    [token] = ts.tokens("{{" + name + "}}", has_source=True)
    assert token["prefilled"] is False


@pytest.mark.parametrize("name", ["source_path", "source_link"])
def test_source_tokens_prefilled_only_when_the_source_is_an_inbox_note(name):
    [with_source] = ts.tokens("{{" + name + "}}", has_source=True)
    [without_source] = ts.tokens("{{" + name + "}}", has_source=False)
    assert with_source["prefilled"] is True
    assert without_source["prefilled"] is False


def test_prefilled_tokens_set_matches_the_sdd_table():
    assert ts.prefilled_tokens(has_source=False) == {
        "uuid", "datestamp", "updated", "date_iso",
        "locale", "vault", "vault_version", "profile",
    }
    assert ts.prefilled_tokens(has_source=True) == (
        ts.prefilled_tokens(has_source=False) | {"source_path", "source_link"}
    )


# ──────────────────────────────────────────────────────────────────────────────
# Headings
# ──────────────────────────────────────────────────────────────────────────────

def test_headings_listed_with_level_text_line_and_body():
    assert ts.headings(MEETING_TEMPLATE) == [
        {"level": 1, "text": "[[{{title}}]]", "line": 14, "has_body": False},
        {"level": 2, "text": "Attendees", "line": 16, "has_body": False},
        {"level": 2, "text": "Agenda", "line": 18, "has_body": True},
        {"level": 2, "text": "Example", "line": 24, "has_body": True},
        {"level": 3, "text": "Notes", "line": 30, "has_body": False},
    ]


def test_headings_skip_frontmatter_fenced_code_and_hashtags():
    text = "---\ntitle: x\n---\n#tag line\n```\n# not\n```\n## Real ##\nbody\n"
    assert ts.headings(text) == [
        {"level": 2, "text": "Real", "line": 8, "has_body": True},
    ]


def _heading_texts(text: str) -> list[str]:
    return [h["text"] for h in ts.headings(text)]


def test_a_shorter_backtick_run_does_not_close_a_longer_fence():
    text = "````md\n```\n# in\n```\n# still in\n````\n# out\n"
    assert _heading_texts(text) == ["out"]
    assert [t["name"] for t in ts.tokens("````\n```\n{{a}}\n```\n{{b}}\n````\n{{c}}\n")] == ["c"]


def test_a_fence_line_with_an_info_string_does_not_close_a_fence():
    text = "```\n# in\n```python\n# in2\n```\n# out\n"
    assert _heading_texts(text) == ["out"]


def test_a_backtick_opener_whose_info_string_has_a_backtick_is_not_a_fence():
    text = "```inline``` {{a}}\n# out\n{{b}}\n"
    assert _heading_texts(text) == ["out"]
    assert [t["name"] for t in ts.tokens(text)] == ["a", "b"]


def test_a_tilde_fence_stays_open_across_backtick_lines():
    text = "~~~\n```\n# in\n```\n# in2\n~~~\n# out\n"
    assert _heading_texts(text) == ["out"]


def test_a_templater_span_is_matched_across_a_fence_boundary():
    text = "```\n<%\n```\n{{a}}\n%>\n{{b}}\n"
    assert [t["name"] for t in ts.tokens(text)] == ["b"]


def test_headings_inside_a_multiline_templater_span_are_skipped():
    text = "<%*\n# js comment\n%>\n## Kept\n"
    assert [h["text"] for h in ts.headings(text)] == ["Kept"]


# ──────────────────────────────────────────────────────────────────────────────
# Templater spans
# ──────────────────────────────────────────────────────────────────────────────

def test_templater_spans_listed_with_start_line_and_text():
    spans = ts.templater_spans(MEETING_TEMPLATE)
    assert spans == [
        {"line": 2, "text": '<% tp.date.now("YYYYMMDDHHmmss") %>'},
        {"line": 21, "text": '<%*\nlet d = tp.date.now("YYYY")\n%>'},
    ]


def test_templater_include_on_line_one_is_a_span_not_a_point():
    spans = ts.templater_spans(INCLUDE_FIRST_TEMPLATE)
    assert spans == [
        {"line": 1, "text": '<% await tp.file.include("[[x_frontmatter]]") %>'},
    ]
    assert [t["name"] for t in ts.tokens(INCLUDE_FIRST_TEMPLATE)] == ["title", "title"]
    assert [h["text"] for h in ts.headings(INCLUDE_FIRST_TEMPLATE)] == ["{{title}}"]
    assert ts.frontmatter_keys(INCLUDE_FIRST_TEMPLATE) == []


def test_templater_whitespace_control_variant_is_a_span():
    assert ts.templater_spans("a <%- tp.file.title -%> b") == [
        {"line": 1, "text": "<%- tp.file.title -%>"},
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Filled-note checks
# ──────────────────────────────────────────────────────────────────────────────

def _statuses(text: str) -> dict[str, str]:
    return {f["check"]: f["status"] for f in ts.filled_note_check(text).findings}


def test_filled_note_check_passes_on_a_clean_note():
    result = ts.filled_note_check(CLEAN_NOTE)
    assert result.ok is True
    assert set(_statuses(CLEAN_NOTE).values()) == {"PASS"}


def test_filled_note_check_fails_on_a_remaining_templater_opener():
    text = CLEAN_NOTE + "\nUnclosed <% tp.date.now()\n"
    result = ts.filled_note_check(text)
    assert result.ok is False
    assert _statuses(text)["no_templater"] == "FAIL"


def test_filled_note_check_fails_on_a_remaining_token():
    text = CLEAN_NOTE + "\n{{summary}}\n"
    result = ts.filled_note_check(text)
    assert result.ok is False
    assert _statuses(text)["no_tokens"] == "FAIL"


def test_filled_note_check_fails_on_a_user_authored_tomo_key():
    text = CLEAN_NOTE.replace("title:", "tomo:\n  state: x\ntitle:", 1)
    result = ts.filled_note_check(text)
    assert result.ok is False
    assert _statuses(text)["no_user_tomo_key"] == "FAIL"


def test_filled_note_check_fails_on_a_missing_fence():
    text = "# Weekly sync\n\nBody.\n"
    result = ts.filled_note_check(text)
    assert result.ok is False
    assert _statuses(text)["leading_fence"] == "FAIL"


def test_filled_note_check_fails_on_an_unclosed_fence():
    text = "---\ntitle: x\n\n# Weekly sync\n"
    result = ts.filled_note_check(text)
    assert result.ok is False
    assert _statuses(text)["frontmatter_closed"] == "FAIL"


def _finding(text: str, check: str) -> dict:
    [found] = [f for f in ts.filled_note_check(text).findings if f["check"] == check]
    return found


def test_filled_note_check_fails_on_an_unclosed_code_fence_hiding_a_token():
    text = CLEAN_NOTE + "\n```\nOwner: {{title}}\n"
    result = ts.filled_note_check(text)
    assert result.ok is False
    finding = _finding(text, "code_fence_closed")
    assert finding["status"] == "FAIL"
    assert "line 17" in finding["detail"]
    assert finding["fix"]


def test_filled_note_check_fails_on_an_unclosed_code_fence_without_tokens():
    text = CLEAN_NOTE + "\n~~~\nplain text\n"
    result = ts.filled_note_check(text)
    assert result.ok is False
    assert _statuses(text)["code_fence_closed"] == "FAIL"
    assert _statuses(text)["no_tokens"] == "PASS"


def test_filled_note_check_passes_closed_code_fences():
    text = CLEAN_NOTE + "\n~~~\nx\n~~~\n````\n```\n````\n"
    assert ts.filled_note_check(text).ok is True
    assert _statuses(text)["code_fence_closed"] == "PASS"


def test_unclosed_code_fence_detail_names_only_the_line_number():
    text = CLEAN_NOTE + "\n```secret-lang\nprivate words\n"
    detail = _finding(text, "code_fence_closed")["detail"]
    assert "secret" not in detail
    assert "private" not in detail


def test_findings_never_echo_note_text_other_than_token_names():
    text = (
        "---\ntomo:\n  state: confidential-value\ntitle: x\n---\n"
        "<% tp.user.leak('confidential-span') %>\n{{left_over}}\n"
        "```\nconfidential-fenced\n"
    )
    findings = ts.filled_note_check(text).findings
    blob = " ".join(f"{f['detail']} {f['fix']}" for f in findings)
    assert "confidential" not in blob
    assert "{{left_over}}" in blob


def test_filled_note_findings_carry_check_status_detail_and_fix():
    [finding, *_] = ts.filled_note_check("no fence\n").findings
    assert set(finding) == {"check", "status", "detail", "fix"}
    assert finding["fix"]


# ──────────────────────────────────────────────────────────────────────────────
# Parity
# ──────────────────────────────────────────────────────────────────────────────

def _load_token_render():
    spec = importlib.util.spec_from_file_location(
        "token_render_parity", SCRIPTS_DIR / "token-render.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_token_regex_equals_token_render_token_re():
    token_render = _load_token_render()
    assert ts.TOKEN_RE.pattern == token_render._TOKEN_RE.pattern
    assert ts.TOKEN_RE.flags == token_render._TOKEN_RE.flags


# ──────────────────────────────────────────────────────────────────────────────
# Prefilled resolver (spec 044 T2.1)
# ──────────────────────────────────────────────────────────────────────────────

RESOLVE_TEMPLATE = """---
UUID: {{uuid}}
locale: {{locale}}
title: {{title}}
source: {{source_link}}
---
# {{title}}

```
{{uuid}}
```
\\{{uuid}} <% tp.date.now() %> {{datestamp}}
"""

VALUES = {"uuid": "20261105120000", "locale": "de", "datestamp": "2026-11-05",
          "source_link": "[[Meeting raw]]"}


def test_resolve_prefilled_replaces_prefilled_and_keeps_points():
    out = ts.resolve_prefilled(RESOLVE_TEMPLATE, VALUES)
    assert "UUID: 20261105120000\n" in out
    assert "locale: de\n" in out
    assert out.count("{{title}}") == 2
    assert out.endswith("2026-11-05\n")


def test_resolve_prefilled_leaves_fenced_escaped_and_templater_tokens():
    out = ts.resolve_prefilled(RESOLVE_TEMPLATE, VALUES)
    assert "```\n{{uuid}}\n```" in out
    assert "\\{{uuid}}" in out
    assert "<% tp.date.now() %>" in out


def test_resolve_prefilled_never_resolves_source_link_even_with_source():
    with_source = ts.resolve_prefilled(RESOLVE_TEMPLATE, VALUES, has_source=True)
    assert "source: {{source_link}}" in with_source
    assert {"name": "source_link", "line": 5, "prefilled": True} in ts.tokens(
        with_source, has_source=True)


def test_resolve_prefilled_source_path_only_with_source():
    text = "from {{source_path}}\n"
    values = {"source_path": "100 Inbox/a.md"}
    assert ts.resolve_prefilled(text, values) == text
    assert ts.resolve_prefilled(text, values, has_source=True) == "from 100 Inbox/a.md\n"


def test_resolve_prefilled_two_tokens_on_one_line_with_different_lengths():
    text = "x {{uuid}} y {{locale}} z {{title}}\n"
    out = ts.resolve_prefilled(text, {"uuid": "1", "locale": "a-much-longer-value"})
    assert out == "x 1 y a-much-longer-value z {{title}}\n"


def test_resolve_tokens_replaces_only_named_tokens_outside_protected_text():
    text = "s: {{source_link}}\n```\n{{source_link}}\n```\n\\{{source_link}} {{title}}\n"
    out = ts.resolve_tokens(text, {"source_link": "[[a]]"})
    assert out == "s: [[a]]\n```\n{{source_link}}\n```\n\\{{source_link}} {{title}}\n"


def test_resolve_prefilled_missing_value_becomes_empty_and_no_token_is_left():
    out = ts.resolve_prefilled("---\nvault: {{vault}}\n---\n", {})
    assert out == "---\nvault: \n---\n"
    assert ts.tokens(out) == []


def test_resolve_prefilled_value_newline_keeps_line_numbers():
    text = "---\nprofile: {{profile}}\ntitle: {{title}}\n---\n"
    out = ts.resolve_prefilled(text, {"profile": "a\nb"})
    assert out.splitlines()[1] == "profile: a b"
    assert ts.tokens(out) == [{"name": "title", "line": 3, "prefilled": False}]


def test_source_link_value_is_a_wikilink_when_the_source_is_kept():
    assert ts.source_link_value("100 Inbox/sub/Meeting raw.md", True) == "[[Meeting raw]]"


def test_source_link_value_is_empty_when_the_source_will_be_deleted():
    assert ts.source_link_value("100 Inbox/sub/Meeting raw.md", False) == ""


def test_source_link_value_is_empty_without_a_source():
    assert ts.source_link_value(None, True) == ""
    assert ts.source_link_value("", True) == ""


def test_deferred_tokens_are_prefilled_source_tokens():
    assert ts.DEFERRED_TOKENS == frozenset({"source_link"})
    assert ts.DEFERRED_TOKENS <= ts.prefilled_tokens(has_source=True)


def test_generated_values_equal_token_render():
    from datetime import datetime, timezone
    now = datetime(2026, 11, 5, 17, 30, 5, tzinfo=timezone.utc)
    token_render = _load_token_render()
    assert ts.generated_values(now) == token_render.resolve_generated_tokens(now)


def test_config_values_equal_token_render_for_config_tokens():
    config = {
        "profile": "miyo",
        "frontmatter": {"optional": [
            {"key": "locale", "token": "locale", "default": "de"},
            {"key": "Vault", "token": "vault", "default": "Privat"},
            {"key": "VaultVersion", "token": "vault_version", "default": 2},
            {"key": "Other", "token": "other", "default": "x"},
            {"key": "NoDefault", "token": "nodefault"},
        ]},
    }
    expected = {k: v for k, v in _load_token_render().resolve_config_tokens(config).items()
                if k in ts.CONFIG_TOKENS}
    assert ts.config_values(config) == expected
    assert expected == {"locale": "de", "vault": "Privat", "vault_version": "2",
                        "profile": "miyo"}


def test_config_values_tolerate_missing_or_odd_sections():
    assert ts.config_values({}) == {}
    assert ts.config_values({"frontmatter": {"optional": "nope"}}) == {}


@pytest.mark.parametrize("optional", [
    [{"key": "locale", "token": "locale", "default": ""}],
    [{"key": "VaultVersion", "token": "vault_version", "default": 0}],
    [{"key": "Vault", "token": "vault", "default": False}],
    [{"key": "Profile", "token": "profile", "default": "from-optional"}],
], ids=["empty-string-default", "zero-default", "false-default", "optional-profile-wins"])
def test_config_values_equal_token_render_on_edge_defaults(optional):
    config = {"profile": "miyo", "frontmatter": {"optional": optional}}
    expected = {k: v for k, v in _load_token_render().resolve_config_tokens(config).items()
                if k in ts.CONFIG_TOKENS}
    assert ts.config_values(config) == expected
    entry = optional[0]
    assert expected[entry["token"]] == str(entry["default"])


@pytest.mark.parametrize("frontmatter", ["x", ["a", "b"], 3])
def test_config_values_tolerate_a_frontmatter_that_is_not_a_mapping(frontmatter):
    assert ts.config_values({"frontmatter": frontmatter}) == {}
    assert ts.config_values({"frontmatter": frontmatter, "profile": "miyo"}) == {
        "profile": "miyo"}


def test_config_values_skip_optional_items_that_are_not_usable_entries():
    optional = ["x", None, ["y"], {"token": ["locale"], "default": "de"},
                {"token": "locale", "default": "de"}]
    assert ts.config_values({"frontmatter": {"optional": optional}}) == {"locale": "de"}
