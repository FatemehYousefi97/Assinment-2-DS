"""Health-aware, per-shard round-robin routing shared by Gateway/Coordinator."""
import logging
import threading
from collections import defaultdict

import httpx

from .sharding import ShardMap

logger = logging.getLogger("bank.routing")


class NoHealthyReplica(Exception):
    pass


class ReplicaPool:
    def __init__(self, shard_map: ShardMap):
        self.map = shard_map
        self.client = httpx.Client(timeout=httpx.Timeout(8, connect=2))
        self.lock = threading.Lock()
        self.healthy = {url: False for shard in self.map.shards for url in shard.replicas}
        self.next_index = defaultdict(int)
        self.stop_event = threading.Event()
        self.worker = None

    def poll(self):
        for shard in self.map.shards:
            for url in shard.replicas:
                try:
                    result = self.client.get(url + "/health", timeout=2)
                    live = result.status_code == 200 and result.json().get("shard") == shard.name
                except (httpx.RequestError, ValueError):
                    live = False
                with self.lock:
                    previous = self.healthy[url]
                    self.healthy[url] = live
                if live != previous:
                    logger.warning("replica_health_changed shard=%s url=%s healthy=%s", shard.name, url, live)

    def start(self):
        self.poll()
        self.worker = threading.Thread(target=self._loop, daemon=True, name="health-monitor")
        self.worker.start()

    def _loop(self):
        while not self.stop_event.wait(1):
            self.poll()

    def close(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=3)
        self.client.close()

    def members(self):
        with self.lock:
            return {s.name: [{"url": url, "healthy": self.healthy[url]}
                             for url in s.replicas] for s in self.map.shards}

    def pick(self, shard_name: str, excluded: set[str]) -> str:
        shard = self.map.by_name[shard_name]
        with self.lock:
            candidates = [url for url in shard.replicas if self.healthy[url] and url not in excluded]
            if not candidates:
                raise NoHealthyReplica(f"No healthy replicas for shard {shard_name}")
            index = self.next_index[shard_name] % len(candidates)
            self.next_index[shard_name] += 1
            return candidates[index]

    def request(self, shard: str, method: str, path: str, *, json=None, headers=None):
        """Retry transport/5xx failures only; 4xx conveys a business decision.

        This retry is safe because all write APIs require idempotency keys/tx IDs.
        """
        excluded: set[str] = set()
        last_error = None
        while True:
            try:
                url = self.pick(shard, excluded)
            except NoHealthyReplica as exc:
                raise NoHealthyReplica(str(last_error or exc)) from exc
            try:
                result = self.client.request(method, url + path, json=json, headers=headers)
                if result.status_code < 500:
                    return result
                last_error = f"{url}: HTTP {result.status_code}"
            except httpx.RequestError as exc:
                last_error = str(exc)
            logger.warning("replica_request_failed shard=%s url=%s reason=%s", shard, url, last_error)
            with self.lock:
                self.healthy[url] = False
            excluded.add(url)

