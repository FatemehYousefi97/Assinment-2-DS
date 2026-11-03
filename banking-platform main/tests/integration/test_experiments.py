"""Live tests 1,2,3,5,7. Crash orchestration for 4,6 is in scripts/."""
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import httpx
import psycopg

from .conftest import await_all_replicas, await_status, balance, transfer


def test_experiment_1_shard_distribution(api):
    with psycopg.connect(os.environ["DB_A_URL"]) as db_a, psycopg.connect(os.environ["DB_B_URL"]) as db_b:
        assert db_a.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1000
        assert db_b.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1000
        assert db_a.execute("SELECT COUNT(*) FROM accounts WHERE account_id > 'A1000'").fetchone()[0] == 0
        assert db_b.execute("SELECT COUNT(*) FROM accounts WHERE account_id <= 'A1000'").fetchone()[0] == 0
    assert api.get("/accounts/A0001/balance").json()["shard"] == "A"
    assert api.get("/accounts/A1001/balance").json()["shard"] == "B"
    assert api.get("/accounts/A2000/balance").json()["shard"] == "B"
    print("EXPERIMENT 1 PASS: exclusive DB ownership and correct Gateway routes")


def test_experiment_2_round_robin_replicas(api):
    await_all_replicas(api)
    seen = {api.get("/accounts/A0010/balance").json()["replica"] for _ in range(16)}
    assert seen == {"A1", "A2"}, seen
    seen_b = {api.get("/accounts/A1010/balance").json()["replica"] for _ in range(16)}
    assert seen_b == {"B1", "B2"}, seen_b
    print("EXPERIMENT 2 PASS: both A/B replicas selected:", seen, seen_b)


def test_experiment_3_concurrent_deposits_withdrawals(api):
    account = "A0090"
    initial = balance(api, account)

    def job(i):
        verb = "deposit" if i % 2 == 0 else "withdraw"
        with httpx.Client(base_url=str(api.base_url), timeout=20) as worker:
            response = worker.post(f"/accounts/{verb}", json={
                "account_id": account, "amount": "1.00", "request_id": str(uuid4())})
        assert response.status_code == 200, response.text
        return response.json()["replica"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        used = set(executor.map(job, range(40)))
    assert used == {"A1", "A2"}, used
    assert balance(api, account) == initial
    print("EXPERIMENT 3 PASS: 40 concurrent operations, final balance preserved", initial)


def test_experiment_5_atomic_local_and_cross_shard(api):
    accounts = ("A0020", "A0021", "A0030", "A1030")
    before = {a: balance(api, a) for a in accounts}
    local = transfer(api, accounts[0], accounts[1], "3.00")
    assert local.status_code == 200, local.text
    assert local.json()["status"] == "COMPLETED"
    distributed = transfer(api, accounts[2], accounts[3], "4.00")
    assert distributed.status_code in (200, 202), distributed.text
    tx = await_status(api, distributed.json()["tx_id"])
    assert tx["status"] == "COMMITTED", tx
    assert tx["acknowledgements"] == {"A": True, "B": True}, tx
    after = {a: balance(api, a) for a in accounts}
    assert after[accounts[0]] == before[accounts[0]] - 3
    assert after[accounts[1]] == before[accounts[1]] + 3
    assert after[accounts[2]] == before[accounts[2]] - 4
    assert after[accounts[3]] == before[accounts[3]] + 4
    print("EXPERIMENT 5 PASS: single-shard atomic transaction and durable 2PC")


def test_experiment_7_overlapping_concurrent_distributed_transfers(api):
    accounts = ("A0040", "A0041", "A1040", "A1041")
    total_before = sum((balance(api, a) for a in accounts), Decimal(0))
    routes = [("A0040", "A1040"), ("A1040", "A0041"),
              ("A0041", "A1041"), ("A1041", "A0040")]

    def send(i):
        source, dest = routes[i % len(routes)]
        with httpx.Client(base_url=str(api.base_url), timeout=40) as client:
            response = transfer(client, source, dest, "2.00")
        assert response.status_code in (200, 202, 409), response.text
        return response.json()["tx_id"]

    with ThreadPoolExecutor(max_workers=6) as executor:
        ids = list(executor.map(send, range(12)))
    states = [await_status(api, tx_id, timeout=120)["status"] for tx_id in ids]
    assert set(states) <= {"COMMITTED", "ABORTED"}, states
    assert states.count("COMMITTED") >= 1, states
    total_after = sum((balance(api, a) for a in accounts), Decimal(0))
    assert total_before == total_after, (total_before, total_after)
    print("EXPERIMENT 7 PASS: overlapping transfers; committed=%d aborted=%d conservation=%s" %
          (states.count("COMMITTED"), states.count("ABORTED"), total_after))

