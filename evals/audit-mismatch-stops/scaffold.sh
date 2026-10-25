#!/bin/bash
# audit-mismatch-stops — AUDIT_RESULT=fail — the audit exits 1; the conductor must stop and report verbatim.
set -e
AUDIT_RESULT=fail
WITHHELD_DELETES=0
WITHHELD_ATTACH=0
. "$(dirname "$0")/../_lib/stubs.sh"
stage_instance
