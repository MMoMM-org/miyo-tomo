#!/usr/bin/env python3
# version: 0.5.0
"""embed_rewrite.py — Write the attachment plan's embed text into note bodies."""
from __future__ import annotations

import re

from lib.attachment_index import _EMBED_RE, narrow_candidates

_FENCE_OPEN_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})([^\n]*)$")


def _fence_spans(body: str) -> list[tuple[int, int]]:
    """Character spans of every fenced code block in `body`.

    A `![[...]]` inside a fence is example text in the note, not a dependency
    of it, and must survive a rewrite untouched.

    This is a line scan rather than one regex because CommonMark's closing
    rule is not expressible as a Python pattern: a fence closes only on a run
    of the SAME character at least as long as the one that opened it, and
    `re` has no variable-length backreference comparison. The regex this
    replaced closed on the first run of 3+ backticks whatever the opening
    length, so a 4-backtick fence containing a 3-backtick line ended early and
    a real embed still inside it was rewritten — measured 2026-09-27, and the
    inverse of the defect T3.3 exists to fix: instead of a stale reference
    surviving, a fenced example was silently corrupted.

    Two faults closed HERE, each pinned by a test: a closing run shorter than
    the opening one, and a CRLF closing line whose `\r` defeated the
    end-of-line anchor and swallowed the rest of the note as fenced. Tilde
    (`~~~`) fences are newly recognised, which is a third change but not a
    fault the regex had — it never recognised them.

    A third fault, an unclosed fence matching nothing at all so everything
    after a dangling fence was treated as live body text, was fixed one commit
    earlier and is PRESERVED here, not fixed here. Stated precisely because
    the first version of this docstring folded it in as "three faults closed
    at once", which credited this change with the previous one's work.

    Tilde fences (`~~~`) are recognised too — CommonMark allows them and a
    note discussing backtick syntax is exactly where one appears.
    """
    spans: list[tuple[int, int]] = []
    pos = 0
    open_at: int | None = None
    open_marker = ""
    for line in body.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if open_at is None:
            match = _FENCE_OPEN_RE.match(stripped)
            # An info string may not contain a backtick on a backtick fence
            # (CommonMark); a tilde fence's may.
            if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                open_at = pos
                open_marker = match.group(1)
        else:
            candidate = stripped.strip()
            if (
                candidate
                and candidate[0] == open_marker[0]
                and candidate == candidate[0] * len(candidate)
                and len(candidate) >= len(open_marker)
            ):
                spans.append((open_at, pos + len(line)))
                open_at = None
        pos += len(line)
    if open_at is not None:
        # An unclosed fence runs to the end of the note, which is how
        # Obsidian renders it.
        spans.append((open_at, len(body)))
    return spans


def _target_and_suffix(raw: str) -> tuple[str, str]:
    """Split a `[[...]]` payload into (target, suffix).

    `suffix` is everything from the first alias/anchor marker (`|`, `#`, `^`)
    onward, kept verbatim so an alias or an anchor survives a rewrite intact.
    Unlike `attachment_index._strip_alias_and_anchor`, this never discards
    that tail — it is text the rewrite must put back.
    """
    idx = len(raw)
    for sep in ("|", "#", "^"):
        pos = raw.find(sep)
        if pos != -1 and pos < idx:
            idx = pos
    return raw[:idx], raw[idx:]


def rewrite_attachment_embeds(body: str, attachments: list[str], plan) -> str:
    """Write the attachment plan's embed text into a note body.

    `attachments` is `item["attachments"]` — the note's resolved inbox paths.
    `plan` is the run's `AttachmentPlan`; each source's `embed` is the exact
    target to write, or None to leave its embeds alone. A withheld source has
    `embed` None too. Nothing is decided here.

    An embed belongs to a source only if it resolves to it by
    `narrow_candidates`, the resolver's own rule, over this note's
    attachments: a bare name by basename, a written path only when the source
    ends with it on a folder boundary. An embed resolving to two of the
    note's attachments, or to none, is left alone.

    Only the target changes: the `|…`, `#…`, `^…` tail is put back verbatim.
    Embeds inside fenced code and links without the leading `!` are left
    alone. See `docs/tomo/scripts/lib/embed_rewrite.md`.
    """
    index: dict[str, list[str]] = {}
    embeds: dict[str, str] = {}
    for path in attachments or []:
        index.setdefault(path.rsplit("/", 1)[-1], []).append(path)
        decision = plan.by_source.get(path)
        if decision is not None and decision.embed is not None:
            embeds[path] = decision.embed

    if not embeds:
        return body

    fence_spans = _fence_spans(body)

    def _in_fence(pos: int) -> bool:
        return any(start <= pos < end for start, end in fence_spans)

    def _replace(match: re.Match) -> str:
        if _in_fence(match.start()):
            return match.group(0)
        bang, raw = match.group(1), match.group(2)
        if not bang:
            return match.group(0)  # plain [[...]] link — not an embed
        target, suffix = _target_and_suffix(raw)
        candidates = narrow_candidates(target, index)
        if len(candidates) != 1 or candidates[0] not in embeds:
            return match.group(0)
        return f"![[{embeds[candidates[0]]}{suffix}]]"

    return _EMBED_RE.sub(_replace, body)
