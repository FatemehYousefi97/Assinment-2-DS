#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose --profile test run --rm -T test-runner pytest -s -v \
  tests/integration/test_experiments.py -k experiment_7

