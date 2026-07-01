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
