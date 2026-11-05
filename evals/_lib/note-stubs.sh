#!/bin/bash
# note-stubs.sh — stub kit for the /note eval cases under evals/ (spec 044
# ADR-8). Sourced by each /note case's scaffold.sh, which sets two variables
# first:
#   NOTE_DRAFTS=none|kept|interrupted|unfrozen|stale
#                 a stage directory from an earlier session (none: no stage):
#                 kept         failed at instructions_json, steps_done [note]
#                 interrupted  failed_step "", steps_done [note]
#                 unfrozen     failed at kado_config, steps_done []
#                 stale        no recorded step (start lists it as stale)
#   NOTE_DELIVER=delivered|source_gone|failed_kado_config|failed_note|
#                failed_instructions_json|failed_instructions_md|
#                failed_source_mark|withdrawn|exists_note|
#                exists_instructions_json|exists_destination
#                 what `note-instructions.py deliver` meets after its checks
# then calls `stage_note_instance`. cwd = the eval workspace; nothing outside
# it is written and nothing under tomo/ is read (the workspace has no tomo/
# tree). The skill and command come from the assembled plugin.
#
# The fixture vault (templates, the inbox source note) is written to
# scripts/note-fixture.json; every stub reads it, and tests/note_stub_kit.py
# fills the fake Kado of the real scripts from the same file.
#
# Output formats below are COPIED from Tomo's scripts, not generated; when one
# of those changes, re-check the copy (tests/test_stub_contract.py runs each
# stub and its real script on the same argv and fails on any difference):
#   note-session start   tomo/scripts/note-session.py:124-132 (mode),
#                        :145-165 (object), :212 (ASCII JSON line); kept and
#                        stale split tomo/scripts/lib/note_meta.py:215-239
#                        (_kept_entry, list_stages; frozen :187-189)
#   note-session match   tomo/scripts/note-session.py:170-186, :207-210 (empty
#                        glob list, exit 2)
#   new                  tomo/scripts/note-instructions.py:216-234 (object),
#                        :160-170 (refused --template/--source, exit 2),
#                        :185-189 + :580-582 (unreadable source, exit 1),
#                        :192-202 (stem, one second later when taken);
#                        meta.json tomo/scripts/lib/note_meta.py:49-64, :96-105, :161-163
#   stage                tomo/scripts/note-instructions.py:250-271 (refused
#                        --title/--destination, exit 2), :240-247 (unknown or
#                        malformed stem, exit 2), :274-311 (note.md from
#                        draft.md, object), :321-330 (frozen keeps meta);
#                        frozen rules tomo/scripts/lib/note_meta.py:187-212;
#                        check tomo/scripts/lib/template_syntax.py:305-366
#   deliver              tomo/scripts/note-instructions.py:523-537 (EXISTS:
#                        first line, object, exit), :360-369 (object),
#                        :379-391 (check failed, step ""), :508-520 (step
#                        order, kado_config :510-516), :394-404 (destination
#                        clash, withdrawn), :438-467 (in-flight mark, failed,
#                        exists), :470-505 (source mark), :526-527 (no title,
#                        exit 2, no JSON)
#   drop                 tomo/scripts/note-instructions.py:543-549
#   template-outline     tomo/scripts/template-outline.py:99-112 (unreadable,
#                        exit 1 object :190-196), :123-132 (outline), :172-187
#                        (template.md + outline.json), :198 (stdout)
#   note-process read    tomo/scripts/note-process.py:85-87, :135 (no process
#                        file: tomo/scripts/lib/note_process.py:153-157)
# Each stub's argv is checked against what tomo/dot_claude/skills/
# note-from-template/SKILL.md passes; anything else prints
# `stub <name>: unexpected argv: …` and exits 2. Every call is appended to
# tomo-tmp/calls.log.
# bash 3.2 compatible.

