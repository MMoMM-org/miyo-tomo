# WHY: inbox (command)

> Rationale for decisions in `tomo/dot_claude/commands/inbox.md`. This file was created as part of
> XDD 018 (Inbox Routing Redesign) to preserve institutional knowledge before
> the legacy command was replaced.

## Command is a Shim, Not a Duplicate

WHY: The `/inbox` command file contains only routing logic and entry-point detection — it does not duplicate the workflow steps from `inbox-orchestrator.md` or `instruction-builder.md`. An earlier version had detailed "How It Works" prose in the command file describing what each called script does. That content drifted from the agent specs after updates and caused false-start invocations where the command's own description of the workflow confused the LLM into taking actions the agent spec had since changed. The command file now defers all workflow detail to the agent files it impersonates.

## Impersonate Both Agents, Never Dispatch Them

WHY: Both `inbox-orchestrator` and `instruction-builder` must be impersonated by the main session. The Anthropic platform does not allow nested agents to use the `Agent` tool. When either was dispatched as a subagent, its execution context lacked the `Agent` tool and it fell back to processing all items serially — destroying the fan-out parallelism that Phase B depends on. Impersonation keeps the main session in control of all `Agent` tool dispatches. This is a hard 1-level nesting limit: main session dispatches leaf agents, never orchestrators.

## Auto-Detection: Pass 2 Before Pass 1

WHY: Pass 2 (instruction rendering) takes priority in auto-detection because an approved suggestions doc means the user has already done the review work and is waiting for instructions. Running Pass 1 first in this state would analyze the same inbox items again and produce a new suggestions doc, either overwriting or duplicating the already-approved one. The detection order (Pass 2 → Pass 1) ensures the pipeline always advances forward through the workflow, never sideways.

## Pass 2 Detection is Cheap; Pass 1 Detection is Delegated

WHY: The command detects Pass 2 eligibility at the command level with a cheap `listDir` + top-of-file checkbox read. Pass 1 detection is not done at the command level — the command unconditionally impersonates the orchestrator and lets the orchestrator's Phase A2.5c handle "nothing to do" with its own truly-empty early exit. This asymmetry exists because Pass 2's signal (an `[x] Approved` checkbox) is fast to check with a single Kado call. Pass 1's signal (`tomo.state=captured` in frontmatter across many files) would require a full inbox scan — the same scan the orchestrator runs in Phase A anyway. Duplicating that scan at the command level would waste a Kado call and risk the command's discovery diverging from the orchestrator's.

## Inbox Path Always Resolved from Config

WHY: The inbox path varies per vault. Hardcoding `"Inbox"` or `"100 Inbox/"` in the command would break any vault where the user configured a different path during setup. The path is read from `vault-config.yaml` via `scripts/read-config-field.py` as the first step, before any `listDir` or scan. This makes the command portable across vault configurations without modification.

## --recover Flag Requires Explicit User Initiation

WHY: Tomo cannot determine automatically whether captured notes with no associated workflow doc represent drift (something went wrong mid-pipeline) or steady state (Hashi cleaned up the workflow doc after apply, and the notes are already processed). Auto-recovery would risk re-running Pass 1 for already-processed items and producing duplicate suggestions docs. The `--recover` flag makes the recovery decision explicit — the user opts in when they know they have drift.

## --recover Sets an Environment Variable, Not a Command-Line Flag to the Orchestrator

WHY: The `/inbox` command cannot pass structured arguments to the orchestrator it impersonates — impersonation means the main session reads the agent file and executes it directly. The `TOMO_INBOX_RECOVER=1` environment variable is the coordination mechanism: the command sets it in the environment before impersonating the orchestrator, and the orchestrator reads it in Phase A2.5c.1. This keeps the interface between the command and the orchestrator explicit and inspectable without requiring a formal argument-passing protocol.

## --pass1 and --pass2 Force Flags Skip Auto-Detection

WHY: Auto-detection covers the common case but users occasionally need to override it. `--pass2` exists for cases where the user edited a suggestions doc after the checkbox was checked and wants to force a re-render. `--pass1` exists for cases where the user wants to generate new suggestions without checking for approved docs first. Force flags bypass the detection logic entirely and impersonate the specified agent directly.
