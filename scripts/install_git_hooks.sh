#!/usr/bin/env bash
# Copy custom Git hooks from docker/.githooks into .git/hooks (templates live in-repo).
# Does not build Docker images or run compose — hooks invoke make targets that use Docker when they run.
#
# Installed hooks call from repo root: make git-hooks-commit (pre-commit), make git-hooks-push (pre-push).
#
# - make setup ENV=local|test runs this without INSTALL_GIT_HOOKS_REQUIRED (best-effort; never fails setup).
# - make install-git-hooks sets INSTALL_GIT_HOOKS_REQUIRED=1 (must succeed — copy-only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

REQUIRED="${INSTALL_GIT_HOOKS_REQUIRED:-}"

SRC_DIR="$ROOT/docker/.githooks"
DST_DIR="$ROOT/.git/hooks"

log() { echo "[hooks] $*"; }
fail() { log "$*" >&2; exit 1; }

if [[ ! -d .git ]]; then
  log "No .git directory; skipping Git hooks."
  if [[ "$REQUIRED" == "1" ]]; then
    fail "Not a Git repository (no .git)."
  fi
  exit 0
fi

if [[ ! -f "$SRC_DIR/pre-commit" || ! -f "$SRC_DIR/pre-push" ]]; then
  if [[ "$REQUIRED" == "1" ]]; then
    fail "Missing hook templates under $SRC_DIR (expected pre-commit and pre-push)."
  fi
  log "Skipped — missing templates under $SRC_DIR/"
  exit 0
fi

mkdir -p "$DST_DIR"
cp "$SRC_DIR/pre-commit" "$DST_DIR/pre-commit"
cp "$SRC_DIR/pre-push" "$DST_DIR/pre-push"
chmod +x "$DST_DIR/pre-commit" "$DST_DIR/pre-push" || true

log "Copied docker/.githooks → .git/hooks (pre-commit / pre-push invoke Make targets that use Docker)."
exit 0