stage_note_instance() {
  NOTE_DRAFTS="${NOTE_DRAFTS-none}"
  NOTE_DELIVER="${NOTE_DELIVER-delivered}"
  case "$NOTE_DRAFTS" in none|kept|interrupted|unfrozen|stale) ;; *)
    echo "note-stubs.sh: NOTE_DRAFTS must be none|kept|interrupted|unfrozen|stale, got '$NOTE_DRAFTS'" >&2
    return 1 ;; esac
  case "$NOTE_DELIVER" in
    delivered|source_gone|failed_kado_config|failed_note|failed_instructions_json) ;;
    failed_instructions_md|failed_source_mark|withdrawn|exists_note) ;;
    exists_instructions_json|exists_destination) ;;
    *) echo "note-stubs.sh: NOTE_DELIVER '$NOTE_DELIVER' is not a known outcome" >&2; return 1 ;;
  esac
  local _stub_head
  mkdir -p scripts tomo-tmp/note config

  _stub_head='import json, os, re, shutil, sys
NAME = os.path.basename(sys.argv[0])[:-3]
os.makedirs("tomo-tmp", exist_ok=True)
with open("tomo-tmp/calls.log", "a") as _f:
    _f.write(os.path.basename(sys.argv[0]) + " " + " ".join(sys.argv[1:]) + "\n")


def unexpected():
    print("stub %s: unexpected argv: %s" % (NAME, " ".join(sys.argv[1:])), file=sys.stderr)
    sys.exit(2)


def parse(args, valued=(), required=()):
    out, i = {}, 0
    while i < len(args):
        a = args[i]
        if "=" in a and a.split("=", 1)[0] in valued and a.split("=", 1)[0] not in out:
            key, value = a.split("=", 1)
            out[key] = value
            i += 1
        elif a in valued and i + 1 < len(args) and a not in out:
            out[a] = args[i + 1]
            i += 2
        else:
            unexpected()
    for r in required:
        if r not in out:
            unexpected()
    return out


FIXTURE = json.load(open("scripts/note-fixture.json", encoding="utf-8"))
VAULT = FIXTURE["vault"]
STEM_RE = re.compile(r"\d{4}-\d{2}-\d{2}_\d{6}")
STAGE_ROOT = os.path.join("tomo-tmp", "note")
STEPS = ("note", "instructions_json", "instructions_md", "source_mark")
'
  _write_stub() {
    printf '%s' "$_stub_head" > "scripts/$1"
    if [ -n "${2-}" ]; then printf '%s\n' "$2" >> "scripts/$1"; fi
    cat >> "scripts/$1"
  }

  cat > config/vault-config.yaml <<'YAML'
profile: miyo
concepts:
  inbox: 100 Inbox/
  atomic_note:
    path: Atlas/Notes/
templates:
  base_path: X/Templates/
  note_include:
    - t_*_tomo
  mapping:
    daily: t_daily_tomo
YAML

  python3 - <<'PY'
import json
template = """---
date: {{datestamp}}
attendees:
tags: meeting
---
# Meeting

Related: {{source_link}}

## Agenda

## Decisions

## Action items
"""
source = """Meeting with Dana Weber and Luis Ortega on 2026-11-05 about the Q4 roadmap.

Agenda: the Q4 roadmap and the hiring plan for the platform team.

Decisions: we ship the importer in November, and we hire one backend engineer.

Action items: Dana drafts the job post by Friday. Luis books the budget review with finance.
"""
fixture = {
    "base_path": "X/Templates/",
    "note_include": ["t_*_tomo"],
    "daily": "t_daily_tomo",
    "inbox": "100 Inbox/",
    "atomic_path": "Atlas/Notes/",
    "profile": "miyo",
    "vault": {
        "X/Templates/t_meeting_tomo.md": template,
        "X/Templates/t_daily_tomo.md": "---\ndate: {{datestamp}}\n---\n# {{datestamp}}\n",
        "X/Templates/Readme.md": "Templates for new notes.\n",
        "100 Inbox/Meeting with Dana.md": source,
    },
}
with open("scripts/note-fixture.json", "w", encoding="utf-8") as f:
    json.dump(fixture, f, ensure_ascii=False, indent=2)
PY

  # A stage directory from an earlier session, in the shape note-instructions.py
  # writes (meta.json: tomo/scripts/lib/note_meta.py:49-64, :161-163).
  if [ "$NOTE_DRAFTS" != none ]; then
    NOTE_DRAFTS="$NOTE_DRAFTS" python3 - <<'PY'
