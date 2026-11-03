#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

mkdir -p reports

python -m garak \
  --target_type rest \
  -G evals/garak/rest_config.json \
  --spec probes.promptinject,probes.dan,probes.encoding,probes.leakreplay \
  --generations 3 \
  --parallel_attempts "${GARAK_PARALLEL:-4}" \
  --report_prefix "$ROOT/reports/garak"
