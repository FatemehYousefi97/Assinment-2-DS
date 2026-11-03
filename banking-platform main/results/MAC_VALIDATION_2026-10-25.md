# Docker/PostgreSQL validation on student's Mac - 2026-10-25

Evidence source: actual terminal outputs copied by the student from
`/Users/Fatima/Documents/ترم ۳/assingment2 DS/banking-platform` into the
project collaboration. These checks were **run on the student's Mac**, not
inside the original source-generation container. This file records only
observed results; it is not a synthetic test log.

## Runtime

- Host: Apple Silicon Mac (`arm64`).
- Docker Engine 29.1.3; Docker Compose v2.40.3-desktop.1.
- Runtime: Python 3.12.15, pytest 8.3.5, PostgreSQL 16 Alpine.
- Nine core services: `db-a`, `db-b`, `db-coordinator`, `bank-a1`,
  `bank-a2`, `bank-b1`, `bank-b2`, `coordinator`, `gateway`.
- Docker images built using a reachable USTC PyPI mirror after timeouts from
  the normal `pypi.org` index. Docker Desktop Documents Folder access was
  enabled to allow mounting SQL initialization scripts.

## All seven mandatory experiments: observed PASS

| No. | Script | Actual evidence from student's terminal |
| --- | --- | --- |
| 1 | `experiment_1.sh` | Exclusive database ownership and correct Gateway shard routes; `1 passed` |
| 2 | `experiment_2.sh` | A1/A2 and B1/B2 each selected by load balancer; `1 passed` |
| 3 | `experiment_3.sh` | 40 concurrent operations; final tested balance `1000.00`; `1 passed` |
| 4 | `experiment_4.sh` | Bank A1 stopped while traffic ran; A1 served 11 requests and A2 172; **zero failed requests**; replica restored |
| 5 | `experiment_5.sh` | Local atomic transfer and durable cross-shard 2PC; `1 passed` |
| 6 | `experiment_6.sh` | Coordinator after-PREPARE hard crash recovered to `ABORTED`; after-COMMIT_DECIDED crash recovered to `COMMITTED`; prepared-XID cleanup checked |
| 7 | `experiment_7.sh` | 12 overlapping distributed transfers `COMMITTED`, 0 aborted; tested sum conserved at `4000.00`; `1 passed` |

### Supplemental protocol and regression tests

- `pytest -s -v tests/integration/test_protocol.py`: **5 passed**.
  Includes duplicate deposit/transfer request ID, conflicting request reuse,
  first YES/second NO vote with durable ABORT and duplicate ABORT, repeated
  COMMIT, and insufficient-funds ABORT.
- After adding `PYTEST_ADDOPTS=-p no:cacheprovider`, full non-disruptive
  `pytest -s -v tests/integration`: **10 passed in 2.96s**, with **no cache
  warnings**. This combined suite contains the 5 regular experiment tests
  (experiments 1, 2, 3, 5, 7) and all 5 protocol tests; disruptive experiments
  4 and 6 are separate scripts.

### Coordinator crash evidence

- After PREPARE, request `aa1ac4ae-285c-429c-9a70-6f6a425d9e8c`:
  persisted `PREPARED`, decision `None`; after restart: `ABORTED`, receipts
  and prepared-XID cleanup verified.
- After COMMIT decision, request `6135efef-8198-4047-8db2-87906641a622`:
  persisted `COMMIT_DECIDED`, decision `COMMIT`; after restart: `COMMITTED`,
  receipts and cleanup verified.

### Participant outage and observed regression fix

An initial `experiment_participant_disconnect.sh` run failed (do **not** mark
that first attempt successful). `docker compose start coordinator` attempted
to start the deliberately failed dependency `bank-b1`. At the same time, both
B replicas blocked during `INSERT INTO accounts ... ON CONFLICT DO NOTHING`
at application startup, waiting on a prepared transaction's `transactionid`
lock. Diagnostic SQL reported:

- `pg_prepared_xacts`: `bank_B_69aa4527-0dd1-4773-9e82-2fe43b4c62af`.
- `pg_stat_activity`: 2 sessions waiting on `Lock / transactionid`, both in
  the bulk seed `INSERT INTO accounts`.

Implemented two real fixes:

1. Shard startup skips the bulk insert if the shard account set is already
   complete. The student rebuilt and recreated B1/B2; both became healthy
   even while the prepared transaction still existed.
2. The outage script starts Coordinator via
   `docker compose up -d --no-deps --no-build coordinator`, avoiding an
   accidental restart of the deliberately offline shard.

First, the previously stuck request
`4ee15020-74c8-44e6-a616-4ea6bbf8236f` was independently verified as
`COMMITTED` with both durable receipts and no leftover prepared XIDs.

The corrected outage test was then rerun with new request
`fbb377f8-cdd9-463f-80de-32b27fc9753f` and tx ID
`f1d1089d-9efc-40f0-84f1-ccb0f8c64b14`:

- Hard Coordinator crash after durable `COMMIT_DECIDED` confirmed.
- Both `bank-b1` and `bank-b2` were intentionally stopped.
- Recovered Coordinator returned `PENDING`, decision `COMMIT`, with only the
  A acknowledgement true; **B remained offline**.
