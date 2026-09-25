"""deadlock.py：等待图（记录边、确定性找环、回滚、快照恢复）。"""
from __future__ import annotations

import json
import struct

_MAGIC = b"DEADLOCK1\n"
_HEADER = struct.Struct(">I")


class WaitGraph:
    def __init__(self):
        self.edges = set()
        self.waited = {}
        self.aborted = set()
        self._out = {}
        self._in = {}
        self._since = {}

    def wait(self, waiter: str, holder: str, since: int) -> dict:
        if (waiter, holder) not in self.edges:
            self.edges.add((waiter, holder))
            self._out.setdefault(waiter, set()).add(holder)
            self._in.setdefault(holder, set()).add(waiter)
            self._since[(waiter, holder)] = since
        self.waited.setdefault(waiter, since)
        return {"edges": len(self.edges)}

    def release(self, txn: str) -> dict:
        removed = self._remove_txn(txn)
        return {"released": removed}

    def _remove_txn(self, txn: str) -> int:
        """删掉 txn 作为等待方或被等待方的全部边，返回删边数。"""
        affected_waiters = set(self._in.get(txn, ()))
        affected_waiters.add(txn)
        removed = 0
        for waiter in tuple(self._out.get(txn, ())):
            self.edges.discard((txn, waiter))
            self._in.get(waiter, set()).discard(txn)
            self._since.pop((txn, waiter), None)
            removed += 1
        for holder in tuple(self._in.get(txn, ())):
            self.edges.discard((holder, txn))
            self._out.get(holder, set()).discard(txn)
            self._since.pop((holder, txn), None)
            removed += 1
        self._out.pop(txn, None)
        self._in.pop(txn, None)
        for waiter in affected_waiters:
            if not self._out.get(waiter):
                self.waited.pop(waiter, None)
                self._out.pop(waiter, None)
        return removed

    def find_cycle(self):
        """按事务 id 升序选起点做深度优先，返回第一条回边构成的环。"""
        white, gray, black = 0, 1, 2
        color = {}
        nodes = set(self._out)
        nodes.update(self._in)
        for start in sorted(nodes):
            if color.get(start, white) != white:
                continue
            color[start] = gray
            frames = [(start, iter(sorted(self._out.get(start, ()))))]
            while frames:
                node, neighbors = frames[-1]
                nxt = next(neighbors, None)
                if nxt is None:
                    color[node] = black
                    frames.pop()
                    continue
                state = color.get(nxt, white)
                if state == white:
                    color[nxt] = gray
                    frames.append((nxt, iter(sorted(self._out.get(nxt, ())))))
                elif state == gray:
                    for index, (frame_node, _) in enumerate(frames):
                        if frame_node == nxt:
                            return [frame[0] for frame in frames[index:]]
        return []

    def resolve(self) -> dict:
        victims = []
        rounds = 0
        while True:
            cycle = self.find_cycle()
            if not cycle:
                break
            rounds += 1
            def victim_key(index):
                node = cycle[index]
                successor = cycle[(index + 1) % len(cycle)]
                return (-self._since.get((node, successor), 0), node)

            victim = cycle[min(range(len(cycle)), key=victim_key)]
            self._remove_txn(victim)
            self.aborted.add(victim)
            victims.append(victim)
        return {
            "victims": victims,
            "rounds": rounds,
            "edges": sorted(map(list, self.edges)),
            "aborted": sorted(self.aborted),
        }

    def persist(self) -> bytes:
        records = []
        for waiter, holder in sorted(self.edges):
            payload = json.dumps(
                {"t": "e", "w": waiter, "h": holder,
                 "s": self._since.get((waiter, holder), 0)},
                separators=(",", ":"),
            ).encode("utf-8")
            records.append(_HEADER.pack(len(payload)) + payload)
        for txn in sorted(self.aborted):
            payload = json.dumps({"t": "a", "txn": txn},
                                 separators=(",", ":")).encode("utf-8")
            records.append(_HEADER.pack(len(payload)) + payload)
        return _MAGIC + b"".join(records)

    def restore(self, blob: bytes = None) -> dict:
        if blob is None:
            raise ValueError("restore 需要 persist() 产出的快照字节")
        if not blob.startswith(_MAGIC):
            raise ValueError("无法识别的快照格式")
        self.edges = set()
        self.waited = {}
        self.aborted = set()
        self._out = {}
        self._in = {}
        self._since = {}
        pos = len(_MAGIC)
        while pos < len(blob):
            if len(blob) - pos < _HEADER.size:
                break
            (length,) = _HEADER.unpack_from(blob, pos)
            pos += _HEADER.size
            if len(blob) - pos < length:
                break
            raw = blob[pos:pos + length]
            pos += length
            try:
                record = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            kind = record.get("t")
            if kind == "e":
                waiter, holder, since = record["w"], record["h"], record["s"]
                self.edges.add((waiter, holder))
                self._out.setdefault(waiter, set()).add(holder)
                self._in.setdefault(holder, set()).add(waiter)
                self._since[(waiter, holder)] = since
                self.waited.setdefault(waiter, since)
            elif kind == "a":
                self.aborted.add(record["txn"])
        return {
            "edges": sorted(map(list, self.edges)),
            "aborted": sorted(self.aborted),
        }

    def stats(self) -> dict:
        return {"edges": len(self.edges), "aborted": sorted(self.aborted)}
