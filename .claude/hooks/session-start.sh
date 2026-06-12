#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "=== Session Start: Installing dependencies ==="

cd "$CLAUDE_PROJECT_DIR"

# ── Python dependencies ───────────────────────────────────────────────────────
echo "[1/4] Installing Python dependencies..."
pip install -q --exists-action i \
  fastapi==0.115.5 \
  "uvicorn[standard]==0.32.1" \
  "httpx>=0.27,<0.28" \
  atproto==0.0.55 \
  apscheduler==3.10.4 \
  python-multipart==0.0.18 \
  requests-oauthlib==2.0.0 \
  Pillow==11.0.0 \
  "pytest>=8.0,<9.1" \
  "pytest-asyncio>=0.23,<2.0" \
  "pytest-html>=4.0,<5.0" \
  pytest-cov \
  allure-pytest \
  hypothesis \
  selenium \
  ruff 2>&1 | grep -v "^WARNING\|^ERROR: Cannot uninstall" || true

# ── Env setup ─────────────────────────────────────────────────────────────────
echo "[2/4] Configuring environment..."
echo 'export PYTHONPATH="."' >> "$CLAUDE_ENV_FILE"
echo 'export DATA_DIR="/tmp/auto-affiliate-data"' >> "$CLAUDE_ENV_FILE"
mkdir -p /tmp/auto-affiliate-data

# ── QA Suite — session-start gate ────────────────────────────────────────────
# Run each file in its own process — they share the FastAPI app object and
# running them together causes an "Event loop is closed" error on the second file.
echo "[3/4] Running QA suite (session-start gate)..."
{
  python -m pytest api/tests/test_qa_suite.py \
    -q --tb=short --no-header -p no:allure_pytest
  python -m pytest api/tests/test_qa_intelligent.py \
    -q --tb=short --no-header -p no:allure_pytest
} 2>&1 | tee /tmp/qa-session-start.log

QA_EXIT=${PIPESTATUS[0]}

if [ "$QA_EXIT" -ne 0 ]; then
  echo ""
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  ⚠  QA GATE FAILED — review /tmp/qa-session-start.log ║"
  echo "╚══════════════════════════════════════════════════════╝"
  # Non-fatal: warn but allow session to start so bugs can be fixed
  exit 0
fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✓  QA GATE PASSED — all session-start checks green  ║"
echo "╚══════════════════════════════════════════════════════╝"

# ── Linter availability check ─────────────────────────────────────────────────
echo "[4/4] Verifying ruff linter..."
ruff --version

echo ""
echo "=== Session ready ==="
