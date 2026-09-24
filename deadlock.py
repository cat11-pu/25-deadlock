"""deadlock.py：等待图（基线：只记边，不检测、不恢复）。"""
from __future__ import annotations


class WaitGraph:
    def __init__(self):
        self.edges = set()
        self.waited = {}
        self.aborted = set()

    def wait(self, waiter: str, holder: str, since: int) -> dict:
        self.edges.add((waiter, holder))
        self.waited.setdefault(waiter, since)
        return {"edges": len(self.edges)}

    def release(self, txn: str) -> dict:
        before = len(self.edges)
        self.edges = {edge for edge in self.edges if txn not in edge}
        return {"released": before - len(self.edges)}

    def find_cycle(self):
        """基线：不检测，永远说没有环。"""
        return []

    def resolve(self) -> dict:
        raise NotImplementedError("死锁回滚还没实现")

    def persist(self) -> bytes:
        raise NotImplementedError("快照还没实现")

    def restore(self, blob: bytes = None) -> dict:
        raise NotImplementedError("重启恢复还没实现")

    def stats(self) -> dict:
        return {"edges": len(self.edges), "aborted": sorted(self.aborted)}
