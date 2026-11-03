"""Inject a crash *after* a durable coordinator state transition.

Executed within the test-runner Docker Compose service, not on the host.
"""
import os
import sys
import time
from uuid import UUID

import httpx
import psycopg


def main():
    point = sys.argv[1]
    if point not in ("after_prepare", "after_commit_decision"):
        raise SystemExit("Invalid crash point")
    request_id = os.environ["REQUEST_ID"]
    UUID(request_id)
    src, dst = ("A0091", "A1091") if point == "after_commit_decision" else ("A0092", "A1092")
    data = {"request_id": request_id, "from_account": src,
            "to_account": dst, "amount": "7.00"}
    print(f"Injecting {point} for request_id={request_id}", flush=True)
    try:
        with httpx.Client(timeout=20) as client:
            client.post("http://coordinator:8000/transfers", json=data, headers={
                "X-Internal-Token": os.environ["INTERNAL_TOKEN"], "X-Fault-At": point})
    except httpx.RequestError:
        pass  # Expected: os._exit(91) drops the connection abruptly.

    expected = "PREPARED" if point == "after_prepare" else "COMMIT_DECIDED"
    deadline = time.monotonic() + 20
    with psycopg.connect(os.environ["COORD_DB_URL"]) as db:
        while time.monotonic() < deadline:
            row = db.execute("SELECT state,decision FROM distributed_transfers WHERE request_id=%s",
                             (request_id,)).fetchone()
            if row is not None and row[0] == expected:
                assert row[1] == (None if point == "after_prepare" else "COMMIT")
                print(f"CRASH VERIFIED: state={row[0]} decision={row[1]}", flush=True)
                return
            time.sleep(0.25)
    raise SystemExit(f"Expected durable crash state {expected}, observed {row}")


if __name__ == "__main__":
    main()

