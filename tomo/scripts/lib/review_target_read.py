# review_target_read.py — Pass 2 of /review reads the periodic note it delivers into, and its template.
# version: 0.1.0
"""The Kado reads of ``review-instructions.py`` around the target note (spec 045 T4.2, ADR-13; split out of the
script at spec 046 T6.2).

``note_text(vault, path)`` is a note's text, None when nothing is at ``path``. ``locate(vault, setup, period_name)``
reads the configured candidate paths of the period's note in order (flat folder first) until one exists; when none
does, it searches the vault by the note's name, never taking the staged copy in the inbox, and reads every hit —
then ``review_actions.locate_target`` picks the target. None when the setup's naming does not parse the period.
``template(vault, setup, target)`` reads the template and its variant for a note that does not exist yet, None for
one that does.

Every Kado failure but NOT_FOUND raises ``review_vault.Stopped``. No clock, no file I/O.

Design notes: docs/tomo/scripts/lib/review_target_read.md
"""
from __future__ import annotations

import posixpath
from typing import Dict, List, Optional

from lib import review_actions as ra
from lib import review_config as rc
from lib import review_delivery as rdl
from lib import review_new_note as rnn
from lib.kado_client import KadoNotFoundError
from lib.period import parse_name, render_name
from lib.review_vault import Vault, kado_stops


def note_text(vault: Vault, path: str) -> Optional[str]:
    """The note's text; None when nothing is at ``path``; ``Stopped`` on any other failure."""
    with kado_stops():
        try:
            content = vault.client.read_note(path).get("content")
        except KadoNotFoundError:
            return None
    return content if isinstance(content, str) else None


def locate(vault: Vault, setup: rc.ReviewSetup, period_name: str) -> Optional[ra.Target]:
    """The period's note among the configured paths, else among the vault's notes of its name; None when the
    setup's naming does not parse ``period_name``."""
    period = parse_name(period_name, setup.format, setup.rule)
    if period is None:
        return None
    candidates = period.note_paths(setup.folder, setup.format)
    texts: Dict[str, Optional[str]] = {}
    for path in candidates:
        texts[path] = note_text(vault, path)
        if texts[path] is not None:
            break
    elsewhere: List[str] = []
    if all(texts.get(p) is None for p in candidates):
        name = f"{render_name(period, setup.format)}.md"
        with kado_stops():
            hits = vault.client.search_by_name(name)
        inbox = setup.inbox.strip().strip("/") + "/"
        elsewhere = sorted(str(h.get("path")) for h in hits
                           if isinstance(h, dict) and posixpath.basename(str(h.get("path") or "")) == name
                           and not str(h.get("path")).startswith(inbox))      # never the staged copy in the inbox
        for path in elsewhere:
            texts[path] = note_text(vault, path)
    return ra.locate_target(candidates, texts, elsewhere)


def template(vault: Vault, setup: rc.ReviewSetup, target: ra.Target) -> Optional[rnn.Template]:
    """The template and its variant a new note is built from; None when the target note exists."""
    if target.text is not None:
        return None
    raw_path, variant_path = rdl.template_paths(setup)
    return rnn.Template(raw=note_text(vault, raw_path) if raw_path else None,
                        variant=note_text(vault, variant_path) if variant_path else None)
