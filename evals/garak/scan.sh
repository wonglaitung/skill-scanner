#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

mkdir -p reports

python -m garak \
  --target_type rest \
  -G evals/garak/rest_config.yaml \
  --spec probes.promptinject,probes.dan,probes.encoding,probes.leakreplay \
  --generations 3 \
  --report_prefix reports/garak
