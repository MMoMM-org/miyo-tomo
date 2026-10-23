# Tier 1: Tomo PKM Intelligence Architecture

> Parent: — (this is the root)
> Status: Implemented
> Source: [Brainstorm Spec](https://github.com/MMoMM-org/miyo-kokoro/blob/main/tomo/references/tomo-lyt-knowledge-model-spec.md) (Kokoro)

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

**Apply step (Post-MVP):** Tomo Hashi (友橋, the Obsidian plugin — see Kokoro ADR-009) reads the `instructions.json` sibling of the approved set and applies each action deterministically via the Obsidian Plugin API. See [§7 Execution Model](#7-execution-model).

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
| Outside-inbox writes (Post-MVP) | Tomo Hashi (Obsidian Plugin API, reads `instructions.json`) | Yes |
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

### Post-MVP Vision: Tomo Hashi executor

Long-term, deterministic execution outside the inbox is handled by **Tomo
Hashi** (友橋), a separate Obsidian community plugin (see Kokoro ADR-009).
Hashi has no AI surface — it mechanically executes the Pass-2 instruction
set against the vault via the Obsidian Plugin API. Two-pass dual vetting
is preserved; the second pass is the user's review of the rendered
`instructions.md` before triggering Hashi:

```
Pass 1: Tomo proposes DIRECTION (suggestions doc)
        ↓
        User accepts / denies / modifies
        ↓
Pass 2: Tomo generates DETAILED INSTRUCTION SET — two siblings:
          instructions.md   (human review, checkboxes)
          instructions.json (canonical, machine-readable)
        ↓
        User reviews + approves the .md
        ↓
Tomo Hashi reads .json and applies each action via Obsidian Plugin API.
On success, Hashi ticks the matching `- [ ] Applied` checkbox in the .md.
```

Once approval is given, execution is deterministic — Hashi's code is
reviewed and installed as an Obsidian plugin; the AI never writes outside
the inbox. This achieves **WYSIWYG**: every change to vault content
outside the inbox is deterministic, the user saw it in the instruction
set before triggering Hashi, and the Hashi code path itself contains no
LLM calls.

> **Note (2026-04-23):** earlier drafts of this spec positioned
> **Seigyo (制御)** as the post-MVP executor. Per Kokoro's 2026-04-23
> Tomo Hashi handoff (and ADR-009), that characterisation is stale —
> Seigyo is on the backburner and, if ever built, is likely to be a
> remote-control plugin for Obsidian window management and live vault
> testing, not an executor. Tomo Hashi fills the executor niche.

### Execution Boundary Summary

| Operation | MVP | Post-MVP |
|-----------|-----|----------|
| Read anywhere | Tomo via Kado | Tomo via Kado |
| Write to inbox folder | Tomo via Kado | Tomo via Kado |
| Write outside inbox | User (manually) | Tomo Hashi (Obsidian Plugin API, reads `instructions.json`) |
| Decision logic | Tomo skills (AI) | Tomo skills (AI) |

**Key implication for MVP:** No Tomo agent modifies content outside the inbox. Inbox-side state — suggestions and instruction documents, lifecycle state in frontmatter — is written via Kado by the pipeline scripts the agents run. Vault content changes are applied by the user or Tomo Hashi, never by an agent. (The `vault-executor` agent originally planned for inbox cleanup was retired in XDD 018.)


## 8. Component Map

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Tomo (Docker)                               │
│                                                                          │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐  │
│  │ Agents             │  │ Skills             │  │ Config             │  │
│  │                    │  │                    │  │                    │  │
│  │ suggestion-        │  │ suggest-handling   │  │ vault-config.yaml  │  │
│  │  conductor (P1)    │  │ routing-plan-      │  │ discovery-cache    │  │
│  │ inbox-analyst      │  │  consumer          │  │ profiles/*.yaml    │  │
│  │  (per item)        │  │ template-render    │  │                    │  │
│  │ synthesis-         │  │ lyt-patterns       │  │ Scripts            │  │
│  │  conductor (P2)    │  │ obsidian-*         │  │                    │  │
│  │ voice-transcriber  │  │ tomo-*-wizard      │  │ tomo/scripts/*.py  │  │
│  │ moc-architect      │  │ … see tomo/        │  │ (deterministic     │  │
│  │ garden-auditor     │  │   dot_claude/skills│  │  pipeline steps)   │  │
│  │ vault-explorer     │  │                    │  │                    │  │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘  │
│                                                                          │
│                                     │ MCP Protocol                       │
│                                     ▼                                    │
│                             ┌──────────────┐                             │
│                             │  Kado MCP    │                             │
│                             │  (remote)    │                             │
│                             └──────────────┘                             │
└──────────────────────────────────────────────────────────────────────────┘
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

### Agents and how they run

A command either **impersonates** an agent (the main session reads the agent file and runs its workflow itself) or **dispatches** it as a subagent via `Agent()`. Orchestrators that must dispatch further agents are always impersonated, because a dispatched subagent cannot use the `Agent` tool. Pure script runners are dispatched to keep their context isolated.

| Agent | Entry point | Runs as | Role |
|-------|-------------|---------|------|
| `suggestion-conductor` | `/inbox` (actions `suggest`, `fan-resolve`) | Impersonated | Pass 1 orchestrator — classifies fresh inbox sources into suggestions documents |
| `inbox-analyst` | `suggestion-conductor` | Dispatched, one per item | Classifies one inbox item and writes its `result.json` |
| `synthesis-conductor` | `/inbox` (action `synthesize`) | Dispatched | Pass 2 orchestrator — renders instructions from approved suggestions, fan docs, MOC proposals and garden-audit documents |
| `voice-transcriber` | `/inbox` (action `transcribe`) | Dispatched | Transcribes inbox audio with local faster-whisper |
| `moc-architect` | `/moc-propose` | Impersonated | Proposes new MOCs for under-organised topic clusters |
| `garden-auditor` | `/garden-audit` | Impersonated | Whole-vault structural scan written as a reviewable audit document |
| `vault-explorer` | `/explore-vault` | Impersonated | Scans vault structure, builds the MOC tree and the discovery cache |

## 9. Workflow Map

Workflows describe HOW components interact. Each workflow spec (Tier 2) references the components it uses.

**Note (MVP):** "Agents involved" lists agents that propose or manage inbox-side state. Actual content changes outside the inbox are performed by the **user** (see [§7 Execution Model](#7-execution-model)).

| Workflow | Components used | Tomo agents (propose) | Executor (apply) |
|----------|----------------|------------------------|------------------|
| [Inbox Processing](../tier-2/workflows/inbox-processing.md) | User Config, Discovery Cache, Template System, Profiles | suggestion-conductor + inbox-analyst (Pass 1), synthesis-conductor (Pass 2), voice-transcriber | User (MVP) / Tomo Hashi (Post-MVP) |
| [Daily Note](../tier-2/workflows/daily-note.md) | User Config, Template System | suggestion-conductor + inbox-analyst, synthesis-conductor | User (MVP) / Tomo Hashi (Post-MVP) |
| [LYT/MOC Linking](../tier-2/workflows/lyt-moc-linking.md) | Profiles, Discovery Cache, User Config | suggestion-conductor + inbox-analyst, synthesis-conductor | User (MVP) / Tomo Hashi (Post-MVP) |
| MOC Proposal ([spec 021](../../specs/021-moc-propose-consolidation/)) | Profiles, Discovery Cache, User Config | moc-architect, then synthesis-conductor once approved | User (MVP) / Tomo Hashi (Post-MVP) |
| Garden Audit ([spec 030](../../specs/030-garden-audit/)) | User Config, Discovery Cache | garden-auditor, then synthesis-conductor once approved | User (MVP) / Tomo Hashi (Post-MVP) |
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
| **Execution (Post-MVP)** | **Tomo Hashi Obsidian plugin reads `instructions.json`** | **WYSIWYG, deterministic execution via Obsidian Plugin API, no AI in the apply step** |
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
