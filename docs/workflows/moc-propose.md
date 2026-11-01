# How Tomo proposes new MOCs (and why cache freshness matters)

Tomo suggests creating a new Map of Content (MOC) when a topic has accumulated enough notes without one (LYT's "Mental Squeeze Point"). There are **two paths**, and they differ in *when* they run and *how fresh* their data is:

- **Passive — automatically during `/inbox`.** While analysing each inbox item, Tomo proposes a new MOC in two cases: (a) the item's topic doesn't match any existing MOC, so a thematic MOC is suggested for it; or (b) the item's topic matches a **placeholder MOC** you already linked but haven't created — a dead `[[… MOC]]` wikilink sitting in one of your MOC bodies. Both run against the discovery cache from your **last `/explore-vault`** — no live vault scan at inbox time.
- **Active — on demand with `/moc-propose`.** This command **scans the vault live** (whole-vault, or scoped with `tag:` / `folder:` / `class:` / `title:` / free text) and writes a reviewable MOC proposal-doc to your inbox. Use it when you want an up-to-the-minute answer independent of cache age.

**Practical consequence — the passive `/inbox` detection is only as current as your last `/explore-vault`:**

- A MOC or placeholder link you added since the last explore **won't be matched during `/inbox` until you re-run `/explore-vault`**.
- Conversely, notes you've *filed* under a MOC since the last explore may still look unparented in a stale cache, so a `/moc-propose` scan can mention notes you've already organised.

So: **re-run `/explore-vault` after you've added or reorganised notes or MOCs** to refresh what `/inbox` can detect — or reach for **`/moc-propose`** when you want a live scan right now. (A cache-staleness warning in `/inbox` is planned — backlog F-21.)

## Work through a proposal

`/moc-propose` writes a document with `_moc-proposal` in its name to your inbox. Each proposed MOC is its own section.

1. Tick `Accept` on each section you want. A section you leave unticked counts as rejected.
2. If a section extends an existing MOC, also tick the entries under **Missing members** that you want linked. With none ticked, that section is skipped.
3. Run `/inbox`. Pass 2 turns the accepted sections into an instruction set.
4. Apply the instruction set like any other, see [Process inbox items](inbox.md).

## Excluding notes or MOCs from proposals

You can tell Tomo to leave specific notes or MOCs out of its MOC suggestions by tagging them. Both tags go in the note's **frontmatter** `tags:` list:

- **`MiYo/Tomo/exclude/note`** — the note is never offered as a candidate for a new MOC (it's dropped from the `/moc-propose` scan). Use it for notes that are intentionally standalone and shouldn't be clustered.
- **`MiYo/Tomo/exclude/moc`** — the MOC is never offered as a link target for inbox items (`/inbox` leaves it out of the MOCs it considers), and it is skipped by the "missing uplink" check (`/moc-propose check:moc-uplinks`). Use it for top-level maps (e.g. a root index) that correctly have no parent and should not collect notes. The MOC stays in the cache, and other workflows (`/moc-propose`, the garden audit, `/explore-vault`) still read it. To link inbox notes to it again, remove the tag and re-run `/explore-vault`.

```yaml
---
tags: [MiYo/Tomo/exclude/note]
---
```

> **Frontmatter only.** These tags are read from the YAML frontmatter `tags:` list. An **inline** `#MiYo/Tomo/exclude/note` written in the note body is **not** recognised and the exclusion is silently ignored. (This differs from MOC discovery, which accepts inline tags — a known inconsistency.) After adding or removing an exclude tag, re-run **`/explore-vault`** so the rebuilt cache picks it up.
