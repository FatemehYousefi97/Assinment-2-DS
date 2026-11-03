#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "Running experiments 1, 2, 3, 5, 7..."
for number in 1 2 3 5 7; do
  bash "scripts/experiment_${number}.sh"
done
echo "Running supplemental protocol and idempotency tests..."
docker compose --profile test run --rm -T test-runner pytest -s -v tests/integration/test_protocol.py
echo "Running experiment 4: replica outage under load..."
bash scripts/experiment_4.sh
echo "Running experiment 6: actual Coordinator crashes and recovery..."
bash scripts/experiment_6.sh
echo "ALL COMPOSE EXPERIMENTS FINISHED - review each script's assertion and logs."

