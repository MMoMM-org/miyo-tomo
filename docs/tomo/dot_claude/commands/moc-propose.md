# WHY: /moc-propose

> Rationale for decisions in `tomo/dot_claude/commands/moc-propose.md`. The
> command is a thin shim that routes to the `moc-architect` agent (impersonated).

## Impersonate, Don't Dispatch (status-quo until F-54)

WHY: `/moc-propose` is a one-shot user-invoked command with no fan-out.
`moc-architect` has no further subagents to dispatch — its Bash subprocess calls
to `moc-discovery.py` and `suggestions-reducer.py` work fine from any context
(Bash is not the Agent tool). It has no `AskUserQuestion` interaction loop that
benefits from staying in the main session, and no hot-path token accumulation
that would reward context isolation. So the command instructs the model to read
`.claude/agents/moc-architect.md` and execute its Workflow steps in-context
rather than dispatching via the `Agent` tool. Status-quo impersonation is the
lower-risk default until F-54 validates dispatch broadly. The command file itself
stays a shim (per `feedback_impersonate_command_should_be_shim`): detailed
"how it works" lives in the agent spec, not here, so the two never drift.

## `check:` Prefix Routes to the MOC-Uplink Audit (ADR-12, T6.5)

WHY: `check:moc-uplinks` is a fifth whitelisted prefix added in Phase 6. It
routes to `moc-discovery.py --check-moc-uplinks` — a focused audit of MOCs
missing a parent `up::`, distinct from the notes-discovery scan. It is a prefix
(not a bare keyword) for the same reason as `tag:`/`folder:`/`class:`/`title:`:
exact-match prefixes avoid misrouting free-text queries that happen to contain
the word.
