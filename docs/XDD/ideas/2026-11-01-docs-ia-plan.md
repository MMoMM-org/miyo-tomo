# User Docs: Information Architecture Plan (#41)

> Status: approved, steps 1 and 2 done. Created 2026-11-01.
> Scope: the reader-facing pages in `docs/`. `docs/tomo/`, `docs/XDD/`, `docs/ai/` and `docs/evolution/` are maintainer material and stay where they are.

## Inventory

| Page | Lines | Last change | Role today |
|---|---:|---|---|
| `README.md` (root) | 225 | current | Pitch, quick start, repo structure, agents, commands |
| `docs/README.md` | 33 | 2026-06-06 | Index and quick links |
| `docs/installation.md` | 72 | 2026-06-01 | Lean install path |
| `docs/setup.md` | 282 | 2026-07-13 | Install walkthrough, launcher, updates, cleanup |
| `docs/configuration.md` | 253 | 2026-06-23 | Config model and settings reference |
| `docs/usage.md` | 378 | 2026-10-24 | Sessions; one 275-line "Common workflows" section; command reference |
| `docs/troubleshooting.md` | 515 | 2026-10-24 | Errors by area; 234 lines are Inbox Processing |
| `docs/template-syntax.md` | 273 | 2026-07-12 | Template reference |
| `docs/instructions-json.md` | 1498 | 2026-10-29 | Hashi consumer contract, not a reader page |

## Gaps found

Measured by searching the five main pages (`usage`, `setup`, `configuration`, `troubleshooting`, `installation`). A hit shows that a word appears, not that the topic is explained, so "covered" below still needs a reader test.

| Topic | State |
|---|---|
| `/garden-audit` | Only the root README names the command. `usage.md` mentions "garden" but not the command |
| Force Atomic Note | Not mentioned on any page |
| Backup and restore | Not mentioned, although `scripts/` ships them |
| Deactivating a tracker (`active: false`) | Not mentioned, shipped in #38 |
| `/moc-propose` | In `usage.md` only; no troubleshooting entry |
| `@` file picker | In the root README and `troubleshooting.md` only; no usage entry |
| Concepts primer | Missing: two passes, the three components, what a MOC proposal or instruction set is |
| FAQ | Missing |
| Screenshots | None, no image convention |

`configuration.md` is the page most likely to be stale: it last changed on 2026-06-23, before the tracker work and spec 042.

## Proposed tree

```text
docs/
├── README.md                 index by reader journey
├── concepts.md               NEW  two passes, Tomo/Kado/Hashi, the documents Tomo writes
├── installation.md           keep
├── setup.md                  keep; backup and restore added
├── configuration.md          keep; refreshed
├── usage.md                  session start, what Tomo changes, launcher and command reference
├── workflows/                NEW  one page per job, split out of usage.md
│   ├── inbox.md              Pass 1, Pass 2, Force Atomic Note, daily log, trackers
│   ├── explore-vault.md
│   ├── moc-propose.md
│   ├── garden-audit.md       NEW content
│   └── hashi-hooks.md
├── troubleshooting.md        keep as is; split later only if a reader test asks for it
├── faq.md                    NEW
├── template-syntax.md        keep
├── instructions-json.md      keep; linked as a contract, not from the journey
└── images/                   NEW  convention: <page>-<subject>.png, written alt text
```

## Migration order

Each step is one PR.

1. `concepts.md` and the `docs/README.md` index. Everything else links here.
2. Split `usage.md` into `workflows/`, moving text only. Check anchors: `docs/README.md` links to `usage.md#process-inbox-items` and `usage.md#common-workflows`, and tests or `/tomo-help` may point at these pages.
3. Fill the gaps: `/garden-audit`, Force Atomic Note, backup and restore, tracker deactivation.
4. Refresh `configuration.md`, using `doc-product extract` where the schemas allow it.
5. `faq.md`, from recurring entries in `troubleshooting.md`.
6. Reader test with `doc-product review`.
7. Screenshots. These need a running instance and Obsidian.

## Owner decisions (2026-11-01)

1. `workflows/` is a subfolder.
2. `troubleshooting.md` stays one page for now.
3. English only.
