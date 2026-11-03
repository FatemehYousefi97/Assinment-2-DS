import unittest
from pathlib import Path

from app.sharding import Shard, ShardMap

CONFIG = Path(__file__).parents[2] / "config/shards.json"


class ShardingTests(unittest.TestCase):
    def setUp(self):
        self.map = ShardMap.load(CONFIG)

    def test_all_2000_accounts_have_exclusive_owner(self):
        owners = [self.map.owner(f"A{i:04d}") for i in range(1, 2001)]
        self.assertEqual(owners.count("A"), 1000)
        self.assertEqual(owners.count("B"), 1000)
        self.assertEqual(owners[999], "A")
        self.assertEqual(owners[1000], "B")

    def test_nonassigned_and_malformed_accounts_rejected(self):
        for value in ("A0000", "A2001", "A9999", "B0001", "A20", "A-001", "A01000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.map.owner(value)

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            ShardMap([Shard("A", 1, 1000, ("a1", "a2")),
                      Shard("B", 1000, 2000, ("b1", "b2"))])

    def test_duplicate_name_rejected(self):
        with self.assertRaises(ValueError):
            ShardMap([Shard("A", 1, 1000, ("a1", "a2")),
                      Shard("A", 1001, 2000, ("b1", "b2"))])


if __name__ == "__main__":
    unittest.main()

