# version: 0.1.0
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
