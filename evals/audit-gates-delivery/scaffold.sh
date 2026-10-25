#!/bin/bash
# audit-gates-delivery — AUDIT_RESULT=ok — nothing withheld; the audit must gate upload and state flip.
set -e
AUDIT_RESULT=ok
WITHHELD_DELETES=0
WITHHELD_ATTACH=0
. "$(dirname "$0")/../_lib/stubs.sh"
stage_instance
