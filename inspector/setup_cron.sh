#!/usr/bin/env bash
# Setup cron jobs for the Elmehdi Fiction Inspector.
#
# Schedule:
#   - Tests every 6h (00h, 06h, 12h, 18h) — 6 tests per feature = ~30 tests/day
#   - Daily report at 08h00
#   - Weekly trend report on Sundays at 08h30
#
# Usage: bash inspector/setup_cron.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$(which python3)"
LOG_DIR="$PROJECT_DIR/inspector/logs"
mkdir -p "$LOG_DIR"

CRON_TAG="# elmehdi-fiction-inspector"

# Remove existing inspector cron jobs
(crontab -l 2>/dev/null || true) | grep -v "$CRON_TAG" | crontab - || true

# Build new cron lines
NEW_CRONS=$(cat <<EOF
# ─── Elmehdi Fiction Inspector ──────────────────────────────────────────────
0  0,6,12,18 * * *  cd "$PROJECT_DIR" && $PYTHON -m inspector.run_tests >> "$LOG_DIR/tests.log" 2>&1  $CRON_TAG
0  8          * * *  cd "$PROJECT_DIR" && $PYTHON -m inspector.run_tests --report >> "$LOG_DIR/daily.log" 2>&1  $CRON_TAG
30 8          * * 0  cd "$PROJECT_DIR" && $PYTHON -m inspector.run_tests --weekly >> "$LOG_DIR/weekly.log" 2>&1  $CRON_TAG
EOF
)

# Append to existing crontab
(crontab -l 2>/dev/null || true; echo "$NEW_CRONS") | crontab -

echo "✅ Cron jobs installed:"
crontab -l | grep "inspector"
echo ""
echo "Logs will be written to: $LOG_DIR"
echo ""
echo "To remove: crontab -l | grep -v elmehdi-fiction-inspector | crontab -"
