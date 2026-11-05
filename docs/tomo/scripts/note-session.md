# WHY: note-session.py

> Rationale for decisions in `tomo/scripts/note-session.py`.
> The script is the deterministic session start of `/note` (spec 044, ADR-6):
> `start` reads the mode, the draft state and the template candidates; `match`
> previews proposed globs on the first run (F1).

## WHY the Session Start Is a Script

WHY: ADR-6. Parsing `$ARGUMENTS`, splitting stage directories into kept and
stale, checking `note_include` and filtering the template listing are rules,
not judgement. Done by the model they drift between runs (a glob matched
case-insensitively once, the daily template offered once). One script makes
the start the same every time and testable without a model in the loop
(constitution L1, core logic separate from AI glue).

## WHY the Request Text Never Appears in the Output

WHY: CON-3. The request is user material (it may name a client or a diagnosis).
The skill already holds `$ARGUMENTS`; the script only reports the mode. Neither
stdout nor stderr carries it, and a test passes a marker string to prove it.
`process_template` is the exception the interface names: it is the stem after
`--process`, a template name, which the skill needs to say which template it is
asking about.

## WHY Everything After `--process` Is the Stem

WHY: template stems carry spaces (`Meeting Notes`). Taking only the next
whitespace token would turn `/note --process Meeting Notes` into a lookup for
`Meeting`, which is reported as unknown. The rest of the text, stripped and
with one pair of surrounding quotes removed, is the stem. `--process` with
nothing after it is still process mode with an empty stem; the skill reports
the template as unknown (F7-AC11) rather than the script failing. Only the exact
token `--process` selects the mode: `--processor x` is free text (note mode),
so a request that merely starts with those letters is never read as a template
name. One trailing `.md` is removed from the stem, because a user who names the
file (`/note --process t_meeting.md`) means the template whose listing stem is
`t_meeting`; without that, the lookup would always miss.

## WHY an Empty `--process` Stem Makes No Kado Call

WHY: CON-7 budget. An empty stem can never be found, so the listing would only
spend a call for a `process_template_path` that is empty anyway. The skill
already reports the template as unknown from the empty stem.

## WHY the Skill Passes `--args=<text>`

WHY: argparse reads a lone `--process` after `--args` as an option and fails.
The `=` form binds any text, including an empty one, to `--args`.

## WHY Config Is Read Directly, Not Through read-config-field.py

WHY: every Python script that needs `vault-config.yaml` (`mark-captured.py`,
`instruction-render.py`, `token-render.py`, `vault-summary.py`, ...) takes
`--config config/vault-config.yaml` and loads it with `yaml.safe_load`;
`read-config-field.py` exists for agent prompts, so a model does not write
inline Python. Spawning it from a script adds a process and a JSON round trip
for the same `safe_load`. The script keeps its semantics: a missing key is
absent, never an error (the `--field` exit 1 the SDD gotcha warns about does
not arise). A missing, unparseable or non-UTF-8 file (`UnicodeDecodeError`,
a `ValueError`) reads as empty config, with one stderr line naming the problem
class only — a crash there would make the model re-run the script. A file that
parses but is not a mapping reads as empty config without a line. The read is
`lib/note_io.load_vault_config`; this policy stays in the script (see
`docs/tomo/scripts/lib/note_io.md`).

## WHY No Listing When `note_include` Is Absent (Note Mode)

WHY: without `note_include` the skill runs the first-run setup, which calls
`match` to preview globs; a listing in `start` would be thrown away and costs a
Kado call against the 20-per-5-s budget (CON-7). `include_configured` is true
only for a non-empty list of non-empty strings: anything else cannot be matched
and makes the setup rewrite it through `vault-config-writer.py`.

## WHY Process Mode Lists Whatever `note_include` Says

WHY: the SDD interface — `process_template_path` is the vault path of the stem
in `templates.base_path`, empty when not found. A process file belongs to a
template, not to the `/note` selection, so a user may set one up before or
without confirming `note_include`. Candidates stay empty while `note_include`
is absent, so the listing does not leak into the note flow.

## WHY Direct Children Only (`depth=1`)

WHY: `templates.mapping` names templates relative to `base_path` as filenames,
and the `note_include` schema matches "template filenames under
templates.base_path". A recursive listing would also pull Templater script
folders and could return two files with the same stem, which makes
`process_template_path` ambiguous.

## WHY Globs Match the Basename Without `.md`, Case-Sensitively

WHY: the SDD pattern preview. The owner's scheme (`t_*`) names templates by
prefix; matching the full path would make a glob depend on where the template
folder sits. `fnmatch.fnmatchcase` because `fnmatch.fnmatch` folds case on
macOS and not on Linux: the same globs would select different templates on the
host and in the container.

## WHY the Daily Template Is Always Excluded

WHY: F1-AC6. The daily note has its own flow and tracker logic; offering it as
a `/note` kind would create a second daily note. It is dropped after matching,
so `*` cannot bring it back. `templates.mapping.daily` may carry `.md`
(`vault-example.yaml`), and only its basename stem is compared.
`excluded_daily` names it only when the listing returned it — it reports what
was excluded, not what is configured.

## WHY Listing Order Is Kept

WHY: Kado returns a stable order for the same folder; the preview table of the
SDD follows it. Sorting would reorder what the user sees between `match` and
the candidate list for no gain.

## WHY a Listing Failure Exits 0

WHY: the repo rule — an agent-called script exits 0 when its output is usable,
or the model re-runs it. `folder_listed: 0` with `listing_error` set is usable:
the skill says the folder is empty or not readable by the Kado key and gives the
remedy (F2-AC4). An empty listing is not proof of an empty folder (CON-7), so
the script never claims "no templates". `listing_error` is the Kado error text
(paths and status, no note content), shown verbatim by the skill. A missing
`templates.base_path` is reported the same way, without a Kado call. A
transport failure that escapes the client as `OSError` or `TimeoutError`
(socket reset, read timeout) is reported the same way, as the class name and
its message: neither carries the request text, which never reaches the client.

## WHY the JSON Is Written ASCII-Escaped

WHY: `json.dumps(..., ensure_ascii=False)` raises `UnicodeEncodeError` when
stdout is not UTF-8 (a `C`/`POSIX` locale in a container, a pipe opened as
ASCII), and also on a lone surrogate, which Python makes of argv bytes that are
not valid UTF-8. `ensure_ascii=True` cannot fail on either: every non-ASCII
character becomes a `\uXXXX` escape that any JSON reader decodes back.
Reconfiguring `sys.stdout` to UTF-8 was rejected: it still fails on a
surrogate, and it changes a process-wide stream for one write.

## WHY `match` Exits 2 on an Empty Glob List

WHY: SDD interface. An empty list would report every template unmatched, and
the skill could read that as "the folder has no templates". A bad invocation is
the honest result.

## WHY Kept Drafts Come From lib/note_meta.py

WHY: the kept/stale split (failed_step set or steps_done non-empty) is owned by
`lib/note_meta.list_stages`; re-deriving it here would drift from the writer
(`note-instructions.py`). Stage directories are read relative to the working
directory, which is the instance root in the container.
