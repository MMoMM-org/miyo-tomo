# Tier 3: Structure Scan

> Parent: [Vault Exploration](../../tier-2/workflows/vault-exploration.md)
> Status: Draft
> Agent: `vault-explorer`

---

## 1. Purpose

Define how vault-explorer maps the vault's folder structure, counting notes per concept folder, detecting folders not mapped to concepts, and identifying the overall vault topology.

## 2. Process

```
1. Read vault-config for concept folder paths
   → inbox, atomic_note (with subdirs), map_note (paths + tags),
     calendar, project, area, source, template, asset

2. For each concept path:
   kado-search listDir (depth=1 when available)
   → count files (type=file) and subfolders (type=folder)
   → record total notes per concept

3. Scan vault root for unmapped folders
   kado-search listDir on root (depth=1)
   → compare against all configured concept paths
   → any folder not claimed by a concept → "unmapped"

4. For atomic_note path (and any concept with subdirectories):
   Recursive scan for subfolder structure
   → record each subfolder with its note count
   → detect Dewey-numbering pattern if present

5. Output structure map for the cache
```

## 3. Output

```yaml
# In discovery-cache.yaml
vault_structure:
  concepts_mapped:
    inbox: { path: "+/", note_count: 12, subdirs: 0 }
    atomic_note:
      base: { path: "Atlas/202 Notes/", note_count: 72 }
      subdirs:
        - { path: "Atlas/202 Notes/2021 Thoughts/", note_count: 10 }
        - { path: "Atlas/202 Notes/2611 Code Snippets/", note_count: 51 }
        - { path: "Atlas/202 Notes/2821 Quotes/", note_count: 64 }
        # ...
      total_notes: 281
    map_note: { paths: ["Atlas/200 Maps/"], note_count: 27 }
    calendar:
      daily: { path: "Calendar/Days/", note_count: 180 }
      # ...
    project: { path: "Efforts/Projects/", note_count: 15 }
    area: { path: "Efforts/Areas/", note_count: 8 }
    source: { path: "Atlas/Sources/", note_count: 32 }
    asset: { path: "Atlas/290 Assets/295 Attachments/", file_count: 59 }
  
  unmapped_folders:
    - "Atlas/Sources/Books/"      # might be a sub-concept
    - "X/900 Support/Scripts/"    # utility, not PKM content
  
  total_notes: 614
  total_files: 673                # including non-md
```

## 4. Unmapped Folder Handling

Unmapped folders (not claimed by any concept path) are:
- **Reported** to the user during first-run confirmation
- **Not automatically assigned** — user decides what they are
- **Common:** template folders, plugin folders, attachment subfolders, support scripts

On first run (`/explore-vault --confirm`): ask user for each unmapped folder whether it should be:
- Added to an existing concept (e.g., "Atlas/Sources/Books/" → part of `source`)
- Ignored (not PKM content)
- Left for future

On subsequent runs: unmapped folders are silently logged unless new ones appear.

## 5. Kado listDir Strategy

### With depth Parameter (Post-Kado Enhancement)

```
listDir(path, depth=1) → immediate children with type + childCount
  → fast, shows structure in one call
  → recurse into subfolders as needed
```

### Without depth Parameter (Current Kado)

```
listDir(path) → all files recursively
  → parse paths to extract unique directory paths
  → group by directory → count per directory
  → slower, returns more data than needed
```

vault-explorer should detect whether `depth` is supported (check for `type` field in response items) and use the optimal strategy.

## 6. First-Run vs Subsequent Runs

| Aspect | First run | Subsequent |
|--------|-----------|------------|
| Scan scope | Full vault | Full vault (same) |
| User confirmation | Yes (present unmapped, confirm structure) | Only if new unmapped folders found |
| Config updates | Propose concept path additions | Skip (unless `--confirm` flag) |
| Duration | Longer (confirmation step) | Shorter (scan + write) |

## 7. Edge Cases

**Symlinks:** Kado resolves symlinks — files appear under their symlinked path. vault-explorer doesn't need special handling.

**Empty concept folders:** Report as note_count: 0. Not an error — the user may not have populated them yet.

**Very deep nesting (>5 levels):** Warn user. PKM vaults rarely need deep nesting; this might indicate a misconfigured concept path.

**Vault root not readable:** Fatal error — Kado scope likely too restrictive. Report and suggest checking Kado permissions.
