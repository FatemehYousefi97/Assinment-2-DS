"""Durable two-phase commit coordinator with repeatable recovery.

No COMMIT is issued before a durable COMMIT_DECIDED record. Any undecided
transaction after a crash is safely aborted, including participants whose
PREPARE answer was lost: participant tombstones fence late PREPARE messages.
"""
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from psycopg.types.json import Jsonb

from .routing import NoHealthyReplica, ReplicaPool
from .schemas import TransferRequest
from .sharding import ShardMap
from .util import connect, transaction_lock

logger = logging.getLogger("bank.coordinator")
MAP = ShardMap.load(os.environ.get("SHARD_MAP_PATH", str(Path(__file__).parents[1] / "config/shards.json")))
POOL = ReplicaPool(MAP)
RECOVERY_STOP = threading.Event()
RECOVERY_THREAD = None


def init_database():
    with connect() as conn:
        conn.execute((Path(__file__).parents[1] / "db/coordinator.sql").read_text())


def get_transaction(tx_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM distributed_transfers WHERE tx_id=%s", (tx_id,)).fetchone()


def set_state(tx_id, state, *, decision=None, reason=None):
    with connect() as conn:
        conn.execute("""UPDATE distributed_transfers SET state=%s,
            decision=COALESCE(%s,decision),reason=COALESCE(%s,reason),updated_at=now()
            WHERE tx_id=%s""", (state, decision, reason, tx_id))
    logger.info("coordinator_transition tx_id=%s state=%s decision=%s", tx_id, state, decision)


def acknowledged(tx_id, shard):
    with connect() as conn:
        conn.execute("""UPDATE distributed_transfers
            SET acknowledgements=jsonb_set(acknowledgements,ARRAY[%s],'true'::jsonb),updated_at=now()
            WHERE tx_id=%s""", (shard, tx_id))


def participant_payload(row, shard):
    if shard == row["source_shard"]:
        return {"tx_id": str(row["tx_id"]), "role": "DEBIT",
                "account_id": row["from_account"], "amount": str(row["amount"])}
    return {"tx_id": str(row["tx_id"]), "role": "CREDIT",
            "account_id": row["to_account"], "amount": str(row["amount"])}


def call_participant(shard, endpoint, payload, *, inject_vote_no=False):
    try:
        headers = {"X-Internal-Token": os.environ["INTERNAL_TOKEN"]}
        if inject_vote_no and os.environ.get("ENABLE_FAULT_INJECTION", "false").lower() == "true":
            headers["X-Inject-Vote-No"] = "true"
        response = POOL.request(shard, "POST", f"/internal/{endpoint}",
                                json=payload, headers=headers)
        if response.status_code != 200:
            logger.warning("participant_refused shard=%s endpoint=%s status=%s body=%s",
                           shard, endpoint, response.status_code, response.text[:250])
            return False
        body = response.json()
        if endpoint == "prepare":
            return body.get("vote") == "YES"
        return body.get("status") == ("COMMITTED" if endpoint == "commit" else "ABORTED")
    except (NoHealthyReplica, ValueError) as exc:
        logger.warning("participant_unreachable shard=%s endpoint=%s error=%s", shard, endpoint, exc)
        return False


def settle(row):
    """Retry-safe completion; only acknowledge proof of a participant outcome."""
    if row["decision"] not in ("COMMIT", "ABORT"):
        raise RuntimeError("Undecided transaction cannot enter phase 2")
    endpoint = "commit" if row["decision"] == "COMMIT" else "abort"
    for shard in sorted((row["source_shard"], row["target_shard"])):
        if row["acknowledgements"].get(shard) is True:
            continue
        if call_participant(shard, endpoint, {"tx_id": str(row["tx_id"])}):
            acknowledged(row["tx_id"], shard)
    refreshed = get_transaction(row["tx_id"])
    if all(refreshed["acknowledgements"].get(s) is True for s in
           (row["source_shard"], row["target_shard"])):
        set_state(row["tx_id"], "COMPLETED")


def inject(fault: str | None, expected: str):
    if fault == expected and os.environ.get("ENABLE_FAULT_INJECTION", "false").lower() == "true":
        logger.critical("INJECTED_CRASH point=%s; process stopping via os._exit", expected)
        os._exit(91)  # Deliberate ungraceful crash after durable state has been committed.


def run_new_transfer(tx_id, fault: str | None):
    """Caller holds the coordinator's database-scoped advisory lock."""
    row = get_transaction(tx_id)
    set_state(tx_id, "PREPARING")
    everyone_voted_yes = True
    reject_reason = None
    for index, shard in enumerate(sorted((row["source_shard"], row["target_shard"]))):
        if not call_participant(shard, "prepare", participant_payload(row, shard),
                                inject_vote_no=(index == 1 and fault == "second_participant_reject")):
            everyone_voted_yes = False
            reject_reason = f"Shard {shard} refused or timed out during PREPARE"
            break
    if everyone_voted_yes:
        set_state(tx_id, "PREPARED")
        inject(fault, "after_prepare")
        set_state(tx_id, "COMMIT_DECIDED", decision="COMMIT")
        inject(fault, "after_commit_decision")
    else:
        # Even participants not reached, or whose replies were lost, are sent
        # durable ABORT tombstones, preventing late PREPARE resurrection.
        set_state(tx_id, "ABORT_DECIDED", decision="ABORT", reason=reject_reason)
    settle(get_transaction(tx_id))


def recover_once():
    with connect() as conn:
        unfinished = conn.execute("SELECT tx_id FROM distributed_transfers WHERE state <> 'COMPLETED' ORDER BY created_at").fetchall()
    for candidate in unfinished:
        tx_id = candidate["tx_id"]
        try:
            # Skips in-flight synchronous coordinations without interrupting.
            with transaction_lock(tx_id, wait=False) as acquired:
                if not acquired:
                    continue
                row = get_transaction(tx_id)
                if not row or row["state"] == "COMPLETED":
                    continue
                if row["decision"] is None:
                    # A durable COMMIT was never chosen; abort is the only safe
                    # unilateral recovery action, even if all shards prepared.
                    set_state(tx_id, "ABORT_DECIDED", decision="ABORT",
                              reason="Recovered an undecided coordinator transaction")
                    row = get_transaction(tx_id)
                settle(row)
        except Exception:
            logger.exception("recovery_retry_later tx_id=%s", tx_id)


def recovery_loop():
    while not RECOVERY_STOP.is_set():
        try:
            recover_once()
        except Exception:
            logger.exception("recovery_scan_failed")
        RECOVERY_STOP.wait(2)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global RECOVERY_THREAD
    init_database()
    POOL.start()
    RECOVERY_STOP.clear()
    RECOVERY_THREAD = threading.Thread(target=recovery_loop, daemon=True, name="2pc-recovery")
    RECOVERY_THREAD.start()
    yield
    RECOVERY_STOP.set()
    RECOVERY_THREAD.join(timeout=4)
    POOL.close()


app = FastAPI(title="Durable 2PC Transaction Coordinator", lifespan=lifespan)


def view(row):
    if row["state"] == "COMPLETED":
        public = "COMMITTED" if row["decision"] == "COMMIT" else "ABORTED"
    else:
        public = "PENDING"
    return {"tx_id": str(row["tx_id"]), "request_id": str(row["request_id"]),
            "status": public, "state": row["state"], "decision": row["decision"],
            "acknowledgements": row["acknowledgements"], "reason": row["reason"]}


def transfer_status_code(body):
    # An aborted transfer must not look like successful banking completion.
    return {"PENDING": 202, "COMMITTED": 200, "ABORTED": 409}[body["status"]]


def require_internal(x_internal_token):
    secret = os.environ.get("INTERNAL_TOKEN")
    if not secret or x_internal_token != secret:
        raise HTTPException(403, "Invalid internal token")


@app.get("/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1")
    return {"healthy": True, "role": "coordinator"}


@app.post("/transfers")
def transfer(request: TransferRequest, x_internal_token: str | None = Header(None),
             x_fault_at: str | None = Header(None)):
    require_internal(x_internal_token)
    try:
        src, dst = MAP.owner(request.from_account), MAP.owner(request.to_account)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if src == dst:
        raise HTTPException(422, "Coordinator is only for cross-shard transfers")
    if x_fault_at and x_fault_at not in ("after_prepare", "after_commit_decision", "second_participant_reject"):
        raise HTTPException(422, "Invalid fault injection point")
    if x_fault_at and os.environ.get("ENABLE_FAULT_INJECTION", "false").lower() != "true":
        raise HTTPException(403, "Fault injection disabled")
    new_tx_id = uuid4()
    with transaction_lock(new_tx_id):
        with connect() as conn:
            inserted = conn.execute("""INSERT INTO distributed_transfers
                (tx_id,request_id,from_account,to_account,amount,source_shard,target_shard,state)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'INITIATED')
                ON CONFLICT(request_id) DO NOTHING RETURNING tx_id""",
                (new_tx_id, request.request_id, request.from_account, request.to_account,
                 request.amount, src, dst)).fetchone()
            if inserted is None:
                existing = conn.execute("SELECT * FROM distributed_transfers WHERE request_id=%s",
                                        (request.request_id,)).fetchone()
                if ((existing["from_account"], existing["to_account"], existing["amount"])
                        != (request.from_account, request.to_account, request.amount)):
                    raise HTTPException(409, "Request ID was reused with different transfer details")
                body = view(existing)
                return JSONResponse(body, status_code=transfer_status_code(body))
        try:
            run_new_transfer(new_tx_id, x_fault_at)
        except Exception:
            # The state remains durable. The recovery worker will abort an
            # undecided transaction or finish a decided one; no false success.
            logger.exception("transfer_interrupted tx_id=%s", new_tx_id)
        row = get_transaction(new_tx_id)
    body = view(row)
    return JSONResponse(body, status_code=transfer_status_code(body))


@app.get("/transactions/{tx_id}")
def transaction_status(tx_id: UUID, x_internal_token: str | None = Header(None)):
    require_internal(x_internal_token)
    row = get_transaction(tx_id)
    if not row:
        raise HTTPException(404, "Unknown transaction ID")
    return view(row)


@app.get("/requests/{request_id}")
def request_status(request_id: UUID, x_internal_token: str | None = Header(None)):
    require_internal(x_internal_token)
    with connect() as conn:
        row = conn.execute("SELECT * FROM distributed_transfers WHERE request_id=%s", (request_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Unknown request ID")
    return view(row)
