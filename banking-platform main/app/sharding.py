"""Strict, deterministic and non-overlapping account ownership map."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

ACCOUNT_PATTERN = re.compile(r"^A([0-9]{4})$")


@dataclass(frozen=True)
class Shard:
    name: str
    start: int
    end: int
    replicas: tuple[str, ...]


class ShardMap:
    def __init__(self, shards: list[Shard]):
        if not shards:
            raise ValueError("Shard map must not be empty")
        ordered = sorted(shards, key=lambda s: s.start)
        for index, shard in enumerate(ordered):
            if shard.start < 1 or shard.end > 9999 or shard.start > shard.end:
                raise ValueError("Invalid account range")
            if not shard.name or len(shard.replicas) < 2:
                raise ValueError("Every shard needs a name and two replicas")
            if index and ordered[index - 1].end >= shard.start:
                raise ValueError("Overlapping shard ranges")
        if len({s.name for s in ordered}) != len(ordered):
            raise ValueError("Duplicate shard name")
        self.shards = ordered
        self.by_name = {shard.name: shard for shard in ordered}

    @classmethod
    def load(cls, path: str | Path) -> "ShardMap":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([Shard(s["name"], s["start"], s["end"], tuple(s["replicas"]))
                    for s in raw["shards"]])

    def owner(self, account_id: str) -> str:
        match = ACCOUNT_PATTERN.fullmatch(account_id)
        if match is None:
            raise ValueError("Account ID must match A0001..A2000")
        number = int(match.group(1))
        for shard in self.shards:
            if shard.start <= number <= shard.end:
                return shard.name
        raise ValueError("Account not assigned to any shard")

