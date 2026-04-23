# version: 0.1.0
"""yaml-fixer.py — Pre-process YAML to fix common errors before parsing.

Fixes applied (in order):
  1. Normalize line endings to LF
  2. Strip trailing whitespace per line
  3. Replace tab indentation with 2 spaces
  4. Repair inconsistent indentation levels
  5. Quote bare strings containing ':' that are unquoted values
  6. Auto-close unclosed sequences/mappings at EOF

Usage:
  python3 yaml-fixer.py [FILE]          Fix YAML from FILE or stdin, output to stdout
  python3 yaml-fixer.py --check [FILE]  Exit 0 if already valid, 1 if needs fixing (no output)
  python3 yaml-fixer.py --help          Show this help

Exit codes:
  0 — success (output is valid YAML, or was already valid)
  1 — unfixable: YAML could not be repaired (error written to stderr)
"""

import re
import sys
import argparse

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ---------------------------------------------------------------------------
# Fix: normalize line endings
# ---------------------------------------------------------------------------

def fix_line_endings(text: str) -> str:
    """Normalize all line endings to LF."""
    return text.replace('\r\n', '\n').replace('\r', '\n')


# ---------------------------------------------------------------------------
# Fix: strip trailing whitespace
# ---------------------------------------------------------------------------

def fix_trailing_whitespace(lines: list[str]) -> list[str]:
    return [line.rstrip() for line in lines]


# ---------------------------------------------------------------------------
# Fix: tab → space indentation
# ---------------------------------------------------------------------------

def fix_tabs(lines: list[str]) -> list[str]:
    """Replace leading tabs with 2 spaces each."""
    result = []
    for line in lines:
        stripped = line.lstrip('\t')
        n_tabs = len(line) - len(stripped)
        if n_tabs:
            line = ('  ' * n_tabs) + stripped
        result.append(line)
    return result


# ---------------------------------------------------------------------------
# Fix: indentation repair
# ---------------------------------------------------------------------------

def _indent_level(line: str) -> int:
    return len(line) - len(line.lstrip(' '))


def fix_indentation(lines: list[str]) -> list[str]:
    """
    Detect and fix inconsistent indentation.

    Strategy: collect all unique indent levels (excluding 0) from non-blank,
    non-comment lines, then check if they form a consistent multiple. If the
    smallest indent unit is odd or creates ambiguous nesting, round each level
    to the nearest multiple of 2.

    Conservative: only normalises lines whose indent is NOT already a multiple
    of 2.
    """
    # Collect non-zero indent levels from content lines
    levels = set()
    for line in lines:
        if line.strip() and not line.strip().startswith('#'):
            lvl = _indent_level(line)
            if lvl > 0:
                levels.add(lvl)

    if not levels:
        return lines

    # Determine the smallest indent unit
    min_indent = min(levels)

    # If every level is already a multiple of 2, nothing to do
    if all(lvl % 2 == 0 for lvl in levels):
        return lines

    # Build a normalisation map: original level → corrected level
    # Round each level to nearest multiple of 2 that preserves nesting order
    sorted_levels = sorted(levels)
    norm_map: dict[int, int] = {}
    for i, lvl in enumerate(sorted_levels):
        # Nesting depth relative to the min unit
        depth = round(lvl / min_indent)
        norm_map[lvl] = depth * 2

    result = []
    for line in lines:
        if not line.strip():
            result.append(line)
            continue
        lvl = _indent_level(line)
        if lvl in norm_map and lvl != norm_map[lvl]:
            line = ' ' * norm_map[lvl] + line.lstrip(' ')
        result.append(line)
    return result


# ---------------------------------------------------------------------------
# Fix: quote bare strings containing ':'
# ---------------------------------------------------------------------------

# Matches a YAML mapping value that is a bare string containing ':'
# Key: value_with_colon_or_spaces
_BARE_VALUE_RE = re.compile(
    r'^(\s*[\w\-\.]+\s*:\s+)'   # group 1: key + colon + space(s)
    r'([^"\'\[{|>!&*#\s][^\n]*)'  # group 2: value — starts with non-special char
)


def _needs_quoting(value: str) -> bool:
    """Return True if value contains ':' and is not already quoted."""
    value = value.strip()
    if not value:
        return False
    # Already quoted
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return False
    # Contains a colon that would confuse YAML (colon followed by space or at end)
    return bool(re.search(r':\s|:$', value))


def fix_bare_colons(lines: list[str]) -> list[str]:
    """Quote bare string values that contain ':' followed by space or at EOL."""
    result = []
    for line in lines:
        m = _BARE_VALUE_RE.match(line)
        if m:
            prefix = m.group(1)
            value = m.group(2).rstrip()
            if _needs_quoting(value):
                # Escape any existing double-quotes in the value
                escaped = value.replace('"', '\\"')
                line = prefix + f'"{escaped}"'
        result.append(line)
    return result


# ---------------------------------------------------------------------------
# Fix: auto-close unclosed sequences / mappings at EOF
# ---------------------------------------------------------------------------

def fix_unclosed_at_eof(lines: list[str]) -> list[str]:
    """
    If the last non-empty line ends with ', ' or '- ', it is likely an
    unclosed list item. Strip the trailing separator.
    """
    if not lines:
        return lines

    # Find last non-empty line
    idx = len(lines) - 1
    while idx >= 0 and not lines[idx].strip():
        idx -= 1

    if idx < 0:
        return lines

    last = lines[idx]
    # Trailing ', ' or '- '
    if last.rstrip().endswith(', ') or last.rstrip().endswith('- '):
        lines = lines[:]
        lines[idx] = last.rstrip().rstrip(',').rstrip('-').rstrip()
    return lines


