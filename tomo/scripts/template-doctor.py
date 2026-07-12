# version: 0.3.0
"""template-doctor.py — Audit, dry-render, and scaffold Tomo note templates.

Checks whether an Obsidian note template renders correctly through Tomo's static
Pass-2 pipeline (token resolution + ``tomo:`` block stamping). Three modes:

  audit       Static structural checks only. No rendering, no config needed.
  dry-render  Resolve ``{{tokens}}`` via token-render.py, stamp the ``tomo:``
              block via lib.doc_frontmatter.merge_tomo_block_into_markdown, then
              verify the rendered frontmatter is a single clean leading block
              with the template's own keys intact (none stranded in the body).
  scaffold    Emit a minimal, guaranteed-literal-fence template for a note type
              (atomic|moc|daily|project|source) to stdout — a correct starting
              point. Richer seed templates live in the vault's config/templates.

The load-bearing rule both modes enforce: the template must OPEN with a literal
``---`` fence. Tomo does not execute Templater at render time, so a template
whose opening fence is delegated to a Templater include (``<% tp.file.include(
"[[x_frontmatter]]") %>`` as line 1) has, from Tomo's point of view, no leading
frontmatter — merge_tomo_block prepends a fresh block and the template's
title/tags/aliases strand as note body. dry-render reproduces that failure
deterministically instead of relying on visual inspection.

Output — a JSON report on stdout:

  {
    "mode": "audit" | "dry-render",
    "template": "<path>",
    "ok": bool,                       # true when no FAIL findings
    "findings": [
      {"check": str, "status": "PASS"|"WARN"|"FAIL",
       "detail": str, "fix": str | null}
    ],
    "rendered_preview": str | null    # dry-render only: the stamped frontmatter
  }

Exit codes:
  0  no FAIL findings (WARN allowed)
  1  at least one FAIL finding, or an operational error (file missing, etc.)
  2  bad invocation
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.doc_frontmatter import (  # noqa: E402
    FrontmatterMergeError,
    merge_tomo_block_into_markdown,
)

TOKEN_RENDER = SCRIPT_DIR / "token-render.py"

# Known token vocabulary — mirrors token-render.py + docs/template-syntax.md.
# Config-sourced and custom tokens legitimately extend this set, so a token
# outside it is a WARN (not a FAIL): it may be a user config/custom token.
KNOWN_TOKENS = {
    # generated
    "uuid", "datestamp", "updated", "date_iso",
    # content
    "title", "tags", "body", "up", "summary", "aliases", "related", "children",
    # config-sourced (MiYo defaults)
    "locale", "vault", "vault_version", "profile",
    # metadata
    "source_path", "source_link", "classification", "classification_number",
}

# The only universally-required token: a note needs a name. uuid/datestamp are
# MiYo-profile frontmatter properties, not universal — and token-render only errors
# on a required token that is USED but unresolvable, never on one merely absent, so
# a profile-agnostic template needs neither. They stay in KNOWN_TOKENS (recognised
# when present) but are not asserted as required here.
REQUIRED_TOKENS = {"title"}

# Representative token values so dry-render exercises the real renderer. tags is
# a list so token-render emits its indented-YAML-sequence form, matching live.
SAMPLE_TOKENS = {
    "uuid": "20260101000000",
    "datestamp": "2026-01-01",
    "updated": "2026-01-01 00:00",
    "date_iso": "2026-01-01T00:00:00Z",
    "title": "Sample Title",
    "tags": ["type/note/normal"],
    "aliases": [],
    "summary": "A one-sentence sample summary.",
    "body": "Sample body paragraph.",
    "up": "[[Sample (MOC)]]",
    "related": "",
}

SAMPLE_TOMO_BLOCK = {
    "doc_type": "rendered-note",
    "state": "pending-move",
    "run_id": "2026-01-01T00-00-00Z-000000",
    "updated_at": "2026-01-01T00:00:00Z",
}

_TEMPLATER_OPEN_RE = re.compile(r"^\s*<%")
_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

# Minimal, literal-fence scaffolds — a correct starting point per note type.
# Every token stays inside KNOWN_TOKENS so the scaffold passes its own audit.
_SCAFFOLDS = {
    "atomic": (
        "---\nUUID: {{uuid}}\nDateStamp: {{datestamp}}\nUpdated: {{updated}}\n"
        "title: {{title}}\ntags:{{tags}}\nSummary: {{summary}}\n---\n\n"
        "# [[{{title}}]]\n\n{{body}}\n"
    ),
    "moc": (
        "---\nUUID: {{uuid}}\nDateStamp: {{datestamp}}\nUpdated: {{updated}}\n"
        "title: {{title}}\ntags:{{tags}}\nSummary: {{summary}}\n---\n\n"
        "> [!connect] Your way around\n> up:: {{up}}\n\n"
        "# [[{{title}}]]\n\n{{body}}\n\n## Related\n"
    ),
    "daily": (
        "---\nUUID: {{uuid}}\nDateStamp: {{datestamp}}\ntitle: {{title}}\n"
        "tags:\n  - type/calendar/daily\n---\n\n"
        "# [[{{title}}]]\n\n## Notes\n\n{{body}}\n"
    ),
    "project": (
        "---\nUUID: {{uuid}}\nDateStamp: {{datestamp}}\ntitle: {{title}}\n"
        "tags:{{tags}}\nSummary: {{summary}}\n---\n\n"
        "> [!connect] Your way around\n> up:: {{up}}\n\n"
        "# [[{{title}}]]\n\n## Goal\n\n{{body}}\n\n## Tasks\n"
    ),
    "source": (
        "---\nUUID: {{uuid}}\nDateStamp: {{datestamp}}\ntitle: {{title}}\n"
        "tags:{{tags}}\nSummary: {{summary}}\n---\n\n"
        "> [!connect] Your way around\n> up:: {{up}}\n\n"
        "# [[{{title}}]]\n\n## Summary\n\n{{body}}\n"
    ),
}


def _finding(check, status, detail, fix=None):
    return {"check": check, "status": status, "detail": detail, "fix": fix}


def _first_content_line(text):
    """Return (index, stripped) of the first non-blank line, or (None, '')."""
    for i, raw in enumerate(text.splitlines()):
        if raw.strip():
            return i, raw.strip()
    return None, ""


def _leading_block_lines(text):
    """Return the lines *between* the opening and closing ``---`` fences.

    Returns None when the text does not open with a literal ``---`` fence, or []
    when the fence is opened but never closed.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return []  # opened but unclosed


