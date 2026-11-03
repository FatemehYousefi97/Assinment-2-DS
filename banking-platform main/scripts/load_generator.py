"""Experiment 4: continuous requests while bank-a1 is forcibly stopped."""
import collections
import os
import sys
import time

import httpx


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    base = os.environ.get("GATEWAY_URL", "http://gateway:8000")
    seen = collections.Counter()
    failed = []
    deadline = time.monotonic() + duration
    with httpx.Client(timeout=6) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(base + "/accounts/A0095/balance")
                if response.status_code != 200:
                    failed.append(f"HTTP {response.status_code}: {response.text}")
                else:
                    seen[response.json()["replica"]] += 1
            except httpx.RequestError as exc:
                failed.append(str(exc))
            time.sleep(0.05)
    print("EXP4 replica distribution:", dict(seen), flush=True)
    print("EXP4 failed requests:", len(failed), failed[:5], flush=True)
    if seen["A2"] == 0 or failed:
        raise SystemExit(1)
    print("EXP4 PASS: traffic continued on a healthy replica", flush=True)


if __name__ == "__main__":
    main()

