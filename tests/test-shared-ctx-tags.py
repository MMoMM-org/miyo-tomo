#!/usr/bin/env python3
# version: 0.1.0
"""test-shared-ctx-tags.py — Smoke tests for shared-ctx-builder.build_tag_prefixes.

Covers the per-prefix proposable-based policy that replaced
`tomo.suggestions.{proposable,excluded}_tag_prefixes` on 2026-04-21.

Happy path:
  - proposable:true prefixes emitted; proposable:false filtered out
  - cache.tag_taxonomy.prefixes.*.known_values merged in
Drift guards (exit 1 + actionable message):
  - `tags.prefixes` missing entirely
  - `tags.prefixes` is a list (legacy flat shape — the bug that blocked Pass 1)
  - a prefix entry is missing `proposable`
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stderr
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "shared_ctx_builder", SCRIPTS_DIR / "shared-ctx-builder.py"
)
scb = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(scb)


def _must(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def _expect_exit(fn, *args, must_contain: str = "", label: str = ""):
    buf = io.StringIO()
    try:
        with redirect_stderr(buf):
            fn(*args)
    except SystemExit as e:
        _must(e.code == 1, f"{label}: expected exit 1, got {e.code}")
        err = buf.getvalue()
        if must_contain:
            _must(must_contain in err, f"{label}: expected stderr to mention {must_contain!r}, got {err!r}")
        return
    _must(False, f"{label}: expected SystemExit, got success")


# Happy path fixture
CACHE = {
    "tag_taxonomy": {
        "prefixes": {
            "topic": {"known_values": ["applied/docker", "applied/tools"]},
            # Cache may surface prefixes the user hasn't declared — harmless.
            "unseen-prefix": {"known_values": ["x"]},
        }
    }
}

VAULT_CFG = {
    "tags": {
        "prefixes": {
            "type": {
                "description": "Note type",
                "known_values": ["note/normal", "others/moc"],
                "wildcard": False,
                "proposable": True,
                "required_for": ["atomic_note", "map_note"],
            },
            "topic": {
                "description": "Topic area",
                "known_values": ["knowledge/lyt"],
                "wildcard": True,
                "proposable": True,
                "required_for": [],
            },
            "Raindrop": {
                "description": "Raindrop import",
                "known_values": ["Obsidian"],
                "wildcard": False,
                "proposable": False,
                "required_for": [],
            },
        }
    }
}


def test_happy_path_filters_by_proposable():
    out = scb.build_tag_prefixes(CACHE, VAULT_CFG)
    names = {p["name"] for p in out}
    _must(names == {"type", "topic"}, f"expected type+topic, got {names}")
    # proposable flag is not leaked downstream
    for p in out:
        _must("proposable" not in p, f"{p['name']}: proposable should not leak")
    print("[PASS] happy path: only proposable:true prefixes are emitted")


def test_cache_values_merge_into_user_prefix():
    out = scb.build_tag_prefixes(CACHE, VAULT_CFG)
    topic = next(p for p in out if p["name"] == "topic")
    _must("knowledge/lyt" in topic["known_values"], "user value preserved")
    _must("applied/docker" in topic["known_values"], "cache value merged in")
    _must("applied/tools" in topic["known_values"], "cache value merged in")
    # Dedupe, preserve order
    _must(len(topic["known_values"]) == len(set(topic["known_values"])),
          "known_values must be deduped")
    print("[PASS] cache known_values merge into matching user prefix")


def test_missing_tags_section_errors():
    _expect_exit(
        scb.build_tag_prefixes, CACHE, {},
        must_contain="/explore-vault --confirm",
        label="missing tags.prefixes",
    )
    print("[PASS] missing tags.prefixes → exit 1 with /explore-vault hint")


def test_legacy_list_shape_errors():
    """The exact shape that blocked Pass 1 on 2026-04-21."""
    _expect_exit(
        scb.build_tag_prefixes, CACHE,
        {"tags": {"prefixes": ["type", "status", "topic"]}},
        must_contain="must be a dict",
        label="legacy list shape",
    )
    print("[PASS] legacy flat-list tags.prefixes → exit 1 (regression guard)")


def test_entry_missing_proposable_errors():
    _expect_exit(
        scb.build_tag_prefixes, CACHE,
        {"tags": {"prefixes": {
            "type": {
                "description": "x",
                "known_values": [],
                "wildcard": False,
                # missing proposable
                "required_for": [],
            }
        }}},
        must_contain="is missing `proposable`",
        label="entry missing proposable",
    )
    print("[PASS] entry missing proposable → exit 1 with field name")


def main() -> int:
    test_happy_path_filters_by_proposable()
    test_cache_values_merge_into_user_prefix()
    test_missing_tags_section_errors()
    test_legacy_list_shape_errors()
    test_entry_missing_proposable_errors()
    print("\n\u2713 All shared-ctx-builder tag-prefix tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
