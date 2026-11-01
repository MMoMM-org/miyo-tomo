# Audit your vault

`/garden-audit` scans the whole vault for structural problems and writes a review report to your inbox. It changes no note. You tick the fixes you want and apply them through `/inbox`, the same way as any other proposal.

```
/garden-audit            # works out what to do next
/garden-audit audit      # force a fresh scan
/garden-audit configure  # manage exclusions
/garden-audit suggest    # find targets for the findings you ticked
/garden-audit stats      # read-only overview in chat, nothing is written
```

The bare command picks the mode for you. The first time, it starts the exclusion wizard. If your newest report has ticked **Suggest targets** boxes that haven't run yet, it runs `suggest`. Otherwise it runs a fresh scan.

## What it checks

| Check | Group | What it finds |
|---|---|---|
| `broken_up` | Integrity | A note's `up` link points at something that doesn't resolve |
| `dead_link` | Integrity | A wikilink points at a note that doesn't exist |
| `unparented` | Structure | A note has no parent |
| `orphan` | Structure | A note has no links to or from it |
| `duplicate_stem` | Advisory | Two notes share a filename |
| `stale_moc` | Advisory | A MOC hasn't changed for a long time, 90 days by default |
| `parent_not_moc` | Advisory | A note's parent exists but isn't tagged as a MOC |

Advisory findings are for reading. They have no fix to tick.

## Work through a report

1. Run `/garden-audit`. It writes `<inbox>/<YYYY-MM-DD_HHMM>_garden-audit.md`, plus a `.json` file of the same name that Tomo and Tomo Hashi use.
2. Open the report. Findings are sorted by severity.
3. Tick **Apply** on each fix you want. Where a finding offers **Replace with:** or **Repoint to:**, fill it in.
4. Not sure what to link to? Tick **Suggest targets** on the finding and run `/garden-audit` again. Tomo adds a list of candidates to that finding and re-uploads the report. It doesn't scan again.
5. Tick `Approved` at the top of the report, then run `/inbox`.
6. `/inbox` turns the ticked fixes into an instruction set. Apply it like any other, see [Process inbox items](inbox.md).

Nothing happens until `Approved` is ticked. Approving also pauses the report's advisory findings, 30 days by default. They come back if they are still unresolved.

## Exclude parts of your vault

Some folders are meant to look unusual. Daily notes, for example, rarely have a parent. `/garden-audit configure` shows where findings cluster and asks what to do with each cluster:

- **Exclude permanently**, for all checks or only some.
- **Push back temporarily**, for example for 90 days while you tidy up a folder.
- **Keep it in the audit.**

Your choices go to `config/garden-audit-exclusions.yaml` in the instance, not through `/inbox`. To check what is open, excluded or pushed back, run `/garden-audit stats`.
