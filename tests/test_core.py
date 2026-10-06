"""Behaviour tests for the skip list core."""

import unittest

from skiplist.core import LevelSource
from skiplist.core import SkipList


class FixedSource:
    """A deterministic source that always gives the same decision."""

    def __init__(self, decision):
        self.decision = bool(decision)
        self.taken = 0

    def promote(self):
        self.taken += 1
        return self.decision


class ScriptedSource:
    """A deterministic source replaying a fixed script, then its last entry."""

    def __init__(self, decisions):
        self.decisions = [bool(decision) for decision in decisions]
        self.taken = 0

    def promote(self):
        index = min(self.taken, len(self.decisions) - 1)
        self.taken += 1
        return self.decisions[index]


class TestSkipList(unittest.TestCase):
    def test_01_empty_list_and_rejected_inputs(self):
        tree = SkipList()
        self.assertEqual(len(tree), 0)
        self.assertEqual(tree.height, 1)
        self.assertEqual(list(tree), [])
        self.assertEqual(tree.items(), [])
        self.assertIsNone(tree.get(4))
        self.assertEqual(tree.get(4, "none"), "none")
        self.assertFalse(tree.contains(4))
        self.assertFalse(tree.delete(4))
        with self.assertRaises(IndexError):
            tree.select(1)
        with self.assertRaises(IndexError):
            tree.select(0)
        with self.assertRaises(TypeError):
            tree.insert("4", "value")
        with self.assertRaises(TypeError):
            tree.get(None)
        with self.assertRaises(TypeError):
            tree.rank(2.5)
        with self.assertRaises(TypeError):
            tree.range_scan(1.5, 3)
        with self.assertRaises(ValueError):
            SkipList(max_level=0)
        with self.assertRaises(ValueError):
            LevelSource(())

    def test_02_insert_and_get_in_ascending_order(self):
        tree = SkipList()
        for key in range(1, 31):
            self.assertTrue(tree.insert(key, "v%02d" % key))
        self.assertEqual(len(tree), 30)
        for key in range(1, 31):
            self.assertEqual(tree.get(key), "v%02d" % key)
            self.assertTrue(tree.contains(key))
        self.assertIsNone(tree.get(0))
        self.assertIsNone(tree.get(31))
        self.assertEqual(tree.get(31, "missing"), "missing")

    def test_03_shuffled_insert_keeps_key_order(self):
        order = [37, 4, 92, 15, 68, 51, 23, 80, 6, 45,
                 99, 12, 60, 28, 73, 1, 88, 34, 56, 41]
        tree = SkipList()
        for key in order:
            tree.insert(key, key * 2)
        expected = sorted((key, key * 2) for key in order)
        self.assertEqual(list(tree), expected)
        self.assertEqual(tree.keys(), [key for key, _ in expected])
        self.assertEqual(tree.values(), [value for _, value in expected])

    def test_04_duplicate_keys_overwrite_the_value(self):
        source = FixedSource(False)
        tree = SkipList(source=source)
        self.assertTrue(tree.insert(5, "first"))
        self.assertTrue(tree.insert(9, "second"))
        self.assertFalse(tree.insert(5, "third"))
        self.assertEqual(len(tree), 2)
        self.assertEqual(list(tree), [(5, "third"), (9, "second")])
        self.assertEqual(tree.get(5), "third")
        self.assertEqual(tree.get(9), "second")
        self.assertEqual(source.taken, 2)

    def test_05_select_returns_the_pair_at_the_rank(self):
        tree = SkipList(source=LevelSource((1, 0)))
        for key in (10, 20, 30, 40, 50):
            tree.insert(key, key + 1)
        self.assertEqual(tree.select(1), (10, 11))
        self.assertEqual(tree.select(3), (30, 31))
        self.assertEqual(tree.select(5), (50, 51))
        with self.assertRaises(IndexError):
            tree.select(6)
        with self.assertRaises(IndexError):
            tree.select(0)
        with self.assertRaises(TypeError):
            tree.select("1")

    def test_06_rank_matches_the_iteration_position(self):
        tree = SkipList(source=LevelSource((1, 0)))
        keys = (4, 8, 15, 16, 23, 42)
        for key in keys:
            tree.insert(key, "k%d" % key)
        for position, key in enumerate(keys, start=1):
            self.assertEqual(tree.rank(key), position)
        self.assertEqual(tree.rank(99), 0)
        self.assertEqual(tree.rank(1), 0)
        with self.assertRaises(TypeError):
            tree.rank(1.0)

    def test_07_range_scan_is_closed_at_both_ends(self):
        tree = SkipList(source=LevelSource((1, 0)))
        for key in range(10, 100, 10):
            tree.insert(key, "n%d" % key)
        self.assertEqual(
            tree.range_scan(30, 60),
            [(30, "n30"), (40, "n40"), (50, "n50"), (60, "n60")],
        )
        self.assertEqual(tree.range_scan(30, 30), [(30, "n30")])
        self.assertEqual(tree.range_scan(35, 55), [(40, "n40"), (50, "n50")])
        self.assertEqual(tree.range_scan(0, 5), [])
        self.assertEqual(tree.range_scan(85, 200), [(90, "n90")])
        self.assertEqual(tree.range_scan(60, 40), [])
        self.assertEqual(len(tree.range_scan(10, 90)), 9)

    def test_08_delete_reports_presence_and_hides_the_key(self):
        tree = SkipList(source=LevelSource((1, 0)))
        for key in (5, 3, 9, 1, 7):
            tree.insert(key, key * 10)
        self.assertFalse(tree.delete(4))
        self.assertFalse(tree.delete(99))
        self.assertTrue(tree.delete(3))
        self.assertEqual(len(tree), 4)
        self.assertIsNone(tree.get(3))
        self.assertFalse(tree.contains(3))
        self.assertNotIn(3, tree)
        self.assertTrue(tree.delete(5))
        self.assertTrue(tree.delete(9))
        self.assertTrue(tree.delete(1))
        self.assertTrue(tree.delete(7))
        self.assertEqual(len(tree), 0)
        self.assertEqual(list(tree), [])
        self.assertFalse(tree.delete(7))

    def test_09_height_follows_the_tallest_node_and_shrinks(self):
        source = ScriptedSource([1, 1, 0])
        tree = SkipList(source=source, max_level=4)
        for key in (1, 2, 3, 4, 5):
            tree.insert(key, key)
        self.assertEqual(tree.node_levels(), [3, 1, 1, 1, 1])
        self.assertEqual(tree.height, 3)
        self.assertLessEqual(max(tree.node_levels()), tree.max_level)
        self.assertTrue(tree.delete(1))
        self.assertEqual(tree.height, 1)
        self.assertEqual(tree.node_levels(), [1, 1, 1, 1])
        for key in (2, 3, 4, 5):
            tree.delete(key)
        self.assertEqual(len(tree), 0)
        self.assertEqual(tree.height, 1)

    def test_10_levels_come_from_the_injected_source(self):
        patterned = SkipList(source=LevelSource((1, 1, 0)))
        for key in range(6):
            patterned.insert(key, key)
        self.assertEqual(patterned.node_levels(), [3, 3, 3, 3, 3, 3])
        self.assertEqual(patterned.height, 3)

        flat = SkipList(source=FixedSource(False))
        for key in range(4):
            flat.insert(key, key)
        self.assertEqual(flat.node_levels(), [1, 1, 1, 1])
        self.assertEqual(flat.height, 1)

        tall = SkipList(source=FixedSource(True), max_level=3)
        for key in range(4):
            tall.insert(key, key)
        self.assertEqual(tall.node_levels(), [3, 3, 3, 3])
        self.assertEqual(tall.height, 3)
        self.assertLessEqual(max(tall.node_levels()), tall.max_level)
