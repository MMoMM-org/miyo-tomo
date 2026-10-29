# Spec 039 — Research (2026-10-11)

Four read-only research passes ran before the PRD, one per perspective. Their reports are kept here in full; the synthesis and the owner decisions they forced are at the end. Line numbers refer to `main` at `d583cd3`.

---

## R1 — Technical: the Pass 2 attachment path

**Headline:** Pass 2 never checks a `move_asset` against the vault, no delete depends on any `move_asset`, and the vault listing `validate_destinations` uses sees only `.md` files. `ignore` deliberately ships a move onto an occupied destination — a vault check would drop every one, which needs a decision.

### 1. `_build_move_asset_actions`, `validate_destinations`, `make_folder_listing`

- A `move_asset` action is `{id, action:"move_asset", source, destination}` (`render_withhold.py:292-297`), plus `applied` from `build_actions` (:2873-2874). No owner field. Hashi's schema for it is `additionalProperties: false` (`Hashi/src/schema/instructions.schema.json` `$defs.move_asset`), so any internal owner field must be stripped; `_strip_internal_link_fields` (`render_resolve.py:443-470`) handles only `move_note` and `link_to_moc`.
- Ownership is tracked only for SKIPPED attachments (:819-827). For an emitted attachment the first owner is computed (:814-818, 829) and discarded; there is no path→owners or path→id map. The owner key is `_ensure_md_extension(resolve_source_path(...))`, the same expression `_build_move_note_actions` uses for `source_inbox_item` (:665-670), so it joins with site 3's `moves_by_origin`.
- Current claim check: run-internal `claimed`, case-folded, first claim wins (:945-963). No vault check in Pass 2. Pass 1 checks only the asset folder (`suggestions-reducer.py:698`). `ignore` or no remedy leaves the destination unchanged even when Pass 1 saw it occupied (:763-764, :940-944).
- `validate_destinations` (:1261-1404) takes only `move_note`/`create_moc` (:1306), groups by `destination.casefold()`, vault half at :1318-1325. Paired-delete candidates come from `_paired_delete_candidates`, which reads only `source_inbox_item`/`audio_peer` (:1069-1084) — a `move_asset` yields none. `_drop_moves_with_paired_deletes` (:1181-1258) removes any dropped id regardless of kind. The real delete withdrawal is by id in `withdraw_unjustified_deletes` (:2721-2783), called at `instruction-render.py:857`. Clash prose `_destination_clash_reason` (:1036-1066) says "a note already exists at…" — wrong for an attachment. The `dropped` dicts read `title` and `source_inbox_item`, both absent on a `move_asset`.
- `make_folder_listing` (:991-1033) keeps only `.md` files (:1023), keyed via `_dest_join(folder, name[:-3])`, no folder entries, and caches the *filtered* map — the pitfall the Pass 1 twin `_VaultFolderLookup` avoids by caching raw entries and deriving `notes()`, `assets()` and `occupied_by_folder()` (`suggestions-reducer.py:314-418`). Widening it costs a second `list_dir` per folder unless the cache becomes raw. Listing errors read as empty (:1028-1029). The listing is passed only when `client` exists, i.e. only when `confirmed` is non-empty (`instruction-render.py:411-417, 672-674`).
- To make `move_asset` a vault-checked claimant: a non-`.md` listing keyed by `_asset_dest_join` plus folder occupancy with a raw cache; a grouping branch (run-internal collisions are already settled by `claimed`, so only the vault half adds anything; a note and an asset cannot share a key); attachment-specific wording; owning notes for ADR-6 (`suppress_moves_for_unfiled_attachments` :1534-1637) via a `skipped_assets`-shaped entry — ordering allows it (validate :672, suppress :690). A separate guard would also need `WITHDRAWAL_GUARDS` (`render_helpers.py:95-101`) and `drop_sources` (`instruction-render.py:866-891`); `attribute_withdrawal_causes` assumes guards are disjoint per action kind (`render_helpers.py:111-113`).
- Today Hashi fails a move onto a present destination with "Inconsistent state — both source and destination present" (`Hashi/src/actions/moveAsset.ts:72-74`), including `same_file`.
- Which deletes a dropped `move_asset` should take: there is no `delete_source` for an attachment path at any site. The stakes are the owning origins' deletes (origin + audio peer, site 3, :2142-2165). The id mechanism works as soon as those deletes name the `move_asset` id in `depends_on`; `withdraw_unjustified_deletes` is not kind-limited.

### 2. `_build_delete_source_actions`, site 3 (:2096-2165)

