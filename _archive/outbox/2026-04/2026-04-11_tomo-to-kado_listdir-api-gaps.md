---
from: tomo
to: kado
date: 2026-04-11
topic: kado-search listDir — API gaps blocking /explore-vault
status: done
status_note: All 4 issues resolved in spec 004 (0.2.0). See _outbox/for-tomo/ for full reply.
priority: high
requires_action: true
---

# kado-search `listDir` — API gaps blocking Tomo's `/explore-vault`

Tomo's `/explore-vault` workflow (Phase 2 of the setup wizard) relies heavily on `kado-search listDir` to walk the vault, count notes per concept, detect subdirectories, and build the MOC tree. While integrating we hit four independent issues with `listDir` that required script workarounds and don't match the documented behavior. This handoff surfaces them for the Kado roadmap.

**Tomo side**: all four issues have workaround patches in flight (`scripts/lib/kado_client.py`, `scripts/vault-scan.py`, `scripts/moc-tree-builder.py`, `scripts/test-kado.py`). Tomo is not blocked — but the Kado-side improvements below would let us remove the workarounds and get richer data.

---

## 1. `path` with trailing slash rejected as HTTP 406

**Observation**: every concept path in Tomo's `vault-config.yaml` ends with `/` (e.g. `100 Inbox/`, `Atlas/202 Notes/`). Passing such a path to `kado-search listDir` returns `HTTP 406 Not Acceptable`. Dropping the trailing slash (`100 Inbox`) works.

**Puzzling**: `src/mcp/request-mapper.ts:90-94` already normalizes `listDir` paths:
```ts
function normalizeDirPath(path: string, operation: string): string {
    if (operation !== 'listDir') return path;
    if (path === '' || path === '/') return '';
    return path.endsWith('/') ? path : path + '/';
}
```
So a trailing slash should be a no-op. The 406 must originate higher in the stack (transport layer? path-access gate? Accept header negotiation?).

**Reproducer** (via Claude Code MCP integration):
```
kado-search operation="listDir" path="100 Inbox/"   →  HTTP 406
kado-search operation="listDir" path="100 Inbox"    →  OK
```

**Suggested fix**: accept trailing slashes everywhere or return a proper `VALIDATION_ERROR` with a helpful message instead of HTTP 406 (which is misleading — nothing about content negotiation).

---

## 2. Response items have no `type` field

**Observation**: `src/obsidian/search-adapter.ts:30-38` defines `mapFileToItem`:
```ts
function mapFileToItem(file: TFile): CoreSearchItem {
    return {
        path: file.path,
        name: file.name,
        created: file.stat.ctime,
        modified: file.stat.mtime,
        size: file.stat.size,
    };
}
```

No `type` field. Documented API shape in `docs/api-reference.md:498-509` matches — `{path, name, created, modified, size}`.

**Impact on Tomo**: our scanner scripts can't distinguish files from folders (and since `listDir` only returns files via `app.vault.getFiles()`, there's no folder entries at all — see issue 3). We had to remove all `item.type === 'file'` / `item.type === 'folder'` filters from three Python scripts.

**Suggested fix**: add `type: 'file' | 'folder'` to `CoreSearchItem`. Even if `listDir` currently only returns files, this is a forward-compatible schema change that lets clients reason about the response shape.

Alternative: add `contentType` / `mimeType` (file-only) so clients can at least distinguish Markdown from binary attachments without string-matching on `name`.

---

## 3. `listDir` is inherently recursive (uses `getFiles()`)

**Observation**: `src/obsidian/search-adapter.ts:111-114`:
```ts
function listDir(app: App, request: CoreSearchRequest): CoreSearchItem[] {
    const prefix = normalizeDir(request.path ?? '');
    return app.vault.getFiles().filter((f) => f.path.startsWith(prefix)).map(mapFileToItem);
}
```

`app.vault.getFiles()` returns **all files in the vault**, recursively. `listDir` then filters by path prefix. So `listDir("Atlas")` returns every `.md` file under `Atlas/` at any depth — not just direct children.

