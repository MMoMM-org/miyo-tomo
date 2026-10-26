#!/bin/bash
# state-flip-failure-reported — FLIP_RESULT=fail — the state flip exits 1; the failed-step line reaches the report.
set -e
AUDIT_RESULT=ok
WITHHELD_DELETES=0
WITHHELD_ATTACH=0
FLIP_RESULT=fail
. "$(dirname "$0")/../_lib/stubs.sh"
stage_instance
