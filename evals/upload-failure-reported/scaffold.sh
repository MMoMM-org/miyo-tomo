#!/bin/bash
# upload-failure-reported — UPLOAD_RESULT=fail — the upload exits 1; no state flip, the failed-step line reaches the report.
set -e
AUDIT_RESULT=ok
WITHHELD_DELETES=0
WITHHELD_ATTACH=0
UPLOAD_RESULT=fail
. "$(dirname "$0")/../_lib/stubs.sh"
stage_instance
