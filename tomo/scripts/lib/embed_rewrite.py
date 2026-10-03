#!/usr/bin/env python3
# version: 0.4.0
"""embed_rewrite.py — Rewrite `![[...]]` embed targets for renamed attachments."""
from __future__ import annotations

import re

from lib.attachment_index import _EMBED_RE
from lib.typed_name_check import check_typed_name

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
    fault the regex had — it never claimed them.

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

    `proposed_name` is substituted VERBATIM — there is no basename step
    here — so name two separate mechanisms, not one, for why the "bare
    basename, never a path" guarantee above actually holds:

    - a Tomo-COMPUTED name holds it by construction of its producer
      (`_propose_asset_name`, suggestions-reducer.py, emits a basename);
    - an owner-TYPED name holds it because of the `check_typed_name` gate
      below, whose `separator_present` verdict refuses any name containing
      `/` outright (ADR-5: refused, never sanitised).

    Until spec 038 T4.3 added that gate the second mechanism did not exist
    and this paragraph asserted a property the code did not have: a typed
    `Archive/karte.png` was substituted whole, hard-coding a folder into
    every rewritten body — the exact thing the sentence promises never
    happens — while `_build_move_asset_actions` refused the same record and
    emitted no move, so the body pointed at a file the run never created.

    The cost of that gate is real and worth stating: `check_typed_name` is
    now called from here AND from `_build_move_asset_actions`, two places
    that must keep agreeing, and nothing in the type system makes them.
    T3.2 produced the defect above by changing one and not the other. The
    agreement is pinned by execution instead — one case in
    `tests/test_038_t4_3_refused_name_rewrites_no_embed.py` feeds a single
    refused name to both halves and asserts the builder emits
    `typed_name_refused` AND the body comes back byte-identical. Deciding
    the refusal once upstream and carrying the verdict on the record is the
    better design; it changes the wire contract, so it is in
    `docs/XDD/backlog.md` rather than here.

    The gate covers only the typed-name verdict. A move withheld for a
    RUN-level reason the per-note rewrite cannot see — a destination
    collision (`kind: collision`), a path with no basename
    (`kind: no_basename`) — still leaves this function rewriting a body for
    an attachment that is never filed. Those predate T4.3 and are not
    closed by it; both need the single-verdict record above, since the
    `claimed` map they depend on is global to the run.

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
        # spec 038 T4.3: an owner-TYPED name is validated before it can reach
        # a body. Gated on `name_is_owner_supplied` and refused on the same
        # verdict `_build_move_asset_actions` refuses on, because that builder
        # emits no move for a refused name — rewriting the body anyway pointed
        # it at a file the run never created. ADR-5: refused, never sanitised,
        # so the entry is skipped and the body left alone; basenaming a
        # separator-bearing name here to rescue it would file the attachment
        # under a name the owner did not choose.
        if remedy_entry.get("name_is_owner_supplied"):
            if not check_typed_name(new_name).ok:
                continue
        old_basename = path.rsplit("/", 1)[-1]
        renames[old_basename] = new_name

    if not renames:
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
        new_basename = renames.get(target.rsplit("/", 1)[-1])
        if new_basename is None:
            return match.group(0)
        return f"![[{new_basename}{suffix}]]"

    return _EMBED_RE.sub(_replace, body)
