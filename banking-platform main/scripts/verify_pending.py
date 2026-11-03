"""A recorded COMMIT must remain pending while one participant is unreachable."""
import os
import sys
import time

import httpx


def main():
    request_id = sys.argv[1]
    deadline = time.monotonic() + 20
    with httpx.Client(timeout=5) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(f"http://coordinator:8000/requests/{request_id}",
                                      headers={"X-Internal-Token": os.environ["INTERNAL_TOKEN"]})
                if response.status_code == 200:
                    state = response.json()
                    assert state["decision"] == "COMMIT", state
                    assert state["status"] == "PENDING", state
                    print("PENDING VERIFIED DURING PARTICIPANT OUTAGE:", state)
                    return
            except httpx.RequestError:
                pass
            time.sleep(0.5)
    raise SystemExit("Coordinator never reported pending COMMIT during participant outage")


if __name__ == "__main__":
    main()

