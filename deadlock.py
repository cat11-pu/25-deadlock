"""deadlock.py：等待图（检测环、回滚、快照与恢复）。"""
from __future__ import annotations

import json


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
        self._prune_waited()
        return {"released": before - len(self.edges)}

    def _prune_waited(self):
        waiting = {edge[0] for edge in self.edges}
        self.waited = {txn: since for txn, since in self.waited.items() if txn in waiting}

    def find_cycle(self):
        """按事务 id 升序起点做迭代式 DFS，返回第一条回边构成的环。"""
        adjacency = {}
        nodes = set()
        for waiter, holder in self.edges:
            adjacency.setdefault(waiter, []).append(holder)
            nodes.add(waiter)
            nodes.add(holder)
        for holders in adjacency.values():
            holders.sort()

        color = {}
        for start in sorted(nodes):
            if start in color:
                continue
            color[start] = 1
            path = [start]
            stack = [(start, iter(adjacency.get(start, [])))]
            while stack:
                node, neighbors = stack[-1]
                descended = False
                for nxt in neighbors:
                    state = color.get(nxt, 0)
                    if state == 0:
                        color[nxt] = 1
                        path.append(nxt)
                        stack.append((nxt, iter(adjacency.get(nxt, []))))
                        descended = True
                        break
                    if state == 1:
                        return path[path.index(nxt):]
                if not descended:
                    color[node] = 2
                    stack.pop()
                    path.pop()
        return []

    def resolve(self) -> dict:
        victims = []
        rounds = 0
        while True:
            cycle = self.find_cycle()
            if not cycle:
                break
            rounds += 1
            victim = min(cycle, key=lambda txn: (-self.waited.get(txn, 0), txn))
            victims.append(victim)
            self.aborted.add(victim)
            self.edges = {edge for edge in self.edges if victim not in edge}
            self._prune_waited()
        return {
            "victims": victims,
            "rounds": rounds,
            "edges": sorted([list(edge) for edge in self.edges]),
            "aborted": sorted(self.aborted),
        }

    def persist(self) -> bytes:
        records = [{"aborted": txn} for txn in sorted(self.aborted)]
        records += [
            {"waiter": waiter, "holder": holder, "since": self.waited.get(waiter, 0)}
            for waiter, holder in sorted(self.edges)
        ]
        return b"".join(
            json.dumps(record, ensure_ascii=False).encode("utf-8") + b"\n"
            for record in records
        )

    def restore(self, blob: bytes = None) -> dict:
        if blob is not None:
            self.edges = set()
            self.waited = {}
            self.aborted = set()
            for line in blob.split(b"\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
                if not isinstance(record, dict):
                    continue
                if "aborted" in record:
                    self.aborted.add(record["aborted"])
                elif "waiter" in record and "holder" in record:
                    self.edges.add((record["waiter"], record["holder"]))
                    self.waited.setdefault(record["waiter"], record.get("since", 0))
        return {
            "aborted": sorted(self.aborted),
            "edges": sorted([list(edge) for edge in self.edges]),
        }

    def stats(self) -> dict:
        return {"edges": len(self.edges), "aborted": sorted(self.aborted)}
