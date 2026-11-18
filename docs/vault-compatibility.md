# Vault Compatibility: Templates and Plugins

Tomo writes new files into your inbox through Kado: suggestion and instruction documents, review documents, instruction sets, and new notes built from your templates. Obsidian and its plugins react to every new or changed file. Most plugins never notice Tomo's files. A few act on them in ways that break a delivery or change a note before Hashi applies it.

This page lists the interactions that are known, what you see when they happen, and how to set up your templates and plugins so they do not happen.

- [Templates without a complete frontmatter block](#templates-without-a-complete-frontmatter-block)
- [Templater runs on new files](#templater-runs-on-new-files)
- [Plugins that stamp open notes](#plugins-that-stamp-open-notes)

## Templates without a complete frontmatter block

**What you see:** a new note carries two frontmatter blocks, or keys such as `title`, `tags` or `banner` appear as plain text below the frontmatter.

**Why:** Tomo adds its `tomo:` block to the note's leading `---` block. It never runs Templater. If your template only gets its opening `---` from a Templater include (for example `<% tp.file.include("[[x_frontmatter]]") %>`), Tomo sees no frontmatter at the first line. It then puts its own block in front, and the rest becomes note body.

**What to do:** start the template with a literal `---` and close the block with `---`, keeping Templater expressions inside it as values. The rules and examples are in [Template Syntax → Frontmatter: a complete `---` block is required](template-syntax.md#frontmatter-a-complete-----block-is-required).

Your template may need its include for other notes. In that case, keep it and create a Tomo variant next to it: the same name with `_tomo` before `.md` (`t_month_privat.md` → `t_month_privat_tomo.md`), with a complete frontmatter block. The `/review` setup asks about this when it finds a template without a frontmatter block at its first line:
- **Use it as it is:** keeps the template, and the note gets the second block.
- **I'll create a Tomo variant:** stops the setup so you can create the variant, then choose it in `/review setup`.

## Templater runs on new files

**What you see:**

- A new note that Tomo delivered is already rendered in the inbox. It has a creation-time `UUID`, filled dates, and a second frontmatter block.
- Or it has already moved to its calendar folder before Hashi applied the set, and Hashi reports `skipped-already`.
- Or **another file** moved there: the instruction set's readable `…_instructions.md` sits at the path of the new note, for example `Calendar/304 Quarterly/2026-Q1.md`. A retry of the delivery then finds a "target note" that is not yours.

**Why:** with Templater's **Trigger Templater on new file creation** turned on, Templater (2.27) runs the Templater code in **every new Markdown file that already has content**, not only in files created from a folder template. A new note that Tomo builds from your template still holds your raw Templater code, so Templater runs it about a third of a second after Kado writes it. A template that calls `tp.file.move(...)` moves the file there and then.

Tomo writes the readable instructions half a second after the note. Templater keeps track of which file it is working on in one shared setting for all its runs. When a long template is still running as the next file arrives, its `tp.file.move` can move that next file instead of the note.

**What to do:** stop Templater from rendering Tomo's new notes on creation. They are meant to be rendered after the move, when you run `Templater: Replace Templates in Active File`. Choose one of the two options:

1. **A guard in the templates Tomo delivers (recommended).** Put this check at the top of the first `<%* … %>` block of each template that Tomo uses for new notes, for example your weekly, monthly and quarterly templates:

   ```js
   <%*
   if (tp.file.folder(true).startsWith("100 Inbox")) {
     throw new Error("Tomo: do not render in the inbox");
   }
   // … the rest of your template
   ```

   Use your own inbox folder name. When Templater runs the template on creation in the inbox, the error makes it stop and leave the file as Tomo wrote it. Obsidian shows Templater's "Template parsing error" notice once; that notice is expected.

   After Hashi moves the note, the check no longer applies, and `Replace Templates in Active File` renders it as usual. Skipping only the `tp.file.move` is not enough: Templater replaces the whole file with its rendered result, so nothing would be left to render after the move.
2. **Templater's setting "Only trigger for files matching a template rule".** With this on, Templater no longer runs code in new files that already have content. Folder templates for new empty files keep working. The setting applies to the whole vault: notes that another plugin creates with Templater code in them are no longer rendered on creation either.

To check: deliver a review that creates a new note. The note stays in the inbox with its `<% … %>` code unchanged, and nothing appears in the calendar folder until Hashi applies the set.

## Plugins that stamp open notes

**What you see:** a delivery stops with `doc-changed` and reason `open-unsaved`, or another Tomo write is refused because the note is "open in the editor with unsaved changes".

**Why:** plugins such as **update-time-on-edit** or the **Linter** write a timestamp (for example `Updated:`) into a note that is open in the editor, without saving it. Kado refuses to write a note that has unsaved changes in the editor, so it never overwrites what you typed. A stamp counts as such a change, even when you typed nothing.

**What to do:**

- Save (Cmd+S) or close the note, then choose **Retry**. A retried delivery writes only the steps that are still open; it does not plan again.
- To avoid it, exclude your inbox folder in the plugin's settings. For update-time-on-edit, add the inbox folder to its ignored folders. Then the stamp is not written into Tomo's documents while they are open.

## Related

- [Template Syntax](template-syntax.md): tokens, Templater coexistence, the frontmatter rules
- [Troubleshooting](troubleshooting.md): other errors and how to recover
