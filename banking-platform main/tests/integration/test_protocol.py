"""Idempotency and participant-vote tests against live PostgreSQL/replicas."""
import os
from decimal import Decimal
from uuid import uuid4

import httpx

from .conftest import await_status, balance, transfer


def test_idempotent_deposit_and_request_key_conflict(api):
    account, key = "A0070", str(uuid4())
    initial = balance(api, account)
    payload = {"account_id": account, "amount": "2.75", "request_id": key}
    first = api.post("/accounts/deposit", json=payload)
    second = api.post("/accounts/deposit", json=payload)
    assert first.status_code == second.status_code == 200
    assert second.json()["replayed"] is True
    assert balance(api, account) == initial + Decimal("2.75")
    invalid = api.post("/accounts/deposit", json={**payload, "amount": "3.00"})
    assert invalid.status_code == 409


def test_cross_shard_retry_exactly_once(api):
    source, target, request_id = "A0071", "A1071", str(uuid4())
    before_src, before_dst = balance(api, source), balance(api, target)
    first = transfer(api, source, target, "3.25", request_id=request_id)
    assert first.status_code in (200, 202), first.text
    repeated = transfer(api, source, target, "3.25", request_id=request_id)
    assert repeated.status_code in (200, 202), repeated.text
    assert first.json()["tx_id"] == repeated.json()["tx_id"]
    result = await_status(api, first.json()["tx_id"])
    assert result["status"] == "COMMITTED"
    assert balance(api, source) == before_src - Decimal("3.25")
    assert balance(api, target) == before_dst + Decimal("3.25")
    conflict = transfer(api, source, target, "3.26", request_id=request_id)
    assert conflict.status_code == 409


def test_prepared_participant_and_second_vote_no(api):
    """Real first-shard PREPARE; second shard deliberately rejects its vote."""
    src, dst = "A0080", "A1080"
    initial_src, initial_dst = balance(api, src), balance(api, dst)
    with httpx.Client(timeout=30) as client:
        result = client.post("http://coordinator:8000/transfers", json={
            "from_account": src, "to_account": dst,
            "amount": "12.50", "request_id": str(uuid4())}, headers={
                "X-Internal-Token": os.environ["INTERNAL_TOKEN"],
                "X-Fault-At": "second_participant_reject"})
    assert result.status_code in (409, 202), result.text
    outcome = await_status(api, result.json()["tx_id"])
    assert outcome["status"] == "ABORTED", outcome
    assert balance(api, src) == initial_src
    assert balance(api, dst) == initial_dst
    with httpx.Client(timeout=5) as client:
        for shard in ("a1", "b1"):
            reply = client.post(f"http://bank-{shard}:8000/internal/abort",
                                headers={"X-Internal-Token": os.environ["INTERNAL_TOKEN"]},
                                json={"tx_id": result.json()["tx_id"]})
            assert reply.status_code == 200, reply.text
    print("PREPARED first participant, NO second participant, durable ABORT, duplicate ABORT safe")


def test_duplicate_commit_messages(api):
    response = transfer(api, "A0081", "A1081", "2.25")
    assert response.status_code in (200, 202)
    result = await_status(api, response.json()["tx_id"])
    assert result["status"] == "COMMITTED"
    with httpx.Client(timeout=10) as client:
        for shard in ("a1", "b1"):
            for _ in range(2):
                replay = client.post(f"http://bank-{shard}:8000/internal/commit",
                    headers={"X-Internal-Token": os.environ["INTERNAL_TOKEN"]},
                    json={"tx_id": result["tx_id"]})
                assert replay.status_code == 200, replay.text
                assert replay.json()["status"] == "COMMITTED"


def test_insufficient_funds_aborts_all_participants(api):
    source, target = "A0082", "A1082"
    before = balance(api, source), balance(api, target)
    response = transfer(api, source, target, "999999.00")
    assert response.status_code in (409, 202), response.text
    outcome = await_status(api, response.json()["tx_id"])
    assert outcome["status"] == "ABORTED", outcome
    assert (balance(api, source), balance(api, target)) == before

