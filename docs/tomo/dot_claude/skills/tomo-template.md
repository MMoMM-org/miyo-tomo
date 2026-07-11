# WHY: tomo-template (skill)

> Rationale for `tomo/dot_claude/skills/tomo-template/SKILL.md` and its backend
> `tomo/scripts/template-doctor.py`. Charter: miyo-tomo#138.

## Why This Skill Exists — the delegated-fence bug

WHY: During ADR-026 (Hashi Suggestions Editor) live testing, a rendered MOC came out with its
`title`/`tags`/`aliases`/`banner` sitting in the note **body** instead of the frontmatter. Root
cause: the vault template `t_moc_tomo` opened with a Templater include
(`<%await tp.file.include("[[x_frontmatter]]")-%>` as line 1) that supplies the `---` fence only
at Templater-time. Tomo renders **statically** — it never runs Templater — so at stamp time the
template had no literal leading `---`. `lib.doc_frontmatter.merge_tomo_block_into_markdown` then
prepends its own `---\ntomo:…\n---` block, and everything below (the include, `title:`, `tags:`)
becomes body. Users had no way to catch this class of error before a broken note landed in the
inbox. This skill is the interactive front door that audits/converts/validates/scaffolds
templates so the failure is caught (or prevented) at authoring time.

Note: the **repo-source** `tomo/config/templates/t_moc_tomo.md` already opens with a literal
`---` fence and is clean. The bug lived only in the **vault copy** (the real Templater version).
Vault templates are install-once (seeded on first-session discovery, then never overwritten by
`update-tomo`), so a repo fix does not reach an already-installed vault — another reason a
user-facing audit/convert path is needed rather than just fixing the seed.

## Why a Deterministic Backend Script, Not LLM Inspection

WHY: The whole point of the skill is to catch a frontmatter defect that is easy to misjudge by
reading. "Does this template render clean?" depends on a byte-level structural fact (is line 1 a
literal `---`?) and on what `merge_tomo_block_into_markdown` does with it. Per the repo's
deterministic-rendering-over-LLM-assembly principle, that verdict belongs in code. `audit` and
`validate` run `template-doctor.py`; the SKILL forbids eyeballing frontmatter correctness. The
constitution's L1 test rule (happy + failure on every FS-reading path) is satisfied by
`tests/test_template_doctor.py` — including a regression guard that the shipped `t_note_tomo`
renders clean and that a delegated-fence template FAILS `no_stranded_frontmatter`.

## Why `validate` Does a Real Dry-Render (not just a static check)

WHY: The strand only becomes visible **after** token resolution + tomo-block stamping. `validate`
therefore runs the actual path: `token-render.py` resolves `{{tokens}}` with representative
sample values, then `merge_tomo_block_into_markdown` stamps a sample block, then the doctor
checks that the leading frontmatter — with the `tomo:` block removed — is still non-empty (i.e.
the template's own keys survived in the frontmatter). This reproduces the production failure
deterministically and yields a `rendered_preview` the user can see, rather than a heuristic
guess. `audit` is the fast static subset for when a full render is not wanted.

## Why `scaffold` Lives in the Script, Not a `reference/` File

WHY: `update-tomo.sh` syncs only each skill's `SKILL.md` to the instance — not `reference/`
subdirectories. `docs/` and `tomo/config/templates/` are also invisible from inside the Tomo
container. So the skill cannot Read reference templates at runtime. The only container-visible,
synced home for scaffold content is a **script** under `scripts/`. Hence `scaffold` is a
subcommand of `template-doctor.py` (deterministic, synced, testable, single source of truth)
rather than a doc the skill reads.

## Why Scaffold Templates Are Minimal, Not Copies of the config/templates Seeds

WHY: The rich seed templates (`t_*_tomo.md`, with their full callout scaffolding) are the SSoT in
`tomo/config/templates/`. Reproducing them inside `template-doctor.py` would create a second copy
that drifts. `scaffold` instead emits a **minimal, guaranteed-literal-fence** template per note
type — a correct starting point the user grows — and every scaffold's tokens stay inside the
doctor's `KNOWN_TOKENS` set so the scaffold passes its own audit (a test enforces this). Users
who want the rich structure copy from their vault's seeded `config/templates`.

## Why Convert and Scaffold Write to the Inbox, Never Overwrite

WHY: Tomo's MVP execution boundary is proposal-first — Tomo writes only to the inbox folder; the
user applies everything else. Rewriting a user's live template in place would violate that
boundary and risk clobbering hand-tuned Templater logic. `convert` and `scaffold` therefore write
to the inbox with `kado-write-file.py --no-overwrite`, and `convert` re-validates the result with
a dry-render before reporting success (never claim "fixed" without a passing render).
