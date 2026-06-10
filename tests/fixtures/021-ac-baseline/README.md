# 021-ac-baseline — Golden Baseline for Conditions A + C

Spec: `021-moc-propose-consolidation`, Task T3.0.

## What This Baseline Represents

`ac-baseline.json` captures the deterministic inputs that Conditions A and C in
`inbox-analyst.md Step 4` evaluate against, derived from the four scenario fixtures
in `tests/fixtures/test-015-t4-1/`. It was generated **before** Condition B
(accumulation cluster trigger) is removed in T3.1/T3.2.

**The two fields captured are:**

- `mocs` — the scored MOC list Condition A (Classification Guard) matches against.
  Derived by `shared-ctx-builder.py::build_mocs()`.
- `placeholder_links` — the placeholder list Condition C (Placeholder link trigger)
  scans. Derived by `shared-ctx-builder.py::build_placeholder_links()`.

These fields are **not affected by removing `accumulation_index`** (Condition B).
After T3.1/T3.2, regenerating this file must produce byte-identical output.

**Also captured:**

- `agent_step4_ac_contract` — verbatim text of Condition A + C blocks from
  `inbox-analyst.md Step 4` at the time of baseline capture, plus the Condition B
  text that is slated for removal. This is a contract snapshot, not used for
  byte-comparison; it shows what the agent said before B was removed.

## Why the LLM Output Is Not the Baseline

The inbox-analyst is an LLM agent — its per-item `result.json` output (Step 10) is
NOT deterministic across runs. The golden baseline is therefore on the **deterministic
INPUT contract** (the `mocs` and `placeholder_links` that A/C evaluate against), not
on LLM-generated prose.

## How It Was Generated

```
./venv/bin/python tests/fixtures/021-ac-baseline/generate.py
```

From repo root. No live Kado, no timestamps, no randomness.

## How T3.2 Should Assert Byte-Equality

T3.2 removes Condition B from `inbox-analyst.md`. To prove A/C inputs are
unchanged, the test should:

1. Run `generate.py` after the T3.1/T3.2 edits.
2. Compare the new output bytes to `ac-baseline.json`:

```python
import json
from pathlib import Path

baseline = json.loads(Path("tests/fixtures/021-ac-baseline/ac-baseline.json").read_text())
# Regenerate in a temp file
import subprocess, tempfile, shutil
tmp = Path(tempfile.mkdtemp())
# Copy generate.py to a dir, run it, compare output
# OR: call generate() directly and compare the dict

# Structural assertion: for each fixture entry, mocs and placeholder_links
# must be byte-identical to the baseline
for entry in baseline["fixtures"]:
    fixture_name = entry["fixture"]
    assert entry["mocs"] == <regenerated_entry["mocs"]>
    assert entry["placeholder_links"] == <regenerated_entry["placeholder_links"]>
```

Or more simply, byte-compare the entire JSON output:

```bash
./venv/bin/python tests/fixtures/021-ac-baseline/generate.py
# Check SHA256 matches baseline:
# efe09e26c0b9d95d5e36bee598420f44b2443693c54001d6f93f61c8d3ed5343
sha256sum tests/fixtures/021-ac-baseline/ac-baseline.json
```

The `agent_step4_ac_contract` section will differ after T3.2 (Condition B text
removed from agent), so byte-comparison of the entire file only makes sense
BEFORE T3.2 edits the agent. T3.2's assertion should compare the `fixtures[].mocs`
and `fixtures[].placeholder_links` arrays only — not the `_meta.condition_b_text`
or `agent_step4_ac_contract` fields, which will legitimately change.

**Recommended T3.2 assertion:** write a pytest test that:
1. Calls `generate.py` (or inlines the same logic)
2. Loads `ac-baseline.json`
3. For each of the 4 fixture entries, asserts `mocs == baseline_mocs` AND
   `placeholder_links == baseline_placeholder_links` (dict equality, no string-compare)

## Reproducibility Confirmation

Generated twice in sequence, SHA256 was identical both times:
`efe09e26c0b9d95d5e36bee598420f44b2443693c54001d6f93f61c8d3ed5343`
