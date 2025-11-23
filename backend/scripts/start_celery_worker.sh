#!/bin/bash
#
# Start Celery Worker for Splunk TA Generator
#
# This script starts the Celery worker that processes background tasks
# including TA generation and validation.
#
# Usage:
#   ./backend/scripts/start_celery_worker.sh
#
# Environment Variables:
#   CELERY_WORKER_CONCURRENCY - Number of worker processes (default: 4)
#   CELERY_TASK_TIME_LIMIT - Task timeout in seconds (default: 3600)
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
CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"
TIME_LIMIT="${CELERY_TASK_TIME_LIMIT:-3600}"
LOG_LEVEL="${CELERY_LOG_LEVEL:-info}"

echo "Starting Celery Worker..."
echo "  Concurrency: $CONCURRENCY"
echo "  Time Limit: $TIME_LIMIT seconds"
echo "  Log Level: $LOG_LEVEL"
echo "  Queues: default, ta_generation, validation"

# Start the Celery worker
exec celery -A backend.tasks.celery_app worker \
    --loglevel="$LOG_LEVEL" \
    --concurrency="$CONCURRENCY" \
    --max-tasks-per-child=100 \
    --time-limit="$TIME_LIMIT" \
    --queues=default,ta_generation,validation \
    --hostname="worker@%h"
