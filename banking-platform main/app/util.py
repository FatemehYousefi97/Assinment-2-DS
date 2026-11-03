"""Common database connection helpers and transaction IDs."""
import hashlib
import json
import logging
import os
from contextlib import contextmanager
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True,
                           row_factory=dict_row, connect_timeout=5)


def lock_key(tx_id) -> int:
    return int.from_bytes(hashlib.sha256(str(tx_id).encode()).digest()[:8],
                          "big", signed=True)


@contextmanager
def transaction_lock(tx_id, *, wait=True):
    """Database-scoped session advisory lock; released even if handler fails."""
    with connect() as connection:
        key = lock_key(tx_id)
        if wait:
            connection.execute("SELECT pg_advisory_lock(%s)", (key,))
            acquired = True
        else:
            acquired = connection.execute("SELECT pg_try_advisory_lock(%s)", (key,)).fetchone()["pg_try_advisory_lock"]
        try:
            yield acquired
        finally:
            if acquired:
                connection.execute("SELECT pg_advisory_unlock(%s)", (key,))


def payload_hash(*values) -> str:
    def normalized(value):
        return f"{value:.2f}" if isinstance(value, Decimal) else str(value)
    data = json.dumps([normalized(value) for value in values], separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()

