#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose start bank-a1 bank-a2
docker compose run --rm -T --no-deps test-runner python scripts/load_generator.py 12 &
LOAD_PID=$!
trap 'docker compose start bank-a1 >/dev/null 2>&1 || true' EXIT
sleep 2
echo "Stopping bank-a1 during active traffic..."
docker compose stop -t 1 bank-a1
wait "$LOAD_PID"
echo "Restarting stopped replica..."
docker compose start bank-a1
echo "Experiment 4 completed; inspect: docker compose logs --tail=80 gateway bank-a1 bank-a2"

