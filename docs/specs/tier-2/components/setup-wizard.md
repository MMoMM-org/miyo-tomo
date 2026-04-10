# Tier 2: Setup Wizard

> Parent: [PKM Intelligence Architecture](../../tier-1/pkm-intelligence-architecture.md)
> Status: Draft
> Children: [Install Script](../../tier-3/wizard/install-script.md) · [First-Session Discovery](../../tier-3/wizard/first-session-discovery.md)

---

## 1. Purpose

Define the two-phase onboarding that produces a complete vault-config.yaml and discovery cache. Phase 1 runs without Kado; Phase 2 runs with Kado.

## 2. Two-Phase Design

| Phase | Environment | Access | Output |
|-------|-------------|--------|--------|
| **1. Install Script** | Host machine | Filesystem (`ls`) | Starter vault-config.yaml |
| **2. First-Session Discovery** | Docker + Kado | Kado MCP | Refined config + discovery-cache.yaml |

Why two phases:
- Kado might not be running during install
- Basic config is needed to boot Tomo at all
- Deep intelligence requires Kado access

## 3. Phase 1: Install Script

Runs as part of `install-tomo.sh` on the host. No AI involved — deterministic script.

**Inputs gathered:**
1. PKM framework → select profile (miyo/lyt/para/custom)
2. Vault path → validate exists
3. Top-level folders → `ls` vault root, present to user
4. Concept mapping → user maps folders to concepts (inbox, notes, maps, etc.)
5. Lifecycle tag prefix → default "MiYo-Tomo"
6. Kado connection → host, port, bearer token

**Output:** Minimal vault-config.yaml with:
- `schema_version`, `profile`, `profile_version`
- `concepts` (folder paths)
- `lifecycle.tag_prefix`
- Profile defaults for everything else

**Detail spec:** [Install Script](../../tier-3/wizard/install-script.md)

## 4. Phase 2: First-Session Discovery

Triggered by `/explore-vault` in first Tomo session. AI-assisted via vault-explorer agent.

**Process:**
1. Connect to Kado MCP
2. Deep scan vault structure via `kado-search` (listDir, byTag, byName, byFrontmatter)
3. Read sample notes via `kado-read` — detect frontmatter fields, tag patterns, callout usage
4. Read map_notes — extract topics, sections, linked note counts
5. Present findings to user for confirmation/correction
6. Update vault-config.yaml with refined data
7. Build discovery-cache.yaml
8. Suggest template creation if `t_*_tomo` templates don't exist

**Output:** Complete vault-config.yaml + discovery-cache.yaml

**Detail spec:** [First-Session Discovery](../../tier-3/wizard/first-session-discovery.md)

## 5. Re-Running Discovery

`/explore-vault` can be re-run at any time to:
- Refresh the discovery cache (new MOCs, changed tags)
- Detect new patterns in the vault
- Update config with user confirmation

Re-runs do NOT overwrite user-customized config fields. They only update auto-detected fields and rebuild the cache.

## 6. Minimum Viable Vault

For a brand-new empty vault:
- Phase 1 works (user specifies folder paths even if empty)
- Phase 2 produces minimal results (no MOCs to index, no tags to detect)
- Tomo is functional but with degraded intelligence — cache is nearly empty
- As the user adds content, `/explore-vault` becomes increasingly useful