def _extract_tokens(text):
    """Yield {{token}} names outside fenced code blocks and escaped braces."""
    tokens = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # Ignore escaped \{\{ literal-brace documentation.
        cleaned = line.replace(r"\{\{", "").replace(r"\}\}", "")
        tokens.extend(_TOKEN_RE.findall(cleaned))
    return tokens


# ──────────────────────────────────────────────────────────────────────
# audit — static structural checks
# ──────────────────────────────────────────────────────────────────────

def static_audit(text):
    findings = []

    idx, first = _first_content_line(text)
    if first == "---":
        findings.append(_finding(
            "leading_fence", "PASS",
            "Template opens with a literal `---` frontmatter fence.",
        ))
    elif _TEMPLATER_OPEN_RE.match(first):
        findings.append(_finding(
            "leading_fence", "FAIL",
            f"First content line is a Templater expression ({first!r}); Tomo "
            "does not run Templater, so there is no literal opening `---` at "
            "render time (any closing `---` below belongs to the delegated "
            "frontmatter — Tomo never sees its opening).",
            "Inline the frontmatter with a literal opening `---` fence (the "
            "x_yaml_* sub-includes can stay inside the block). See "
            "docs/template-syntax.md → 'Frontmatter: a complete `---` block "
            "is required'.",
        ))
    else:
        findings.append(_finding(
            "leading_fence", "FAIL",
            f"First content line is not a `---` fence (got {first!r}).",
            "Start the template with a literal `---` frontmatter fence.",
        ))

    block = _leading_block_lines(text)
    if block is None:
        # No literal opening fence — `leading_fence` already FAILs and carries the
        # actionable fix. A "nothing to close" finding here would be misleading:
        # the template may well have a closing `---` (from a delegated fence) that
        # Tomo simply never opens. So emit no separate frontmatter_closed finding.
        pass
    elif block == []:
        findings.append(_finding(
            "frontmatter_closed", "FAIL",
            "Opening `---` fence is never closed.",
            "Add a closing `---` line after the frontmatter keys.",
        ))
    else:
        findings.append(_finding(
            "frontmatter_closed", "PASS",
            "Leading frontmatter block is closed.",
        ))
        if any(ln.lstrip().startswith("tomo:") for ln in block):
            findings.append(_finding(
                "no_user_tomo_key", "FAIL",
                "Template already carries a top-level `tomo:` key.",
                "Remove it — Tomo owns and stamps the `tomo:` block itself.",
            ))
        else:
            findings.append(_finding(
                "no_user_tomo_key", "PASS",
                "No user-authored `tomo:` key (Tomo stamps its own).",
            ))

    tokens = _extract_tokens(text)
    unknown = sorted({t for t in tokens if t not in KNOWN_TOKENS})
    if unknown:
        findings.append(_finding(
            "unknown_tokens", "WARN",
            "Token(s) outside the known vocabulary: "
            + ", ".join(f"{{{{{t}}}}}" for t in unknown)
            + ". They resolve to empty string unless defined as config/custom "
            "tokens.",
            "Confirm each is a vault-config custom token, else fix the typo.",
        ))
    else:
        findings.append(_finding(
            "unknown_tokens", "PASS",
            "All tokens are in the known vocabulary.",
        ))

    missing_required = sorted(REQUIRED_TOKENS - set(tokens))
    if missing_required:
        findings.append(_finding(
            "required_tokens", "WARN",
            "Missing "
            + ", ".join(f"{{{{{t}}}}}" for t in missing_required)
            + " — Pass 2 names the note from it.",
            "Add the missing token to the template.",
        ))
    else:
        findings.append(_finding(
            "required_tokens", "PASS",
            "The {{title}} token is present.",
        ))

    return findings


