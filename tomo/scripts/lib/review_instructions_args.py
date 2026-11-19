# review_instructions_args.py — the argparse pieces of review-instructions.py: the stem and the plan flags.
# version: 0.1.0
"""Argument types and flags of ``review-instructions.py`` (spec 045 T4.2; spec 046 ADR-12, T5.5; split out of the
script at spec 046 T6.2).

``stem_arg`` is the ``--stem`` type (``review_state.safe_stem``). ``add_plan_flags(cmd)`` adds what ``preview``
and ``deliver`` share: ``--place-anchor`` and the section choices — ``--section-choice <key>=skip|review`` and
``--confirm-moved <key>``, both collected by ``ChoiceFlag`` into one ``{key: choice}`` under ``choices``. A value
that is not ``<key>=skip|review``, a key that is not ``review_doc_parse.SECTION_KEY`` and a key given twice (also
across the two flags) are a bad invocation (exit 2).

No Kado, no clock, no file I/O.

Design notes: docs/tomo/scripts/lib/review_instructions_args.md
"""
from __future__ import annotations

import argparse

from lib import review_section_plan as rsp
from lib import review_state as rs
from lib.review_doc_parse import SECTION_KEY


def stem_arg(text: str) -> str:
    if not rs.safe_stem(text):
        raise argparse.ArgumentTypeError("expected a plain stem like 2026-W13_review (not empty, . or .., no / or \\)")
    return text


class ChoiceFlag(argparse.Action):
    """``--section-choice <key>=skip|review`` and ``--confirm-moved <key>`` into one ``{key: choice}``; a malformed
    value or a key given twice is a bad invocation."""

    def __call__(self, parser, namespace, value, option_string=None):
        if option_string == "--confirm-moved":
            key, choice = value, rsp.CONFIRM_MOVED
        else:
            key, _, choice = value.partition("=")
            if choice not in (rsp.SKIP, rsp.REVIEW):
                parser.error(f"{option_string}: expected <key>=skip|review")
        choices = dict(getattr(namespace, self.dest) or {})
        if not SECTION_KEY.fullmatch(key) or key in choices:
            parser.error(f"{option_string}: expected a section key, each key at most once")
        choices[key] = choice
        setattr(namespace, self.dest, choices)


def add_plan_flags(cmd: argparse.ArgumentParser) -> None:
    """``--place-anchor`` and the two section choice flags of ``preview`` and ``deliver``."""
    cmd.add_argument("--place-anchor", help="The heading the user chose instead of the configured anchor")
    cmd.add_argument("--section-choice", action=ChoiceFlag, dest="choices", metavar="KEY=skip|review",
                     help="Answer a section stop: leave the section out, or put it into Tomo Review")
    cmd.add_argument("--confirm-moved", action=ChoiceFlag, dest="choices", metavar="KEY",
                     help="Replace a moved block where it sits now")
