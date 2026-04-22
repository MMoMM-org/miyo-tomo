# version: 0.1.0
"""token-render.py — Resolve {{token}} placeholders in Tomo templates.

Reads a template (markdown with {{token}} placeholders), resolves tokens from
multiple sources in precedence order, and outputs rendered content to stdout.

Token resolution order:
  1. Generated   — uuid, datestamp, updated, date_iso (computed at render time)
  2. Config      — derived from vault-config.yaml frontmatter.optional defaults
  3. Content     — title, tags, aliases, summary, body, up, related
  4. Metadata    — source_path, source_link, classification, profile, etc.
  5. Custom      — templates.custom_tokens[].source == "static" (others skipped in MVP)
  6. Validate    — required tokens must be resolved; optional tokens → empty string

Special handling:
  - Fenced code blocks (```) — tokens inside are NOT processed
  - Templater syntax (<% %>) — preserved as-is
  - Escaped braces \\{\\{ — rendered as literal {{
  - List values (tags, aliases) — formatted as indented YAML list with leading newline

Usage:
  python3 token-render.py [--template FILE] [--tokens FILE] [--tokens-json JSON]
                           [--config PATH] [--help]
  Template content can also be read from stdin.

Exit codes:
  0 — success
  1 — error (unresolvable required token, file not found, invalid JSON, etc.)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

REQUIRED_TOKENS = {"uuid", "datestamp", "title"}

# Tokens whose values, when a list, are formatted as indented YAML sequences
LIST_TOKENS = {"tags", "aliases"}

# ──────────────────────────────────────────────────────────────────────────────
# YAML config loader (stdlib-only fallback + PyYAML if available)
# ──────────────────────────────────────────────────────────────────────────────

def _load_yaml_stdlib(text):
    """
    Minimal YAML loader that extracts simple scalar and list values.
    Handles the subset of YAML used in vault-config.yaml:
      - key: value
      - key:
          - item
    Does NOT handle nested mappings, multi-line strings, or anchors.
    Returns a nested dict (best-effort).
    """
    lines = text.splitlines()
    result = {}
    stack = [(result, -1)]  # (current_dict, indent_level)

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()

        # Skip blank lines and comments
        if not stripped or stripped.lstrip().startswith("#"):
            i += 1
            continue

        indent = len(line) - len(line.lstrip())
        content = stripped.lstrip()

        # Pop stack to correct parent
        while len(stack) > 1 and stack[-1][1] >= indent:
            stack.pop()

        current_dict = stack[-1][0]

        if content.startswith("- "):
            # List item — find the list key in parent
            # The list is stored under the last key that had no value
            pass  # handled below via list accumulation

        elif ":" in content:
            key, _, value = content.partition(":")
            key = key.strip()
            value = value.strip()

            if value == "" or value.startswith("#"):
                # Mapping key — peek ahead for list items or nested mapping
                next_items = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].rstrip()
                    if not next_line or next_line.lstrip().startswith("#"):
                        j += 1
                        continue
                    next_indent = len(lines[j]) - len(lines[j].lstrip())
                    next_content = next_line.lstrip()
                    if next_content.startswith("- "):
                        if next_indent > indent:
                            item = next_content[2:].strip()
                            # Strip inline comments
                            item = item.split(" #")[0].strip()
                            # Strip quotes
                            if (item.startswith('"') and item.endswith('"')) or \
                               (item.startswith("'") and item.endswith("'")):
                                item = item[1:-1]
                            next_items.append(item)
                            j += 1
                            continue
                    break
                if next_items:
                    current_dict[key] = next_items
                    i = j
                    continue
                else:
                    # Nested mapping
                    sub = {}
                    current_dict[key] = sub
                    stack.append((sub, indent))
            else:
                # Scalar value
                # Strip inline comments
                value = value.split(" #")[0].strip()
                # Strip quotes
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                current_dict[key] = value

        i += 1

    return result


def load_yaml(path):
    """Load YAML file, preferring PyYAML if available."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _load_yaml_stdlib(text)


# ──────────────────────────────────────────────────────────────────────────────
# Token resolution
# ──────────────────────────────────────────────────────────────────────────────