- Receives `confirmed, move_notes, daily_updates, skipped, …` (:1969-1981), never `move_assets`; `build_actions` passes only `move_notes` (:2855-2862) though `move_assets` is in scope (:2841-2845).
- `depends_on` = every `move_note` id for the origin (:2116-2124, :2141); origin delete :2147, audio-peer deletes :2164.
- No origin→attachment mapping at site 3. Cleanest source: a new `{origin_key: [move_asset ids]}` map from `_build_move_asset_actions`, mirroring `daily_action_ids_by_origin`, built without the `seen` short-circuit for emitted paths (:820-827).
- Shared attachments: one `move_asset` per unique source path (:804, 820). With path P embedded by notes A and B, both origins' deletes would name P's move; if it fails, both origins are kept.
- Attachments without a `move_asset`: `vault_collision_held`/degraded rename — note filed, delete stays (intended; suppress excludes it :1587-1589). `typed_name_refused`, `collision`, `no_basename` — owning `move_note`s are suppressed, so deletes are already withdrawn via the `move_note` id. Only emitted moves need adding.
- Tests pinning `depends_on` exactly: `tests/test_036_t2_4_phase_validation.py:241,263` (fixture has `attachments: []`, unaffected); `tests/integration/test_036_delete_justification_e2e.py:559`; `tests/test_036_depends_on_emission.py`. Likely affected (carry attachments with deletes, UNVERIFIED): `test_034_t5_4_*`, `test_034_t5_3_*`, `test_031_t2_6_*`, `test_031_t6_2_*`, `test_036_t2_3_*`.
- Hashi needs no change: its planner honours `depends_on` on any kind (`Hashi/src/executor/planner.ts:264-290`); `KIND_ORDER` puts `move_asset` before `delete_source` (:39-56).

### 3. `rewrite_renamed_embeds` and the timing problem

- Called at `instruction-render.py:572-574` inside the render loop, before the staged note is written (:587); moves are computed later in `build_actions` (:643-651). (The comment at :567 cites a stale ":551".)
- `embed_rewrite.py` (0.4.2, :92-170): only `rename` with a non-empty, check-passing `proposed_name` builds `renames` (:133-148). Matching is by basename alone (:165) — verified: `![[Folder/Sub/name.png]]` became `![[new.png]]` for attachment `100 Inbox/A/name.png`. Output is always bare (:168). Known gap (:123-125): a run-level withhold still rewrites the body. `_target_and_suffix` does not strip whitespace, so `![[ name.png ]]` is never rewritten, while `extract_attachment_embeds` does strip.
- A path-qualify decision must be made at or before :572 and needs: (a) the final folder (`cfg["concepts.asset"]`, loaded :396, default at `render_moc_actions.py:52`, or the new `proposed_dir` — which must be added to the parser projection `suggestion-parser.py:508-516` and the markdown join); (b) the final basename; (c) a vault-wide basename index (none exists); (d) the run's other final basenames; (e) run-level withholds, not known in the loop. Alternative: compute the asset plan before the loop, or move the rewrite after `build_actions` and re-write the staged files (feasibility UNVERIFIED; :627-630 and :707-714 show later rewrites happen).
- Note embeds use `qualified_target` (`source_link.py:43-51`), which drops `.md` and adds an alias — not fit for attachments: the extension must stay, and an alias on an image embed may be read as a size (UNVERIFIED).
- Bare embeds whose basename exists elsewhere already happen today: (1) any non-conflicting attachment (Pass 1 checks only the asset folder), (2) a computed rename (`_propose_asset_name` checks only `vault_assets`, `occupied_folders`, `proposed`, `suggestions-reducer.py:570-579`), (3) a path-qualified original embed made bare by a rename.
- Hashi applies `move_asset` through `fileManager.renameFile` (`moveAsset.ts:87`, `ObsidianVaultFS.ts:95-98`); whether Obsidian then rewrites links depends on settings (UNVERIFIED).

### 4. `typed_name_check.py` (0.1.3)

