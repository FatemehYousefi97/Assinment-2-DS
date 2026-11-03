"""Stateless banking replica backed by one shard's authoritative PostgreSQL DB.

PREPARE TRANSACTION is a *real* PostgreSQL 2PC prepared transaction: changed
rows remain locked and invisible until COMMIT/ROLLBACK PREPARED. Every phase is
serialized per transaction ID using PostgreSQL session advisory locks shared
by all replicas of this shard.
"""
import logging
import os
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from psycopg import sql
from psycopg.types.json import Jsonb

from .schemas import AmountRequest, Phase2Request, PrepareRequest, TransferRequest
from .sharding import ShardMap
from .util import connect, payload_hash, transaction_lock

logger = logging.getLogger("bank.shard")
SHARD = os.environ.get("SHARD_NAME", "A")
REPLICA = os.environ.get("REPLICA_ID", "A1")
MAP = ShardMap.load(os.environ.get("SHARD_MAP_PATH", str(Path(__file__).parents[1] / "config/shards.json")))


def own(account: str):
    try:
        if MAP.owner(account) != SHARD:
            raise ValueError("Account belongs to another shard")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def internal_auth(x_internal_token: str | None = Header(None)):
    secret = os.environ.get("INTERNAL_TOKEN")
    if not secret or x_internal_token != secret:
        raise HTTPException(403, "Invalid internal token")


def initialize():
    shard = MAP.by_name[SHARD]
    with connect() as conn:
        conn.execute((Path(__file__).parents[1] / "db/shard.sql").read_text())
        # Do not re-run INSERT ... ON CONFLICT against every account on each
        # replica restart. A PostgreSQL prepared transaction can hold a row
        # update lock, and even ON CONFLICT DO NOTHING waits for that lock.
        # A plain MVCC count does not wait for those row locks, so fully
        # initialized replicas can start and receive COMMIT/ABORT messages.
        expected = shard.end - shard.start + 1
        existing = conn.execute(
            "SELECT count(*) AS n FROM accounts WHERE account_id BETWEEN %s AND %s",
            (f"A{shard.start:04d}", f"A{shard.end:04d}"),
        ).fetchone()["n"]
        if existing == expected:
            logger.info("accounts_already_seeded shard=%s count=%s", SHARD, existing)
            return
        with conn.transaction():
            conn.execute("""INSERT INTO accounts (account_id, balance)
                SELECT 'A' || lpad(n::text,4,'0'), 1000.00
                FROM generate_series(%s::integer,%s::integer) AS n
                ON CONFLICT (account_id) DO NOTHING""", (shard.start, shard.end))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize()
    logger.info("replica_started shard=%s replica=%s", SHARD, REPLICA)
    yield


app = FastAPI(title=f"Bank Shard {SHARD} Replica {REPLICA}", lifespan=lifespan)


@app.get("/health")
def health():
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return {"healthy": True, "shard": SHARD, "replica": REPLICA}
    except psycopg.Error as exc:
        raise HTTPException(503, "Database unavailable") from exc


