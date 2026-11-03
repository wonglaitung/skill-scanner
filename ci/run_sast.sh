#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== SKILL.md validation =="
python3 ci/validate_skill.py

echo "== Ruff =="
ruff check adapters ci evals skills

if command -v semgrep >/dev/null 2>&1; then
  echo "== Semgrep =="
  semgrep --config p/python --config p/javascript --config p/owasp-top-ten \
    adapters ci skills --error
else
  echo "[SKIP] semgrep not installed"
fi

if command -v shellcheck >/dev/null 2>&1; then
  echo "== ShellCheck =="
  mapfile -t shell_files < <(find skills -name '*.sh' -type f 2>/dev/null)
  if [ "${#shell_files[@]}" -gt 0 ]; then
    shellcheck "${shell_files[@]}"
  else
    echo "[SKIP] no shell scripts"
  fi
else
  echo "[SKIP] shellcheck not installed"
fi

if command -v gitleaks >/dev/null 2>&1; then
  echo "== gitleaks =="
  gitleaks detect --source . --no-git
else
  echo "[SKIP] gitleaks not installed"
fi

if command -v trivy >/dev/null 2>&1; then
  echo "== Trivy =="
  mkdir -p reports
  trivy fs --scanners vuln,misconfig --format sarif \
    --output reports/trivy.sarif .
else
  echo "[SKIP] trivy not installed"
fi
