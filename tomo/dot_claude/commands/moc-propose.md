---
name: moc-propose
description: Proactively propose a Map-of-Content (MOC) for an under-organised topic area. Routes to the moc-architect agent, which discovers under-organised topic clusters via vault scan and writes a reviewable proposal-doc to your inbox folder.
argument-hint: "optional: tag:X | folder:Y | class:Z | title:T | <free-text> | <empty for whole-vault scan>"
---
# /moc-propose — Propose a new MOC for a topic, folder, classification, or whole-vault scan
# version: 0.2.4

Proactively propose a Map-of-Content (MOC) for an under-organised topic area.
Routes to the `moc-architect` agent, which runs `moc-discovery.py` then `suggestions-reducer.py`
and writes a reviewable proposal-doc to your inbox folder.

## STRICT — How to Run This Command

| Step | Agent | How to run |
|------|-------|------------|
| All steps | `moc-architect` | **Impersonate** — read `.claude/agents/moc-architect.md` and execute its Workflow steps in your context. Do NOT dispatch via the `Agent` tool. |

Why impersonate: `/moc-propose` is a one-shot user-invoked command with
no fan-out. `moc-architect` has no further subagents to dispatch (its
Bash subprocess calls to `moc-discovery.py` and `suggestions-reducer.py`
would work fine from a dispatched context — Bash is not Agent), no
`AskUserQuestion` interaction loop that benefits from staying in the
main session, and no hot-path token accumulation that would reward
context isolation. Status-quo impersonation is the lower-risk default
until F-54 validates dispatch broadly.

Authoritative spec: `.claude/agents/moc-architect.md`.

## Usage

```
/moc-propose tag:topic/applied/zsh        # tag-based discovery
/moc-propose folder:Atlas/202 Notes/2611 Code Snippets/   # folder-scoped
/moc-propose class:2611                   # classification-based (MiYo profile)
/moc-propose title:"Shell & Terminal"     # seed by proposed title verbatim
/moc-propose shell und terminal           # free-text seeding (no whitelisted prefix)
/moc-propose                              # whole-vault density scan (no args)
```

## Routing Rule (STRICT)

Whitelisted prefixes: `tag:`, `folder:`, `class:`, `title:`

- Argument starts with one of the four whitelisted prefixes (exact, lowercase) → use the
  corresponding mode.
- Argument present but does NOT start with a whitelisted prefix → **free-text mode**.
- No argument at all → **scan mode** (whole-vault density scan).

**STRICT:** Do NOT auto-correct capitalised variants.  
`Tag:foo` → free-text (not tag mode).  
`Folder:X` → free-text (not folder mode).  
Prefixes must match exactly — these fall through by design to avoid misrouting titles
that contain colons (e.g. `Shell: A Survey`).

