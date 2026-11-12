"""Spec 045 T5.1 — the WHY documents of the /review command and the periodic-review skill (PRD F1-F7; ADR-1).

The two documents under ``docs/tomo/dot_claude/`` are the rationale layer of the
runtime files T5.2 writes. This test is the drift guard between those documents
and the CLI contracts of Phases 2-4: the subcommand names are read from the real
argparse parsers (``build_parser()`` of every review script and of
``vault-config-writer.py``) through ``tests/review_cli_contract.py``, never typed
by hand, so the test fails when a subcommand is added, renamed or removed and
the WHY document still names the old contract — in either direction.

Mechanisms a mutation of the parsers falsifies:
- ``test_skill_doc_names_every_subcommand_of_every_review_parser`` — a subcommand
  added to a parser (or missing from the document) fails the forward check.
- ``test_skill_doc_names_no_subcommand_the_parsers_lack`` — a subcommand removed
  from a parser while the document still names it fails the reverse check; so
  does a flag the document attaches to a subcommand that the parser does not take.
- ``test_skill_doc_names_the_review_writer_subcommand`` — the writer's ``review``
  subcommand (ADR-5) must be named with its required flags inside one mention.
- ``test_skill_doc_names_the_read_script_and_its_required_flags`` —
  ``review-read.py`` has no subcommand; its required flags must sit inside one
  ``review-read.py …`` mention, not anywhere in the document.
- ``test_every_review_script_span_is_a_contract_mention`` — a backtick span that
  names a review script but matches no mention form (wrapped, reworded) fails,
  so it cannot slip past the sweeps above silently.
"""
from __future__ import annotations

import re

import pytest

from review_cli_contract import (
    REPO,
    WRITER_SCRIPT,
    build_parsers,
    flags,
    read_mentions,
    required_flags,
    review_subcommands,
    sub_mentions,
    subparsers,
    unmatched_review_spans,
    writer_mentions,
)

DOCS_DIR = REPO / "docs" / "tomo" / "dot_claude"
COMMAND_DOC = DOCS_DIR / "commands" / "review.md"
SKILL_DOC = DOCS_DIR / "skills" / "periodic-review.md"


@pytest.fixture(scope="module")
def parsers():
    return build_parsers()


@pytest.fixture(scope="module")
def subcommands(parsers):
    return review_subcommands(parsers)


@pytest.fixture(scope="module")
def skill_doc() -> str:
    assert SKILL_DOC.is_file(), f"missing WHY document: {SKILL_DOC.relative_to(REPO)}"
    return SKILL_DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def command_doc() -> str:
    assert COMMAND_DOC.is_file(), f"missing WHY document: {COMMAND_DOC.relative_to(REPO)}"
    return COMMAND_DOC.read_text(encoding="utf-8")


def test_both_why_documents_exist():
    assert COMMAND_DOC.is_file(), f"missing WHY document: {COMMAND_DOC.relative_to(REPO)}"
    assert SKILL_DOC.is_file(), f"missing WHY document: {SKILL_DOC.relative_to(REPO)}"


def test_parsers_are_the_source_of_the_subcommand_list(subcommands):
    """The guard reads the real parsers: three scripts carry subcommands, review-read.py carries none."""
    assert set(subcommands) == {"review-session.py", "review-doc.py", "review-instructions.py"}
    assert all(subcommands[script] for script in subcommands)


def test_skill_doc_names_every_subcommand_of_every_review_parser(skill_doc, subcommands):
    named = {(script, sub) for script, sub, _flags in sub_mentions(skill_doc)}
    expected = {(script, sub) for script, subs in subcommands.items() for sub in subs}
    missing = sorted(expected - named)
    assert not missing, f"the skill WHY document does not name these subcommands as `<script> <sub>`: {missing}"


def test_skill_doc_names_no_subcommand_the_parsers_lack(skill_doc, subcommands):
    mentions = sub_mentions(skill_doc)
    assert mentions, "the skill WHY document names no `<script> <sub>` at all"
    unknown = sorted({(script, sub) for script, sub, _flags in mentions if sub not in subcommands[script]})
    assert not unknown, f"the skill WHY document names subcommands the parsers do not have: {unknown}"
    bad_flags = sorted(
        (script, sub, flag)
        for script, sub, mention_flags in mentions
        for flag in mention_flags
        if flag not in flags(subcommands[script][sub])
    )
    assert not bad_flags, f"the skill WHY document attaches flags a subcommand does not take: {bad_flags}"


def test_skill_doc_names_the_review_writer_subcommand(skill_doc, parsers):
    writer_subs = subparsers(parsers[WRITER_SCRIPT])
    assert "review" in writer_subs, "vault-config-writer.py lost its `review` subcommand (ADR-5)"
    mentions = writer_mentions(skill_doc)
    assert mentions, "the skill WHY document must name `vault-config-writer.py review`"
    writer_flags = flags(writer_subs["review"])
    bad_flags = sorted({flag for mention in mentions for flag in mention if flag not in writer_flags})
    assert not bad_flags, f"the skill WHY document attaches flags the writer's review subcommand does not take: {bad_flags}"
    required = required_flags(writer_subs["review"])
    assert any(required <= set(mention) for mention in mentions), (
        f"no `vault-config-writer.py review …` mention carries every required flag {sorted(required)}: {mentions}")


def test_skill_doc_names_the_read_script_and_its_required_flags(skill_doc, parsers):
    read_parser = parsers["review-read.py"]
    assert not subparsers(read_parser), "review-read.py grew subcommands; extend SUB_MENTION and this test"
    mentions = read_mentions(skill_doc)
    assert mentions, "the skill WHY document must name `review-read.py`"
    read_flags = flags(read_parser)
    bad_flags = sorted({flag for mention in mentions for flag in mention if flag not in read_flags})
    assert not bad_flags, f"the skill WHY document attaches flags review-read.py does not take: {bad_flags}"
    required = required_flags(read_parser)
    assert any(required <= set(mention) for mention in mentions), (
        f"no `review-read.py …` mention carries every required flag {sorted(required)}: {mentions}")


@pytest.mark.parametrize("doc_path", [COMMAND_DOC, SKILL_DOC], ids=["command", "skill"])
def test_every_review_script_span_is_a_contract_mention(doc_path):
    """A backtick span naming a review script must match a mention form, or the sweeps above never see it."""
    stray = unmatched_review_spans(doc_path.read_text(encoding="utf-8"))
    assert not stray, f"{doc_path.name}: spans that name a review script but match no mention form: {stray}"


def test_command_doc_is_the_shim_rationale(command_doc):
    """The command WHY names the shim contract: $ARGUMENTS verbatim into the periodic-review skill (ADR-1)."""
    assert "$ARGUMENTS" in command_doc
    assert "periodic-review" in command_doc
    assert re.search(r"`review-session\.py start`", command_doc), (
        "the command WHY must say that `start` parses the argument, not the shim")
