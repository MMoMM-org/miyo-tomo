---
name: garden-audit
description: Audit the knowledge garden for staleness, broken links, orphaned notes, and missing connections. On first run surfaces permanent exclusions to configure; re-run with --configure to update them.
argument-hint: "optional: --configure"
---
# /garden-audit
# version: 0.1.0

Audit the knowledge garden for staleness, broken links, orphaned notes, and
missing connections. Produces a reviewable audit report in your inbox folder.

## STRICT — How to Run This Command

| Step | Agent | How to run |
|------|-------|------------|
| All steps | `garden-auditor` | **Impersonate** — read `.claude/agents/garden-auditor.md` and execute its Workflow steps in your context. Do NOT dispatch via the `Agent` tool. |

Authoritative spec: `.claude/agents/garden-auditor.md`.

## Usage

```
/garden-audit              # full audit run; first-run triggers exclusion wizard
/garden-audit --configure  # re-run the exclusion wizard without a full audit
```

Pass `--configure` through to the `garden-auditor` agent as-is.

# STRICT — IMPERSONATE, never dispatch. Why: dispatched subagents cannot use the Agent tool.
