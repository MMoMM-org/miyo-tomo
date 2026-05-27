# WHY: instruction-builder

> Rationale for decisions in `tomo/dot_claude/agents/instruction-builder.md`. This file was created as part of
> XDD 018 (Inbox Routing Redesign) to preserve institutional knowledge before
> the legacy agent was replaced.

## Pure Orchestrator Identity — No Markdown Assembly

WHY: The instruction-builder was explicitly constrained to call scripts in sequence and write their outputs, never to compose markdown or instruction content itself. LLMs drift from format specifications silently — they paraphrase locked wording, reorder sections, and invent fields. The render scripts (`instruction-render.py`, `suggestions-render.py`) are the single source of truth for document format. Splitting that responsibility between a script and an LLM creates two parallel format definitions that inevitably diverge. When a format bug surfaces, it becomes unclear which source needs fixing.

## Impersonation over Subagent Dispatch

WHY: `instruction-builder` must be impersonated by the main session, not dispatched as a subagent. Step 2.5 (FAN Resolve Subflow) dispatches `inbox-analyst` subagents via the `Agent` tool. The Anthropic platform prevents nested agents from using the `Agent` tool themselves — a dispatched `instruction-builder` would arrive in a context where the `Agent` tool is unavailable and would attempt to inline the analyst work serially. Impersonation keeps the dispatch happening from the top-level main session where the `Agent` tool is available.

## Never Redirect stderr into stdout on Script Calls

WHY: All pipeline scripts (`suggestion-parser.py`, `suggestions-reducer.py`, `suggestions-render.py`, `instruction-render.py`, `instructions-diff.py`, `upload-rendered.py`) print operational status and warnings to stderr by design. Appending `2>&1` to any command that redirects stdout to a file merges those log lines into the output file before the JSON blob. The script exits 0 because it succeeded, so the parse failure only surfaces on the next pipeline step's `json.load` call with a non-obvious error. The root cause — stderr contamination — is invisible. Leaving stderr unredirected surfaces it immediately in the Bash tool's output where the agent can see it.

## Step 1: Single Batch Config Load

WHY: All config fields the pipeline needs are read in one script call at Step 1. An earlier pattern read config fields individually at the point of first use, spreading config-read calls throughout the workflow. This made it harder to diagnose missing-field failures (they surface mid-pipeline rather than upfront) and wasted multiple round-trips for config that is static for the lifetime of a run.

## Step 2: Find the Companion suggestions-fan.md

WHY: The Force-Atomic flow produces a companion `*_suggestions-fan.md` document alongside the primary `*_suggestions.md`. When both exist and the companion is approved, they form a reconciliation pair that must be parsed together — the parser merges their content to resolve force-atomic notes that span the two documents. Ignoring an unapproved companion is intentional: the user has not yet decided on those items and the merge would include unreviewed content.

## Step 2.5: FAN Resolve Subflow Halts and Reports Before Step 3

WHY: When `pending_fan_resolutions` is non-empty, the parser has found Force Atomic notes without a corresponding atomic proposal. The system cannot proceed to render instructions for items that are still unresolved — the instruction set would be incomplete or inconsistent. Instead of partially rendering, the subflow writes a Force-Atomic Resolve doc to the vault and asks the user to review it before re-running `/inbox`. This ensures the user sees all atomic proposals before approving the full instruction set.

## Step 2.5: FAN Resolve Dispatches inbox-analyst with force_atomic Flag

WHY: The `force_atomic: true` flag bypasses the inbox-analyst's normal "worthiness gate" — the check that decides whether a note is worth splitting into an atomic note. For FAN resolve items, that decision has already been made by the upstream suggestions pass: the note was flagged as needing an atomic. Re-running the worthiness gate on the second pass would risk rejecting items the user already decided were worth splitting.

## Step 3: Fresh run-id for Pass-2 Run

WHY: The Pass-2 run uses a newly generated run ID, not the run ID from the upstream suggestions document. The upstream run ID identifies the Pass-1 analysis session. The Pass-2 run ID identifies the rendering and vault-write session. Mixing them would corrupt the `source_*` fields in the `tomo:` block, making it impossible to trace which Pass-2 execution produced a given output if the user runs Pass 2 multiple times (e.g. after editing the suggestions doc and re-approving).

## Step 3: --upstream-type Determines the Render Path

WHY: Three upstream document types exist — `suggestions`, `moc-proposal`, and `suggestions-fan` — each requiring different parsing and rendering logic. Determining the type from the `tomo.doc_type` frontmatter field on the upstream document (rather than from the filename pattern or a user-provided flag) makes the dispatch resilient to filename changes and ensures the type is always read from the authoritative source.

## Step 4: upload-rendered.py Handles kado-write, Not the Agent

WHY: The `upload-rendered.py` script handles the distinction between markdown files (written via `operation=note`) and binary or structured files (written via `operation=file` with base64 encoding). If the agent called `kado-write` directly for each file, it would need to implement this distinction itself, and would need to know which files in the rendered output directory require which operation. This logic is concentrated in the script, which is the correct location for it.

## Step 5: Coverage Audit Before Reporting

WHY: A prior version reported "Pass 2 complete" without verifying that every approved suggestion had a corresponding instruction. Users discovered discrepancies only when trying to apply instructions and finding items missing. The `instructions-diff.py` audit catches count mismatches and per-item coverage gaps before the user sees the success report. Exit code 1 from the audit stops the pipeline — the agent reports the diff verbatim and does not claim success.

## MOC-Branch: One Instructions Doc for All Clusters

WHY: When the user approves multiple MOC proposals simultaneously, the instruction-builder produces a single bundled `instructions.json` covering all approved clusters. An earlier approach produced one instructions doc per cluster. This was rejected because: (a) the user had to apply N separate instruction files for what was conceptually a single operation, and (b) partial application left the vault in an intermediate state where some MOCs were created but their relationship links were not yet added. A single bundled doc is applied atomically.

## MOC-Branch: Unticked Clusters Are Squelched, Not Rejected

WHY: When the user reviews a MOC proposal and leaves some clusters unticked, those clusters represent topics the user chose not to create MOCs for in this pass. Marking the proposal document as "rejected" at the file level would be wrong — the document is partially accepted, not fully rejected. The `squelch-unticked.py` script records the unticked cluster signatures so they are not re-proposed in future `/inbox` runs without new supporting notes. The proposal document itself transitions to `accepted` because the ticked portion was accepted.

## What the Agent Never Does — Rationale for Each Prohibition

WHY reading template files from the vault: Template content belongs in scripts or config — not in vault files that the user might edit. Vault templates would create a silent dependency between the pipeline and user-managed content that could break the pipeline whenever the user modifies a template.

WHY not composing note content or frontmatter: Composition is where format drift happens. Every field value, tag format, and frontmatter key must match the schema exactly. Scripts enforce this; LLM text generation does not.

WHY not reading MOC callouts to resolve section positions: The instruction entry tells the user to find the first editable callout in Obsidian. This is a deterministic rule that requires no vault read. Reading the MOC content at instruction-build time would add a Kado round-trip and couple the instruction content to the MOC's current state — which may change between when instructions are built and when they are applied.

WHY not mapping position values: `position` values in the instruction set are assigned by `instruction-render.py` according to the profile's ordering rules. If the agent overrode these, two different ordering strategies would coexist, producing inconsistent instruction sets across runs.
