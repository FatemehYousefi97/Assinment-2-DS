"""Command-line banking client. All requests go through the public Gateway."""
import argparse
import json
import os
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description="Distributed Banking Client")
    parser.add_argument("--gateway", default=os.environ.get("GATEWAY_URL", "http://localhost:8080"))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("balance")
    p.add_argument("account")
    for name in ("deposit", "withdraw"):
        p = sub.add_parser(name)
        p.add_argument("account")
        p.add_argument("amount", help="Decimal string, e.g. 10.25")
        p.add_argument("--request-id", default=None)
    p = sub.add_parser("transfer")
    p.add_argument("source")
    p.add_argument("destination")
    p.add_argument("amount")
    p.add_argument("--request-id", default=None)
    for name in ("status", "request"):
        p = sub.add_parser(name)
        p.add_argument("id")
    args = parser.parse_args()
    if args.command == "balance":
        method, path, data = "GET", f"/accounts/{args.account}/balance", None
    elif args.command in ("deposit", "withdraw"):
        method, path = "POST", f"/accounts/{args.command}"
        data = {"account_id": args.account, "amount": args.amount,
                "request_id": args.request_id or str(uuid4())}
    elif args.command == "transfer":
        method, path = "POST", "/transfers"
        data = {"from_account": args.source, "to_account": args.destination,
                "amount": args.amount, "request_id": args.request_id or str(uuid4())}
    else:
        method, path, data = "GET", f"/{'transactions' if args.command == 'status' else 'requests'}/{args.id}", None
    try:
        with httpx.Client(timeout=35) as client:
            result = client.request(method, args.gateway + path, json=data)
        print(json.dumps(result.json(), indent=2, ensure_ascii=False))
        if result.status_code >= 400:
            raise SystemExit(1)
    except httpx.RequestError as exc:
        print(f"Connection error: {exc}")
        if data is not None:
            print(f"Retry/query using the SAME request ID: {data['request_id']}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()