import json, os
kind = os.environ["NOTE_DRAFTS"]
failed, done = {
    "kept": ("instructions_json", ["note"]),
    "interrupted": ("", ["note"]),
    "unfrozen": ("kado_config", []),
    "stale": ("", []),
}[kind]
stem = "2026-11-04_163000"
meta = {
    "stem": stem, "run_id": "2026-11-04T16-30-00Z-0ld0ff",
    "created": "2026-11-04T16:30:00Z", "generated": "2026-11-04T16:30:00Z",
    "template": "X/Templates/t_meeting_tomo.md", "template_stem": "t_meeting_tomo",
    "source_path": None, "title": "Budget review",
    "inbox_file": "100 Inbox/%s_Budget review.md" % stem,
    "destination": "Atlas/Notes/", "default_destination": "Atlas/Notes/",
    "keep_source": False, "steps_done": done, "failed_step": failed, "profile": "miyo",
}
stage = os.path.join("tomo-tmp", "note", stem)
os.makedirs(stage)
with open(os.path.join(stage, "meta.json"), "w") as f:
    f.write(json.dumps(meta, indent=2) + "\n")
draft = ("---\ndate: 2026-11-04\nattendees: Dana Weber\ntags: meeting\n---\n# Meeting\n\n"
         "Related: {{source_link}}\n\n## Agenda\n\nBudget\n\n## Decisions\n\nNone\n\n"
         "## Action items\n\nNone\n")
for name, text in (("draft.md", draft), ("note.md", draft.replace("{{source_link}}", ""))):
    with open(os.path.join(stage, name), "w") as f:
        f.write(text)
PY
  fi

  _write_stub note-session.py <<'PY'
from fnmatch import fnmatchcase


def read_meta(stage):
    try:
        meta = json.load(open(os.path.join(stage, "meta.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) and meta.get("stem") == os.path.basename(stage) else None


def listing():
    kept, stale = [], []
    stems = sorted(n for n in os.listdir(STAGE_ROOT)
                   if os.path.isdir(os.path.join(STAGE_ROOT, n)) and STEM_RE.fullmatch(n)) \
        if os.path.isdir(STAGE_ROOT) else []
    for stem in stems:
        meta = read_meta(os.path.join(STAGE_ROOT, stem))
        if meta is None or not (meta["failed_step"] or meta["steps_done"]):
            stale.append(stem)
            continue
        kept.append({
            "stem": meta["stem"], "title": meta["title"], "template": meta["template"],
            "created": meta["created"], "failed_step": meta["failed_step"],
            "steps_done": list(meta["steps_done"]),
            "frozen": bool(meta["steps_done"]) or meta["failed_step"] in STEPS,
        })
    return kept, stale


def templates():
    base = FIXTURE["base_path"]
    found = sorted(p for p in VAULT if p.startswith(base) and "/" not in p[len(base):]
                   and p.endswith(".md"))
    return [{"path": p, "stem": os.path.basename(p)[:-3]} for p in found]


def matches(stem, globs):
    return any(fnmatchcase(stem, g) for g in globs)


args = sys.argv[1:]
if not args or args[0] not in ("start", "match"):
    unexpected()
globs, daily = FIXTURE["note_include"], FIXTURE["daily"]
if args[0] == "start":
    text = parse(args[1:], valued=("--args",), required=("--args",))["--args"]
    parts = text.split(maxsplit=1)
    mode, stem = "note", ""
    if parts and parts[0] == "--process":
        mode = "process"
        stem = parts[1].strip() if len(parts) > 1 else ""
        if len(stem) >= 2 and stem[0] == stem[-1] and stem[0] in "\"'":
            stem = stem[1:-1].strip()
        stem = stem[:-3] if stem.endswith(".md") else stem
    kept, stale = listing()
    found = templates() if (mode == "process" and stem) or (mode == "note" and globs) else []
    result = {
        "mode": mode,
        "process_template": stem,
        "process_template_path": next((t["path"] for t in found if stem and t["stem"] == stem), ""),
        "include_configured": bool(globs),
        "note_include": globs,
        "kept_drafts": kept,
        "stale_stages": stale,
        "candidates": [t for t in found if t["stem"] != daily and matches(t["stem"], globs)],
        "folder_listed": len(found),
        "listing_error": "",
    }
else:
    o = parse(args[1:], valued=("--globs",), required=("--globs",))
    wanted = [g.strip() for g in o["--globs"].split(",") if g.strip()]
    if not wanted:
        print("note-session: match needs at least one glob", file=sys.stderr)
        sys.exit(2)
    found = templates()
    stems = [t["stem"] for t in found]
    other = [s for s in stems if s != daily]
    result = {
        "matched": [s for s in other if matches(s, wanted)],
        "unmatched": [s for s in other if not matches(s, wanted)],
        "excluded_daily": daily if daily in stems else "",
        "folder_listed": len(found),
        "listing_error": "",
    }
sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
PY

  _write_stub note-instructions.py "NOTE_DELIVER = '$NOTE_DELIVER'" <<'PY'
import unicodedata
from datetime import datetime, timedelta

RUN_ID = "2026-11-05T10-00-00Z-c0ffee"
NOW = "2026-11-05T10:00:00Z"
FIRST_STEM = datetime(2026, 11, 5, 10, 0, 0)
FORBIDDEN = set('\\/:*?"<>|\x00')
TOKEN_RE = re.compile(r"\\?\{\{([a-z_][a-z0-9_]*)\}\}")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def fail2(message):
    print("note-instructions: " + message, file=sys.stderr)
    sys.exit(2)


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False))


def unsafe(value):
    return any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") and c not in "\u200c\u200d"
               for c in value)


