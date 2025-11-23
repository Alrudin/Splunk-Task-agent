#!/bin/bash
#
# Start Celery Beat Scheduler for Splunk TA Generator
#
# This script starts the Celery Beat scheduler for periodic tasks
# such as sample retention cleanup and other maintenance jobs.
#
# Note: This is for future use when periodic tasks are implemented.
#
# Usage:
#   ./backend/scripts/start_celery_beat.sh
#
# Environment Variables:
#   CELERY_LOG_LEVEL - Logging level (default: info)
#

set -e

# Change to the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Load environment variables from .env if present
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Loading environment variables from .env"
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# Set default values
LOG_LEVEL="${CELERY_LOG_LEVEL:-info}"

# Create directory for beat state files if it doesn't exist
BEAT_DIR="/tmp/celery-beat"
mkdir -p "$BEAT_DIR"

echo "Starting Celery Beat Scheduler..."
echo "  Log Level: $LOG_LEVEL"
echo "  Schedule DB: $BEAT_DIR/celerybeat-schedule"
echo "  PID File: $BEAT_DIR/celerybeat.pid"

# Start Celery Beat
exec celery -A backend.tasks.celery_app beat \
    --loglevel="$LOG_LEVEL" \
    --pidfile="$BEAT_DIR/celerybeat.pid" \
    --schedule="$BEAT_DIR/celerybeat-schedule"
