# /moc-propose — Propose a new MOC for a topic, folder, classification, or whole-vault scan
# version: 0.1.0

Proactively propose a Map-of-Content (MOC) for an under-organised topic area.
Routes to the `moc-architect` agent, which runs `moc-discovery.py` then `suggestions-reducer.py`
and writes a reviewable proposal-doc to your inbox folder.

## STRICT — How to Run This Command

**You (the Claude session reading this command) IMPERSONATE the `moc-architect` agent
definition at `.claude/agents/moc-architect.md` — execute its Workflow steps in your
own context.**

**NEVER** dispatch `moc-architect` via the `Agent` / `Task` tool.

Reason: `moc-architect` orchestrates two python subprocesses (`moc-discovery.py`,
`suggestions-reducer.py`). These are Bash dispatches, not nested Agent calls.
A subagent cannot reliably spawn further subagents — if you dispatch `moc-architect`
as a subagent, the subprocess calls fail or the agent tool is unavailable and the
pipeline produces no output.

Concrete mapping:
- `moc-architect.md` Workflow Phase 1 (parse args + route mode) → YOUR step
- Phase 2 (`moc-discovery.py` subprocess) → Bash call by YOU
- Phase 3 (abort-reason handling) → YOUR step
- Phase 4 (`suggestions-reducer.py` subprocess) → Bash call by YOU
- Phase 5 (Kado write + user message) → YOUR step

In other words: `moc-architect` is the ONLY agent in this command's workflow that
you IMPERSONATE. There are no further subagents to dispatch.

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

## How It Works

1. **Parse args** — determine mode from the routing rule above.
2. **Resolve inbox path** — `python3 scripts/read-config-field.py --field concepts.inbox --default "100 Inbox/"`.
3. **Run `moc-discovery.py`** — subprocess with the mode flag:
   - `--tag <value>`, `--folder <value>`, `--class <value>`, `--title <value>`,
     `--free-text <value>`, or `--scan` (no args).
   - Script verifies `discovery-cache.yaml` is present. If missing, it returns
     `abort_reason: cache-empty`; you surface the message and exit:
     > "MOC proposal requires vault cache. Please run `/explore-vault` first to
     > populate `discovery-cache.yaml`."
   - Other abort reasons: `zero-candidates` ("Keine Notes zum Topic gefunden"),
     `candidate-cap-exceeded`, `cache-miss-cap-exceeded`. Surface the German message
     and exit — write no proposal-doc.
4. **Run `suggestions-reducer.py --moc-proposal-mode`** — renders proposal-doc Markdown
   (up to `max_results=5` clusters, sorted by confidence; overflow noted as
   "Weitere N Cluster gefunden — re-run später").
5. **Kado write** — writes
   `<inbox_path>/tomo-moc-proposal-<YYYYMMDD>-<HHmm>-<top-slug>.md`.
6. **Report to user** — tell the user the proposal-doc path, cluster count, and top
   confidence score. Remind them to open in Obsidian, tick Accept, then run `/inbox`.

Full agent spec: `.claude/agents/moc-architect.md`.

## Agents This Command Coordinates

- `moc-architect` — IMPERSONATED (not dispatched). Orchestrates:
  - `moc-discovery.py` — Bash subprocess; produces `DiscoveryReport` JSON
  - `suggestions-reducer.py --moc-proposal-mode` — Bash subprocess; renders and
    writes the proposal-doc via Kado
