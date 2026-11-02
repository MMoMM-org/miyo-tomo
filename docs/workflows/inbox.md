# Process inbox items

This is the day-to-day loop. When new items have landed in your inbox folder (voice memos, web clips, quick captures, anything ready for triage), run:

```
/inbox
```

`/inbox` runs the **2-pass workflow**:

1. **Pass 1 — Suggestions.** Analysts read each captured item and propose what should happen to it: classification, tags, MOC links, target folder. The result is a markdown suggestions document at `<inbox>/<YYYY-MM-DD_HHMM>_suggestions.md`. Nothing is moved or rewritten in the vault yet.
2. **You review and approve.** Open the suggestions doc. Each action has a tri-state checkbox (Approve / Skip / Delete source); flip the boxes you want, then check the top-level `[x] Approved` header when ready.
3. **Pass 2 — Instructions.** Tomo expands the approved suggestions into a concrete instruction set with file-level actions (write_file, link, tag, archive). It runs automatically when `/inbox` next sees an approved suggestions doc — or force it with `/inbox --pass2`.
4. **Apply the actions.** Tomo doesn't write outside the inbox; this step is yours. Two paths:
    - **Manually**: open the instruction set in Obsidian, perform each action yourself (write note, add link, set tag), tick `[x] Applied` per action.
    - **Via Tomo Hashi**: run the instruction-set executor in [Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi) on the file. Choose preview mode — `Preview on` (approve each action), `Preview off` (visible apply), or `No confirmation` (background).
5. **Clean up when you're ready — nothing does it for you.** An applied instruction set and the suggestions doc it came from **stay in your inbox**, and so do abandoned ones you never approved. There is no automatic removal, and nothing re-processes them in the meantime: re-running `/inbox` reports `idle` with the reason *"All approved items already covered by existing instructions"*.

    **One thing to know if you do delete them: delete the pair, not just one half.** The leftover instruction set is what records that the work is done. Remove it while leaving its approved suggestions doc behind, and the next `/inbox` run sees an approved doc nothing covers — and builds the instruction set again. Deleting both, or neither, is always safe.

> **Two surfaces, one rule.** You can review and edit a run two ways: directly
> in the suggestions document, or in [Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi)'s
> structured Suggestions Editor. Both work on the same run. Once you've saved
> that run in the editor, the editor's values are what Pass 2 uses for the
> whole run — not the markdown, even for fields you left untouched in the
> editor. Don't go back and edit the markdown for that run afterwards; the
> edit is dropped, not merged in. If a run produced a second suggestions
> document, Tomo needs both saved in the editor — otherwise it uses the
> markdown for the whole run instead, and Pass 2 says so when that happens.
> If you haven't opened the editor for a run at all, the suggestions document
> is what counts, which is why editing it directly and running `/inbox
> --pass2 --force` works the way the rest of this page describes.

`/inbox` is auto-resumable: there is no state you have to track. Each run it re-reads the inbox from the vault, works out what changed, and does the next step — run Pass 1, run Pass 2, transcribe audio, or report idle. You just keep running `/inbox`.

## When an attachment's name is already taken

If an inbox note embeds a file — a scan, a photo, a PDF — Tomo files that file
into your attachments folder alongside the note. When a file of that name is
**already there**, Tomo does not guess. Pass 1 adds an **Attachment Conflicts**
section to the suggestions document, above the suggestions, and you decide.

Each entry names the file, the destination that is occupied, and which of your
notes embeds it. It also tells you whether the two files are actually the same:

| What it says | What it means |
|---|---|
| A different file already holds this name | Two unrelated files, one name. Renaming keeps both. |
| This is the same file already in the vault | You already have it. Renaming would leave you with two copies. |
| The files could not be compared | Tomo could not read one of them — look before you accept the rename. |

Three remedies, one per entry. **Rename is pre-ticked** — it is the only one
that files the attachment successfully in every case:

