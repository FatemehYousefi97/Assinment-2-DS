"""Public API: clients are unaware of shard and replica placement."""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .routing import NoHealthyReplica, ReplicaPool
from .schemas import AmountRequest, TransferRequest
from .sharding import ShardMap

MAP = ShardMap.load(os.environ.get("SHARD_MAP_PATH", str(Path(__file__).parents[1] / "config/shards.json")))
POOL = ReplicaPool(MAP)
COORDINATOR = os.environ.get("COORDINATOR_URL", "http://coordinator:8000")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    POOL.start()
    yield
    POOL.close()


app = FastAPI(title="Shard-Aware Banking Gateway", version="1.0", lifespan=lifespan)


def owner(account_id: str):
    try:
        return MAP.owner(account_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def forward(shard, method, path, payload=None):
    try:
        response = POOL.request(shard, method, path, json=payload)
    except NoHealthyReplica as exc:
        raise HTTPException(503, str(exc)) from exc
    return JSONResponse(response.json(), status_code=response.status_code)


def to_coordinator(method, path, payload=None):
    try:
        with httpx.Client(timeout=30) as client:
            response = client.request(method, COORDINATOR + path, json=payload,
                                      headers={"X-Internal-Token": os.environ.get("INTERNAL_TOKEN", "")})
        return JSONResponse(response.json(), status_code=response.status_code)
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(503, "Coordinator unavailable; retry/query status with same request ID") from exc


@app.get("/health")
def health():
    return {"healthy": True, "role": "gateway"}


@app.get("/routing")
def routing():
    return POOL.members()


@app.get("/accounts/{account_id}/balance")
def balance(account_id: str):
    return forward(owner(account_id), "GET", f"/balance/{account_id}")


@app.post("/accounts/deposit")
def deposit(request: AmountRequest):
    return forward(owner(request.account_id), "POST", "/deposit", request.model_dump(mode="json"))


@app.post("/accounts/withdraw")
def withdraw(request: AmountRequest):
    return forward(owner(request.account_id), "POST", "/withdraw", request.model_dump(mode="json"))


@app.post("/transfers")
def transfer(request: TransferRequest):
    src = owner(request.from_account)
    dst = owner(request.to_account)
    payload = request.model_dump(mode="json")
    if src == dst:
        return forward(src, "POST", "/transfer-local", payload)
    return to_coordinator("POST", "/transfers", payload)


@app.get("/transactions/{tx_id}")
def status(tx_id: UUID):
    return to_coordinator("GET", f"/transactions/{tx_id}")


@app.get("/requests/{request_id}")
def by_request_id(request_id: UUID):
    return to_coordinator("GET", f"/requests/{request_id}")
