# version: 0.1.0
"""render_io.py — Kado read helpers shared across the render pipeline.

Extracted from instruction-render.py (#42, D-07 Constitution L2 split). Holds the
two vault readers used by both the orchestrator's render loop and render_resolve
(read_template). Kept in a leaf module — imports only kado_client — so both
callers can share them without a cycle. The script-runner render_via_script stays
in the orchestrator (it resolves token-render.py relative to the scripts dir).
"""
from __future__ import annotations

import sys

from lib.kado_client import KadoClient, KadoError

def read_note_body(client: KadoClient, path: str) -> str:
    """Read a note via Kado and extract body (content after frontmatter)."""
    try:
        result = client.read_note(path)
        content = result.get("content", "")
    except KadoError as exc:
        print(f"  [warn] Could not read source {path}: {exc}", file=sys.stderr)
        return ""

    # Strip frontmatter (--- ... ---)
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            body = content[end + 3:].strip()
            return body
    return content.strip()


def read_template(client: KadoClient, template_path: str) -> str | None:
    """Read a template file from the vault via Kado.

    Handles both full vault-relative paths (e.g. "Atlas/900 Templates/t_note_tomo.md")
    and bare stems (e.g. "t_note_tomo"). Bare stems are resolved via kado-search byName.
    """
    # Ensure .md extension
    if not template_path.endswith(".md"):
        template_path += ".md"
    # If bare stem (no path separator), resolve via search
    if "/" not in template_path:
        try:
            results = client.search_by_name(template_path)
            if results:
                template_path = results[0].get("path", template_path)
                print(f"  [template] Resolved bare stem to: {template_path}", file=sys.stderr)
            else:
                print(f"  [error] Template not found by name: {template_path}", file=sys.stderr)
                return None
        except KadoError as exc:
            print(f"  [error] Could not search for template {template_path}: {exc}", file=sys.stderr)
            return None
    try:
        result = client.read_note(template_path)
        return result.get("content", "")
    except KadoError as exc:
        print(f"  [error] Could not read template {template_path}: {exc}", file=sys.stderr)
        return None


