#!/bin/bash
# Git commit helper for Voyage sessions
# Usage: bash git_commit.sh [message]

REPO_DIR="$(dirname "$0")"
cd "$REPO_DIR"

MSG="${1:-Session update $(date +%Y-%m-%d_%H:%M)}"

git add -A 2>/dev/null || true
git commit -m "$MSG" 2>/dev/null || echo "[INFO] Nothing to commit or git not initialized"

echo "[OK] Committed: $MSG"
