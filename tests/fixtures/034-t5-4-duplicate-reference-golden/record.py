#!/usr/bin/env python3
# version: 1.0.0
"""Record the spec-034 T5.4 duplicate-reference action-list baseline.

Drives `lib.render_actions.build_actions` — the real Pass-2 action assembler,
with no Kado client — over `input.json` and writes the whole action list to
`actions.json`.

Run from the repo root:  ./venv/bin/python tests/fixtures/034-t5-4-duplicate-reference-golden/record.py

This exists so the baseline can be re-derived and its provenance checked. It is
NOT run by the suite: the fixture it produced was committed before the T5.4
implementation was written, which is what makes it evidence rather than a
restatement of whatever the new code emits. Re-running it after a deliberate
behaviour change is the only legitimate reason to regenerate — and then the
diff is the review.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent
REPO_ROOT = FIXTURE_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT / "tomo" / "scripts"))

from lib.render_actions import build_actions  # noqa: E402

data = json.loads((FIXTURE_DIR / "input.json").read_text(encoding="utf-8"))
actions, skipped_assets = build_actions(
    data["manifest"],
    data["confirmed"],
    data["daily_updates"],
    data["skipped"],
    data["cfg"],
    kado_client=None,
)
(FIXTURE_DIR / "actions.json").write_text(
    json.dumps(
        {"actions": actions, "skipped_assets": skipped_assets},
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(f"recorded {len(actions)} actions, {len(skipped_assets)} skipped assets")
