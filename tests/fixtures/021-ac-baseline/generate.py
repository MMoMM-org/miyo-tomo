#!/usr/bin/env python3
# version: 1.1.0
"""generate.py — Regenerate ac-baseline.json from the test-015-t4-1 fixture set.

Deterministic: no timestamps, no randomness, no live Kado calls.
Run from repo root:

    ./venv/bin/python tests/fixtures/021-ac-baseline/generate.py

Output: tests/fixtures/021-ac-baseline/ac-baseline.json
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]  # tests/fixtures/021-ac-baseline/ → repo root
SCRIPTS = REPO / "tomo" / "scripts"
FIXTURE_SRC = REPO / "tests" / "fixtures" / "test-015-t4-1"
OUT_FILE = REPO / "tests" / "fixtures" / "021-ac-baseline" / "ac-baseline.json"
AGENT_PATH = REPO / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md"

sys.path.insert(0, str(SCRIPTS))

# Load shared-ctx-builder (hyphenated filename — importlib required)
_spec = importlib.util.spec_from_file_location(
    "shared_ctx_builder", SCRIPTS / "shared-ctx-builder.py"
)
scb = importlib.util.module_from_spec(_spec)
scb.__package__ = "shared_ctx_builder"
sys.modules["shared_ctx_builder"] = scb
_spec.loader.exec_module(scb)

SCENARIOS = [
    "scenario_a_accumulation_match.json",
    "scenario_b_no_match.json",
    "scenario_c_placeholder_wins.json",
    "scenario_d_absent_index.json",
]


def _extract_step4_blocks(agent_text: str) -> tuple[str, str]:
    """Return (condition_a_text, condition_c_text) from Step 4.

    Condition B (Accumulation cluster trigger) was retired in T3.2 (spec 021
    ADR-10). This function no longer requires or captures the B block.
    """
    step4_start = agent_text.find("### Step 4")
    step5_start = agent_text.find("### Step 5")
    step4 = agent_text[step4_start:step5_start].strip()

    a_start = step4.find("**Classification Guard:**")
    c_start = step4.find("**Placeholder link trigger.**")

    if -1 in (a_start, c_start):
        raise RuntimeError(
            "inbox-analyst.md Step 4: expected Condition A and C blocks not found — "
            "has the spec been modified? Check Step 4 block headings."
        )

    # Condition A runs from its heading to the start of Condition C
    a_text = step4[a_start:c_start].strip()
    # Condition C runs from its heading to the end of Step 4
    c_text = step4[c_start:].strip()
    return a_text, c_text


def generate() -> int:
    agent_text = AGENT_PATH.read_text(encoding="utf-8")
    condition_a, condition_c = _extract_step4_blocks(agent_text)

    version_match = re.search(r"#\s*version:\s*(\S+)", agent_text)
    agent_version = version_match.group(1) if version_match else "unknown"

    baseline_entries = []
    for fname in SCENARIOS:
        path = FIXTURE_SRC / fname
        if not path.exists():
            print(f"ERROR: fixture not found: {path}", file=sys.stderr)
            return 1

        data = json.loads(path.read_text(encoding="utf-8"))
        ctx = data["shared_ctx"]

        # Rebuild cache from fixture's mocs + placeholder_links
        cache: dict = {
            "map_notes": [
                {
                    "path": m["path"],
                    "title": m["title"],
                    "topics": m["topics"],
                }
                for m in ctx.get("mocs", [])
            ],
        }
        if "placeholder_links" in ctx:
            cache["placeholder_links"] = ctx["placeholder_links"]

        built_mocs = scb.build_mocs(cache)
        built_placeholders = scb.build_placeholder_links(cache)

        baseline_entries.append({
            "fixture": fname,
            "source": f"tests/fixtures/test-015-t4-1/{fname}",
            "mocs": built_mocs,
            "placeholder_links": built_placeholders,
            "item": data["item"],
        })

    baseline = {
        "_meta": {
            "spec": "021-moc-propose-consolidation",
            "task": "T3.0",
            "purpose": (
                "Golden baseline: Conditions A+C shared_ctx inputs BEFORE "
                "Condition B (accumulation) removal in T3.2"
            ),
            "deterministic_artifact": (
                "mocs + placeholder_links arrays from each test-015-t4-1 fixture, "
                "as produced by build_mocs() + build_placeholder_links()"
            ),
            "agent_version_at_capture": agent_version,
            "regeneration_command": "./venv/bin/python tests/fixtures/021-ac-baseline/generate.py",
            "fixture_set": "tests/fixtures/test-015-t4-1/",
            "conditions_captured": [
                "A (Classification Guard)",
                "C (Placeholder link trigger)",
            ],
            # condition_b_text removed in T3.2 — Condition B retired per spec 021 ADR-10
        },
        "agent_step4_ac_contract": {
            "condition_a": condition_a,
            "condition_c": condition_c,
        },
        "fixtures": baseline_entries,
    }

    output = json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=False)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(output, encoding="utf-8")
    print(f"Written {len(output.encode('utf-8'))} bytes to {OUT_FILE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(generate())