- **Rename** — files it under a computed free name (`karte (2).png`), and
  rewrites the embed in your note to match, so the note keeps working. Under
  the Rename line sits a **Folder** line, pre-filled with the folder the
  occupied name lives in. You can change either one before you apply:
    - **The name is yours to change**: type over the text between the
      backticks on the Rename line. Tomo files it under what you typed instead
      of the computed one. If Pass 1 couldn't find a free name at all, the
      backticks start out **empty** — type a name there yourself.
    - **The folder is yours to change**: type over the text between the
      backticks on the Folder line, for example to file the map into your maps
      folder where nothing is called `karte.png`. A folder that doesn't exist
      yet is fine; Pass 2 says it "will be created on apply". Leave the line
      alone and the folder stays as it is. The Folder line only counts while
      Rename is ticked.
    - A folder never goes into the Rename line. Typing `maps/karte.png` there
      is refused as a path — use the Folder line.
  (You can set the name and folder in Tomo Hashi's Suggestions Editor instead
  of the markdown, too — see "Two surfaces, one rule" above: if this run
  produced a second suggestions document, save that one in the editor too, or
  your typed values are dropped in favour of the markdown. In the editor you
  pick the folder from your existing folders — the inbox is not offered — so a
  folder that does not exist yet, or one Pass 2 refuses, can only come from
  the Folder line in the markdown.) [#185](https://github.com/MMoMM-org/miyo-tomo/issues/185)
- **Keep in inbox** — leaves the file where it is. The note is still filed; only
  the file stays behind.
- **Ignore** — sends the move anyway. It will be refused unless you free the
  name yourself before applying.

> **When the comparison says it is the same file**, the pre-ticked Rename gives
> you a second copy of something you already have. Tick **Keep in inbox**
> instead if you would rather not file it at all.

**Keep in inbox or Ignore still file the note.** They hold back the *file*,
not the note — so the filed note will point at a file that is still sitting in
your inbox. That reference still works; it just reaches backwards. Tomo says
so in the instruction set, both on the action and in its summary. **A typed
name that Pass 2 refuses is the one exception** — it holds back the note as
well; see below.

**A typed name or folder is checked, never corrected.** Tomo doesn't guess at
what you meant by swapping out a character — it either files exactly what you
typed, or refuses it outright. (Tomo Hashi's editor is different: when you
type something there that the markdown would refuse, the editor cleans the
name up for you, visibly, before it saves. Tomo itself never does.)

A typed **name** is refused when it is:

- **blank** — empty, or nothing but whitespace,
- **a path, not a plain filename** — it contains `/`,
- **padded** — it starts or ends with a space or other whitespace such as a tab,
- **unsafe** — it contains a control character, `{{` or `<%`,
- **carrying a character your vault forbids** — any of `\` `:` `*` `?` `"` `<` `>` `|`,
- **carrying a character that breaks links** — any of `#` `^` `[` `]`.

A typed **folder** is refused when it is:

- **blank**, or the line is damaged so it no longer holds exactly one folder in
  backticks,
- **leaving the vault** — it starts with `/`, `~` or `./`, uses `\`, starts
  with a drive letter such as `C:`, or contains a `.` or `..` segment,
- **holding an empty part** — it contains `//`,
- **padded** — a part of the path starts or ends with a space or other
  whitespace such as a tab,
- **ending in `/`**,
- **unsafe** — a control character, `{{` or `<%`,
- **carrying a forbidden character** — any of `:` `*` `?` `"` `<` `>` `|`,
- **carrying a link-breaking character** — any of `#` `^` `[` `]`,
- **the inbox itself, or inside it** — the next run would read the file as
  inbox material again. Upper/lower case and Unicode form are ignored in this
  check, so `100 inbox/x` is refused too when your inbox is `100 Inbox`.

"That name is already taken" is deliberately not one of these reasons — Tomo
checks that separately, against the vault, and reports it as described next.

**When a typed name or folder is refused, the attachment isn't filed — and
neither is any note in this run that embeds it.** Both stay behind in your
inbox: the instruction set lists them under "Attachments still in the inbox",
and Pass 2 reports them in your terminal too. To fix it, correct the name or
folder in the suggestions document, then:

- **before you apply:** run `/inbox --pass2 --force`;
- **after you applied:** run `/inbox --recover`. The attachment and its notes
  are still in the inbox, and the re-run proposes the default name or folder
  again. It offers your choice again only if the target is still taken; if the
  target is free, the attachment is simply filed there.

**What Pass 2 tells you about the target.** Pass 2 looks at the vault for the
final path before it writes the move. An occupied target is reported under
"Attachments still in the inbox", because no move is written for it; the other
findings sit in the block of the move that is written:

- **occupied** — something is already at that path (a file, a folder, or a
  file that differs only in upper/lower case). The attachment is not filed over
  it and stays in the inbox together with the note. Free the target in the
  vault, or pick another name or folder, and run `/inbox --pass2 --force`
  before you apply (`/inbox --recover` after).
- **not checked** — the vault did not answer for that path, so Tomo cannot say
  whether it is free. The move is still written, and you can apply it as it is;
  if it fails, the attachment and its note stay in the inbox. To be sure
  first, look in the vault for the path named in the message.
- **will be created on apply** — the folder you typed on the Folder line
  doesn't exist yet. Nothing to do.
- **Embed written with path** — another file in your vault has the same name,
  so the note links to the file by its full path instead of the bare name. The
  link works the same; the longer form is what keeps it pointing at the right
  file. [#185](https://github.com/MMoMM-org/miyo-tomo/issues/185)

To change your mind after Pass 2 has run but before you apply: tick a different
remedy in the suggestions document, then run `/inbox --pass2 --force`.

## Tagged notes from MiYo tools

If you use [Tomo Tsukai](https://github.com/MMoMM-org/miyo-tomo-tsukai) or another MiYo tool that tags inbox notes with `MiYo/<Feature>/…`, and you have a matching handler registered, `/inbox` groups all such captures for the same target into **one** merged suggestion rather than surfacing them individually. You review and approve it the same way you would any other suggestion. No special command is needed — the grouping happens automatically during Pass 1.

To register or edit a handler, use **`/tomo-tag-handler-wizard`**. See [Configuration → Tag-handler framework](../configuration.md#configtag-handlers--tag-handler-framework) for the full reference.

## Force Atomic Note

Tomo doesn't turn every item into a note. Small items often become a daily-log entry or a suggestion with no note attached. If you want a standalone note anyway, tick **Force Atomic Note** on that item. The box appears on items Tomo chose not to promote and under each log entry.

1. Tick **Force Atomic Note** and `Approved` in the suggestions document, then run `/inbox`.
2. Tomo analyses those items in full and writes a second document, `<inbox>/<YYYY-MM-DD_HHMM>_suggestions-fan.md`.
3. Review that document, tick its `Approved` box, and run `/inbox` again.

Pass 2 then builds one instruction set from both documents.

## What a re-run redoes (and what it leaves alone)

Each `/inbox` does **one step**, and prefers finishing in-flight work over new intake. The common situations:

- **New note dropped** → Pass 1 suggests it.
- **You approved a suggestions doc** → Pass 2 synthesises its instructions.
- **You re-run after applying** → Tomo sees the work is already done (an instruction set covers it, unchanged) and stays **idle** — it will *not* re-render a duplicate.
- **You edited an approved suggestions doc** after its instructions were generated → Tomo detects the change and re-synthesises just that one.
- **Approved work pending *and* a new note** → Pass 2 runs first (finish the batch); the new note is suggested on your next run. Want to intake the new note now instead? `/inbox --pass1`.

Tomo only treats a doc as "changed" when its **body** changes (your edits) — its own bookkeeping (marking a doc approved) never counts as a change.

## Forcing a phase

| Command | Does |
|---------|------|
| `/inbox --pass1` | Suggest new sources now (even if Pass 2 work is pending) |
| `/inbox --pass2` | Synthesise only what's changed or not yet done |
| `/inbox --pass2 --force` | Re-synthesise **all** approved docs, ignoring "already done" |
| `/inbox --pass1 --force` | Re-suggest **everything**, including already-captured items |
| `/inbox --force` | Full rebuild — re-suggest, then re-synthesise everything |

`--force` is a modifier you add to a phase (or use alone for a full rebuild). For the decision logic in detail, see [Inbox Change Detection & Pass Routing](../XDD/reference/tier-2/workflows/inbox-change-detection.md) (with flowchart).
