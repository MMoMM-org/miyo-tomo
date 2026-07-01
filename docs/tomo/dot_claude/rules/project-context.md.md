# WHY: project-context.md — Obsidian Wikilinks rule

## The bug (#63, follow-on from #62)

The original rule told the model to **"wrap each wikilink in backticks so it
visually stands out in your output."** The model over-applied it: it backticked
wikilinks it wrote *into vault notes* via `kado-write`, turning `[[Note]]` into
`` `[[Note]]` `` — inline code, which Obsidian does **not** resolve as a
navigable link. A display convenience silently corrupted stored vault content.

## The fix — move display formatting out of the model's hands

Highlighting a wikilink is a *rendering* concern, not a *content* concern, so it
belongs in a deterministic layer, not in an LLM instruction that the model must
remember to apply in chat but suppress on writes (a distinction it got wrong).

`tomo/dot_claude/hooks/wikilink-highlight.sh` is a **MessageDisplay** hook: it
backticks `[[...]]` in the *rendered* chat output only. The transcript and the
text the model reads back stay bare, and nothing the model writes to the vault is
touched. So the rule is now simply "write wikilinks bare, always" — one
unconditional imperative, no chat-vs-write branch for the model to fumble.

Reference implementation: the private Tomo instance shipped this hook
(`2026-06-14`); this ports it into the source with the `msgdisplay-last.json`
debug stash removed (the input schema — `.delta` in, `displayContent` out — is
now known and stable).

## Why the hook is safe

It can never blank or corrupt output: missing `jq`/`perl`, an empty/unknown
`.delta` field, or a no-op transform all exit 0 with no output, so Claude Code
shows the original message. It also skips `[[...]]` already adjacent to a
backtick, so pre-formatted links are not double-wrapped.

## Delivery

Shipped by both `install-tomo.sh` (hooks `*.sh` glob + `settings.json` copy) and
`update-tomo.sh` (version-gated hook sync + `settings.json` jq-merge). The
MessageDisplay entry is additive to the existing `Notification` + `PreToolUse`
hooks.

Refs: #62 (obsidian-markdown skill note), #63 (this fix).

---

# WHY: project-context.md — `@` File References section trimmed (#63)

## What was removed and why

The `@` section described *how the picker works* — that it ships under XDD 010
and replaces Claude Code's built-in `@`; that it emits one combined candidate
stream (open notes first, then inbox, then vault, top 15); that it filters via
fzf with a grep fallback; that dedupe preserves first-seen order; plus a
returns-table, a "Consequence" narrative, and a worked example.

None of that is something the model *does* — the picker runs outside the model,
and describing its internals in a runtime rules file is the same anti-pattern
that bit skills/agents: the model can start reasoning it should replicate or
reason about the mechanism instead of just handling the result. The runtime file
now keeps only the operational contract the model must act on: picked paths are
vault-relative, an ENOENT `Read` on one is expected, fall back to `kado-read`
silently, and a `@"quoted"` insertion is a user-facing hint, not a path.

## The mechanism (reference, not a runtime instruction)

- Picker is XDD 010; it replaces Claude Code's built-in `@`.
- `@` (empty) → currently-open Obsidian notes first, then inbox, then vault (top
  15). `@<text>` → same set filtered via fzf fuzzy match (grep substring
  fallback). One combined stream, no scope prefixes; open notes lead because
  they are the active context and dedupe preserves first-seen order.
- On pick, Claude Code inserts `@<vault-path>` and immediately tries to `Read`
  it; the instance has no vault files locally, hence the expected ENOENT that
  the runtime rule tells the model to absorb and route to Kado.

Kept as-is (reviewed, deliberately not stripped): the **Bash & Python Rules**
inline rationales and the **MVP Execution Boundary** — those are behavioural
guards / scope statements the model acts on, not tooling descriptions, and their
brief "why the validator trips" clauses are compliance-load-bearing.

Refs: #63; XDD 010 (`@` picker).
