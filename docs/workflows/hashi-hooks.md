# Author a Hashi hook

[Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi) runs user-authored `.cjs` hooks from `.tomo-hashi/hooks/` to customise what happens `before`/`after` each instruction-set action. `/hashi-hook` walks you through writing one:

```
/hashi-hook                          # full guided flow
/hashi-hook "stamp moved notes"      # seed the flow with the behaviour you want
```

It asks for the phase (`before`/`after`) and action kind, drafts the hook, then **risk-classifies the generated code** (🟢 Obsidian-API only · 🟡 filesystem/env · 🔴 shell/network/filesystem-writes) and flags hooks that could change many notes in one run. The hook and a handoff document are written **to your inbox** — Tomo never places code in `.tomo-hashi/hooks/` itself.

> ⚠️ Hashi hooks run **unsandboxed on your host** with full vault, filesystem, and network access. Tomo drafts the code; reviewing it, testing it, and all liability are yours. **Back up your vault** before moving a hook into place, and again before the next Hashi run. The handoff doc repeats these warnings and includes a review checklist and the exact target filename.
