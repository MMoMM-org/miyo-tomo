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
