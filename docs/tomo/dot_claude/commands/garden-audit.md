# WHY: /garden-audit command

> Rationale for decisions in `tomo/dot_claude/commands/garden-audit.md`.
> The command is the user-facing entry point for the garden-audit skill (spec 030 Phase 5).
> It is a shim that impersonates `garden-auditor.md` — it does not orchestrate steps itself.

## IMPERSONATE, Not DISPATCH (Slash Command Shim Pattern)

WHY the command instructs the executor to impersonate `garden-auditor.md` rather than
dispatching via the `Agent` tool: subagents launched via the `Agent` tool cannot
themselves use the `Agent` tool — the Anthropic platform does not permit nested Agent
dispatch (platform constraint; revisit if this changes). The garden-auditor agent
orchestrates a multi-step workflow, but all steps are Bash + Read + Write invocations,
not further Agent dispatches. Impersonation loads the agent's system prompt into the
current context and executes it directly, which is identical in capability to a dispatch
but without the nesting restriction. The `STRICT: IMPERSONATE, never dispatch` line
follows the `inbox`, `moc-propose`, and other command shims in the same pattern.

## Command Shim is Overview + Passthrough Only

WHY `/garden-audit` contains only a brief usage block, the IMPERSONATE directive, and
a pointer to `garden-auditor.md` — no workflow steps: the command's role is to surface
`--configure` usage to the user and delegate everything else to the agent. Duplicating
workflow steps in the command would create two sources of truth that drift independently.
If the agent workflow changes (new step, new STRICT), the command would continue to
reference the old steps. Single source of truth: the agent owns the workflow; the
command owns the entry-point description and usage.

## --configure Pass-Through

WHY the command instructs the executor to pass `--configure` to the agent as-is
rather than interpreting it in the command shim: the agent is the only layer that
knows what `--configure` means (it re-runs the wizard against the existing config,
skips the full scan). The command shim has no context about scan vs. wizard mode —
trying to interpret flags at the command layer would duplicate the mode-detection
logic from agent Step 1. Pass-through keeps the command stateless.

## Version 0.1.0

WHY: Initial spec-030 Phase 5 implementation. Authored as a minimal IMPERSONATE shim
following the `inbox.md` and `moc-propose.md` patterns established earlier in the
project. No planned evolution — the shim pattern is stable.
