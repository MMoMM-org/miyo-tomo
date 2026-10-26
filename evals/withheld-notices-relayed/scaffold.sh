#!/bin/bash
# withheld-notices-relayed — two withheld deletes and one withheld attachment; each notice line relayed verbatim, last.
set -e
AUDIT_RESULT=ok
WITHHELD_DELETES=2
WITHHELD_ATTACH=1
. "$(dirname "$0")/../_lib/stubs.sh"
stage_instance