- After B replicas returned, result reached `COMMITTED`, both receipts and
  cleanup verified. Script ended with `Participant-disconnect recovery PASS`.

## PostgreSQL configuration and durability

- `SHOW max_prepared_transactions` returned **100** on each of db-a, db-b,
  db-coordinator.
- `SELECT gid FROM pg_prepared_xacts` returned **0 rows** on db-a and db-b
  after the fault experiments completed.
- Before restarting all three PostgreSQL containers, account A0091 had
  `979.00` and A1091 had `1021.00`; the Coordinator row for request
  `fbb377f8-cdd9-463f-80de-32b27fc9753f` showed `COMPLETED` / `COMMIT`,
  acknowledgements `{"A": true, "B": true}`.
- After `docker compose restart db-a db-b db-coordinator`, **all three
  values were unchanged** and every core container was running/healthy
  (except Gateway, which reports `Up` without an explicit healthcheck).

## Scope and remaining checks

- Observed seven mandatory experiments and supplemental crash/idempotency
  tests: **PASS** as described above.
- The student's Mac images for B replicas were rebuilt after the startup
  fix. Subsequently, the student supplied the full output of the final
  seven-image Compose build (`bank-a1`, `bank-a2`, `bank-b1`, `bank-b2`,
  `coordinator`, `gateway`, `test-runner`): **7/7 successfully built** using
  cached dependencies. All six running application containers were then
  explicitly recreated from the rebuilt images (four bank replicas, one
  Coordinator and one Gateway); `docker compose ps -a` confirmed **all four
  replicas and the Coordinator healthy**, all three PostgreSQL containers
  healthy and Gateway Up. Fresh post-recreate smoke checks then passed:
  Gateway `/health` returned `{"healthy":true,"role":"gateway"}`;
  the CLI read A0500=1000.00, deposited 1.00 (balance 1001.00), withdrew
  1.00 (balance restored to 1000.00), and transferred 1.00 from A0500 to
  A1500. The transfer returned `COMMITTED` / `COMPLETED`, decision `COMMIT`,
  both A and B acknowledgements true, tx ID
  `9468d47e-9046-49f3-bdf1-81cdf0396d4b`. Both CLI `status` (transaction
  ID) and CLI `request` (request ID
  `264dd0c3-3ce8-4c27-b333-ace90b9d8bd3`) returned the same durable
  `COMMITTED` result. Four unit tests were run inside the rebuilt test-runner:
  **4 passed in 0.002s**.

### Final full regression on rebuilt application images

After recreating all six application containers, the student reran
`bash scripts/run_all_experiments.sh` and supplied its full 416-line
terminal output. **All seven mandatory experiments and five protocol tests
passed again**, with no pytest cache warnings:

- Experiment 1: `1 passed in 0.18s`.
- Experiment 2: `1 passed in 0.40s` (all A1/A2/B1/B2 selected).
- Experiment 3: `1 passed in 0.28s`, 40 concurrent operations, balance 1000.00.
- Experiment 5: `1 passed in 0.39s`, local atomic and distributed 2PC.
- Experiment 7: `1 passed in 1.12s`, 12 commits, 0 aborts, sum 4000.00.
- Supplemental protocol: `5 passed in 1.06s`.
- Experiment 4: A1 stopped under live load; A1 served 11 and A2 served 172
  requests, **0 failed**; A1 restored.
- Experiment 6: hard crash after PREPARE (request
  `5456c57d-a4fe-429f-9f26-1427e2dd6503`) recovered `ABORTED`, and hard
  crash after COMMIT_DECIDED (request
  `0b3a5f78-22ec-4945-aceb-418d01899c84`) recovered `COMMITTED`; durable
  participant receipts and prepared-XID cleanup verified in both cases.

The run ended with `ALL COMPOSE EXPERIMENTS FINISHED`.

### Final post-build participant-outage regression: PASS

The student then reran `bash scripts/experiment_participant_disconnect.sh`
on those same rebuilt images:

- Request ID `cef15714-f4ac-401e-9481-ccfe34f1772c`, transaction ID
  `ae732c23-142b-4d3f-a2b6-384385a6d129`.
- Durable `COMMIT_DECIDED` / decision `COMMIT` confirmed immediately before
  deliberate Coordinator crash.
- Both B replicas stopped. Coordinator restarted with `--no-deps` while B
  remained offline; status query confirmed `PENDING`, ACKs `{"A":true}`.
- Both B replicas restored; recovery reached `COMMITTED`, with both durable
  receipts and prepared-XID cleanup verified.
- Final script line: **`Participant-disconnect recovery PASS`**.
- A final `docker compose ps -a` showed all four banking replicas, the
  Coordinator and all three PostgreSQL servers **healthy**, and Gateway Up.
- GitHub publication and Docker Hub pushes: **NOT PERFORMED**; require the
  student's own accounts and publication decision.
- Bonus live re-sharding and autonomous self-healing: **NOT IMPLEMENTED**;
  require explicit approval per the original project instructions.
- Development-only secrets and enabled fault injection must not be shipped
  as production settings. `.env` is excluded from the deliverable archive.
