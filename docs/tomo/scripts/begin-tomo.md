# WHY: begin-tomo.sh

> Rationale for decisions in `scripts/lib/begin-tomo.sh.template`.

## The Container Runs in the Host's Time Zone (#202)

WHY the launcher passes `TZ`: a container starts on UTC, so `date` and
`time.localtime()` were two hours off a host on summer time.

WHY the zone comes from the `/etc/localtime` link: macOS does not set `TZ`. The link
target ends in the zone name on macOS and on Linux. A `TZ` of the form `:/path` names a
file rather than a zone, and the container has no such host file, so it is ignored.

WHY `tzdata` plus the `tomo.has_tzdata` label: without zone data glibc falls back to UTC
without an error, so `TZ` alone can silently do nothing. The label makes an existing
image rebuild once, the same way `tomo.has_socat` does.

WHY machine timestamps stay UTC: `run_id`, `generated` and `updated_at` are compared
across runs and carry a `Z`. Only what the owner reads moves to local time.

## The Tab Is Named After Tomo, Not After Docker

WHY a tab title: the host terminal labels a tab after its foreground process, which is
`docker`, so several Tomo tabs and an unrelated Docker tab looked the same. The launcher
sets an OSC 0 title `友 Tomo · <instance>` before `docker run` and clears it on exit.

WHY `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1`: Claude Code in the container writes its own
title through the attached TTY and would replace the Tomo title on the first prompt.

WHY not the tab icon: iTerm2 draws the icon of the running host process (the Docker
whale). No escape sequence sets a custom icon; only an iTerm2 profile with a custom icon
could, switched in with `SetProfile`. That writes into the owner's iTerm2 configuration
and only works in iTerm2, so it was left out in favour of the title.

WHY only on a TTY: piped or scripted launches must not get escape bytes in their output.
