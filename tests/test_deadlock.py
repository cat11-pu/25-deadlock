import unittest

from deadlock import WaitGraph
from txnapi import Registry


class TestWaitGraph(unittest.TestCase):
    def test_wait_records_edge(self):
        graph = WaitGraph()
        graph.wait("t1", "t2", 5)
        self.assertEqual(graph.stats()["edges"], 1)

    def test_release_removes_edges(self):
        graph = WaitGraph()
        graph.wait("t1", "t2", 5)
        self.assertEqual(graph.release("t2")["released"], 1)

    def test_release_counts_only_existing(self):
        graph = WaitGraph()
        graph.wait("t1", "t2", 5)
        self.assertEqual(graph.release("t9")["released"], 0)

    def test_stats_shape(self):
        self.assertIn("aborted", WaitGraph().stats())

    def test_registry_wraps_graph(self):
        registry = Registry()
        registry.wait("t1", "t2", 1)
        self.assertEqual(registry.graph.stats()["edges"], 1)


if __name__ == "__main__":
    unittest.main()


class TestDeadlockFeatures(unittest.TestCase):
    def _sample_graph(self):
        graph = WaitGraph()
        for waiter, holder, since in [
            ("t1", "t2", 5),
            ("t2", "t3", 7),
            ("t3", "t1", 2),
            ("t4", "t5", 9),
            ("t5", "t4", 1),
        ]:
            graph.wait(waiter, holder, since)
        return graph

    def test_find_cycle_deterministic(self):
        graph = self._sample_graph()
        self.assertEqual(graph.find_cycle(), ["t1", "t2", "t3"])
        self.assertEqual(graph.find_cycle(), ["t1", "t2", "t3"])

    def test_find_cycle_empty_on_acyclic(self):
        graph = WaitGraph()
        graph.wait("t1", "t2", 1)
        self.assertEqual(graph.find_cycle(), [])

    def test_resolve_breaks_all_cycles(self):
        graph = self._sample_graph()
        result = graph.resolve()
        self.assertEqual(result["victims"], ["t2", "t4"])
        self.assertEqual(result["rounds"], 2)
        self.assertEqual(result["edges"], [["t3", "t1"]])
        self.assertEqual(result["aborted"], ["t2", "t4"])
        self.assertEqual(graph.find_cycle(), [])

    def test_resolve_victim_tie_breaks_lexicographically(self):
        graph = WaitGraph()
        graph.wait("tb", "ta", 3)
        graph.wait("ta", "tb", 3)
        self.assertEqual(graph.resolve()["victims"], ["ta"])

    def test_persist_restore_roundtrip(self):
        graph = self._sample_graph()
        graph.resolve()
        reborn = WaitGraph()
        restored = reborn.restore(graph.persist())
        self.assertEqual(restored["aborted"], ["t2", "t4"])
        self.assertEqual(restored["edges"], [["t3", "t1"]])
        self.assertEqual(sorted(reborn.waited), ["t3"])

    def test_restore_ignores_trailing_partial_record(self):
        graph = self._sample_graph()
        graph.resolve()
        blob = graph.persist() + b'{"aborted": "t9'
        reborn = WaitGraph()
        restored = reborn.restore(blob)
        self.assertEqual(restored["aborted"], ["t2", "t4"])
        self.assertEqual(restored["edges"], [["t3", "t1"]])

    def test_registry_wait_release_shape_unchanged(self):
        registry = Registry()
        self.assertEqual(registry.wait("t1", "t2", 1), {"edges": 1})
        self.assertEqual(registry.release("t1"), {"released": 1})
