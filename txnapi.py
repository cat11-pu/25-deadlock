"""txnapi.py：对外门面（老接口 wait/release 不能改）。"""
from __future__ import annotations

from deadlock import WaitGraph


class Registry:
    def __init__(self):
        self.graph = WaitGraph()

    def wait(self, waiter: str, holder: str, since: int) -> dict:
        return self.graph.wait(waiter, holder, since)

    def release(self, txn: str) -> dict:
        return self.graph.release(txn)

    def find_cycle(self):
        return self.graph.find_cycle()

    def persist(self) -> bytes:
        return self.graph.persist()

    def resolve(self) -> dict:
        return self.graph.resolve()

    def restore(self, blob: bytes = None) -> dict:
        return self.graph.restore(blob)