@app.get("/balance/{account_id}")
def balance(account_id: str):
    own(account_id)
    with connect() as conn:
        row = conn.execute("SELECT balance FROM accounts WHERE account_id=%s", (account_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Account not found")
    logger.info("balance replica=%s account=%s", REPLICA, account_id)
    return {"account_id": account_id, "balance": str(row["balance"]),
            "shard": SHARD, "replica": REPLICA}


class Declined(Exception):
    pass


def local_operation(kind: str, request: AmountRequest | TransferRequest):
    if kind == "TRANSFER_LOCAL":
        own(request.from_account)
        own(request.to_account)
        accounts = sorted((request.from_account, request.to_account))
        digest = payload_hash(kind, request.from_account, request.to_account, request.amount)
    else:
        own(request.account_id)
        accounts = [request.account_id]
        digest = payload_hash(kind, request.account_id, request.amount)

    try:
        with connect() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL lock_timeout = '4000ms'")
                receipt = conn.execute("""INSERT INTO operation_receipts (request_id,request_hash,result)
                    VALUES (%s,%s,'{}'::jsonb) ON CONFLICT DO NOTHING RETURNING request_id""",
                    (request.request_id, digest)).fetchone()
                if receipt is None:
                    stored = conn.execute("SELECT request_hash,result FROM operation_receipts WHERE request_id=%s",
                                          (request.request_id,)).fetchone()
                    if stored["request_hash"] != digest:
                        raise HTTPException(409, "Request ID already used for a different operation")
                    result = stored["result"]
                    return {**result, "replica": REPLICA, "replayed": True}

                locked = conn.execute("SELECT account_id,balance FROM accounts WHERE account_id = ANY(%s) ORDER BY account_id FOR UPDATE",
                                      (accounts,)).fetchall()
                if len(locked) != len(accounts):
                    raise HTTPException(404, "Account not found")
                balances = {r["account_id"]: r["balance"] for r in locked}
                if kind == "DEPOSIT":
                    balances[request.account_id] += request.amount
                elif kind == "WITHDRAW":
                    if balances[request.account_id] < request.amount:
                        raise Declined("Insufficient funds")
                    balances[request.account_id] -= request.amount
                else:
                    if balances[request.from_account] < request.amount:
                        raise Declined("Insufficient funds")
                    balances[request.from_account] -= request.amount
                    balances[request.to_account] += request.amount
                for account in accounts:
                    conn.execute("UPDATE accounts SET balance=%s WHERE account_id=%s",
                                 (balances[account], account))
                result = {"status": "COMPLETED", "request_id": str(request.request_id),
                          "shard": SHARD, "balances": {k: str(v) for k, v in balances.items()}}
                conn.execute("UPDATE operation_receipts SET result=%s WHERE request_id=%s",
                             (Jsonb(result), request.request_id))
        logger.info("local_commit replica=%s kind=%s request_id=%s", REPLICA, kind, request.request_id)
        return {**result, "replica": REPLICA, "replayed": False}
    except Declined as exc:
        raise HTTPException(409, str(exc)) from exc
    except (psycopg.errors.LockNotAvailable, psycopg.errors.DeadlockDetected) as exc:
        raise HTTPException(503, "Contended account; retry with same request ID") from exc
    except (psycopg.errors.NumericValueOutOfRange, psycopg.errors.CheckViolation) as exc:
        raise HTTPException(409, "Operation exceeds account balance limits") from exc


@app.post("/deposit")
def deposit(request: AmountRequest):
    return local_operation("DEPOSIT", request)


@app.post("/withdraw")
def withdraw(request: AmountRequest):
    return local_operation("WITHDRAW", request)


@app.post("/transfer-local")
def local_transfer(request: TransferRequest):
    return local_operation("TRANSFER_LOCAL", request)


def gid_for(tx_id) -> str:
    return f"bank_{SHARD}_{tx_id}"


def is_prepared(conn, gid: str) -> bool:
    return conn.execute("SELECT 1 FROM pg_prepared_xacts WHERE gid=%s AND database=current_database()",
                        (gid,)).fetchone() is not None


def journal(conn, request_id, gid, state):
    conn.execute("""INSERT INTO participant_journal(tx_id,gid,status) VALUES (%s,%s,%s)
        ON CONFLICT (tx_id) DO UPDATE SET status=EXCLUDED.status,updated_at=now()""",
        (request_id, gid, state))


@app.post("/internal/prepare", dependencies=[Depends(internal_auth)])
def prepare(request: PrepareRequest, x_inject_vote_no: str | None = Header(None)):
    own(request.account_id)
    if x_inject_vote_no == "true" and os.environ.get("ENABLE_FAULT_INJECTION", "false").lower() == "true":
        logger.warning("INJECTED_VOTE_NO shard=%s tx_id=%s", SHARD, request.tx_id)
        raise HTTPException(409, "Injected participant rejection")
    gid = gid_for(request.tx_id)
    with transaction_lock(request.tx_id):
        with connect() as conn:
            prior = conn.execute("SELECT status FROM participant_journal WHERE tx_id=%s",
                                 (request.tx_id,)).fetchone()
            receipt = conn.execute("SELECT role,account_id,amount FROM transfer_receipts WHERE tx_id=%s",
                                   (request.tx_id,)).fetchone()
            if receipt:
                if (receipt["role"], receipt["account_id"], receipt["amount"]) != (
                        request.role, request.account_id, request.amount):
                    raise HTTPException(409, "Conflicting transaction ID")
                return {"vote": "YES", "status": "COMMITTED", "replica": REPLICA}
            if prior and prior["status"] in ("ABORTING", "ABORTED"):
                raise HTTPException(409, "Transaction already aborted (fenced)")
            if is_prepared(conn, gid):
                journal(conn, request.tx_id, gid, "PREPARED")
                return {"vote": "YES", "status": "PREPARED", "replica": REPLICA}
            if prior and prior["status"] in ("PREPARED", "COMMITTED"):
                raise HTTPException(409, "Journal/transaction mismatch; manual inspection required")

            # IMPORTANT: balance mutation and transfer_receipt are in the same
            # PostgreSQL *prepared* transaction, neither committed yet.
            try:
                conn.execute("BEGIN")
                conn.execute("SET LOCAL lock_timeout = '4000ms'")
                conn.execute("SET LOCAL statement_timeout = '7000ms'")
                if request.role == "DEBIT":
                    row = conn.execute("""UPDATE accounts SET balance=balance-%s
                        WHERE account_id=%s AND balance >= %s RETURNING balance""",
                        (request.amount, request.account_id, request.amount)).fetchone()
                    if row is None:
                        raise Declined("Account missing or insufficient funds")
                else:
                    row = conn.execute("UPDATE accounts SET balance=balance+%s WHERE account_id=%s RETURNING balance",
                                       (request.amount, request.account_id)).fetchone()
                    if row is None:
                        raise Declined("Account missing")
                conn.execute("""INSERT INTO transfer_receipts(tx_id,role,account_id,amount)
                    VALUES (%s,%s,%s,%s)""",
                    (request.tx_id, request.role, request.account_id, request.amount))
                conn.execute(sql.SQL("PREPARE TRANSACTION {}").format(sql.Literal(gid)))
            except Exception as exc:
                conn.execute("ROLLBACK")
                if isinstance(exc, Declined):
                    logger.info("prepare_no shard=%s replica=%s tx_id=%s", SHARD, REPLICA, request.tx_id)
                    raise HTTPException(409, str(exc)) from exc
                if isinstance(exc, (psycopg.errors.LockNotAvailable, psycopg.errors.QueryCanceled,
                                    psycopg.errors.DeadlockDetected)):
                    raise HTTPException(409, "Prepare contention/timeout") from exc
                raise
            journal(conn, request.tx_id, gid, "PREPARED")
    logger.info("prepare_yes shard=%s replica=%s tx_id=%s gid=%s", SHARD, REPLICA, request.tx_id, gid)
    return {"vote": "YES", "status": "PREPARED", "replica": REPLICA}


@app.post("/internal/commit", dependencies=[Depends(internal_auth)])
def commit(request: Phase2Request):
    gid = gid_for(request.tx_id)
    with transaction_lock(request.tx_id):
        with connect() as conn:
            receipt = conn.execute("SELECT 1 FROM transfer_receipts WHERE tx_id=%s", (request.tx_id,)).fetchone()
            if receipt:
                journal(conn, request.tx_id, gid, "COMMITTED")
                return {"status": "COMMITTED", "replayed": True, "replica": REPLICA}
            prior = conn.execute("SELECT status FROM participant_journal WHERE tx_id=%s",
                                 (request.tx_id,)).fetchone()
            if prior and prior["status"] in ("ABORTING", "ABORTED"):
                raise HTTPException(409, "Cannot commit aborted transaction")
            if not is_prepared(conn, gid):
                # Never falsely ACK a commit we cannot prove was executed.
                raise HTTPException(409, "No prepared transaction or committed receipt")
            conn.execute(sql.SQL("COMMIT PREPARED {}").format(sql.Literal(gid)))
            journal(conn, request.tx_id, gid, "COMMITTED")
    logger.info("commit shard=%s replica=%s tx_id=%s", SHARD, REPLICA, request.tx_id)
    return {"status": "COMMITTED", "replayed": False, "replica": REPLICA}


@app.post("/internal/abort", dependencies=[Depends(internal_auth)])
def abort(request: Phase2Request):
    gid = gid_for(request.tx_id)
    with transaction_lock(request.tx_id):
        with connect() as conn:
            if conn.execute("SELECT 1 FROM transfer_receipts WHERE tx_id=%s", (request.tx_id,)).fetchone():
                raise HTTPException(409, "Cannot abort committed transaction")
            # Durable tombstone *before* rollback/ACK. Prevents an in-flight
            # late PREPARE from resurrecting a transaction that was aborted.
            journal(conn, request.tx_id, gid, "ABORTING")
            if is_prepared(conn, gid):
                conn.execute(sql.SQL("ROLLBACK PREPARED {}").format(sql.Literal(gid)))
            journal(conn, request.tx_id, gid, "ABORTED")
    logger.info("abort shard=%s replica=%s tx_id=%s", SHARD, REPLICA, request.tx_id)
    return {"status": "ABORTED", "replica": REPLICA}


@app.get("/internal/transaction/{tx_id}", dependencies=[Depends(internal_auth)])
def participant_status(tx_id: str):
    from uuid import UUID
    try:
        UUID(tx_id)
    except ValueError as exc:
        raise HTTPException(422, "Invalid UUID") from exc
    with connect() as conn:
        row = conn.execute("SELECT status,gid FROM participant_journal WHERE tx_id=%s", (tx_id,)).fetchone()
        receipt = conn.execute("SELECT 1 FROM transfer_receipts WHERE tx_id=%s", (tx_id,)).fetchone()
        prepared = is_prepared(conn, gid_for(tx_id))
    return {"tx_id": tx_id, "journal": row["status"] if row else None,
            "prepared": prepared, "committed_receipt": bool(receipt), "replica": REPLICA}