def format_list_token(items):
    """Format a list as an indented YAML sequence with a leading newline.

    Input:  ["type/note/normal", "topic/applied/tools"]
    Output: "\\n  - type/note/normal\\n  - topic/applied/tools"

    This allows `tags:{{tags}}` to render as:
      tags:
        - type/note/normal
        - topic/applied/tools
    """
    if not items:
        return ""
    lines = ["  - " + str(item) for item in items]
    return "\n" + "\n".join(lines)


def resolve_generated_tokens(now):
    """Return generated token dict from a datetime instance."""
    return {
        "uuid": now.strftime("%Y%m%d%H%M%S"),
        "datestamp": now.strftime("%Y-%m-%d"),
        "updated": now.strftime("%Y-%m-%d %H:%M"),
        "date_iso": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def resolve_config_tokens(config):
    """Extract default values from frontmatter.optional entries as tokens."""
    tokens = {}
    frontmatter = config.get("frontmatter", {})
    optional = frontmatter.get("optional", [])
    if isinstance(optional, list):
        for entry in optional:
            if isinstance(entry, dict):
                token_name = entry.get("token")
                default = entry.get("default")
                if token_name and default is not None:
                    tokens[token_name] = str(default)
    # Also extract profile name as a token
    profile = config.get("profile")
    if profile:
        tokens.setdefault("profile", profile)
    return tokens


def resolve_custom_tokens(config):
    """Extract static custom tokens from templates.custom_tokens.

    Only source == "static" tokens are resolved mechanically in MVP.
    computed/frontmatter/context tokens require runtime context not available
    here and are silently skipped (they resolve to empty string).
    """
    tokens = {}
    templates = config.get("templates", {})
    custom = templates.get("custom_tokens", [])
    if isinstance(custom, list):
        for entry in custom:
            if isinstance(entry, dict) and entry.get("source") == "static":
                name = entry.get("name")
                value = entry.get("value")
                if name and value is not None:
                    tokens[name] = str(value)
    return tokens


def build_token_map(now, config, user_tokens):
    """Build the final token map, merging all sources in resolution order.

    Resolution order (later layers win for the same key):
      generated > config-sourced > user-provided > custom-static

    The spec resolution order puts generated first so that uuid/datestamp are
    always correct, and user_tokens (content + metadata) override config defaults.
    Custom static tokens come last but cannot override built-ins or user tokens.
    """
    tokens = {}

    # 1. Generated
    tokens.update(resolve_generated_tokens(now))

    # 2. Config-sourced
    tokens.update(resolve_config_tokens(config))

    # 3 + 4. Content + Metadata (user-provided via --tokens / --tokens-json)
    for key, value in user_tokens.items():
        if isinstance(value, list) and key in LIST_TOKENS:
            tokens[key] = format_list_token(value)
        elif isinstance(value, list):
            # Generic list: join with comma for non-YAML-list tokens
            tokens[key] = ", ".join(str(v) for v in value)
        else:
            tokens[key] = str(value) if value is not None else ""

    # 5. Custom static tokens (only if not already set)
    custom = resolve_custom_tokens(config)
    for key, value in custom.items():
        tokens.setdefault(key, value)

    return tokens


# ──────────────────────────────────────────────────────────────────────────────
# Template rendering
# ──────────────────────────────────────────────────────────────────────────────

# Matches fenced code blocks: opening ``` (with optional language tag)
_FENCE_OPEN = re.compile(r"^```")
# Matches {{token_name}} — token names are lowercase alphanumeric + underscore
_TOKEN_RE = re.compile(r"\\?\{\{([a-z_][a-z0-9_]*)\}\}")


def _split_segments(text):
    """Split template text into alternating (unprotected, protected) segments.

    Protected segments are fenced code blocks (``` ... ```) and Templater
    expressions (<% ... %>).

    Returns list of (content, is_protected) tuples.
    """
    segments = []
    pos = 0
    length = len(text)

    # Patterns for protected regions
    fence_pat = re.compile(r"```.*?```", re.DOTALL)
    templater_pat = re.compile(r"<%.*?%>", re.DOTALL)

    # Build a combined list of protected spans
    protected_spans = []
    for m in fence_pat.finditer(text):
        protected_spans.append((m.start(), m.end(), m.group()))
    for m in templater_pat.finditer(text):
        protected_spans.append((m.start(), m.end(), m.group()))

    # Sort by start position
    protected_spans.sort(key=lambda x: x[0])

    # Merge overlapping spans (shouldn't happen in well-formed templates)
    merged = []
    for span in protected_spans:
        if merged and span[0] < merged[-1][1]:
            # Overlapping — extend
            prev = merged[-1]
            merged[-1] = (prev[0], max(prev[1], span[1]), text[prev[0]:max(prev[1], span[1])])
        else:
            merged.append(span)

    cursor = 0
    for start, end, raw in merged:
        if cursor < start:
            segments.append((text[cursor:start], False))
        segments.append((raw, True))
        cursor = end

    if cursor < length:
        segments.append((text[cursor:], False))

    return segments


def render_template(template_text, token_map):
    """Render template by substituting {{token}} placeholders.

    Rules:
    - Tokens inside fenced code blocks are NOT substituted.
    - Templater syntax (<% %>) is preserved as-is.
    - \\{\\{ → literal {{ (escape sequence).
    - Unknown tokens resolve to empty string.
    """
    segments = _split_segments(template_text)
    output_parts = []

    for content, is_protected in segments:
        if is_protected:
            output_parts.append(content)
            continue

        # Process token substitutions in unprotected segment
        def replace_token(m):
            full_match = m.group(0)
            # Escaped: \{{ → literal {{
            if full_match.startswith("\\"):
                return "{{"
            token_name = m.group(1)
            return token_map.get(token_name, "")

        output_parts.append(_TOKEN_RE.sub(replace_token, content))

    return "".join(output_parts)


def validate_required_tokens(token_map, template_text):
    """Check that all required tokens were resolved in the token_map.

    A required token is considered unresolvable if it is not present in
    token_map (not merely empty — generated tokens always produce a value,
    so absence means something is genuinely wrong).

    Returns list of error messages (empty list = all good).
    """
    errors = []
    for name in REQUIRED_TOKENS:
        if name not in token_map or token_map[name] == "":
            # Check whether the template actually uses this token
            if "{{" + name + "}}" in template_text:
                errors.append(f"Required token '{{{{{name}}}}}' is unresolvable.")
    return errors


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        prog="token-render.py",
        description=(
            "Resolve {{token}} placeholders in Tomo templates. "
            "Reads template from --template FILE or stdin. "
            "Outputs rendered content to stdout."
        ),
    )
    parser.add_argument(
        "--template",
        metavar="FILE",
        help="Path to the template file. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "--tokens",
        metavar="FILE",
        help="JSON file mapping token names to values.",
    )
    parser.add_argument(
        "--tokens-json",
        metavar="JSON",
        help="Inline JSON string mapping token names to values.",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default="config/vault-config.yaml",
        help="Path to vault-config.yaml (default: config/vault-config.yaml).",
    )
    return parser.parse_args()


