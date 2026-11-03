#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'docker compose start coordinator >/dev/null 2>&1 || true' EXIT
for point in after_prepare after_commit_decision; do
  REQUEST_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
  echo "Injecting Coordinator crash at $point request=$REQUEST_ID"
  docker compose run --rm -T --no-deps -e "REQUEST_ID=$REQUEST_ID" test-runner \
    python scripts/fault_coordinator.py "$point"
  echo "Restarting Coordinator and waiting for reconciliation..."
  docker compose start coordinator
  if [[ "$point" == "after_prepare" ]]; then
    expected=ABORTED
  else
    expected=COMMITTED
  fi
  docker compose run --rm -T --no-deps test-runner \
    python scripts/verify_recovery.py "$REQUEST_ID" "$expected"
done
echo "Experiment 6 and recovery scenario B/C completed."

