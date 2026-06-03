# WHY: tomo-companion (output style)

> Rationale for decisions in `tomo/dot_claude/output-styles/tomo-companion.md`.

## An Output Style, Not More CLAUDE.md or Skills

WHY: Tomo's runtime is not software engineering. The default Claude Code system prompt is built for code work — scoping changes, writing comments, verifying builds — which is pure noise for an assistant that curates an Obsidian vault. An output style is the only mechanism that *modifies the system prompt itself* (CLAUDE.md adds a user message after it; skills load on demand; `--append-system-prompt` only appends). It is the right tier for "what role is this session" because that framing must hold on every single turn, before any command or skill loads. CLAUDE.md remains the source of truth for project *mechanics* (knowledge-stack precedence, concept paths, lifecycle state names); the output style owns only role, posture, and voice.

## keep-coding-instructions: false

WHY: The whole point is to *remove* the built-in software-engineering instructions, not keep them. Setting this to `false` strips the "scope changes / write comments / verify work" guidance that does not apply to a PKM companion. The runtime still runs `python3 scripts/*.py` and edits `config/` — but that behaviour is driven by explicit steps in commands/agents, not by the generic coding instructions, so stripping them costs nothing and removes irrelevant framing.

## Boundaries Are Deliberately Duplicated in the System Prompt

WHY: The proposal-first / inbox-only / Kado-mediated rules already live in `CLAUDE.md`. Restating them in the output style is an intentional violation of DRY, accepted because this is Tomo's most safety-critical guarantee (the vault is the source of truth; an accidental direct write is the worst failure mode). CLAUDE.md is a user message *after* the system prompt; the output style is *in* the system prompt and triggers the harness's automatic adherence reminders throughout the conversation. Putting the boundary on the highest-adherence tier buys redundancy exactly where deviation is most expensive. If the boundary wording ever changes, both copies must move together — CLAUDE.md is canonical, the style mirrors it.

## Research Companion Is a Conversational Facet, Not a Pipeline Step

WHY: "What did I write about LYT?" / "find more on this from my notes" is read-only retrieval-and-synthesis. The top-level container session already has the capability — `mcp__kado__*` (incl. `kado-search` full-text filter and `kado-read`) plus `Read(*)` in `settings.json` — so it can answer directly in conversation without a dedicated command. The style names this role so the model knows it is allowed; it does NOT imply a `/research` or `/ask` command exists (none does — see the rule against mentioning non-existent steps). The bullet explicitly states the answer "lives in the conversation, not in a new note" to stop the model from trying to write a note for every research answer, and routes any *capture* of those findings back through the proposal model. A dedicated cache-aware, multi-hop retrieval command remains a separate future PRD candidate if the ad-hoc variant proves too thin.

## Read Is Free, Write Is Proposal-Gated

WHY: The research facet and the write boundary are complementary, not contradictory. Reading the vault through Kado is unrestricted (Kado's own ACL still gates it); only *mutating* vault state is proposal-gated. Framing the two together in the style sharpens the user's mental model: Tomo can look at anything it is permitted to read and think out loud, but it never changes the vault without an approved proposal.

## Selected via settings.json, Synced as a Managed Directory

WHY: The style takes effect because `settings.json` sets `"outputStyle": "tomo-companion"` (propagated to existing instances via update-tomo's jq merge of settings.json). The `.md` file itself does not propagate for free — both `install-tomo.sh` and `update-tomo.sh` sync an *explicit* allowlist of directories, with no generic "copy everything under dot_claude" step. `output-styles/` was therefore added as a new managed directory in both scripts (install: mkdir + guarded cp; update: `add_versioned` loop + plan/execute sections). The file carries a `# version:` comment so update-tomo's version comparison can track it like every other managed runtime file.
