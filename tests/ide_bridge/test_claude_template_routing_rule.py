#!/usr/bin/env python3
# version: 0.1.0
"""test_claude_template_routing_rule.py — Contract assertions for the vault-path
routing rule in tomo/CLAUDE.md.template (T3.3 / ADR-5 / Feature 5).

Strategy: render the template through the same sed substitution pipeline that
install-tomo.sh uses, then assert the rendered CLAUDE.md contains the vault-path
routing rule covering all four namespace cases.

Coverage targets:
  - F5-AC1: selection text used without a Kado read (no read needed for selection)
  - F5-AC2: active-file vault path read via kado-read, not local FS
  - F5-AC3: ambiguous bare path → kado-read first, fall back on not-found/denied;
            true vault path fails closed
  - CON-6: existing {{KADO_*}} placeholders still resolve (no breakage)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE = REPO_ROOT / "tomo" / "CLAUDE.md.template"

# Fixed substitution values (mirror what install-tomo.sh emits)
_SED_SUBS = {
    "{{INSTANCE_NAME}}": "test-instance",
    "{{KADO_HOST}}": "host.docker.internal",
    "{{KADO_PORT}}": "23026",
    "{{KADO_PROTOCOL}}": "http",
}


def _render_template() -> str:
    """Render CLAUDE.md.template via the same sed pipeline install-tomo.sh uses.

    Returns the rendered text.
    """
    sed_args = ["sed"]
    for placeholder, value in _SED_SUBS.items():
        sed_args += ["-e", f"s|{placeholder}|{value}|g"]
    sed_args += [str(TEMPLATE)]

    result = subprocess.run(
        sed_args,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"sed failed: {result.stderr}"
    return result.stdout


# ── CON-6: placeholder substitution still works ──────────────────────────────

def test_kado_placeholders_resolve():
    """CON-6: all {{KADO_*}} and {{INSTANCE_NAME}} placeholders render cleanly."""
    rendered = _render_template()

    # No raw placeholders should remain
    for placeholder in _SED_SUBS:
        assert placeholder not in rendered, (
            f"Placeholder {placeholder!r} was not substituted.\n"
            f"rendered (first 500 chars):\n{rendered[:500]}"
        )

    # Substituted values must appear
    assert "host.docker.internal" in rendered, (
        "KADO_HOST substitution missing from rendered CLAUDE.md"
    )
    assert "23026" in rendered, (
        "KADO_PORT substitution missing from rendered CLAUDE.md"
    )
    assert "http://" in rendered, (
        "KADO_PROTOCOL substitution missing from rendered CLAUDE.md (expected 'http://')"
    )
    assert "test-instance" in rendered, (
        "INSTANCE_NAME substitution missing from rendered CLAUDE.md"
    )


# ── F5-AC2: vault-note paths → kado-read ─────────────────────────────────────

def test_routing_rule_vault_paths_use_kado_read():
    """F5-AC2: rendered CLAUDE.md contains explicit routing of vault paths to kado-read."""
    rendered = _render_template()

    # The rule must instruct kado-read for vault-note path sources
    assert "kado-read" in rendered, (
        "Routing rule missing: 'kado-read' not found in rendered CLAUDE.md.\n"
        "Expected a vault-path routing rule instructing kado-read for vault paths."
    )


def test_routing_rule_covers_active_file():
    """F5-AC2: routing rule explicitly covers the IDE Bridge active file path."""
    rendered = _render_template()

    # Must mention the active file in the vault-path bullet (not just the selection line)
    has_active_file = (
        "active file" in rendered.lower()
        or "active-file" in rendered.lower()
    )
    assert has_active_file, (
        "Routing rule does not mention the active file (bridge active file).\n"
        "F5-AC2 requires: active-file vault path → kado-read."
    )


def test_routing_rule_covers_wikilinks():
    """F5-AC2: routing rule explicitly covers [[wikilinks]] as vault paths."""
    rendered = _render_template()

    assert "[[" in rendered or "wikilink" in rendered.lower(), (
        "Routing rule does not cover [[wikilinks]].\n"
        "F5-AC2 requires [[wikilinks]] to route via kado-read."
    )


def test_routing_rule_covers_mentions():
    """F5-AC2: routing rule covers @-mentions as vault paths."""
    rendered = _render_template()

    # Accept both plain "@-mentions" and backtick-formatted "`@`-mentions"
    has_mentions = (
        "@-mention" in rendered
        or "@mention" in rendered.lower()
        or "@`-mention" in rendered
        or "mention" in rendered.lower()
    )
    assert has_mentions, (
        "Routing rule does not cover @-mentions.\n"
        "F5-AC2 requires @-mentions to route via kado-read."
    )


def test_routing_rule_covers_kado_search_results():
    """F5-AC2: routing rule covers kado-search results as vault paths."""
    rendered = _render_template()

    has_search = (
        "kado-search" in rendered
        or "search result" in rendered.lower()
    )
    assert has_search, (
        "Routing rule does not cover kado-search results.\n"
        "F5-AC2 requires kado-search results to route via kado-read."
    )


# ── F5-AC1: selection text needs no Kado read ────────────────────────────────

def test_routing_rule_selection_no_read_needed():
    """F5-AC1: routing rule indicates selection text arrives in-context (no read)."""
    rendered = _render_template()

    # Must mention selection text and "no read" / "in-context" in the routing section.
    # We look for the presence of "Selection" (capital, sentence-starting) as the routing
    # section uses it explicitly, OR "in-context" or "no read".
    has_selection_rule = (
        "Selection text" in rendered
        or "in-context" in rendered.lower()
        or "in context" in rendered.lower()
        or ("selection" in rendered.lower() and "no read" in rendered.lower())
    )
    assert has_selection_rule, (
        "Routing rule does not address selection text (F5-AC1).\n"
        "Expected 'Selection text' in the routing section stating no read is needed."
    )


# ── Container-local → local Read ─────────────────────────────────────────────

def test_routing_rule_local_read_for_container_files():
    """Routing rule reserves local Read for container-local working files."""
    rendered = _render_template()

    # Local Read must be explicitly named as the tool for container-local files
    has_local_read = (
        "local Read" in rendered
        or "local `Read`" in rendered
        or "container-local" in rendered.lower()
    )
    assert has_local_read, (
        "Routing rule does not mention local Read for container-local files.\n"
        "Expected: local Read reserved for container-local working files."
    )


# ── F5-AC3: ambiguous bare path → kado-read first, fallback ──────────────────

def test_routing_rule_ambiguous_path_kado_first():
    """F5-AC3: ambiguous bare relative path → kado-read first."""
    rendered = _render_template()

    has_ambiguous = (
        "ambiguous" in rendered.lower()
        or "bare" in rendered.lower()
        or "bare relative" in rendered.lower()
    )
    assert has_ambiguous, (
        "Routing rule does not address ambiguous/bare relative paths (F5-AC3).\n"
        "Expected: ambiguous bare path → kado-read first."
    )


def test_routing_rule_fallback_on_not_found():
    """F5-AC3: fall back to local Read only on Kado not-found or denied result."""
    rendered = _render_template()

    has_fallback = (
        "not-found" in rendered.lower()
        or "not found" in rendered.lower()
        or "denied" in rendered.lower()
        or "fallback" in rendered.lower()
        or "fall back" in rendered.lower()
    )
    assert has_fallback, (
        "Routing rule does not mention not-found/denied fallback (F5-AC3).\n"
        "Expected: fall back to local Read only on Kado not-found/denied."
    )


# ── F5-AC3: vault path not found locally → error (fail closed) ───────────────

def test_routing_rule_fail_closed_for_vault_path():
    """F5-AC3: a true vault path not readable via Kado is an error — fail closed."""
    rendered = _render_template()

    # The fail-closed rule must use "error" AND either "do not" or "silently" to be specific.
    # This ensures the test is not satisfied by an unrelated "NEVER" mention.
    has_fail_closed = (
        ("error" in rendered.lower() and "do not" in rendered.lower())
        or "fail closed" in rendered.lower()
        or ("is an error" in rendered.lower())
    )
    assert has_fail_closed, (
        "Routing rule does not indicate fail-closed behavior (F5-AC3).\n"
        "Expected: 'is an error — do not silently substitute a local file' or equivalent."
    )


def test_vault_not_mounted_stated():
    """Routing rule must state that the vault is not mounted in the container."""
    rendered = _render_template()

    has_not_mounted = (
        "not mounted" in rendered.lower()
        or "vault is not" in rendered.lower()
        or "unmounted" in rendered.lower()
    )
    assert has_not_mounted, (
        "Routing rule does not state that the vault is not mounted.\n"
        "Expected: 'vault is not mounted in this container' or equivalent.\n"
        "This is CON-4: Kado is the sole vault surface."
    )


if __name__ == "__main__":
    import sys
    raise SystemExit(pytest.main([__file__, "-v"] + sys.argv[1:]))