# ──────────────────────────────────────────────────────────────────────
# dry-render — real render + stamp + strand-lint
# ──────────────────────────────────────────────────────────────────────

def dry_render(template_path, config_path=None):
    findings = list(static_audit(template_path.read_text(encoding="utf-8")))

    cmd = [
        sys.executable, str(TOKEN_RENDER),
        "--template", str(template_path),
        "--tokens-json", json.dumps(SAMPLE_TOKENS),
    ]
    if config_path:
        cmd += ["--config", str(config_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        findings.append(_finding(
            "token_resolution", "FAIL",
            "token-render.py failed: " + (proc.stderr.strip() or "unknown error"),
            "Resolve the unresolvable required token(s) reported above.",
        ))
        return findings, None
    findings.append(_finding(
        "token_resolution", "PASS",
        "All {{tokens}} resolved with sample values.",
    ))
    rendered = proc.stdout

    try:
        stamped = merge_tomo_block_into_markdown(rendered, SAMPLE_TOMO_BLOCK)
    except FrontmatterMergeError as exc:
        findings.append(_finding(
            "tomo_stamp", "FAIL",
            f"Tomo could not stamp its block: {exc}",
            "Fix the leading frontmatter so the fence is literal and closed.",
        ))
        return findings, None

    stamped_block = _leading_block_lines(stamped)
    non_tomo = _frontmatter_without_tomo(stamped_block or [])
    if not non_tomo:
        findings.append(_finding(
            "no_stranded_frontmatter", "FAIL",
            "After stamping, the leading frontmatter holds only the `tomo:` "
            "block — the template's own keys stranded as note body.",
            "Give the template a literal opening `---` fence so its keys stay "
            "in the frontmatter.",
        ))
    else:
        findings.append(_finding(
            "no_stranded_frontmatter", "PASS",
            "Template keys remain in the frontmatter after the `tomo:` block "
            "is stamped.",
        ))

    return findings, _preview(stamped)


def _frontmatter_without_tomo(block_lines):
    """Return frontmatter lines with the leading tomo: block removed."""
    out = []
    in_tomo = False
    for ln in block_lines:
        if ln.startswith("tomo:"):
            in_tomo = True
            continue
        if in_tomo:
            # tomo block children are indented; a non-indented line ends it.
            if ln[:1].isspace() or ln.strip() == "":
                continue
            in_tomo = False
        out.append(ln)
    return [ln for ln in out if ln.strip()]


def _preview(stamped, max_lines=40):
    lines = stamped.splitlines()
    head = lines[:max_lines]
    if len(lines) > max_lines:
        head.append(f"… ({len(lines) - max_lines} more lines)")
    return "\n".join(head)


# ──────────────────────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["audit", "dry-render", "scaffold"])
    parser.add_argument("--template", help="template file path (audit/dry-render)")
    parser.add_argument("--config", help="vault-config.yaml (dry-render only)")
    parser.add_argument(
        "--type", choices=sorted(_SCAFFOLDS), help="note type (scaffold)")
    args = parser.parse_args(argv)

    if args.mode == "scaffold":
        if not args.type:
            parser.error("scaffold requires --type")
        sys.stdout.write(_SCAFFOLDS[args.type])
        return 0

    if not args.template:
        parser.error(f"{args.mode} requires --template")
    template_path = Path(args.template)
    if not template_path.is_file():
        print(json.dumps({
            "mode": args.mode, "template": str(template_path), "ok": False,
            "findings": [_finding(
                "file", "FAIL", f"Template not found: {template_path}", None)],
            "rendered_preview": None,
        }, ensure_ascii=False, indent=2))
        return 1

    preview = None
    if args.mode == "audit":
        findings = static_audit(template_path.read_text(encoding="utf-8"))
    else:
        findings, preview = dry_render(template_path, args.config)

    ok = not any(f["status"] == "FAIL" for f in findings)
    print(json.dumps({
        "mode": args.mode, "template": str(template_path), "ok": ok,
        "findings": findings, "rendered_preview": preview,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
