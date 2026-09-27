#!/usr/bin/env python3
# version: 0.1.0
"""embed_rewrite.py — Rewrite `![[...]]` embed targets for renamed attachments."""
from __future__ import annotations

import re

from lib.attachment_index import _EMBED_RE

# A fenced code block: an opening line of 3+ backticks (with an optional
# info string), through the next line that is itself a run of 3+ backticks.
# A `![[...]]` inside one is example text in the note body, not a dependency
# of it, and must survive a rewrite untouched.
_FENCE_RE = re.compile(
    r"^[ \t]*`{3,}[^\n]*\n.*?^[ \t]*`{3,}[ \t]*$", re.DOTALL | re.MULTILINE
)


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


def rewrite_renamed_embeds(
    body: str,
    attachments: list[str],
    remedies_by_source: dict[str, dict],
) -> str:
    """Rewrite embed targets for attachments this run's owner renamed.

    `attachments` is `item["attachments"]` — the note's own resolved,
    inbox-relative attachment paths. `inbox-triage.py` keeps the as-typed
    embed text (`embed_target`) only for UNRESOLVED references; a resolved
    one carries only the resolved path, so basename is the only handle left
    to match body text against (`_target_and_suffix`, above). This is why
    matching is by basename rather than by full resolved path — a bare
    `![[karte.png]]` in the body has no path component to compare.

    `remedies_by_source` is keyed by that same resolved path (spec 037 T3.0's
    transport: `{source, remedy, proposed_name}`). Only a `source` whose
    remedy is `rename` with a non-empty `proposed_name` changes anything
    here — `keep_in_inbox`, `ignore`, a null `proposed_name`, or no remedy
    record at all all leave the attachment's filed name unchanged, so the
    body is left alone for those.

    A renamed attachment's OLD basename is replaced by the BARE new
    basename (owner ruling 2026-09-27) — never the new full path (which
    would hard-code the asset folder into every rewritten body) and never
    the original path prefix (which would point at a folder the file has
    left). `_build_move_asset_actions` (`render_actions.py`) has not run
    yet at the point this is called, so the new basename is recomputed
    directly from `proposed_name` rather than read back from a move action.

    Every matching embed in the body is rewritten, not just the first one —
    a note can embed the same attachment more than once. An embed inside a
    fenced code block is left alone, and so is any `[[...]]` missing the
    leading `!` (a plain link, not an embed).
    """
    renames: dict[str, str] = {}
    for path in attachments or []:
        remedy_entry = remedies_by_source.get(path)
        if not remedy_entry or remedy_entry.get("remedy") != "rename":
            continue
        new_name = remedy_entry.get("proposed_name")
        if not new_name:
            continue
        old_basename = path.rsplit("/", 1)[-1]
        renames[old_basename] = new_name

    if not renames:
        return body

    fence_spans = [match.span() for match in _FENCE_RE.finditer(body)]

    def _in_fence(pos: int) -> bool:
        return any(start <= pos < end for start, end in fence_spans)

    def _replace(match: re.Match) -> str:
        if _in_fence(match.start()):
            return match.group(0)
        bang, raw = match.group(1), match.group(2)
        if not bang:
            return match.group(0)  # plain [[...]] link — not an embed
        target, suffix = _target_and_suffix(raw)
        new_basename = renames.get(target.rsplit("/", 1)[-1])
        if new_basename is None:
            return match.group(0)
        return f"![[{new_basename}{suffix}]]"

    return _EMBED_RE.sub(_replace, body)