# ---------------------------------------------------------------------------
# Frontmatter extraction for markdown files
# ---------------------------------------------------------------------------

def split_frontmatter(text: str):
    """
    If text looks like a markdown file with YAML frontmatter, return
    (before, frontmatter, after). Otherwise return (None, text, None).
    The 'before' is either '' or None.
    """
    if not text.startswith('---'):
        return None, text, None
    # Find the closing '---'
    rest = text[3:]
    # Allow an optional newline right after the opening ---
    if rest.startswith('\n'):
        rest = rest[1:]
    close = re.search(r'\n---[ \t]*(\n|$)', rest)
    if close:
        frontmatter = rest[:close.start()]
        after = rest[close.end():]
        return '', frontmatter, after
    return None, text, None


def join_frontmatter(before, frontmatter: str, after) -> str:
    if before is None:
        return frontmatter
    return '---\n' + frontmatter + '\n---\n' + after


# ---------------------------------------------------------------------------
# Multi-document YAML support
# ---------------------------------------------------------------------------

def split_documents(text: str) -> list[str]:
    """
    Split text on '---' document separators.
    Returns a list of document strings (including the separator lines).
    """
    # Split but keep the separators with the following doc
    parts = re.split(r'(?m)^---[ \t]*$', text)
    return parts


# ---------------------------------------------------------------------------
# Apply all fixes to a single YAML block
# ---------------------------------------------------------------------------

def apply_fixes(text: str) -> str:
    """Apply all fixes to a YAML block (already line-ending-normalised)."""
    lines = text.split('\n')
    lines = fix_trailing_whitespace(lines)
    lines = fix_tabs(lines)
    lines = fix_indentation(lines)
    lines = fix_bare_colons(lines)
    lines = fix_unclosed_at_eof(lines)
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Top-level fix entry point
# ---------------------------------------------------------------------------

def fix_yaml(text: str) -> str:
    """Fix YAML text. Handles markdown frontmatter and multi-document YAML."""
    # Step 1: normalise line endings globally
    text = fix_line_endings(text)

    # Step 2: check if this is a markdown file with frontmatter
    before, body, after = split_frontmatter(text)
    if before is not None:
        # Only fix the frontmatter portion
        fixed_body = apply_fixes(body)
        return join_frontmatter(before, fixed_body, after)

    # Step 3: multi-document YAML
    docs = split_documents(text)
    if len(docs) > 1:
        fixed_docs = [apply_fixes(doc) for doc in docs]
        return '---'.join(fixed_docs)

    # Step 4: plain YAML
    return apply_fixes(text)


# ---------------------------------------------------------------------------
# Validation via PyYAML (optional)
# ---------------------------------------------------------------------------

def is_valid_yaml(text: str) -> bool:
    """Return True if text parses as valid YAML. Always True if PyYAML absent."""
    if not HAS_YAML:
        return True
    try:
        list(yaml.safe_load_all(text))
        return True
    except yaml.YAMLError:
        return False


def validate_yaml(text: str):
    """
    Return (ok: bool, error: str|None).
    If PyYAML is unavailable, always returns (True, None).
    """
    if not HAS_YAML:
        return True, None
    try:
        list(yaml.safe_load_all(text))
        return True, None
    except yaml.YAMLError as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog='yaml-fixer.py',
        description=(
            'Pre-process YAML to fix common errors before parsing.\n\n'
            'Fixes applied:\n'
            '  1. Normalize line endings to LF\n'
            '  2. Strip trailing whitespace\n'
            '  3. Replace tab indentation with 2 spaces\n'
            '  4. Repair inconsistent indentation\n'
            "  5. Quote bare strings containing ':'\n"
            '  6. Auto-close unclosed sequences/mappings at EOF\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '  python3 yaml-fixer.py myfile.yaml\n'
            '  cat broken.yaml | python3 yaml-fixer.py\n'
            '  python3 yaml-fixer.py --check myfile.yaml\n'
        ),
    )
    parser.add_argument(
        'file',
        nargs='?',
        metavar='FILE',
        help='YAML file to fix. Reads from stdin if not given.',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help=(
            'Check mode: exit 0 if input is already valid YAML, '
            '1 if it needs fixing. No output.'
        ),
    )
    args = parser.parse_args()

    # Read input
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as fh:
                text = fh.read()
        except OSError as e:
            print(f'yaml-fixer: error reading file: {e}', file=sys.stderr)
            sys.exit(1)
    else:
        text = sys.stdin.read()

    # Empty input is fine
    if not text.strip():
        if not args.check:
            sys.stdout.write(text)
        sys.exit(0)

    # --check mode: exit 0 if already valid, 1 if not
    if args.check:
        ok, _ = validate_yaml(text)
        sys.exit(0 if ok else 1)

    # Attempt to fix
    fixed = fix_yaml(text)

    # Validate the result
    ok, err = validate_yaml(fixed)
    if not ok:
        # If PyYAML is present and result still fails, report error
        print(f'yaml-fixer: could not repair YAML: {err}', file=sys.stderr)
        sys.exit(1)

    sys.stdout.write(fixed)
    # Ensure trailing newline
    if fixed and not fixed.endswith('\n'):
        sys.stdout.write('\n')

    sys.exit(0)


if __name__ == '__main__':
    main()
