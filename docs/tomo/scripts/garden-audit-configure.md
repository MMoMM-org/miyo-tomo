# WHY: garden-audit-configure.py

> Rationale for decisions in `tomo/scripts/garden-audit-configure.py`.
> Wizard-support helper for `garden-auditor.md` — two modes: `--summarize` and `--write`.

## Why a Separate Script Instead of Agent Reading/Writing Directly (Bugs A + B)

Two bugs in the original garden-auditor.md wizard drove the creation of this helper:

**Bug A — Read-tool 256 KB cap on garden-audit-doc.json**: The wizard Step A instructed
the agent to read `tomo-tmp/garden-audit-doc.json` with the `Read` tool to compute cluster
counts. On a real vault, the doc can exceed 256 KB (large vaults produce hundreds of
findings with full detail). The Read tool truncates at 256 KB — the agent would silently
compute clusters from a partial doc, misrepresenting the distribution.

`--summarize` reads the doc in Python (no cap), computes cluster counts, and emits a
compact plain-text summary that fits comfortably in the agent's context window.

**Bug B — Write-tool read-before-write trap on garden-audit-exclusions.yaml**: The wizard
Step D instructed the agent to use the `Write` tool to write the exclusion config. The
`Write` tool enforces read-before-write: the agent must `Read` the file first. On a
first-run, the seed file exists (created by `install-tomo`) but writing a freshly
composed YAML without reading first fails the tool's guard. The agent would have to
read the seed, discard it, and write — adding a round trip and fragility around the
read-before-write contract.

`--write` receives the user's choices as a JSON string, validates them, composes the
YAML entirely in Python, and writes to `--output` unconditionally. No read needed.

## Why `--summarize` Writes to Stdout (Not a File)

The agent receives the cluster summary as a Bash capture (`$(...)`) and presents it to
the user verbatim. Writing to a file would add an extra Read step and risk the 256 KB
cap again on the cluster summary itself (though in practice the summary is always small).
Stdout is the natural pipe contract: Bash → agent variable → user message.

## Why `--write` Takes `--choices` as a File Path (Not an Inline JSON String)

The agent assembles choices from the user's AskUserQuestion answers and writes them to a
**new** temp file (`tomo-tmp/garden-audit-choices.json`) via the `Write` tool, then passes
the file path to `--choices`. Two reasons favour the file-path approach over inline JSON:

1. **Shell quoting fragility on large JSON**: Passing a multi-entry JSON object as a
   shell argument requires the agent to produce correctly quoted JSON inside a Bash
   heredoc or single-quoted string. A single unescaped `'` or newline in a reason field
   breaks the shell parse. File I/O eliminates the quoting surface entirely.

2. **New-file Write has no read-before-write guard**: The Write tool enforces
   read-before-write on *existing* files. `tomo-tmp/garden-audit-choices.json` is a new
   file — the agent creates it fresh each wizard run, so no read is needed. This cleanly
   avoids the same trap as Bug B (see above) while keeping the choices data off the shell
   command line.

The choices file is transient (tomo-tmp/ is not versioned) and is overwritten on each
wizard run. No cleanup step is needed.

## Why `configured: true` is Always Written by the Script

The garden-auditor agent Step 3 detects first-run via `configured: false` (or absence
of the flag). The seed config ships with `configured: false` to trigger the wizard on
first use. After the wizard completes — even when the user confirms zero exclusions —
`configured: true` must be written to prevent the wizard from re-running on subsequent
audits. Delegating this to the script (rather than the agent) ensures it is always set
regardless of which code path the agent takes through the wizard.

## Why `--summarize` Uses OR Logic for Cluster Thresholds

A folder qualifies as an abnormality cluster when it has ≥10 absolute findings **OR**
≥20% of the total. The OR condition means: even a folder with fewer than 10 findings
is flagged if it dominates the vault's finding distribution. This catches both large
vaults (where 20% of 200 findings = 40) and small vaults (where 6 findings in one
folder = 100% dominance). Using AND instead would miss the small-vault case — a user
with 6 findings all in `Calendar/` would see "no clusters" even though Calendar is the
only problem area.

## Why Validation Is in the Script, Not the Agent

The exclusions schema (`garden-audit-exclusions.schema.json`) has several constraints:
valid `target.type` values, valid `check` names, required `until` for temporary mode,
ISO date format on `created`/`until`. The agent cannot reliably enforce these during
composition — LLM paraphrasing of user choices can produce subtly wrong YAML. The script
validates each field and exits non-zero on violation, surfacing the error before writing.
This follows the same pattern as `garden-audit.py` (validates via the KadoClient
contract) and `garden-audit-parser.py` (validates via schema check before emitting actions).

## cwd-relative defaults (spec 030, 2026-07-21)

WHY `--input` defaults to `tomo-tmp/garden-audit-doc.json` and `--output` to
`config/garden-audit-exclusions.yaml`: the agent calls `--summarize` / `--write` bare from the
instance cwd (Tomo default-path standard — docs/ai/memory/general.md 2026-06-24). `--choices`
stays without a default (the agent writes a fresh temp choices file per run, so its path varies).
Because `--input`/`--output` now always resolve to a value, the old "requires --input" /
"requires --output" guards were removed; only `--write` without `--choices` remains an error.

## Version 0.4.0

WHY: 0.4.0 (spec 030) — cwd-relative defaults for `--input`/`--output` (agent calls bare);
`--choices` stays required for `--write`. `update-tomo.sh` skips unchanged versions.

## Version 0.5.0 — settings round-trip (2026-07-23)

WHY write_config re-reads the existing output file and carries its `settings` block over: the
wizard regenerates the whole YAML from the choices JSON, and settings (stale_moc_days,
advisory_pushback_days) are manually maintained knobs the wizard never asks about — without the
round-trip a reconfigure would silently reset the user's thresholds to defaults. The header
comment now distinguishes wizard-owned exclusions ("do not edit") from the manually-editable
settings block.