- `REFUSAL_REASONS = frozenset({"separator_present","forbidden_character","blank"})` (:31); `_NON_SEPARATOR_FORBIDDEN_CHARS = FORBIDDEN_CHARS - {"/"}` (:37); `FORBIDDEN_CHARS = frozenset('\\/:*?"<>|\x00')` (`obsidian_filename.py:32`). `check_typed_name` (:53-80): blank via `not name.strip()`, then `/`, then forbidden; padding accepted verbatim, flagged pending (:62-69).
- Consumers: `render_withhold.py:231` (only when `name_is_owner_supplied`), :930 stores `refusal_reason`. `_typed_name_refusal_reason` (:692-720) branches on `separator_present` (:710) and `forbidden_character` (:715); **anything else falls to the "blank" sentence (:720)** — a new reason without a branch is silently mis-phrased. `embed_rewrite.py:145` uses only `.ok`. `render_inbox_actions.py:126` and `render_md.py:864` branch on `kind`. `instruction-render.py:1039-1046` does not project `refusal_reason`.
- Tests pinning the closed set: `test_038_t3_1_typed_name_check.py` (:40, :235-247 exact frozenset, :250-256, :259 signature, per-reason asserts, a padding-pinning test); `test_038_t3_2_typed_name_refusal.py` (:130, 293, 394, mutation table :434-442); `test_038_t3_4_refusal_reported.py` (:122, :138); `test_038_t4_2_parser_reads_the_typed_name.py` (:241-285, :321, :349); `test_038_t4_3_refused_name_rewrites_no_embed.py`; `test_038_t4_4_the_two_paths_converge.py` (:85, :564, :617).
- Docs stating "exactly three": `docs/tomo/scripts/lib/typed_name_check.md:71+`, `docs/tomo/scripts/lib/render_actions.md:1550-1610`, docstring `render_withhold.py:34-36`.

### 5. `extract_attachment_embeds` (0.4.0)

- `_EMBED_RE = r"(!)?\[\[([^\[\]]+)\]\]"` (:13) — slashes and spaces match. `_strip_alias_and_anchor` (:161-171) keeps the path, strips alias and `#`/`^`. Verified: `![[Folder/Sub/name.png]]` → `Folder/Sub/name.png`; `![[Atlas/290 Assets/my file (2).png|alias]]` → `Atlas/290 Assets/my file (2).png`.
- Caveat: `#`, `^` or `|` in a path truncates it (:168-170).
- `narrow_candidates` (:89-121) resolves a qualified target only against the INBOX index — a qualified embed pointing outside the inbox reads `unresolved` at triage.

### Open technical questions (R1)

1. `ignore` under a vault check: exemption or drop? (`same_file=True` is the sharpest case.)
2. Does a vault-dropped `move_asset` hold its owning note (ADR-6), or only withdraw the delete via `depends_on`?
3. Owner data: side map from `_build_move_asset_actions`, or a stripped internal field?
4. Should a delete depend on a `move_asset` shared with another origin?
5. Reuse `_VaultFolderLookup` or a lib twin?
6. Vault-wide basename check: which Kado call, case-folding, available before :572?
7. Rewrite timing: plan before the loop, or rewrite after `build_actions` (would also close `embed_rewrite.py:123-125`).
8. Basename-only matching rewrites a qualified embed pointing elsewhere.
9. Path-qualified attachment embed format: keep the extension, no alias.
10. #185's new reason needs its own branch in `_typed_name_refusal_reason`.
11. `proposed_dir` must reach every `_asset_dest_join` site (Pass 1 :712, :575; Pass 2 :831, :939); Pass 1 lists only `asset_folder`.

---

## R2 — Integration: wire schema, inventory and markdown surface

### 1. Schemas and the version bump

