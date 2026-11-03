# Requirements matrix and acceptance checklist

Source of truth: *Assignment 2: Distributed Banking Platform*, four-page university PDF. The supplementary prompt adds further validation and delivery detail.

Status terminology: **Verified (Mac)** means the requirement was implemented and the student supplied a passing live Docker transcript from their Mac; **Partial** means implementation exists but some acceptance evidence is outstanding; **Not Implemented** means intentionally not started. Source generation originally occurred without Docker, so Mac results are external student-provided evidence and are separately logged in `results/MAC_VALIDATION_2026-10-25.md`.

| PDF reference | Requirement | Implementation | Acceptance evidence / test | Status |
| --- | --- | --- | --- | --- |
| §2 | CLI with balance, deposit, withdraw, transfer, status | `app/client.py` | Live CLI balance/deposit/withdraw/cross-shard transfer and status/request lookup passed | Verified (Mac) |
| §2–3 | Exclusive ranges, deterministic Shard Map | `config/shards.json`, `app/sharding.py` | 4 ShardMap unit tests; live `experiment_1.sh` | Verified (Mac) |
| §2–3 | Two independent persistent DBs | `docker-compose.yml`, `db/shard.sql` | `experiment_1.sh`; restart persistence test | Verified (Mac) |
| §2–3 | Two stateless replicas per shard | Compose services A1/A2/B1/B2 | `experiment_2.sh`; 4 healthy replicas | Verified (Mac) |
| §2–3 | Health checks + Round Robin + failover | `app/routing.py`, `app/gateway.py` | `experiment_2.sh`, `experiment_4.sh` (183 requests, 0 failures) | Verified (Mac) |
| §3 | Concurrent operations without lost updates | `app/shard.py` row locks, receipts | `experiment_3.sh`: 40 writes, exact balance 1000.00 | Verified (Mac) |
| §4 | Balance and local ACID writes | `app/shard.py` | Protocol tests and experiment 3 | Verified (Mac) |
| §4 | One-transaction same-shard transfer | `app/shard.py:local_operation` | `experiment_5.sh` | Verified (Mac) |
| §4–5 | Real PREPARE, COMMIT, ABORT | `app/shard.py` PostgreSQL prepared XIDs | `experiment_5`, vote-NO test and real `pg_prepared_xacts` evidence | Verified (Mac) |
| §5 | Durable state machine and COMMIT-before-send | `db/coordinator.sql`, `app/coordinator.py` | Fault injection states and SQL query | Verified (Mac) |
| §5 | Vote NO after previous YES → ABORT | Participant fault header + Coordinator | `test_prepared_participant_and_second_vote_no` passed | Verified (Mac) |
| §5 recovery B | Stop after all PREPARED, no decision | Durable PREPARED + recover ABORT | `experiment_6.sh`: aborted after restart | Verified (Mac) |
| §5 recovery C | Crash after COMMIT decided | Durable COMMIT + recovery retries | `experiment_6.sh`: committed after restart | Verified (Mac) |
| §5 | Idempotent Phase 2, exactly-once effect | Receipt in prepared TX, tombstone, advisory lock | 5 protocol tests passed, including duplicate COMMIT/ABORT | Verified (Mac) |
| §5 | PENDING/UNKNOWN transaction status query | `GET /transactions/{id}`, `/requests/{id}` | Participant disconnection: PENDING then COMMITTED | Verified (Mac) |
| §6.1 | DB shard distribution + Gateway route | See §2–3 | `experiment_1.sh`: PASS | Verified (Mac) |
| §6.2 | Load distribution logs on both replicas | Replica response ID + structured logs | `experiment_2.sh`: PASS | Verified (Mac) |
| §6.3 | Concurrent operations through replicas | DB row locking | `experiment_3.sh`: PASS | Verified (Mac) |
| §6.4 | Replica crash under load | Health monitor + retry | `experiment_4.sh`: PASS | Verified (Mac) |
| §6.5 | Local/cross-shard transfers | Local ACID + 2PC | `experiment_5.sh`: PASS | Verified (Mac) |
| §6.6 | Coordinator crash at durable COMMIT | Real `os._exit(91)` fault injection | `experiment_6.sh`: both crash points PASS | Verified (Mac) |
| §6.7 | Concurrent overlapping transfers | 2PC + SQL locks + conservation assertions | `experiment_7.sh`: 12 commits; conserved 4000.00 | Verified (Mac) |
| §7 +12% | Online migration to C / snapshot / delta / epoch / 2PC | Design proposal only | No implementation or tests | Not Implemented |
| §8 +10% | Custom self-healing controller | Design proposal only | No implementation or tests | Not Implemented |
| §9 | Compose, source, report, demo, publication instructions | `Dockerfile`, Compose, `README.md`, `docs/*`, output PDF | Local Docker deployment validated; publishing to personal accounts pending | Partial |

## Verification: initial sandbox and student's Mac (2026-10-25)

1. `python3 -m compileall -q app tests scripts` — **PASS** (syntax compiled without errors).
2. `python3 -m unittest discover -s tests/unit -v` — **PASS**, four tests in 0.002 seconds.
3. `yaml.safe_load('docker-compose.yml')` — **PASS**, all ten service definitions parsed. This is *not* Compose semantic/build validation.
4. In the initial sandbox, `docker info` was **NOT RUN** because Docker was unavailable. The student subsequently ran Docker 29.1.3 and Compose 2.40.3 on an Apple Silicon Mac.
5. Initial package-index timeouts were resolved via the reachable USTC PyPI mirror during the student's actual Docker image build.
6. **Mac live evidence:** all seven mandatory experiment scripts passed, five protocol tests passed, both Coordinator crash points recovered, and participant outage remained PENDING until B returned. PostgreSQL showed `max_prepared_transactions=100` and no leftover prepared XIDs after resolution.
7. Database durability: after restarting all three PostgreSQL containers, both observed balances and the durable COMMIT row were unchanged.
8. Last combined pytest integration run: **10 passed in 2.96 seconds**, without cache warnings. A subsequent seven-image rebuild, six-container application recreate, and CLI smoke passed. Four unit tests also passed inside the rebuilt test-runner. The seven mandatory experiments plus five protocol tests were then rerun on the rebuilt images and **all passed again**. A fresh participant-disconnect recovery test also **passed**; all core services were healthy afterward. See `results/MAC_VALIDATION_2026-10-25.md` for the startup-deadlock diagnosis/fix.

## Final acceptance instructions on a Docker machine

```bash
cp .env.example .env              # change secret values
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
bash scripts/run_all_experiments.sh
bash scripts/experiment_participant_disconnect.sh
docker compose logs --no-color gateway coordinator bank-a1 bank-a2 bank-b1 bank-b2
```

The listed results are transcribed from genuine Mac terminal outputs supplied by the student. Final image rebuild, CLI smoke, unit tests, all seven post-rebuild experiments and repeat participant-disconnect test are **complete**. Personal-account publication remains outstanding. Never label a test as passed merely because its script exists.

