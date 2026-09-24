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
