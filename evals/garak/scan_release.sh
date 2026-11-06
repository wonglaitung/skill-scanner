#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

SKILL="${SKILL:-account-balance-query}"
TARGETS="${TARGETS:-targets}"
TIMESTAMP="$(date +%Y-%m-%d-%H%M%S)"
PROBE_FILE="${GARAK_PROBE_FILE:-evals/garak/release_probes_v2.txt}"
SPEC="${GARAK_SPEC:-$(paste -sd, "$PROBE_FILE")}"

export SKILL
export TARGETS
export GARAK_SPEC="$SPEC"
export GARAK_PARALLEL="${GARAK_PARALLEL:-16}"
export GARAK_REPORT_PREFIX="${GARAK_REPORT_PREFIX:-$ROOT/reports/garak/release/$SKILL/$TIMESTAMP/garak}"

"$ROOT/evals/garak/scan.sh"

REPORT="${GARAK_REPORT_PREFIX}.report.jsonl"
if [ ! -f "$REPORT" ]; then
  echo "garak report missing: $REPORT" >&2
  exit 2
fi
python3 "$ROOT/scripts/garak_summary.py" --report "$REPORT"
