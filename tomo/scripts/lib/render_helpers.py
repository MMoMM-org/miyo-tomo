# version: 0.2.0
"""render_helpers.py — pure, cross-module primitives for instruction rendering.

Extracted from instruction-render.py (#42, D-07 Constitution L2 split). Holds the
tiny stem helpers used by every render submodule (render_actions, render_md,
render_resolve) and the orchestrator. Pure string ops — no Kado, no I/O, no
dependency on any other render module (keeps the module graph a DAG).
"""
from __future__ import annotations


def _stem(path: str | None) -> str:
    """Extract the bare note stem from a path (no folder, no .md)."""
    if not path:
        return ""
    p = path.rsplit("/", 1)[-1]
    if p.endswith(".md"):
        p = p[:-3]
    return p


def _moc_stem(name: str | None) -> str:
    """Normalise a MOC reference to its bare stem."""
    return _stem(name)


def resolve_source_path(
    item_key: str | None, source_path: str | None, inbox_path: str
) -> str:
    """The vault-relative path of an inbox item's source note.

    `item_key` IS that path, verbatim (spec 034 ADR-1), so when it is present
    there is nothing to derive. `source_path` is display text (ADR-2) — a bare
    filename — and reconstructing a path from it can only assume the inbox
    root. That assumption held while discovery was `depth=1`; once discovery
    became recursive it stopped holding, which is why the key exists.

    The reconstruction remains as the fallback so a suggestions document
    produced before spec 034 (every item of which did sit at the inbox root)
    still renders. It is a fallback, never a preference.

    Returns "" when there is nothing to address.
    """
    if item_key:
        return item_key
    if not source_path:
        return ""
    if "/" in source_path:
        return source_path
    return f"{(inbox_path or '').rstrip('/')}/{source_path}"


def resolve_sibling_path(
    item_key: str | None, basename: str | None, inbox_path: str
) -> str:
    """The vault-relative path of a file sitting beside an item's source note.

    Used for the audio peer of a voice transcript. Triage pairs audio to a note
    by containing folder plus stem (`inbox-triage.check_audio`), so the peer is
    a sibling of the note by construction — its folder is the note's folder,
    not the inbox root.

    Falls back to the inbox root only when no key is available, matching
    `resolve_source_path`.
    """
    if not basename:
        return ""
    if "/" in basename:
        return basename
    folder = inbox_path
    if item_key and "/" in item_key:
        folder = item_key.rsplit("/", 1)[0]
    return f"{(folder or '').rstrip('/')}/{basename}"