def relative(value):
    if not isinstance(value, str):
        return None
    v = value.strip()
    absolute = v.startswith(("/", "~")) or (v[:1].isascii() and v[:1].isalpha() and v[1:2] == ":")
    if not v or absolute or "\\" in v or unsafe(v) or "{{" in v or "<%" in v:
        return None
    return v


def visible(path):
    return all(s.strip() and not s.strip().startswith(".") for s in path.split("/"))


def vault_folder(value):
    v = relative(value)
    body = v[:-1] if v and v.endswith("/") else v
    return body + "/" if body and visible(body) else None


def vault_note(value):
    v = relative(value)
    return v if v and v.endswith(".md") and visible(v) else None


def sanitize(title):
    return "".join("-" if c in FORBIDDEN else c for c in title)


def inbox_file(meta):
    return "%s/%s_%s.md" % (FIXTURE["inbox"].rstrip("/"), meta["stem"], sanitize(meta["title"]))


def destination_file(meta):
    return meta["destination"] + sanitize(meta["title"]) + ".md"


def frozen(meta):
    return bool(meta["steps_done"]) or meta["failed_step"] in STEPS


def stage_path(stem):
    if not STEM_RE.fullmatch(stem):
        fail2("malformed stem (want YYYY-MM-DD_HHMMSS)")
    return os.path.join(STAGE_ROOT, stem)


def existing(stem):
    stage = stage_path(stem)
    if not os.path.isdir(stage):
        fail2("unknown stem: no stage directory")
    return stage


