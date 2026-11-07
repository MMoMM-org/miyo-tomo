# Research: 044-note-from-template

> Findings from three read-only research agents on 2026-11-04 (technical, integration and security, requirements and UX). Each line cites the evidence it rests on. Nothing here was run against live Kado or `tomo-instance`.

## Hashi and the Wire

- `move_note` requires `id`, `action`, `source`, `destination`, `title`. `source_inbox_item` is optional and Hashi never reads it (`tomo/schemas/hashi-instructions.schema.json:88-107`).
- `delete_source` requires `id`, `action`, `source_path`, `reason`, `depends_on`. An absent `depends_on` is rejected; `[]` means no partner (`:230-247`).
- Tomo's schema copy is byte-identical to `Hashi/src/schema/instructions.schema.json`. `schema_version` comes from `lib.wire_version.wire_schema_version("instructions.schema.json")`, never hard-coded.
- Hashi's `move_note` renames, then strips the `tomo:` block (`Hashi/src/actions/moveNote.ts:41-113`). Both source and destination present is a failure.
- Hashi withholds a delete until every `depends_on` id is applied (`Hashi/src/executor/InstructionExecutor.ts:405-445`).
- Pass 2 already pairs a `move_note` with a `delete_source` of a different inbox note through `depends_on` (`tomo/scripts/lib/render_source_actions.py:53-99`, site 3). `/note` uses the same shape. No wire change, no schema bump, no blocking handoff.
- Hashi lists only the flat children of the inbox folder and keeps names ending `_instructions.json`; the peer is `<stem>_instructions.md` (`Hashi/src/executor/planner.ts:100-155`).

## Kado

- Listing and reading need read permission only (`Kado/src/mcp/tools.ts:802`, `Kado/src/obsidian/search-adapter.ts:286,340`).
- An empty search can hide a denial (`Kado/src/obsidian/search-adapter.ts:91-97`). A message must never say a template does not exist.
- Tomo documents template-folder read access only as an expectation (`docs/troubleshooting.md:44`). Whether the real key has it is unverified.
- `vault-explorer` reads only mapped templates for token cost and privacy (`tomo/dot_claude/agents/vault-explorer.md:117-121`). The only code that lists the folder is the unknown-type branch of `inbox-author` (`SKILL.md:44-48`).
- `KadoClient` retries 429 and 503 with backoff (`tomo/scripts/lib/kado_client.py:33-37`). A run needs about 12 to 14 calls, so no call cap is needed.

## Config and Writer

- `templates:` has `base_path`, `mapping` and a commented `custom_tokens` (`tomo/config/vault-example.yaml:120-134`). No schema covers it.
- `vault-config-writer.py` only replaces column-0 blocks (`replace_top_level_section`, `:157-200`). Setting one key inside `templates:` byte-identically needs a new in-block helper, plus `tomo/schemas/vault-config-templates.schema.json`.
- `read-config-field.py --field` on a missing key without `--default` exits 1; `--fields ... --format json` omits it and exits 0 (`:63-78`).

## Template Parsing

- Tomo tokens: `\\?\{\{([a-z_][a-z0-9_]*)\}\}` (`tomo/scripts/token-render.py:267`). Fenced code and `<%...%>` are protected (`:270-315`).
- `template-doctor.py` has `_leading_block_lines` and `_extract_tokens` (`:154-182`); modes `audit`, `dry-render`, `scaffold`. Shared helpers belong in `tomo/scripts/lib/`, because hyphenated scripts cannot be imported.
- No heading extractor exists.

## Delivery

- `kado-write-file.py` exit codes: 0 ok, 1 Kado error, 2 I/O, 3 exists with `EXISTS:<vault-path>`, 4 conflict.
- `upload-rendered.py` has no overwrite guard and is not used.
- `validate_destinations(actions, folder_listing)` drops both claimants of a clash and the paired delete (`lib/render_withhold.py:280`). `withdraw_unjustified_deletes` is the delete guard (`:431`). Both drop silently, so `/note` must report a withdrawn action as a failure.
- `build_tomo_block("rendered-note", "pending-move", run_id)` validates against `doc-frontmatter.schema.json`; `merge_tomo_block_into_markdown` needs a leading fence (`lib/doc_frontmatter.py:87,172`).
- `render_instructions_md(actions, metadata, cfg)` needs `generated` and `run_id` in `metadata` (`lib/render_md.py:921`).
- Pass 2 instruction stems are `%Y-%m-%d_%H%M` (`instruction-render.py:474`).

## Source Marking and Triage

- `mark-captured.py` takes `--state <inbox-state.jsonl>` and `--run-id`, not a bare path (`:107-112`). `/note` either writes a one-line state file or performs the same `read_frontmatter` + `write_frontmatter(mode="merge")` pair itself.
- Triage skips `captured` and `pending-move` as fresh (`inbox-triage.py:436-455`). `--recover` treats captured as fresh (`:1603-1655`).
- A captured source with no downstream doc may raise a triage warning (`:1495-1531`). Unverified.

## Instance and Security

- Backup stages all of `config/` (`scripts/backup-tomo.sh:175`), restore copies it back (`scripts/restore-tomo.sh:193-197`).
- `update-tomo.sh` ships commands and skills by glob once they carry `# version:`; `add_seed` exists (`:360-367`).
- `settings.json` already allows `Edit(config/*)`, `Edit(tomo-tmp/*)` and `Bash(python3 scripts/*.py*)`. No change, so no eval gate.
- Constitution L2: scripts and logs carry metadata only. Note text, answers and source text never reach stdout, stderr, the cost log or close-out evidence.
