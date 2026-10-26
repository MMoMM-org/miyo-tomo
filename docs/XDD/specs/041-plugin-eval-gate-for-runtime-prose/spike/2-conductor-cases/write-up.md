## Step 2 result: the `4350ddd` ordering defect is caught, and the STRICT stop is observed for the first time

**Setup.** Two throwaway plugins named `tomo`, each shipping only `agents/synthesis-conductor.md`: one from `main` and one from `4350ddd^`, the commit before the fix. Both got the same two cases. The prompt mirrors production: dispatch `tomo:synthesis-conductor` with the exact prompt `/inbox` uses.

**The scaffold stubs the scripts instead of running them.** `scaffold.sh` writes stub `scripts/*.py` that log their call and print plausible output, plus a `tomo-tmp/routing-plan.json` with one approved suggestions doc. The stubs need no Kado mock and no real vault, and the output is deterministic. What is under test is the conductor's prose, which only the LLM layer can get wrong.

- **Case A, `audit-gates-delivery`:** the audit stub exits 0.
- **Case B, `audit-mismatch-stops`:** the audit stub prints `RESULT: MISMATCH-MARKER-91c2 …` and exits 1.

| Grader | `main` | `4350ddd^` |
|---|---|---|
| A: `tool_order` `instructions-diff.py` before `upload-rendered.py` | ✅ Bash@5 before @6 | ❌ audit at @7, after upload @5 |
| A: `tool_order` `instructions-diff.py` before `state-promoter.py` | ✅ | ❌ |
| B: `tool_used upload-rendered.py`, `min: 0, max: 0` | ✅ 0× | ❌ 1× |
| B: `tool_used state-promoter.py`, `min: 0, max: 0` | ✅ 0× | ❌ 1× |
| B: audit ran (control) | ✅ | ✅ |
| B: diff reported verbatim (`regex` over `last_message`) | ✅ | ✅ |
| Score | 1.0 / 1.0 | 0.33 / 0.6 |

**What this establishes:**

- **The `4350ddd` defect is caught.** Every ordering grader is red against the pre-fix prose and green on `main`.
- **The STRICT stop is now observed.** The spec 036 close-out says the conductor's STRICT stop under a genuine mismatch "has never been observed". On `main` it now has been: the audit ran, nothing was uploaded, no state flipped, and the diff line reached the report.
- **Cost:** about $0.20 per arm for both cases (haiku conductor, 1 run each, `--ablation none`), about 45 s wall-clock with `-j 2`.

**Caveats:**

- `runs: 1`. An LLM layer needs the default of 3 or more before a single green counts as a gate.
- The stubs test orchestration only. Script behaviour stays with pytest, which already covers it.
- Every run needs `--scaffold` and `--allow-tools Bash`. The scaffold runs as the user, so the case files must stay owner-authored.

**Next decision.** Manifest and layout. Both spikes lived outside the repo. Making this permanent means one of two things:

- a `.claude-plugin/plugin.json` over `tomo/dot_claude/`, which makes the runtime tree a dual-purpose artifact;
- or a manifest generated at eval time, for example by a `scripts/run-evals.sh` that assembles a plugin directory, as these spikes did.

The second avoids touching what `install-tomo.sh` and `update-tomo.sh` copy into the instance.
