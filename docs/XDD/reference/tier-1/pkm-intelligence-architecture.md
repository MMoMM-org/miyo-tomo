# Tier 1: Tomo PKM Intelligence Architecture

> Parent: — (this is the root)
> Status: Implemented
> Source: [Brainstorm Spec](../../references/tomo-lyt-knowledge-model-spec.md)

---

## 1. Purpose

Define how Tomo encodes, stores, and uses PKM (Personal Knowledge Management) intelligence to work with Obsidian vaults. This is the architectural framework that all lower-tier specs implement.

## 2. Core Principle

**Tomo is framework-agnostic.** LYT is the primary target, but the architecture supports PARA, Zettelkasten, or custom frameworks through configuration — not code changes. Build for MiYo (Marcus's vault), validate with LYT, best-effort for PARA.

## 3. Architecture: 4-Layer Knowledge Stack

Tomo's PKM intelligence lives in four layers, each with a distinct responsibility:

| Layer | What | Format | Maintained by | Spec |
|-------|------|--------|---------------|------|
| **1. Universal PKM Concepts** | Framework-agnostic vocabulary | Skill logic | Tomo codebase | [Tier 2](../tier-2/components/universal-pkm-concepts.md) |
| **2. Framework Profiles** | Framework-specific data (not logic) | YAML | Tomo codebase + community | [Tier 2](../tier-2/components/framework-profiles.md) |
| **3. User Config** | User's vault-specific ground truth | YAML | User via wizard | [Tier 2](../tier-2/components/user-config.md) |
| **4. Discovery Cache** | Auto-discovered vault semantics | YAML | vault-explorer (auto) | [Tier 2](../tier-2/components/discovery-cache.md) |

### Layer Precedence

**Layer 3 > Layer 2 > Layer 1.** User config always wins over profile defaults, which always win over universal concepts. Layer 4 (discovery cache) is advisory — it informs decisions but never overrides configuration.

**Absent field rule:** If a Layer 3 field is omitted, the Layer 2 profile default applies. If explicitly set to `null`, the field is intentionally disabled — no fallback.

### Separation of Concerns

- **Profiles = data.** Classification categories, folder defaults, relationship markers, keywords.
- **Skills = logic.** Decision heuristics, matching algorithms, confidence scoring, proposal generation.
- **Config = authority.** User's ground truth. Overrides everything.
- **Cache = advisory.** Enriches decisions but is never required. Graceful degradation without it.

## 4. Decision Flow Pattern

Every Tomo action follows this flow through the layers:

```
Input (e.g., inbox note)
  │
  ▼
Layer 1: "What universal concept is this?" (inbox item → classify)
  │
  ▼
Layer 2: "What does the framework say?" (LYT → classification 2600, check MOC match)
  │
  ▼
Layer 3: "What does the user want?" (folder path, template, tags, relationship markers)
  │
  ▼
Layer 4: "What exists in the vault?" (MOC topics, tag patterns, similar notes)
  │
  ▼
Output: Proposal in instruction set (user approves before execution)
```

**Key invariant:** The output is always a *proposal*, never a direct vault modification.

**Two-pass proposal model (inbox processing):** Tomo generates output in two passes — first a high-level **Suggestions** document with alternatives and confidence (user approves the *direction*), then a detailed **Instruction Set** based on confirmed direction (user applies the *details*). This catches misclassifications early and reduces rejection cycles. See [Inbox Processing](../tier-2/workflows/inbox-processing.md).

**Apply step (MVP):** User reads the approved instructions and performs each change manually in Obsidian. Tomo only updates inbox-side state (tagging, archiving) once the user signals completion.

**Apply step (Post-MVP):** Seigyo executes locked scripts after dual vetting. See [§7 Execution Model](#7-execution-model).

## 5. Two-Phase Setup Flow

### Phase 1: Install Script (host, no Kado)

Runs on host machine. Has filesystem access to vault. Produces starter `vault-config.yaml`.

1. Select framework profile (miyo/lyt/para/custom)
2. Provide vault path → `ls` top-level folders
3. Map folders to concepts
4. Set lifecycle tag prefix
5. Generate minimal config

**Spec:** [Setup Wizard](../tier-2/components/setup-wizard.md) → [Install Script](../tier-3/wizard/install-script.md)

### Phase 2: First Tomo Session (Docker, Kado live)

Triggered by `/explore-vault`. Deep scan via Kado MCP.

1. Read MOCs, sample frontmatter, detect tag patterns
2. Present findings for user confirmation
3. Refine `vault-config.yaml`
4. Build `discovery-cache.yaml`

**Spec:** [Setup Wizard](../tier-2/components/setup-wizard.md) → [First-Session Discovery](../tier-3/wizard/first-session-discovery.md)

## 6. Security Model

**Tomo never accesses the vault directly.** All vault operations go through Kado MCP, which enforces a 5-gate permission chain. Tomo runs in a Docker container with no vault filesystem mount.

| Boundary | Enforced by | Deterministic? |
|----------|------------|----------------|
| Vault read access | Kado MCP (Obsidian plugin) | Yes |
| Inbox folder writes | Kado MCP (Obsidian plugin) | Yes |
| Outside-inbox writes (MVP) | User (manual application) | Yes |
| Outside-inbox writes (Post-MVP) | Seigyo (locked scripts) | Yes |
| File visibility | Kado security scope | Yes |
| Container isolation | Docker | Yes |
| Proposal approval | User (instruction set checkboxes) | Yes |
| Decision quality | Tomo skills (AI) | No |

The only non-deterministic element is Tomo's decision-making. Everything that enforces safety is outside Tomo's control. See [§7 Execution Model](#7-execution-model) for the rationale behind splitting inbox writes from outside-inbox writes.

## 7. Execution Model

A critical question for any AI system that writes to user content: **how are approved actions actually applied?** Even with Kado as a safe access layer, AI-driven execution introduces variance — the AI could misread the instruction set, skip actions, apply them in wrong order, or include unintended changes.

### Three Options Considered

| Option | Description | Trade-offs |
|--------|-------------|------------|
| **Tomo Applies** | AI calls `kado-write` directly for all actions | Non-deterministic at execution time. Kado is safe access, but AI deciding *what* to write at *what* moment introduces variance. |
| **User Applies** | User manually performs approved changes | Tedious (copy-paste, manual file creation), but fully deterministic and safe. User has final control at every step. |
| **Script Controlled** | Pre-validated, locked scripts execute structured instructions | Most robust. Deterministic at both decision and execution. Requires the script infrastructure to exist first. |

### MVP Decision: User Applies (Inbox Boundary)

For MVP, **Tomo's deterministic boundary is the inbox folder.** Tomo writes only there:

- Generating instruction set files
- Tagging instruction sets through lifecycle states (`proposed` → `archived`)
- Tagging processed inbox items
- Archiving processed inbox items (move within inbox folder)

**Everything outside the inbox is User Applies.** When the user approves an action in the instruction set, they perform the change manually:

- Create new notes from the proposal (suggested template, title, frontmatter, body)
- Add MOC links to specified sections
- Update tracker fields in daily notes
- Apply tag changes to existing notes

The instruction set is human-readable **by design** — every approved action contains everything the user needs to perform it manually. Tomo is the proposer; the user is the executor.

### Post-MVP Vision: Seigyo + Locked Scripts

Long-term, deterministic execution outside the inbox will be handled by **Seigyo** (the planned Obsidian control plugin) using locked scripts. Two-pass dual vetting:

```
Pass 1: Tomo proposes ACTIONS
        ↓
        User accepts / denies / modifies
        ↓
Pass 2: Tomo generates SEIGYO SCRIPTS with before/after diffs
        ↓
        User accepts / denies / modifies
        ↓
        Scripts are LOCKED — Tomo cannot modify, only invoke
        ↓
Seigyo executes locked scripts with structured parameters
```

The user reviews both the action proposals **and** the scripts that will apply them. Once locked, scripts are deterministic — Tomo can only invoke them with parameters, never modify their logic. This achieves **WYSIWYG**: every change to vault content outside the inbox is deterministic and pre-validated.

### Execution Boundary Summary

| Operation | MVP | Post-MVP |
|-----------|-----|----------|
| Read anywhere | Tomo via Kado | Tomo via Kado |
| Write to inbox folder | Tomo via Kado | Tomo via Kado |
| Write outside inbox | User (manually) | Seigyo (locked scripts, dual-vetted) |
| Decision logic | Tomo skills (AI) | Tomo skills (AI) |

**Key implication for MVP:** The `vault-executor` agent's scope is much narrower than originally planned. It manages **inbox-side state only** (instruction set tagging, inbox item archiving). It does **not** modify content outside the inbox. Vault content changes are user actions, not agent actions.


## 8. Component Map

```
┌──────────────────────────────────────────────────────────┐
│                    Tomo (Docker)                          │
│                                                          │
│  ┌────────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ Agents     │  │ Skills   │  │ Config           │    │
│  │            │  │          │  │                  │    │
│  │ inbox-     │  │ pkm-     │  │ vault-config.yaml│    │
│  │ analyst    │  │ workflows│  │ discovery-cache  │    │
│  │            │  │          │  │ profiles/*.yaml  │    │
│  │ suggestion-│  │ lyt-     │  │                  │    │
│  │ builder    │  │ patterns │  │                  │    │
│  │  (Pass 1)  │  │          │  │                  │    │
│  │            │  │ obsidian-│  │                  │    │
│  │ instruction│  │ fields   │  │                  │    │
│  │ -builder   │  │          │  │                  │    │
│  │  (Pass 2)  │  │ template-│  │                  │    │
│  │            │  │ render   │  │                  │    │
│  │ vault-     │  │          │  │                  │    │
│  │ executor   │  │          │  │                  │    │
│  │ (cleanup)  │  │          │  │                  │    │
│  │            │  │          │  │                  │    │
│  │ vault-     │  │          │  │                  │    │
│  │ explorer   │  │          │  │                  │    │
│  └────────────┘  └──────────┘  └──────────────────┘    │
│                       │                                  │
│                       │ MCP Protocol                     │
│                       ▼                                  │
│               ┌──────────────┐                           │
│               │  Kado MCP    │                           │
│               │  (remote)    │                           │
│               └──────────────┘                           │
└──────────────────────────────────────────────────────────┘
                       │
                       ▼
              ┌──────────────┐
              │ Kado Plugin  │
              │ (Obsidian)   │
              │              │
              │ kado-read    │
              │ kado-write   │
              │ kado-search  │
              └──────────────┘
                       │
                       ▼
              ┌──────────────┐
              │ Obsidian     │
              │ Vault        │
              └──────────────┘
```

## 9. Workflow Map

Workflows describe HOW components interact. Each workflow spec (Tier 2) references the components it uses.

**Note (MVP):** "Agents involved" lists agents that propose or manage inbox-side state. Actual content changes outside the inbox are performed by the **user** (see [§7 Execution Model](#7-execution-model)).

| Workflow | Components used | Tomo agents (propose) | Executor (apply) |
|----------|----------------|------------------------|------------------|
| [Inbox Processing](../tier-2/workflows/inbox-processing.md) | User Config, Discovery Cache, Template System, Profiles | inbox-analyst, suggestion-builder (Pass 1), instruction-builder (Pass 2), vault-executor (cleanup) | User (MVP) / Seigyo (Post-MVP) |
| [Daily Note](../tier-2/workflows/daily-note.md) | User Config, Template System | inbox-analyst, suggestion-builder, instruction-builder | User (MVP) / Seigyo (Post-MVP) |
| [LYT/MOC Linking](../tier-2/workflows/lyt-moc-linking.md) | Profiles, Discovery Cache, User Config | inbox-analyst, suggestion-builder, instruction-builder | User (MVP) / Seigyo (Post-MVP) |
| [Vault Exploration](../tier-2/workflows/vault-exploration.md) | User Config, Discovery Cache | vault-explorer | n/a (read-only) |

## 10. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Abstraction | Framework-agnostic from day one | Support LYT, PARA, custom without code changes |
| Knowledge encoding | 4-layer stack | Clean separation of concerns |
| Precedence | L3 > L2 > L1, L4 advisory | User config is always authority |
| Data vs logic | Profiles = data, Skills = logic | Portable profiles, testable skills |
| Relationships | Marker-based string patterns | No plugin dependency (not tied to Dataview) |
| Templates | One per note type, {{token}} syntax (MVP) | Simple, avoids Templater complexity |
| Lifecycle | Tags with customizable prefix, fixed state names | States are Tomo workflow states, not PKM states |
| Calendar | Container concept with granularity sub-types | Maps to any periodic note setup |
| Setup | Hybrid: install script + Kado discovery | Works without Kado; enriched with Kado |
| Security | All access via Kado, Docker isolation | Deterministic boundaries, AI only proposes |
| **Execution (MVP)** | **User Applies — Tomo writes only to inbox folder** | **Deterministic execution; AI cannot introduce variance at write time outside inbox** |
| **Execution (Post-MVP)** | **Seigyo locked scripts with dual vetting** | **WYSIWYG, scripted execution, no AI in the apply step** |
| **Inbox model** | **2-Pass: Suggestions → Instruction Set** | **User approves direction before details are committed; mirrors Post-MVP dual vetting** |
| **MOC discovery** | **Path AND tag-based, full tree (all levels)** | **Sub-MOCs scattered in different folders are still findable; tree structure surfaces specificity** |
| **Tracker syntax** | **Multi-syntax (inline field, task checkbox, frontmatter)** | **Not framework-locked to Dataview; supports MiYo, others, custom** |
| **Templates** | **User-named, user-extensible tokens, may contain Templater syntax** | **Doesn't enforce conventions; user retains full control of templates** |

## 11. Children

### Tier 2 — Components
- [Universal PKM Concepts](../tier-2/components/universal-pkm-concepts.md)
- [Framework Profiles](../tier-2/components/framework-profiles.md)
- [User Config](../tier-2/components/user-config.md)
- [Discovery Cache](../tier-2/components/discovery-cache.md)
- [Template System](../tier-2/components/template-system.md)
- [Setup Wizard](../tier-2/components/setup-wizard.md)

### Tier 2 — Workflows
- [Inbox Processing](../tier-2/workflows/inbox-processing.md)
- [Daily Note](../tier-2/workflows/daily-note.md)
- [LYT/MOC Linking](../tier-2/workflows/lyt-moc-linking.md)
- [Vault Exploration](../tier-2/workflows/vault-exploration.md)