- Live wire schema `tomo/schemas/suggestions-wire.schema.json`: `schema_version` const `"3"` (:10); `attachment_conflicts[]` items at :175-190, `required ["source","destination","same_file","remedy","proposed_name"]` (:180), `additionalProperties:false` (:181); `remedy` (:186) and `proposed_name` (:187) descriptions start "Editable — " — load-bearing for the inventory join.
- Shape manifest `tomo/schemas/shapes/suggestions-wire.shape.json` (version at :32-34, :326; conflicts node :37-66) — regenerate with `python3 scripts/wire-shape.py --regenerate`.
- **Pre-existing gap:** the vendored Hashi copy `tomo/schemas/hashi-suggestions-wire.schema.json` is still `"const": "2"` with no `attachment_conflicts`. Spec 038 Phase 5 was to refresh it after Hashi confirmed v3; it never was. Hashi's real copy (`../Hashi/src/schema/suggestions-wire.schema.json:10`) is `"3"`.
- `suggestions-doc.schema.json` (Pass 1 structured doc, const "1"): conflict items (:241-270) are `additionalProperties:false`; only affected if Pass 1 emits `proposed_dir`.
- 2→3 precedent: spec 038 `solution.md` :91-98 (CON-1 coordinated release, CON-2 silent markdown fallback), :286-289, :306-319, ADR-1 :368-393 (live schema and manifest move; vendored copy waits for consumer confirmation; `wire_gate.classify()` treats a property added to a closed node as consumer-affecting). Spec 035 ADR-5: no literal version in emitters or acceptors.
- Version readers (schema-const driven, no literal edits): `lib/wire_version.py:30-71`, emitter `suggestions-render.py:545`, acceptor `suggestion-parser.py:272-280`. `scripts/spec038-wire-edit.py` would need a `--proposed-dir` flag.
- Tests pinning suggestions-wire "3": `test_038_suggestions_wire_schema_move.py:71`; `test_035_t4_2b_daily_source_identity.py:196, :524-525`; `test_038_t2_4_wire_baseline_diff.py:134, :147, :154`; `test_wire_snapshot_parity.py:689-760` (exact delta, depends on vendored refresh order); `test_031_t3_1_attachments_schema.py:191`; likely `test_034_t1_2_schemas_item_key.py:118`. Many other "3" hits are the **instructions** wire and must not be touched. `test_035_wire_gate.py:186` requires the regenerated manifest.
- Tests building five-key conflict entries: `test_038_t2_2_attachment_conflicts_wire_projection.py:110-125`, `test_037_remedy_lost_on_the_wire_path.py:102,117`, `test_038_t4_4_the_two_paths_converge.py`, `test_038_t4_2_parser_reads_the_typed_name.py`.

### 2. Decision inventory

- `tomo/schemas/suggestions-decision-inventory.json` (25 rows, D01–D25) + schema. Row: `required [id, markdown_control, wire_field, editable]`, `parser_label` required when editable, optional `note`. D24 = `attachment_conflicts[].remedy`; D25 = `attachment_conflicts[].proposed_name` (shares the rename line). Next id D26, assigned by hand.
- Join tests: `test_038_decision_inventory_join.py` — schema side counts "Editable" descriptions against editable rows (floor 25, :116); parser side harvests string literals and requires each to appear in a row's `parser_label` or an `ABSENCE_RULES` entry (:209-279; floor 61). `test_038_inventory_schema_validation.py:372` `EXPECTED_EDITABLE_MARKED_FIELDS = 25`, :387 `test_wire_schema_marks_exactly_25_editable_fields` → both 26; :436-450 exact em-dash prefix; :461-470 `_IDENTIFIER_RE` rejects T/F/ADR ids, "spec 0xx", "PRD" and **any bare 3–4 digit number** in a note.
- Hashi vendors the inventory and joins it in `editable-field-coverage.test.ts`.
- A separate folder line introduces a new parser literal that D26's `parser_label` must carry; parsing the folder out of the existing rename line would share `["rename"]` like D25 (join limitation 2, `test_038_decision_inventory_join.py:56-60`).

### 3. Markdown surface

- Renderer `render_attachment_conflicts_block` (`suggestions-reducer.py:1438-1535`): `### \`<source>\``, Destination, Embedded by, File comparison, then `- [x] Rename to \`<_asset_dest_join(asset_folder, proposed_name)>\``, `Keep in inbox`, `Ignore (send the move unchanged — …)` (:1516-1531). `destination = _asset_dest_join(asset_folder, source)` (:712).
- Parser (`suggestion-parser.py`): `RE_RENAME_TARGET` (:2261); `_walk_attachment_conflicts` (:2312-2429) considers only checkbox lines (:2400-2403); `rename_impossible` (:2420-2422); `_join_attachment_conflict_remedies` (:2455-2546) strips the exact folder prefix Tomo printed (:2532-2538), `name_is_owner_supplied = proposed_name != doc_name` (:2539). Owner ruling 2026-10-02 pinned by `test_038_t4_2_parser_reads_the_typed_name.py:241-263` `test_a_different_folder_typed_is_refused_separator_present` and :477.
- An editable folder needs: a new line or new rename-line semantics; the untouched default stays byte-identical (CON-3; `test_038_t4_1_markdown_offers_a_place_to_type.py:76`); a new non-checkbox parser branch before :2400; un-rendering against `dirname(destination)` with its own provenance flag; round-trip and convergence tests (`test_037_fix_render_parse_round_trip.py:129`, `test_038_t4_4_the_two_paths_converge.py:467/509/556`).

### 4. Wire path

