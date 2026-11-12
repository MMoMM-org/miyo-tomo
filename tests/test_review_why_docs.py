"""Spec 045 T5.1 — the WHY documents of the /review command and the periodic-review skill (PRD F1-F7; ADR-1).

The two documents under ``docs/tomo/dot_claude/`` are the rationale layer of the
runtime files T5.2 writes. This test is the drift guard between those documents
and the CLI contracts of Phases 2-4: the subcommand names are read from the real
argparse parsers (``build_parser()`` of every review script and of
``vault-config-writer.py``), never typed by hand, so the test fails when a
subcommand is added, renamed or removed and the WHY document still names the old
contract — in either direction.

Mechanisms a mutation of the parsers falsifies:
- ``test_skill_doc_names_every_subcommand_of_every_review_parser`` — a subcommand
  added to a parser (or missing from the document) fails the forward check.
- ``test_skill_doc_names_no_subcommand_the_parsers_lack`` — a subcommand removed
  from a parser while the document still names it fails the reverse check; so
  does a flag the document attaches to a subcommand that the parser does not take.
- ``test_skill_doc_names_the_review_writer_subcommand`` — the writer's ``review``
  subcommand (ADR-5) must be named with its script.
- ``test_skill_doc_names_the_read_script_and_its_required_flags`` —
  ``review-read.py`` has no subcommand; its required flags are the contract.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO / "tomo" / "scripts"
DOCS_DIR = REPO / "docs" / "tomo" / "dot_claude"
COMMAND_DOC = DOCS_DIR / "commands" / "review.md"
SKILL_DOC = DOCS_DIR / "skills" / "periodic-review.md"

REVIEW_SCRIPTS = ("review-session.py", "review-doc.py", "review-instructions.py", "review-read.py")
WRITER_SCRIPT = "vault-config-writer.py"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(script: str):
    spec = importlib.util.spec_from_file_location(script.replace("-", "_").removesuffix(".py"), SCRIPTS_DIR / script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _flags(parser: argparse.ArgumentParser) -> set[str]:
    return {opt for action in parser._actions for opt in action.option_strings}


def _required_flags(parser: argparse.ArgumentParser) -> set[str]:
    return {opt for action in parser._actions if action.required for opt in action.option_strings}


@pytest.fixture(scope="module")
def parsers() -> dict[str, argparse.ArgumentParser]:
    return {script: _load(script).build_parser() for script in REVIEW_SCRIPTS + (WRITER_SCRIPT,)}


@pytest.fixture(scope="module")
def review_subcommands(parsers) -> dict[str, dict[str, argparse.ArgumentParser]]:
    """script -> {subcommand -> its parser}, from the parsers of the review scripts that have subcommands."""
    found = {script: _subparsers(parsers[script]) for script in REVIEW_SCRIPTS}
    return {script: subs for script, subs in found.items() if subs}


@pytest.fixture(scope="module")
def skill_doc() -> str:
    assert SKILL_DOC.is_file(), f"missing WHY document: {SKILL_DOC.relative_to(REPO)}"
    return SKILL_DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def command_doc() -> str:
    assert COMMAND_DOC.is_file(), f"missing WHY document: {COMMAND_DOC.relative_to(REPO)}"
    return COMMAND_DOC.read_text(encoding="utf-8")


# A mention of a subcommand in the document: `review-doc.py write`, optionally followed by flags
# (`review-instructions.py deliver --place-anchor`). The script name is part of the mention so a bare
# `write` in prose is never read as a CLI reference.
MENTION = re.compile(r"`(review-(?:session|doc|instructions)\.py) ([a-z][a-z-]*)((?: --[a-z][a-z-]*)*)`")


def _mentions(doc: str) -> list[tuple[str, str, list[str]]]:
    return [(script, sub, flags.split()) for script, sub, flags in MENTION.findall(doc)]


def test_both_why_documents_exist():
    assert COMMAND_DOC.is_file(), f"missing WHY document: {COMMAND_DOC.relative_to(REPO)}"
    assert SKILL_DOC.is_file(), f"missing WHY document: {SKILL_DOC.relative_to(REPO)}"


def test_parsers_are_the_source_of_the_subcommand_list(review_subcommands):
    """The guard reads the real parsers: three scripts carry subcommands, review-read.py carries none."""
    assert set(review_subcommands) == {"review-session.py", "review-doc.py", "review-instructions.py"}
    assert all(review_subcommands[script] for script in review_subcommands)


def test_skill_doc_names_every_subcommand_of_every_review_parser(skill_doc, review_subcommands):
    named = {(script, sub) for script, sub, _flags in _mentions(skill_doc)}
    expected = {(script, sub) for script, subs in review_subcommands.items() for sub in subs}
    missing = sorted(expected - named)
    assert not missing, f"the skill WHY document does not name these subcommands as `<script> <sub>`: {missing}"


def test_skill_doc_names_no_subcommand_the_parsers_lack(skill_doc, review_subcommands):
    mentions = _mentions(skill_doc)
    assert mentions, "the skill WHY document names no `<script> <sub>` at all"
    unknown = sorted({(script, sub) for script, sub, _flags in mentions if sub not in review_subcommands[script]})
    assert not unknown, f"the skill WHY document names subcommands the parsers do not have: {unknown}"
    bad_flags = sorted(
        (script, sub, flag)
        for script, sub, flags in mentions
        for flag in flags
        if flag not in _flags(review_subcommands[script][sub])
    )
    assert not bad_flags, f"the skill WHY document attaches flags a subcommand does not take: {bad_flags}"


def test_skill_doc_names_the_review_writer_subcommand(skill_doc, parsers):
    writer_subs = _subparsers(parsers[WRITER_SCRIPT])
    assert "review" in writer_subs, "vault-config-writer.py lost its `review` subcommand (ADR-5)"
    writer_mentions = re.findall(rf"`{re.escape(WRITER_SCRIPT)} review((?: --[a-z][a-z-]*)*)`", skill_doc)
    assert writer_mentions, "the skill WHY document must name `vault-config-writer.py review`"
    writer_flags = _flags(writer_subs["review"])
    bad_flags = sorted({flag for flags in writer_mentions for flag in flags.split() if flag not in writer_flags})
    assert not bad_flags, f"the skill WHY document attaches flags the writer's review subcommand does not take: {bad_flags}"
    for flag in _required_flags(writer_subs["review"]):
        assert flag in skill_doc, f"the writer's required flag {flag} is not named in the skill WHY document"


def test_skill_doc_names_the_read_script_and_its_required_flags(skill_doc, parsers):
    read_parser = parsers["review-read.py"]
    assert not _subparsers(read_parser), "review-read.py grew subcommands; extend MENTION and this test"
    assert "`review-read.py" in skill_doc, "the skill WHY document must name `review-read.py`"
    for flag in _required_flags(read_parser):
        assert flag in skill_doc, f"review-read.py's required flag {flag} is not named in the skill WHY document"


def test_command_doc_is_the_shim_rationale(command_doc):
    """The command WHY names the shim contract: $ARGUMENTS verbatim into the periodic-review skill (ADR-1)."""
    assert "$ARGUMENTS" in command_doc
    assert "periodic-review" in command_doc
    assert "review-session.py start" in command_doc, "the command WHY must say that `start` parses the argument, not the shim"
