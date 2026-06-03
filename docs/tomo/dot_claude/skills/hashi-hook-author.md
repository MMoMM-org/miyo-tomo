# WHY: hashi-hook-author (skill)

> Rationale for decisions in `tomo/dot_claude/skills/hashi-hook-author/SKILL.md`.

## Why This Skill Exists

WHY: Hashi executes user-authored `.cjs` hooks from `.tomo-hashi/hooks/` to customize what happens before/after each instruction-set action (`Hashi/src/hooks/`, `Hashi/docs/hooks.md`). Writing a correct hook means knowing the file-naming convention (`<phase>-<action>.cjs`), the `module.exports = async (ctx) => {...}` contract, the `{action, app, logger}` context shape, and the before/after error semantics. Tomo already holds that knowledge from the cross-repo architecture, so a guided author lowers the barrier for users who want Hashi customization but don't want to learn the contract from scratch.

## The Core Risk: Unsandboxed Host Code

WHY: Hashi hooks run with full plugin privilege and **no sandbox** — the trust model is documented as "same as Templater" (`Hashi/docs/hooks.md:3-5`). A hook can reach `child_process`, `node:fs`, the network, and `process.env`. That means a Tomo-generated hook is unsandboxed code that executes on the user's host with full vault/filesystem/network access. This is a genuine expansion of Tomo's trust surface: Tomo itself runs sandboxed in Docker and writes only to the inbox, but the artifact it produces here runs *outside* that sandbox. Every safety decision in the skill follows from this fact.

## Disclaimer First, Liability on the User

WHY: Because the generated code runs unsandboxed, the skill opens with a mandatory disclaimer and acknowledgement gate before any work. The decision (user, this session) was explicitly that review, testing, and liability rest with the user — Tomo offers no guarantee. The disclaimer is the boundary that owns the residual risk the deterministic scanner cannot catch (see `hashi-hook-scan.md`). The handoff doc repeats the disclaimer so it travels with the artifact into the vault, where the user reads it at apply time rather than only at generation time.

## Three-Tier Classification + Mass-Change Flag, Not Restrict-Only

WHY: The user chose a tiered safety model over a hard allowlist. A pure allowlist would block legitimate power-user hooks; pure warnings would normalize dangerous output. The tiers (green free / yellow warn / red confirm-or-refuse) let benign Obsidian-API hooks flow while forcing an explicit, informed decision for dangerous constructs and a clear "not advisable via Tomo" recommendation for red. The orthogonal `mass_change` flag exists because a hook can be tier-green (Obsidian API only) yet still rewrite thousands of notes by iterating the whole vault — danger that risk-by-capability alone would miss. The user added this requirement directly.

## Inbox-Only Handoff, User Places the File

WHY: Tomo's MVP execution boundary permits writes only to the inbox; it must never reach into `.tomo-hashi/hooks/` directly. So the skill emits the hook as a real `.cjs` file plus a handoff doc into the inbox, and the user moves the hook into place themselves. This keeps the human in the loop at exactly the moment the artifact crosses from sandbox to host, and keeps Tomo inside its declared boundary. The two backup warnings (before placing the hook, before the next Hashi run) front the handoff doc because a misbehaving hook's blast radius is the whole vault.

## Persisting the Hooks Path

WHY: The hooks directory is per-vault and stable, so re-asking every run is friction. The path is persisted in `config/vault-config.yaml` under `extensions:` (user decision). `extensions:` is used rather than `concepts:` because the hooks path is a Hashi integration detail, not a PKM concept — keeping it separate avoids polluting the concept namespace that profiles and the rest of the pipeline consume.

## Kado Access Probe Is Advisory, Not a Gate

WHY: The skill probes whether Kado can see the hooks dir so it can warn about clobbering an existing `<phase>-<action>.cjs` (Hashi loads exactly one file per phase+action). The probe is advisory: if Kado cannot reach the dir (not on the ACL allowlist), the skill still produces the artifact and notes "access not verified" in the handoff. Hard-failing on an unreachable probe would block a legitimate workflow over a permission detail the user can resolve at apply time.