**Impact on Tomo**:
- Tomo's per-concept scanner can't report "direct notes vs. notes in subdirectories" separately — everything gets mashed together
- For `atomic_note` (e.g. `Atlas/202 Notes/`), Tomo needs to detect subdirectories to propose Dewey classification. Currently it has to derive subdirectories by splitting paths of the flat recursive listing
- For large vaults this returns every single file under the concept path in one call — no ability to page the top level only

**Suggested fix**: add a `recursive: boolean` option to `listDir`. Default behavior (`recursive: true`) stays the same for backward compatibility. `recursive: false` returns only direct children — both files (TFile) and folders (TFolder), using `app.vault.getAbstractFileByPath(path).children`.

Alternative (non-breaking, lighter): add a new operation `listChildren` that returns only direct children. Keep `listDir` as-is (recursive flat). Tomo would call `listChildren` for structure detection and `listDir` for deep scans.

Related benefit: returning TFolder entries (with `type: 'folder'`) would let clients build a tree without reading every file path.

---

## 4. Empty path (`""`) rejected by path-access gate

**Observation**: `src/core/gates/path-access.ts:37-40`:
```ts
function validatePath(normalized: string): string | null {
    if (normalized.length === 0) {
        return 'Path must not be empty';
    }
    ...
}
```

And `src/core/gates/path-access.ts:56-62`:
```ts
evaluate(request: CoreRequest, _config: KadoConfig): GateResult {
    if (isCoreSearchRequest(request) && request.path === undefined) {
        return {allowed: true};
    }
    const raw = (request as {path?: string}).path ?? '';
    const normalized = normalizePath(raw);
    ...
}
```

The gate short-circuits when `path === undefined` but blocks `path === ""`. To list the vault root, a client must **omit** the path parameter entirely — passing an empty string triggers `'Path must not be empty'`.

**Impact on Tomo**: the `KadoClient.list_dir(path="")` helper sends `path: ""` in the JSON-RPC args, which gets rejected. We patched the client to drop the path arg when empty, but this is a surprising asymmetry — most users intuitively pass `""` to mean "root".

**Suggested fix**: treat `path === ""` as equivalent to `undefined` in the path-access gate (or in `request-mapper.ts` normalization). Document the "omit path to list root" convention in `docs/api-reference.md`.

---

## Summary: suggested Kado roadmap items

| # | Change | Breaking? | Benefit |
|---|--------|-----------|---------|
| 1 | Fix HTTP 406 on trailing-slash `listDir` paths (or return a clearer error) | No | Less frustrating error; matches documented normalization |
| 2 | Add `type: 'file' \| 'folder'` to `CoreSearchItem` | No | Clients can distinguish entry types; forward-compatible |
| 3 | Add `recursive: boolean` to `listDir` (default `true`) **or** add a new `listChildren` operation that returns direct children only (TFile + TFolder) | No | Enables efficient tree building and structure detection |
| 4 | Treat `path: ""` as "list vault root" (match `path: undefined` behavior) | No | Intuitive, less surprising API |

All four are additive — none break existing clients. Items 2+3 are the most impactful; without them any client trying to reason about vault structure (not just content) has to rebuild it from file paths.

---

## Tomo workaround status

Tomo's Python scanner scripts will be patched in parallel to work with the current Kado API:

- `scripts/lib/kado_client.py` — strip trailing slashes in `list_dir()`, drop `path` arg when empty
- `scripts/vault-scan.py` — derive subdirectories from flat file paths; count all returned items as files
- `scripts/moc-tree-builder.py` — drop `type === 'file'` filter, keep `.md` filename check
- `scripts/test-kado.py` — same treatment

Once Kado ships any of items 2+3, Tomo can simplify these scripts.

---

## Questions for Kado

1. Is there an existing plan to add a non-recursive `listDir` mode or a separate `listChildren` operation? (Not visible in `docs/XDD/ideas/` as of this writing.)
2. Should Tomo avoid `listDir` for structure detection and use some other approach (e.g. a dedicated "get vault tree" call)?
3. Any reason `type` was deliberately excluded from `CoreSearchItem`, or was it just "wasn't needed yet"?

Happy to open GitHub issues on `miyo-kado` for each item if that's a better tracking venue than this outbox file.
