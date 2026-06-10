---
name: moc-propose
description: Proactively propose a Map-of-Content (MOC) for an under-organised topic area. Routes to the moc-architect agent, which discovers under-organised topic clusters via vault scan and writes a reviewable proposal-doc to your inbox folder.
argument-hint: "optional: tag:X | folder:Y | class:Z | title:T | <free-text> | <empty for whole-vault scan>"
---
# /moc-propose — Propose a new MOC for a topic, folder, classification, or whole-vault scan
# version: 0.3.0

Proactively propose a Map-of-Content (MOC) for an under-organised topic area.
Routes to the `moc-architect` agent, which runs `moc-discovery.py` then `suggestions-reducer.py`
and writes a reviewable proposal-doc to your inbox folder.

## STRICT — How to Run This Command

| Step | Agent | How to run |
|------|-------|------------|
| All steps | `moc-architect` | **Impersonate** — read `.claude/agents/moc-architect.md` and execute its Workflow steps in your context. Do NOT dispatch via the `Agent` tool. |

Authoritative spec: `.claude/agents/moc-architect.md`.

## Usage

```
/moc-propose tag:topic/applied/zsh        # tag-based discovery
/moc-propose folder:Atlas/202 Notes/2611 Code Snippets/   # folder-scoped
/moc-propose class:2611                   # classification-based (MiYo profile)
/moc-propose title:"Shell & Terminal"     # seed by proposed title verbatim
/moc-propose shell und terminal           # free-text seeding (no whitelisted prefix)
/moc-propose check:moc-uplinks            # audit MOCs missing a parent up::
/moc-propose                              # whole-vault density scan (no args)
```

## Routing Rule (STRICT)

Whitelisted prefixes: `tag:`, `folder:`, `class:`, `title:`, `check:`

- Argument starts with one of the whitelisted prefixes (exact, lowercase) → use the
  corresponding mode. `check:moc-uplinks` → MOC-uplink audit.
- Argument present but does NOT start with a whitelisted prefix → **free-text mode**.
- No argument at all → **scan mode** (whole-vault density scan).

**STRICT:** Do NOT auto-correct capitalised variants.  
`Tag:foo` → free-text (not tag mode).  
`Folder:X` → free-text (not folder mode).  
Prefixes must match exactly — these fall through by design to avoid misrouting titles
that contain colons (e.g. `Shell: A Survey`).