def load(stage):
    try:
        return json.load(open(os.path.join(stage, "meta.json"), encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail2("meta.json unusable (%s)" % type(exc).__name__)


def save(stage, meta):
    with open(os.path.join(stage, "meta.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(meta, indent=2) + "\n")


def resolved_draft(stage, meta):
    path = os.path.join(stage, "draft.md")
    if not os.path.isfile(path):
        return None
    value = ""
    if meta["source_path"] and meta["keep_source"]:
        name = os.path.basename(meta["source_path"])
        value = "[[%s]]" % (name[:-3] if name.endswith(".md") else name)
    out, opened = [], False
    for line in open(path, encoding="utf-8").read().split("\n"):
        if FENCE_RE.match(line):
            opened = not opened
        elif not opened:
            line = TOKEN_RE.sub(lambda m: value if m.group(1) == "source_link"
                                and not m.group(0).startswith("\\") else m.group(0), line)
        out.append(line)
    return "\n".join(out)


def finding(check, status, detail, fix=None):
    return {"check": check, "status": status, "detail": detail, "fix": fix}


def check(text):
    lines = text.split("\n")
    out = []
    if not lines or lines[0].strip() != "---":
        out.append(finding("leading_fence", "FAIL", "The note does not open with a `---` fence.",
                           "Start the note with a `---` frontmatter block."))
        block = None
    else:
        out.append(finding("leading_fence", "PASS", "The note opens with a `---` fence."))
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if close is None:
            out.append(finding("frontmatter_closed", "FAIL", "The opening `---` fence is never closed.",
                               "Add a closing `---` line after the frontmatter keys."))
            block = None
        else:
            out.append(finding("frontmatter_closed", "PASS", "The frontmatter block is closed."))
            block = lines[1:close]
    if block is not None:
        if any(re.match(r"^tomo\s*:", line) for line in block):
            out.append(finding("no_user_tomo_key", "FAIL",
                               "The frontmatter carries a top-level `tomo:` key.",
                               "Remove it; Tomo stamps its own `tomo:` block."))
        else:
            out.append(finding("no_user_tomo_key", "PASS", "No user-authored `tomo:` key."))
    if "<%" in text:
        out.append(finding("no_templater", "FAIL", "Templater syntax `<%` is left in the note.",
                           "Replace each `<% ... %>` with its final text; Tomo never runs Templater."))
    else:
        out.append(finding("no_templater", "PASS", "No Templater syntax is left."))
    opened, body = None, []
    for n, line in enumerate(lines, start=1):
        if FENCE_RE.match(line):
            opened = None if opened else n
        elif opened is None:
            body.append(line)
    if opened:
        out.append(finding("code_fence_closed", "FAIL",
                           "The code fence opened on line %d is never closed." % opened,
                           "Close it with a line repeating its ``` or ~~~ run, or remove the stray opener."))
    else:
        out.append(finding("code_fence_closed", "PASS", "Every code fence is closed."))
    left = sorted({m.group(1) for m in TOKEN_RE.finditer("\n".join(body))
                   if not m.group(0).startswith("\\")})
    if left:
        names = ", ".join("{{" + n + "}}" for n in left)
        out.append(finding("no_tokens", "FAIL", "Token(s) left outside fenced code: %s." % names,
                           "Fill each token with its value or remove it."))
    else:
        out.append(finding("no_tokens", "PASS", "No `{{token}}` is left outside fenced code."))
    return {"ok": all(f["status"] != "FAIL" for f in out), "findings": out}


def cmd_new(args):
    o = parse(args, valued=("--template", "--source"), required=("--template",))
    template = vault_note(o["--template"])
    if template is None:
        fail2("--template must be a relative vault path ending in .md")
    source = None
    if "--source" in o:
        source = vault_note(o["--source"])
        if source is None:
            fail2("--source must be a relative vault path ending in .md")
        if not unicodedata.normalize("NFC", source).casefold().startswith(
                unicodedata.normalize("NFC", FIXTURE["inbox"]).casefold()):
            fail2("--source must be a note inside concepts.inbox")
        if source not in VAULT:
            print("note-instructions: cannot read the source note (KadoNotFoundError)", file=sys.stderr)
            sys.exit(1)
    for offset in range(60):
        stem = (FIRST_STEM + timedelta(seconds=offset)).strftime("%Y-%m-%d_%H%M%S")
        stage = os.path.join(STAGE_ROOT, stem)
        if not os.path.exists(stage):
            break
    os.makedirs(stage)
    if source:
        with open(os.path.join(stage, "source.md"), "w", encoding="utf-8") as f:
            f.write(VAULT[source])
    stem_of_template = os.path.basename(template)[:-3]
    meta = {
        "stem": stem, "run_id": RUN_ID, "created": NOW, "generated": NOW,
        "template": template, "template_stem": stem_of_template, "source_path": source,
        "title": "", "inbox_file": "", "destination": FIXTURE["atomic_path"],
        "default_destination": FIXTURE["atomic_path"], "keep_source": False,
        "steps_done": [], "failed_step": "", "profile": FIXTURE["profile"],
    }
    meta["inbox_file"] = inbox_file(meta)
    save(stage, meta)
    emit({"stem": stem, "run_id": RUN_ID, "default_destination": FIXTURE["atomic_path"],
          "inbox": FIXTURE["inbox"]})


def cmd_stage(args):
    o = parse(args, valued=("--stem", "--title", "--destination", "--keep-source"),
              required=("--stem",))
    title = o.get("--title")
    if title is not None:
        if unsafe(title):
            fail2("--title must not contain control or invisible characters")
        title = title.strip().rstrip(". ")
        if not title:
            fail2("--title must not be blank")
        if title.startswith("."):
            fail2("--title must not start with a dot")
        if "{{" in title or "<%" in title:
            fail2("--title must not contain template syntax")
    destination = o.get("--destination")
    if destination is not None:
        destination = vault_folder(destination)
        if destination is None:
            fail2("--destination must be a relative vault folder")
    keep = o.get("--keep-source")
    if keep not in (None, "true", "false"):
        unexpected()
    stage = existing(o["--stem"])
    meta = load(stage)
    new_title = meta["title"] if title is None else title
    new_dest = meta["destination"] if destination is None else destination.rstrip("/") + "/"
    new_keep = meta["keep_source"] if keep is None else keep == "true"
    names_change = new_title != meta["title"] or new_dest != meta["destination"]
    keep_frozen = "instructions_json" in meta["steps_done"] or meta["failed_step"] == "instructions_json"
    is_frozen = (names_change and frozen(meta)) or (new_keep != meta["keep_source"] and keep_frozen)
    if not is_frozen:
        meta["title"], meta["destination"], meta["keep_source"] = new_title, new_dest, new_keep
        meta["inbox_file"] = inbox_file(meta)
        save(stage, meta)
    resolved = resolved_draft(stage, meta)
    note = os.path.join(stage, "note.md")
    if resolved is None:
        if os.path.exists(note):
            os.remove(note)
        result = {"ok": False, "findings": [finding(
            "draft_present", "FAIL", "draft.md is missing in the stage directory.",
            "Write draft.md, then run stage again.")]}
    else:
        with open(note, "w", encoding="utf-8") as f:
            f.write(resolved)
        result = check(resolved)
    named = bool(meta["title"])
    emit({"stem": meta["stem"], "title": meta["title"],
          "inbox_file": meta["inbox_file"] if named else "",
          "destination_file": destination_file(meta) if named else "",
          "keep_source": meta["keep_source"], "frozen": is_frozen, "check": result})


def deliver_output(meta, status, step="", exists_path="", source_marked=False):
    base = "%s/%s_instructions" % (os.path.dirname(meta["inbox_file"]), meta["stem"])
    return {"status": status, "step": step, "note_path": meta["inbox_file"],
            "instructions_json": base + ".json", "instructions_md": base + ".md",
            "source_marked": source_marked, "steps_done": list(meta["steps_done"]),
            "frozen": frozen(meta), "exists_path": exists_path}


def stop(meta, status, step, code, exists_path=""):
    if exists_path:
        print("EXISTS:" + exists_path)
    emit(deliver_output(meta, status, step, exists_path))
    sys.exit(code)


def record(stage, meta, step):
    if step not in meta["steps_done"]:
        meta["steps_done"].append(step)
    if meta["failed_step"] == step:
        meta["failed_step"] = ""
    save(stage, meta)


def failed_at(stage, meta, step):
    meta["failed_step"] = step
    save(stage, meta)
    print("note-instructions: delivery failed at %s (KadoConnectionError)" % step, file=sys.stderr)
    stop(meta, "failed", step, 1)


def cmd_deliver(args):
    o = parse(args, valued=("--stem",), required=("--stem",))
    stage = existing(o["--stem"])
    meta = load(stage)
    if not meta["title"]:
        fail2("no title staged: run stage --title first")
    resolved = resolved_draft(stage, meta)
    if resolved is None or not check(resolved)["ok"]:
        print("note-instructions: filled-note check failed; fix the draft and run stage",
              file=sys.stderr)
        stop(meta, "failed", "", 1)
    if NOTE_DELIVER == "failed_kado_config":
        print("note-instructions: Kado is not configured (no URL or token)", file=sys.stderr)
        meta["failed_step"] = "kado_config"
        save(stage, meta)
        stop(meta, "failed", "kado_config", 1)
    if NOTE_DELIVER == "exists_destination":
        stop(meta, "exists", "", 3, destination_file(meta))
    if NOTE_DELIVER == "withdrawn":
        print("note-instructions: a guard withdrew an action; nothing written", file=sys.stderr)
        stop(meta, "withdrawn", "", 1)
    targets = deliver_output(meta, "")
    paths = {"note": targets["note_path"], "instructions_json": targets["instructions_json"],
             "instructions_md": targets["instructions_md"]}
    for step in STEPS[:3]:
        if NOTE_DELIVER == "exists_" + step:
            stop(meta, "exists", step, 3, paths[step])
        if NOTE_DELIVER == "failed_" + step:
            failed_at(stage, meta, step)
        record(stage, meta, step)
    marked = False
    if meta["source_path"]:
        if NOTE_DELIVER == "failed_source_mark":
            failed_at(stage, meta, "source_mark")
        marked = NOTE_DELIVER != "source_gone"
        record(stage, meta, "source_mark")
    shutil.rmtree(stage)
    emit(deliver_output(meta, "delivered", source_marked=marked))


def cmd_drop(args):
    o = parse(args, valued=("--stem",), required=("--stem",))
    stage = stage_path(o["--stem"])
    removed = os.path.isdir(stage)
    if removed:
        shutil.rmtree(stage)
    emit({"stem": o["--stem"], "removed": removed})


COMMANDS = {"new": cmd_new, "stage": cmd_stage, "deliver": cmd_deliver, "drop": cmd_drop}
if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
    unexpected()
COMMANDS[sys.argv[1]](sys.argv[2:])
PY

  _write_stub template-outline.py <<'PY'
o = parse(sys.argv[1:], valued=("--template", "--stage", "--out"), required=("--template",))
if ("--stage" in o) == ("--out" in o):
    unexpected()
template = o["--template"]
source_path = None
if "--stage" in o:
    if not STEM_RE.fullmatch(o["--stage"]):
        unexpected()
    stage = os.path.join(STAGE_ROOT, o["--stage"])
    try:
        meta = json.load(open(os.path.join(stage, "meta.json"), encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"template": template, "error": "stage %s: meta.json unusable (%s)"
                          % (o["--stage"], type(exc).__name__)}, ensure_ascii=False))
        sys.exit(2)
    source_path = meta["source_path"]
if template not in VAULT:
    print(json.dumps({"template": template, "error": "KadoNotFoundError: NOT_FOUND"},
                     ensure_ascii=False))
    sys.exit(1)
if template != "X/Templates/t_meeting_tomo.md":
    unexpected()
outline = {
    "template": template,
    "frontmatter": [
        {"key": "date", "has_value": True, "line": 2},
        {"key": "attendees", "has_value": False, "line": 3},
        {"key": "tags", "has_value": True, "line": 4},
    ],
    "headings": [
        {"level": 1, "text": "Meeting", "line": 6, "has_body": True},
        {"level": 2, "text": "Agenda", "line": 10, "has_body": False},
        {"level": 2, "text": "Decisions", "line": 12, "has_body": False},
        {"level": 2, "text": "Action items", "line": 14, "has_body": False},
    ],
    "tokens": [
        {"name": "datestamp", "line": 2, "prefilled": True},
        {"name": "source_link", "line": 8, "prefilled": bool(source_path)},
    ],
    "templater": [],
    "frontmatter_ok": True,
}
dumped = json.dumps(outline, ensure_ascii=False, indent=2) + "\n"
if "--stage" in o:
    with open(os.path.join(stage, "template.md"), "w", encoding="utf-8") as f:
        f.write(VAULT[template].replace("{{datestamp}}", "2026-11-05"))
    with open(os.path.join(stage, "outline.json"), "w", encoding="utf-8") as f:
        f.write(dumped)
else:
    with open(o["--out"], "w", encoding="utf-8") as f:
        f.write(dumped)
print(json.dumps(outline, ensure_ascii=False, indent=2))
PY

  _write_stub note-process.py <<'PY'
args = sys.argv[1:]
if not args or args[0] != "read":
    unexpected()
o = parse(args[1:], valued=("--template", "--outline"), required=("--template",))
if "--outline" in o and not os.path.isfile(o["--outline"]):
    print("note-process: outline unreadable (FileNotFoundError)", file=sys.stderr)
    sys.exit(2)
sys.stdout.write(json.dumps({"exists": False, "declined": False, "destination": "", "required": [],
                             "guidance": "", "missing_required": [], "error": ""},
                            ensure_ascii=True) + "\n")
PY
  unset -f _write_stub
}
