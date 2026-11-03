# Demo recording plan (maximum 15 minutes)

Use a clean, disposable Docker deployment. Show your real terminal and actual outputs; no prerecorded fictional PASS text. Keep a timer visible.

| Timing | Action | Proof to show |
| --- | --- | --- |
| 0:00–1:00 | `docker compose up -d && docker compose ps` | Ten configured services (test-runner on demand), four banking replicas, DBs, Gateway, Coordinator |
| 1:00–2:00 | `curl http://localhost:8080/routing` | Two shard entries and two healthy replicas each |
| 2:00–3:00 | `docker compose exec db-a ...` and `db-b ...` | Exclusive A0001–A1000 vs A1001–A2000 row storage |
| 3:00–4:00 | Repeated `python3 -m app.client balance A0500` plus logs | A1/A2 Round Robin; no unrelated shard |
| 4:00–5:00 | Deposit and withdrawal by CLI | Exact balance, request ID behavior |
| 5:00–6:00 | Same-shard A0500→A0600 and cross-shard A0500→A1500 | Local vs distributed path; query transaction ID |
| 6:00–7:30 | Run experiment 3 via test-runner | Concurrent updates, correct final balance |
| 7:30–9:00 | `bash scripts/experiment_4.sh` | A1 stopped, A2 serves traffic; no unintended shard failover |
| 9:00–11:30 | `bash scripts/experiment_6.sh` | Forced Coordinator crashes, durable COMMIT or ABORT, restart and recovery |
| 11:30–12:30 | SQL `pg_prepared_xacts` and Coordinator decision table | Prepared transactions gone after finalization; ACKs stored |
| 12:30–13:30 | Experiment 7 test | Overlapping cross-shard transfers and conservation |
| 13:30–14:30 | Protocol duplicate test and report/diagram | Idempotence proof, brief state machine and limitations |
| 14:30–15:00 | `docker compose ps`, final summary | Services available, note optional bonuses not implemented |

Useful commands:

```bash
docker compose --profile test run --rm -T test-runner pytest -s -v \
  tests/integration/test_experiments.py -k experiment_3
bash scripts/experiment_4.sh
bash scripts/experiment_6.sh
docker compose --profile test run --rm -T test-runner pytest -s -v \
  tests/integration/test_experiments.py -k experiment_7
docker compose exec db-a psql -U banking -d banking -c "SELECT gid FROM pg_prepared_xacts"
docker compose exec db-coordinator psql -U banking -d banking -c \
  "SELECT state,decision,acknowledgements FROM distributed_transfers ORDER BY created_at DESC LIMIT 5"
```

The optional `experiment_participant_disconnect.sh` provides an extra demonstration if enough time remains. The recovery experiments take real container stop/start time; rehearse with a stopwatch and reduce narration as necessary.

