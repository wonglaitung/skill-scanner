#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REPORT_DIR="${REPORT_DIR:-$ROOT/reports}"
case "$REPORT_DIR" in
  "$ROOT"/*) REPORT_REL="${REPORT_DIR#"$ROOT"/}" ;;
  *)
    echo "[FAIL] REPORT_DIR must be inside $ROOT"
    exit 2
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  echo "[SKIP] docker not available; install gitleaks/trivy locally or run in CI"
  exit 2
fi

GITLEAKS_IMAGE="${GITLEAKS_IMAGE:-zricethezav/gitleaks:latest}"
TRIVY_IMAGE="${TRIVY_IMAGE:-aquasec/trivy:latest}"
USER_SPEC="$(id -u):$(id -g)"

mkdir -p "$REPORT_DIR" .trivy-cache

status=0

echo "== gitleaks =="
docker run --rm \
  -v "$ROOT:/repo" \
  "$GITLEAKS_IMAGE" detect \
  --source /repo \
  --no-git \
  --redact || status=1

if command -v npm >/dev/null 2>&1; then
  echo "== npm audit =="
  npm audit --audit-level=high || status=1
else
  echo "[SKIP] npm not available"
fi

echo "== Trivy vulnerability / misconfig =="
docker run --rm \
  -v "$ROOT:/repo" \
  -v "$ROOT/.trivy-cache:/tmp/trivy" \
  --user "$USER_SPEC" \
  -e TRIVY_CACHE_DIR=/tmp/trivy \
  "$TRIVY_IMAGE" fs \
  --skip-dirs /repo/.git \
  --skip-dirs /repo/node_modules \
  --skip-dirs /repo/.venv-harness \
  --skip-dirs /repo/.harness \
  --skip-dirs /repo/reports \
  --scanners vuln,misconfig \
  --include-dev-deps \
  --format sarif \
  --output "/repo/$REPORT_REL/trivy.sarif" \
  /repo || status=1

echo "== Trivy SBOM =="
docker run --rm \
  -v "$ROOT:/repo" \
  -v "$ROOT/.trivy-cache:/tmp/trivy" \
  --user "$USER_SPEC" \
  -e TRIVY_CACHE_DIR=/tmp/trivy \
  "$TRIVY_IMAGE" fs \
  --skip-dirs /repo/.git \
  --skip-dirs /repo/node_modules \
  --skip-dirs /repo/.venv-harness \
  --skip-dirs /repo/.harness \
  --skip-dirs /repo/reports \
  --format cyclonedx \
  --include-dev-deps \
  --output "/repo/$REPORT_REL/sbom.cdx.json" \
  /repo || status=1

exit "$status"