- `load_changed_wire` (`suggestion-parser.py:245-288`) checks parseability, version and digest — **never jsonschema**. A Hashi-written `proposed_dir` of any shape reaches Pass 2 unvalidated.
- `build_from_wire` (:331-521) projects conflicts at :493-517 with `name_is_owner_supplied: True` unconditionally; `destination` is dropped. `build_from_wire_companion` (:524-564) does not merge the fan wire's `attachment_conflicts` (pre-existing gap).
- Pass 2: `instruction-render.py:391-393, 456-458, 566-573, 643-651`; `_build_move_asset_actions` destination at `render_withhold.py:267` — where `proposed_dir` substitutes for `asset_folder`. `asset_folder` comes from Pass 2 config, not from the wire's `destination`, so "null = dirname(destination)" equals the asset folder only while config is unchanged between passes.
- Spec 038's SDD line "Pass 2 still makes no vault calls" is out of date (`instruction-render.py:672-674`).

### 5. Validating an owner-typed folder (measured)

| input folder | `_asset_dest_join` result | `_check_path_shape` |
|---|---|---|
| `../x` | `../x/karte.png` | `'..' segment` |
| `/abs` | `/abs/karte.png` | leading-slash absolute path |
| `a//b` | `a//b/karte.png` | **passes** |
| `a/` | `a/karte.png` | passes |
| `""` | `/karte.png` | leading-slash |
| `./a` | `./a/karte.png` | relative `./` prefix |
| `a/./b` | `a/./b/karte.png` | **passes** |
| `" a "` | `" a /karte.png"` | **passes** |
| `a\b` | `a\b/karte.png` | backslash |

