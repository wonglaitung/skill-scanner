#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export GARAK_PROBE_FILE="${GARAK_PROBE_FILE:-$ROOT/evals/garak/release_probes_v2.txt}"
exec "$ROOT/evals/garak/scan_release.sh"