def load_template(args):
    if args.template:
        try:
            with open(args.template, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:
            print(f"Error: cannot read template file: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        return sys.stdin.read()


def load_user_tokens(args):
    tokens = {}

    if args.tokens:
        try:
            with open(args.tokens, "r", encoding="utf-8") as fh:
                tokens.update(json.load(fh))
        except OSError as exc:
            print(f"Error: cannot read tokens file: {exc}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as exc:
            print(f"Error: invalid JSON in tokens file: {exc}", file=sys.stderr)
            sys.exit(1)

    if args.tokens_json:
        try:
            inline = json.loads(args.tokens_json)
            tokens.update(inline)
        except json.JSONDecodeError as exc:
            print(f"Error: invalid JSON in --tokens-json: {exc}", file=sys.stderr)
            sys.exit(1)

    return tokens


def load_config(config_path):
    if not os.path.exists(config_path):
        # Config is optional — return empty dict if not found
        return {}
    try:
        return load_yaml(config_path)
    except Exception as exc:
        print(f"Warning: could not load config '{config_path}': {exc}", file=sys.stderr)
        return {}


def main():
    args = parse_args()

    template_text = load_template(args)
    user_tokens = load_user_tokens(args)
    config = load_config(args.config)

    now = datetime.now(timezone.utc)
    token_map = build_token_map(now, config, user_tokens)

    # Validate required tokens before rendering
    errors = validate_required_tokens(token_map, template_text)
    if errors:
        for err in errors:
            print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    rendered = render_template(template_text, token_map)
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
