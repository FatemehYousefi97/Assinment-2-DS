import os
import time
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:8080")


@pytest.fixture(scope="session", autouse=True)
def gateway_ready():
    for _ in range(40):
        try:
            if httpx.get(GATEWAY + "/health", timeout=2).status_code == 200:
                return
        except httpx.RequestError:
            pass
        time.sleep(0.5)
    pytest.fail("Gateway did not become healthy")


@pytest.fixture
def api():
    with httpx.Client(base_url=GATEWAY, timeout=40) as client:
        yield client


def balance(api, account):
    resp = api.get(f"/accounts/{account}/balance")
    assert resp.status_code == 200, resp.text
    return Decimal(resp.json()["balance"])


def transfer(api, source, destination, amount="1.00", request_id=None):
    return api.post("/transfers", json={"from_account": source, "to_account": destination,
                                        "amount": amount, "request_id": request_id or str(uuid4())})


def await_status(api, tx_id, timeout=75):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = api.get(f"/transactions/{tx_id}")
        if response.status_code == 200 and response.json()["status"] != "PENDING":
            return response.json()
        time.sleep(1)
    pytest.fail(f"Transaction {tx_id} did not resolve within {timeout} seconds")


def await_all_replicas(api, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = api.get("/routing")
        if response.status_code == 200:
            rows = response.json()
            if all(len(rows[shard]) == 2 and all(entry["healthy"] for entry in rows[shard])
                   for shard in ("A", "B")):
                return
        time.sleep(0.5)
    pytest.fail("Not all four replicas became healthy")

