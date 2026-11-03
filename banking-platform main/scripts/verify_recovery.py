"""Verify coordinator decision after restart, including both participant receipts."""
import os
import sys
import time

import httpx
import psycopg


def main():
    request_id, expected = sys.argv[1:3]
    if expected not in ("COMMITTED", "ABORTED"):
        raise SystemExit("Invalid expected decision")
    token = os.environ["INTERNAL_TOKEN"]
    deadline = time.monotonic() + 90
    with httpx.Client(timeout=5) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(f"http://coordinator:8000/requests/{request_id}",
                                      headers={"X-Internal-Token": token})
                if response.status_code == 200 and response.json()["status"] == expected:
                    body = response.json()
                    assert body["state"] == "COMPLETED"
                    assert body["acknowledgements"] == {"A": True, "B": True}
                    break
            except httpx.RequestError:
                pass
            time.sleep(1)
        else:
            raise SystemExit(f"Recovery did not reach {expected}")
    with psycopg.connect(os.environ["DB_A_URL"]) as a, psycopg.connect(os.environ["DB_B_URL"]) as b:
        for name, conn in (("A", a), ("B", b)):
            count = conn.execute("SELECT count(*) FROM transfer_receipts WHERE tx_id=%s",
                                 (body["tx_id"],)).fetchone()[0]
            assert count == (1 if expected == "COMMITTED" else 0), (name, count)
            prepared = conn.execute("SELECT count(*) FROM pg_prepared_xacts WHERE gid=%s",
                                    (f"bank_{name}_{body['tx_id']}",)).fetchone()[0]
            assert prepared == 0, (name, prepared)
    print(f"RECOVERY PASS: request={request_id} status={expected}; durable receipts and prepared-xact cleanup verified")


if __name__ == "__main__":
    main()