- `_check_path_shape` (`render_actions.py:182-203`) runs only via `_validate_action_paths` (`instruction-render.py:913-924`) and a violation **aborts the whole Pass 2** (`return 2`) — a typed `../x` would abort the run rather than refuse one entry. A per-entry check must run first, as 038 placed `check_typed_name`.
- Missing: vault-path normalisation; an inbox-folder guard; Kado ACL awareness (a denied folder's listing error reads as empty, i.e. *free*); a folder-existence check — Hashi's `move_asset` contract says **"Parent folder is created if missing"** (`docs/instructions-json.md:768-800`), so a typo silently creates a folder.

### 6. Owner-facing docs to update

- `docs/usage.md:63-97` (attachment name taken), :48-59 (two surfaces); `docs/troubleshooting.md:222-250` ("Tomo checks the destination once, during Pass 1" — becomes false); `docs/instructions-json.md:768-800`.
- Developer WHY docs under `docs/tomo/scripts/`: `suggestion-parser.md`, `suggestions-reducer.md`, `suggestions-render.md`, `lib/render_actions.md`, `lib/embed_rewrite.md`, `lib/typed_name_check.md`, `lib/render_md.md`, `instruction-render.md`, and `lib/wire_gate.md` / `wire_snapshot_parity.md` if the vendored narrative changes.

### Open questions (R2)

1. Folder on its own line, or the rename line's path split into dir + name (reverses the 2026-10-02 ruling)?
2. What does null mean in Pass 2 — the wire's `dirname(destination)` or `cfg["concepts.asset"]`?
3. Pass 1 default: always null? How is a null folder rendered?
4. Unchanged name into a new folder — allowed? (`rewrite_renamed_embeds` does nothing unless the name changes.)
5. Folder refusal classes (closed set, refuse never rewrite).
6. Refusal shape: new `kind` or extended `REFUSAL_REASONS`?
7. Pass 2 vault check for `move_asset`: which listing, which folder, and how is a Kado error treated (today: "empty" = free = fail-open)?
8. Folder provenance flag: one flag or two?
9. Refresh the vendored copy to v3 first?
10. Fan wire drops `attachment_conflicts` — in scope?
11. Should Pass 2 jsonschema-validate an edited wire?
12. `proposed_dir` follows `proposed_name`'s "read only under rename" rule.

---

## R3 — Performance and Kado capability: vault-wide basename uniqueness

### 1. What Kado offers

- Tomo client `tomo/scripts/lib/kado_client.py`: `list_dir(path="/", depth=None, limit=500)` (:253-272, files and folders with `type`, unlimited recursion), `list_notes` (.md only), `search_by_name` (:283-290, `byName`), `resolve_stem_to_path` (:292-311, exact match filtered client-side because "Kado byName does substring matching"). `_search_all` follows cursors (:601-637). Retries on 429/503 up to 4 times, backoff 0.5–10 s, `Retry-After` honoured up to 60 s (:33-37, :674-700).
- **Kado `byName` searches every file type vault-wide** — [Kado] `src/obsidian/search-adapter.ts:408-415` filters `app.vault.getFiles()` (not `getMarkdownFiles()`, which the other operations use) on `f.name`, case-insensitive substring, or an unanchored case-insensitive glob. So `photo.png` also returns `old-photo.png`; Tomo must filter for exact equality. Results are scoped to the API key before paging (:737-741); pages ≤ 500; hidden dot-folders never returned. **Typical cost: one call per basename.**
- Recursive `listDir` works and is paged, but Kado walks and sorts the whole tree for every page; no extension filter. Cost ceil(items/500) calls and large payloads.
- The `_inbox/from-kado` handoffs don't cover `byName`; its behaviour is from source.

### 2. Existing indexes — none covers attachment basenames vault-wide

- `attachment_index.build_inbox_index` (inbox only, exact keys); `_VaultFolderLookup` (per destination folder, depth 1); `make_folder_listing` (Pass 2, `.md` only); `vault-scan.py:127` (counts only); `moc_scan.py:187` (`.md`); `shared-ctx-builder.py:192` (depth 1).
- **Pattern to copy:** `render_resolve.py:599-614` — `byName` once per unique stem, cached, exact-stem filter.

### 3. Rate limits and call cost

- Kado default: 20 requests per 5 s per IP ([Kado] `src/types/canonical.ts:685-686`), 429 with `Retry-After` (`src/mcp/server.ts:108-152`).
- Observed 429s: `docs/tomo/dot_claude/agents/suggestion-conductor.md:45-60`, `docs/tomo/scripts/garden-audit.md:18`, `docs/ai/memory/general.md:7`, `docs/tomo/scripts/moc-tree-builder.md:73`.
- Budget precedents: spec 037 `solution.md:388-405` (`base_kado_calls` 2, `folder_listing_calls` +1 per miss); spec 022 `solution.md:480` ("zero new Kado calls").
- Estimate (A = distinct final basenames filed per run): `byName` per basename = A calls (typically 0–20, inside one rate window; 0 when no attachments). Full vault listing = ceil(items/500) calls every time an attachment is filed (e.g. 18 calls for 9k items) — only worth it above A ≈ 10–20.

### 4. Where Pass 2 could do the lookup

- Client exists only when `confirmed` is non-empty (`instruction-render.py:411-417`).
- The embed form must be decided before the render loop: right after :457, a `basename -> count` census for every final basename, passed to `rewrite_renamed_embeds`. Suggested `make_basename_census(client)` in `render_actions.py`, twin of `make_folder_listing`, counting calls like `_VaultFolderLookup._entries` (`suggestions-reducer.py:332-347`).
- **The count must be adjusted for the run itself:** exclude the attachment's own inbox copy (still in the vault at Pass 2 — `byName` finds it), exclude other inbox sources this run moves away, add other in-run `move_asset` claims on the same basename. Otherwise every filed attachment counts at least 2.
- **Scope gap:** the rewriter only acts when `remedy == "rename"`; attachments filed under their original name keep their embeds untouched.
- Pass 1 alone cannot decide it: the owner may change name or folder before Pass 2.

### 5. Case sensitivity

- Tomo folds destinations (CON-6; `docs/tomo/scripts/suggestions-reducer.md:851-873`), but compares source/inbox keys exactly.
- Kado `byName` lowercases both sides; Python `casefold` folds further, so a client-side casefold equality only narrows Kado's set — safe.
- Obsidian's resolution of an ambiguous bare basename, and whether it ignores case: **unmeasured** (CON-7 forbids live probes). Folding is the safe direction — at worst a link is path-qualified needlessly.

### Recommendation (R3)

`byName` with the bare final basename, exact casefold filter, in Pass 2 after :457 and before the render loop, cached per basename, ≈ A calls, reported as a counter. No full vault listing unless A is regularly > 15. On Kado failure: path-qualify (always resolves if the path is right) or fail open to bare — owner decision.

### Open questions (R3)

1. Obsidian's ambiguous-basename resolution (unmeasured).
2. `byName` only sees files in the key's scope — a restricted key under-counts and can yield a bare but ambiguous embed.
3. Index lag after changes made outside Obsidian.
4. Hidden folders — Obsidian ignores them for links too; probably harmless.
5. Does 039 cover attachments filed without a rename?
6. Real vault size and A per run — unmeasured.
7. Failure direction.

---

## R4 — Requirements: prior criteria, rulings and edge cases

### 1. Criteria style, rulings, and criteria 039 must not break

- **Style:** 036 uses inline IDs (`- [ ] **F1-AC1** — Given …, When …, Then …`); 037/038 use `#### F1:` with unnumbered Given/When/Then and refer to criteria by position in close-outs. Should/Could use S1/C1. Rulings are annotated on the criterion. Each criterion names its channel and path (038 :255-258; ADR-029 §2). Recommendation: 036's inline IDs plus a per-criterion channel tag.
- **Rulings:** 2026-09-27 bare-basename embed (full path was a rejected mutant because it hard-codes `concepts.asset`, `037…/plan/phase-3.md:112`); same day: keep-in-inbox names the attachment, the note is filed (`037…/close-out.md:236-250`), and `vault_collision_held` does not hold the note (`037…/solution.md:333`). 2026-10-02: only Tomo's own prefix is stripped, a typed folder refuses (`038…/plan/README.md:104`) — **`proposed_dir` collides with this ruling**, so the markdown counterpart must be a separate line or the ruling is reversed. 038 ADR-5 refuse-never-sanitise (`038…/solution.md:448-464`); ADR-6 refused name holds the owning note (:466-492). 2026-09-29 disclosure: "the note that embeds it is filed either way, so it will point at a file left behind in the inbox" (`render_md.py:145-151`) — must be re-checked once #186 changes the delete.
- **036's four delete justifications** (`036…/solution.md:519-524`): user-requested (`[]`), daily-only origin, `move_note` origin + audio peer, tag-handler group. The `depends_on` description in **both** `tomo/schemas/instructions.schema.json:253` and `hashi-instructions.schema.json:242` omits `move_asset` — #186 must update both (036's lesson: a description change is a contract change, invisible to the structural diff).
- **Must not break:** 036 F1-AC2, F5-AC1..AC6, Rule 6. 037 F1-AC1, **F1-AC3 (vault consulted once per run — re-baseline explicitly)**, F1-AC4, **F1-AC5 (degrade, don't block — decide failure direction)**, F2-AC2, F2-AC5, F3-AC1, **F3-AC3 (ignore emitted unchanged)**, F3-AC4, F3-AC5, Rule 5, C1-AC2, Scenario 3. 038 F1-AC4, F1-AC5, F1-AC6, **F1-AC9 (instructions wire untouched — #186 touches it, re-state)**, F2-AC2, F2-AC4, F2-AC7, F3-AC1..AC3, **F3-AC4 (occupancy run-local only — 039 supersedes it)**, F3-AC7..AC9, F4-AC1/AC9 (count 25 → 26), F4-AC3.

### 2. Kokoro ADR-029's open item

- `../Kokoro/global/decisions/ADR-029-tomo-hashi-boundary-is-a-set-of-channels.md:136-140`: under `ignore`/keep-in-inbox the note is filed and its source deleted though the attachment move failed; "the owner is told what happens to the attachment, not to the note … Kokoro takes no position until Tomo proposes one." Update 2026-10-11: tracked as #186; "the proposal touches C1 and comes as its own design-time handoff." Cadence (:152): a spec touching any §1 channel gets its own Kokoro handoff at design time; §2 (:77-81): name the channels before implementation.
- Expected handoff: names C1 (`depends_on` values + description), C3/C4 (`proposed_dir`, v4), C10 (Hashi's `skipped-dependency` cascade, both-present refusal); states the option and how the owner is now told about the *note*; carries the two near-miss runs.
- Already promised: `_outbox/for-kokoro/2026-10-11_…adrs-read-two-push-backs…:138-150, 172`; `…adr-018-section-4…:157-166`; Hashi told both options at `_outbox/for-hashi/…nothing-of-ours-depends-on-section-4-measured.md:171-180`.

### 3. Hashi's §4 rulings vs ADR-5

- (a) Sanitise-to-`-` applies only in Hashi's editor; ADR-5 remains Pass 2's independent guard (Hashi confirmed, `…wire-v3-vendored…:58-61`). Remaining: after #185 Tomo's refusal set must equal Hashi's sanitise set (ten + `# ^ [ ]` + padding); the same keystrokes trim in Hashi but refuse in markdown (accepted, document it); **`proposed_dir` has no sanitiser ruling.**
- (b) Inert conflicts grey out — UI only; Tomo never raises a conflict for suppressed items. Hole: Force Atomic bypass (`backlog.md:1149`).
- (c) A typed name survives remedy switches — confirmed harmless; `proposed_dir` needs the same guarantee on both routes.

### 4. `proposed_dir` edge cases

1. Move without rename → two `karte.png`; uniqueness must be computed on the vault as it will be after the run (remove the inbox source, add in-run destinations, keep the occupier). `extract_attachment_embeds` reads qualified embeds, so Tomo is not blinded. (Corrected at close-out §4: production triage does not call that extractor; `inbox-triage.py::resolve_inbox_attachments` is the reader that matters.)
2. Folder does not exist — 037 Scenario 3 says no conflict; Hashi creates the parent folder (R2 §5).
3. Outside Kado's scope or inside the inbox — undiscussed; checks are blind outside scope; inside the inbox the filed note points into the inbox and may be re-triaged. Folder string: refuse `..`, leading `/`, trailing `/`, `\`, empty segments.
4. Same basename elsewhere, folder free → no occupancy conflict, but the embed rule triggers. A computed `proposed_name` is free in the asset folder, not necessarily in `proposed_dir`.
5. Two conflicts choosing the same folder+name → `claimed` withholds the second as `collision`, but its staged body is still rewritten (`backlog.md:1956`), now newly reachable.
6. `proposed_dir` set under a non-rename remedy → ignored; `proposed_dir == dirname(destination)` → treat as null.
7. Case-only differences → occupied/contested (CON-6).
8. Also: empty typed name escapes refusal (`backlog.md:1839`) and Hashi now trims; refusal decided twice (`:1917`) — don't add a third duplicated decision; cross-run notes (`:1404`); Force Atomic (`:1149`); fixture cleanup (`:2406`); byte-identical files moved to a new folder create a second copy (037 close-out :429-442).

### 5. Backlog entries

`:1053` RESOLVED folder occupying a destination · `:1109` OPEN embed rewrite can't tell two same-basename attachments apart · `:1149` OPEN Force Atomic bypass ("no occupancy check anywhere in Pass 2") · `:1404` OPEN rename breaks earlier-filed notes · **`:1757` `_typed_name_refusal_reason` reports any unknown code as blank — prerequisite for #185** · `:1839` OPEN empty typed name · `:1894` OPEN `_walk_attachment_conflicts` fields declared in three places ("worth doing before a fourth field lands") · `:1917` OPEN refusal decided twice — revisit when the consumer is current; v4 is that moment · `:1956` OPEN run-level withhold still rewrites the embed · `:2016` CLOSED withheld attachments relay via `tomo-tmp/withheld-attachments.md` · `:2406` fixture cleanup · `:2457` no join test between `_propose_asset_name` and `check_typed_name` (promised to Hashi) · `:2500` #185 rulings.

### 6. Commitments already made on 2026-10-11

- To Hashi: padding ruling goes as a handoff (`…ten-characters…:85,178-179`); both rulings before #141 needs them, and the join test is backlogged (`…five-originals…:223-226,258-259`); #186 options and "the ADR-029 proposal is ours and not yet written" (`…nothing-of-ours…:171-180, 229-230`). **No reply to the `proposed_dir` handoff exists yet.**
- To Kokoro: a design-time handoff for #186 before implementation.

### Draft features (R4)

F1 editable folder on both surfaces (C3 v4, C4, D26) · F2 unusable folder refused, never repaired · F3 Pass 2 checks every `move_asset` against the vault (supersedes 038 F3-AC4's run-local scope) · F4 path-qualified embed only when ambiguous · F5 #185 refusal class · F6 delete depends on attachment moves (#186; C1 values and description, C10) · S1 handoffs (Kokoro design-time, Hashi v4, user docs on the two-surface difference). Won't-Have candidates: sanitising in Tomo, reverse index of earlier-filed notes, Force Atomic re-detection, folder creation by Tomo, carrying the refusal decision on the wire (unless pulled in with v4).

---

## Synthesis

**Agreements across all four passes**

- `byName` is the cheapest correct vault-wide basename check (≈ one call per distinct filed basename), with an exact casefold filter and run-adjusted counts.
- #186 option 1 needs no Hashi change; the cost is an `{origin → move_asset ids}` map and both schema descriptions of `depends_on`.
- #185 is contained, but `_typed_name_refusal_reason`'s fall-through to "blank" must be fixed first.
- The embed decision must be made before the render loop, or the rewrite moves after `build_actions`.

**Pre-existing gaps found on the way** (candidates for in-scope or backlog)

- Vendored `hashi-suggestions-wire.schema.json` still at v2 (spec 038 Phase 5 never refreshed it).
- `_check_path_shape` aborts the whole Pass 2 on a bad path instead of refusing one entry.
- An edited wire is never schema-validated.
- `build_from_wire_companion` drops the fan wire's `attachment_conflicts`.
- Kado listing errors read as "free" (fail-open).

**Conflicts requiring an owner decision** — recorded in the README's decisions log once taken.
