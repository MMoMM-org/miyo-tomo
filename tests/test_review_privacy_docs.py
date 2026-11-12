#!/usr/bin/env python3
# version: 0.2.0
"""test_review_privacy_docs.py — spec 045 T5.3: the privacy and setup documentation of /review.

Pins PRIVACY.md (PRD F7-AC2, ADR-9): "metadata only" is scoped to Tomo's own
records; every place read content rests is named — the session transcripts in
the container home, tomo-tmp (read.json and proposals.json deleted on write or
abort, left behind by a session that ends without either), the inbox (removing
the delivered files is the user's job); removal is the user's choice; both
`instance/` and `home/` are to be protected like the vault (for example an
encrypted disk); the /review paragraph names what reaches the model (paths of
the created notes, not their content; in Pass 2 the parsed document gives the
model counts and ids only and the preview shows the section as it will land —
never "read back") and recommends Kado deny rules for folders not to be
reviewed, in one sentence.

Each phrase test is pinned to the clause it guards: deleting that clause from
PRIVACY.md fails the test (proven by mutation in an isolated copy, T5.3-fix1).

Pins docs/setup.md linking to that PRIVACY.md section, the README naming
/review, and tomo/config/vault-example.yaml: the weekly pattern GGGG-[W]WW and
a commented review: example that the real reader (lib.review_config) accepts
and whose writer-input form validates against vault-config-review.schema.json.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PRIVACY = ROOT / "PRIVACY.md"
SETUP = ROOT / "docs" / "setup.md"
README = ROOT / "README.md"
EXAMPLE = ROOT / "tomo" / "config" / "vault-example.yaml"
PROFILE = ROOT / "tomo" / "profiles" / "miyo.yaml"
SCHEMA = ROOT / "tomo" / "schemas" / "vault-config-review.schema.json"

sys.path.insert(0, str(ROOT / "tomo" / "scripts"))
from lib import review_config as rc  # noqa: E402

TODAY = date(2026, 11, 12)


def _privacy() -> str:
    return PRIVACY.read_text(encoding="utf-8")


def _section(text: str, heading_pattern: str) -> str:
    """The body of the first heading matching ``heading_pattern`` up to the next heading of the same or a higher level."""
    m = re.search(rf"^(#+) ({heading_pattern})\s*$", text, re.M | re.I)
    assert m, f"missing heading matching {heading_pattern!r}"
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _review_paragraph() -> str:
    """The `/review` paragraph of 'What vault content reaches the LLM': from its 'During' line to the next 'During' line or heading."""
    section = _section(_privacy(), r"What vault content reaches the LLM")
    m = re.search(r"^During \*\*`/review`\*\*", section, re.M)
    assert m, "PRIVACY.md needs a paragraph starting 'During **`/review`**'"
    rest = section[m.start():]
    nxt = re.search(r"^(During |#+ )", rest[1:], re.M)
    return rest[: nxt.start() + 1] if nxt else rest


def _plain(text: str) -> str:
    """Lower-cased, wrapped lines joined, bold markers dropped — so a phrase matches across a line break."""
    return re.sub(r"\s+", " ", text.replace("**", "")).lower()


def _has(text: str, *phrases: str) -> None:
    plain = _plain(text)
    missing = [p for p in phrases if p.lower() not in plain]
    assert not missing, f"missing phrases: {missing}"


def _sentences(text: str) -> list[str]:
    """The plain-text sentences of ``text`` (split at '.' or ';')."""
    return re.split(r"(?<=[.;])\s", _plain(text))


def _one_sentence_has(text: str, *phrases: str) -> None:
    """Some single sentence of ``text`` holds every phrase — the phrases make one claim, not several."""
    assert any(all(p.lower() in s for p in phrases) for s in _sentences(text)), \
        f"no single sentence holds all of {phrases}"


# --- (a) metadata only is scoped to Tomo's own records ----------------------------------

def test_metadata_only_is_scoped_to_tomos_own_records() -> None:
    recorded = _section(_privacy(), r"What Tomo records.*")
    _has(recorded, "metadata only", "tomo's own records", "logs", "error output", "cost records")
    # the scope is stated: the claim covers Tomo's records, not every place content rests
    _has(recorded, "not a promise that no content rests", "where read content rests")


# --- (b) every place read content rests is named ----------------------------------------

def test_names_every_place_read_content_rests() -> None:
    rests = _section(_privacy(), r"Where read content rests")
    _has(rests, "session transcript", "container home", "home/.claude/projects/")
    _has(rests, "tomo-tmp", "read.json", "proposals.json", "without writing", "abort")
    _has(rests, "inbox", "review.md", "_instructions.json")


def test_read_json_and_proposals_json_are_deleted_on_write_or_abort() -> None:
    rests = _section(_privacy(), r"Where read content rests")
    _one_sentence_has(rests, "deletes `read.json` and `proposals.json`", "written to the inbox", "aborted")


def test_read_json_is_named_as_left_behind_by_an_unfinished_session() -> None:
    rests = _section(_privacy(), r"Where read content rests")
    _one_sentence_has(rests, "read.json", "session", "ended", "without writing", "abort", "next `/review`")


def test_removing_the_delivered_inbox_files_is_the_users_job() -> None:
    rests = _section(_privacy(), r"Where read content rests")
    _one_sentence_has(rests, "stay in the inbox", "removing them is yours to do")


# --- (c) removal is the user's choice; protect instance and home like the vault ---------

def test_removal_is_the_users_choice_and_protection_is_recommended() -> None:
    rests = _section(_privacy(), r"Where read content rests")
    _has(rests, "your choice", "does not remove", "encrypted disk")
    _one_sentence_has(rests, "protect the instance directory", "both `instance/` and `home/`", "like your vault")


# --- (d) the /review paragraph names what reaches the model -----------------------------

def test_review_paragraph_names_what_reaches_the_model() -> None:
    para = _review_paragraph()
    _has(para, "daily note", "sections", "5 year journal", "tracker values", "sleep", "energy", "sport")
    _one_sentence_has(para, "paths", "notes created in the period", "not their content")


def test_review_paragraph_says_what_pass_2_shows_the_model() -> None:
    para = _review_paragraph()
    _one_sentence_has(para, "review document you edited", "counts and ids")
    _one_sentence_has(para, "section as it will land", "items you kept", "your wording")
    _has(para, "instruction set", "not shown to the model")
    assert "read back" not in _plain(para), "Pass 2 does not read the document back to the model"


def test_review_paragraph_recommends_kado_deny_rules() -> None:
    para = _review_paragraph()
    _one_sentence_has(para, "kado", "deny rules", "folders you do not want reviewed")


# --- docs/setup.md links to the privacy section; README names /review -------------------

def test_setup_guide_links_to_the_privacy_section() -> None:
    setup = SETUP.read_text(encoding="utf-8")
    links = re.findall(r"\]\(\.\./PRIVACY\.md#([a-z0-9-]+)\)", setup)
    assert links, "docs/setup.md needs a link into ../PRIVACY.md"
    headings = {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-")
                for h in re.findall(r"^#+ (.+)$", _privacy(), re.M)}
    assert set(links) <= headings, f"dangling anchors: {set(links) - headings}"
    _has(setup, "like your vault")


def test_readme_names_review() -> None:
    readme = README.read_text(encoding="utf-8")
    assert re.search(r"^- \*\*`/review`\*\* — ", readme, re.M), "README 'What Tomo Does' needs a /review line"
    assert re.search(r"^\| `/review` \|", readme, re.M), "README command table needs a /review row"


# --- vault-example.yaml ------------------------------------------------------------------

def _example_config() -> dict:
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def _commented_review_example() -> dict:
    """The `review:` block that sits commented out in vault-example.yaml, uncommented and parsed."""
    lines = EXAMPLE.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("# review:")
    except ValueError:
        pytest.fail("vault-example.yaml needs a commented '# review:' example")
    block = []
    for line in lines[start:]:
        if line.startswith("# ───") or not line.startswith("#"):
            break
        block.append(line[2:] if line.startswith("# ") else line[1:])
    data = yaml.safe_load("\n".join(block))
    assert isinstance(data, dict) and isinstance(data.get("review"), dict)
    return data["review"]


def test_weekly_pattern_is_iso_week_year() -> None:
    assert _example_config()["naming"]["calendar_patterns"]["weekly"] == "GGGG-[W]WW"


@pytest.mark.parametrize("kind", ["week", "month"])
def test_commented_review_example_is_a_valid_setup(kind: str) -> None:
    config = _example_config()
    config["review"] = _commented_review_example()
    # `/review setup` enables the periodic folder; the example keeps the profile default (disabled)
    config["concepts"]["calendar"]["granularities"][rc.GRANULARITY[kind]] = {
        "enabled": True, "path": f"Calendar/{rc.GRANULARITY[kind].title()}/"}
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))

    setup = rc.review_setup(config, profile, kind, today=TODAY)       # the real reader accepts it
    assert setup is not None and setup.heading and setup.daily_sections

    proposal = rc.current_setup(config, profile, kind, TODAY)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    # the None keys are dropped before validation — only keys the schema leaves optional may be, so a
    # required field missing from the proposal cannot hide behind the filter
    dropped = {k for k, v in proposal.items() if v is None}
    assert dropped.isdisjoint(_required_keys(schema, kind)), f"required keys dropped: {dropped}"
    writer_input = {"kind": kind, **{k: v for k, v in proposal.items() if v is not None}}
    jsonschema.Draft202012Validator(schema).validate(writer_input)   # the writer input validates
    assert rc.input_problems(writer_input, today=TODAY) == []


def _required_keys(schema: dict, kind: str) -> set[str]:
    """The keys vault-config-review.schema.json requires for ``kind``: the top-level list plus the kind's allOf branch."""
    required = set(schema["required"])
    for clause in schema.get("allOf", []):
        if clause["if"]["properties"]["kind"]["const"] == kind:
            required |= set(clause["then"].get("required", []))
    assert "kind" in required and (kind != "week" or {"first_day", "min_days"} <= required)
    return required
