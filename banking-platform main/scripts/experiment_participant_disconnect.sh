#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'docker compose start bank-b1 bank-b2 coordinator >/dev/null 2>&1 || true' EXIT
REQUEST_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
echo "Crash after durable COMMIT for request=$REQUEST_ID"
docker compose run --rm -T --no-deps -e "REQUEST_ID=$REQUEST_ID" test-runner \
  python scripts/fault_coordinator.py after_commit_decision
echo "Stop all B participants BEFORE coordinator recovery"
docker compose stop -t 1 bank-b1 bank-b2
# The B replicas are intentionally offline here. `compose start coordinator`
# also starts its depends_on services (including bank-b1), defeating the test
# and possibly waiting forever on a prepared transaction held by B.
docker compose up -d --no-deps --no-build coordinator
docker compose run --rm -T --no-deps test-runner python scripts/verify_pending.py "$REQUEST_ID"
echo "Restoring B replicas; persistent COMMIT must finish"
docker compose start bank-b1 bank-b2
docker compose run --rm -T --no-deps test-runner \
  python scripts/verify_recovery.py "$REQUEST_ID" COMMITTED
echo "Participant-disconnect recovery PASS"
