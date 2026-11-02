# FAQ

Short answers to the questions that come up most. For an error message or a step-by-step fix, see [Troubleshooting](troubleshooting.md). For the terms used here, see [Concepts](concepts.md).

## Basics

### Does Tomo change my notes?

No. Tomo writes only to your inbox folder and to its own instance directory. It proposes changes, and you apply them. See [What Tomo does and doesn't change](usage.md#what-tomo-does-and-doesnt-change).

### Do I need Tomo Hashi?

No. Without it, you carry out each action in the instruction set by hand in Obsidian. Hashi applies the set for you and adds an editor for suggestions. See step 4 in [Process inbox items](workflows/inbox.md).

### Why do I need Kado?

The container has no direct access to your vault files. Every read and write goes through Kado, and your API key decides which folders Tomo can reach. See [The three parts](concepts.md#the-three-parts).

## Running `/inbox`

### Why does `/inbox` say there is nothing to do?

Tomo picks up Markdown notes that carry no Tomo state. A note with `tomo.state: captured` in its frontmatter has already been through Pass 1, so never add that field by hand. An attachment on its own is not picked up either. See [/inbox Shows "Nothing to Process"](troubleshooting.md#inbox-shows-nothing-to-process).

### Why does `/inbox` run the same pass again?

The usual cause is a missing tick: Pass 2 starts only when `- [x] Approved` is set at the top of the suggestions document. Pass 2 runs again if you deleted an instruction set but kept its suggestions document, or edited that document afterwards. See [/inbox Keeps Running the Same Pass](troubleshooting.md#inbox-keeps-running-the-same-pass).

### Does ticking `Applied` affect `/inbox`?

No. Nothing in Tomo reads those boxes. They are your record, and Hashi's.

### Why did my note not update the daily note?

Its date is probably older than `daily_log.cutoff_days`, which defaults to 30. Tomo then proposes an atomic note instead, to protect old daily notes. See [Tracker / Daily-Log Update Skipped](troubleshooting.md#tracker--daily-log-update-skipped-for-an-inbox-item).

### Can I get a standalone note for a small item?

Yes. Tick **Force Atomic Note** on the item. See [Force Atomic Note](workflows/inbox.md#force-atomic-note).

### I changed my mind after Pass 2. What now?

If you have not applied yet, edit the suggestions document and run `/inbox --pass2 --force`. If you have applied and an item is still in the inbox, run `/inbox --recover`. See [Forcing a phase](workflows/inbox.md#forcing-a-phase).

### Can I delete old suggestions documents and instruction sets?

Yes, but delete both halves together. If you remove only the instruction set, the next `/inbox` builds it again. Tomo never removes them for you. See step 5 in [Process inbox items](workflows/inbox.md).

### Should I run `/clear` between passes?

It's safe after each pass, because the state lives in the vault and in `tomo-tmp/`. It frees context on long runs, but you lose the conversation about the previous results. See [`/clear` Between Passes](troubleshooting.md#operational-tip-clear-between-passes-saves-context).

### Why is an attachment still in my inbox?

Its name or target was taken or refused, so Tomo held it back, or the move failed when you applied it. Which entry fits depends on what you see:

- A `failed` action: [An Attachment Move Was Refused](troubleshooting.md#an-attachment-move-was-refused--inconsistent-state)
- "target occupied" or "Target not checked": [Pass 2 Says a Target Is Occupied or Not Checked](troubleshooting.md#pass-2-says-a-target-is-occupied-or-not-checked)
- `typed name refused` or `typed folder refused`: [I Typed a Name or Folder Pass 2 Could Not Use](troubleshooting.md#i-typed-a-name-or-folder-pass-2-could-not-use)

## Setup and maintenance

### How do I update Tomo?

Pull the repo, then run `bash scripts/update-tomo.sh --instance <name>`. See [Updating an Instance](setup.md#updating-an-instance).

### Can I run several instances?

Yes. Each one is self-contained and connects to one vault. See [Multiple instances](installation.md#multiple-instances).

### My login expired. Do I need to reinstall?

No. Start the launcher with `bash begin-tomo.sh --auth-port`, then run `claude login` inside the container. See [OAuth Re-authentication](troubleshooting.md#oauth-re-authentication).

### How do I start over?

Use `cleanup-tomo.sh`, then run the installer again. See [Starting Over After a Bad Config](troubleshooting.md#starting-over-after-a-bad-config).

### Can I back up an instance?

Only with a limit today: the backup scripts don't reach an instance in its own folder, such as `~/MiYo/Tomo/<name>/`. See [Backup and Restore](setup.md#backup-and-restore).

### The Hashi icon is green, but Claude doesn't see my note. Why?

Green means only that the connection is up. See [The Green Hashi Icon Only Means "Connected"](troubleshooting.md#the-green-hashi-icon-only-means-connected).
