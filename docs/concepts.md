# Concepts

The ideas behind Tomo, in one page. Read this first if the other pages use a word you don't know.

## The three parts

| Part | What it is | What it does |
|---|---|---|
| **Tomo** | Claude Code workflows in a Docker container | Reads your inbox, proposes what should happen to each item, and prepares the result |
| **[Kado](https://github.com/MMoMM-org/miyo-kado)** | An Obsidian plugin | The gateway. Every vault read and write by Tomo goes through it, and you decide what it allows |
| **[Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi)** | An Obsidian plugin | Optional. Applies an instruction set for you and offers an editor for suggestions |

The container has no direct access to your vault files. Tomo needs Kado to reach them.

## Tomo proposes, you decide

Tomo writes only to your inbox folder and to its own instance directory. It never changes a note elsewhere in the vault. See [What Tomo does and doesn't change](usage.md#what-tomo-does-and-doesnt-change) for the exact list.

So a change to your notes always takes two steps: Tomo proposes it, and you apply it.

## The two passes

`/inbox` works in two passes. You run the same command each time, and Tomo works out what comes next.

1. **Pass 1, suggestions.** Tomo analyses each new inbox item and writes a suggestions document. Nothing is moved.
2. **You review.** You change what you want in the document, tick your choices, and tick `Approved` at the top.
3. **Pass 2, instructions.** Tomo turns the approved suggestions into an instruction set and prepares any new notes in the inbox.
4. **You apply.** You carry out the actions by hand in Obsidian, or let Tomo Hashi do it.

After that, `/inbox` reports `idle` for this work. See [Process inbox items](workflows/inbox.md) for the full loop.

## The documents Tomo writes

| Document | Where | What it is for |
|---|---|---|
| **Suggestions document** | `<inbox>/<YYYY-MM-DD_HHMM>_suggestions.md` | Your review surface for Pass 1 |
| **Instruction set** | `<inbox>/<YYYY-MM-DD_HHMM>_instructions.md` | The actions to apply, each with an `Applied` checkbox |
| **`instructions.json`** | Next to the instruction set | The same actions for Tomo Hashi. The format is in the [contract](instructions-json.md) |

These documents stay in your inbox until you remove them. If you do, remove a suggestions document together with its instruction set. See step 5 in [Process inbox items](workflows/inbox.md) for why.

## Terms

- **Inbox.** The vault folder Tomo processes, set during install.
- **MOC (Map of Content).** A note that links related notes together. Tomo proposes links to existing MOCs and can propose new ones.
- **Tracker.** A field you log in daily notes, such as `Sport` or `Sleep`. Tomo proposes values from your inbox content.
- **Instance.** One installed Tomo with its own config, connected to one vault. You can run several.
- **Framework profile.** The defaults for a way of organising a vault. `miyo` and `lyt` ship with Tomo.
- **Discovery cache.** What `/explore-vault` learned about your vault. It gives hints and never overrides your config.

## How config is layered

Tomo combines four layers, and your config wins over the profile:

1. Universal PKM concepts, built in.
2. The framework profile.
3. Your config, `vault-config.yaml`.
4. The discovery cache, as hints only.

See [Configuration](configuration.md) for what each file holds.
