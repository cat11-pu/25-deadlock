"""check_sample.py：按 sample/waits.json 走一圈，打印验收面。"""
import json
import os
import sys

from deadlock import WaitGraph


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join("sample", "waits.json")
    with open(path, encoding="utf-8") as handle:
        spec = json.load(handle)
    graph = WaitGraph()
    for item in spec["waits"]:
        graph.wait(item["waiter"], item["holder"], item["since"])
    first_cycle = graph.find_cycle()
    resolved = graph.resolve()
    second_cycle = graph.find_cycle()
    blob = graph.persist()
    reborn = WaitGraph()
    restored = reborn.restore(blob)
    print("第一次检测到的环 =", first_cycle)
    print("回滚顺序 =", resolved.get("victims"))
    print("回滚轮数 =", resolved.get("rounds"))
    print("回滚后剩余边 =", sorted(resolved.get("edges", [])))
    print("回滚后还有没有环 =", bool(second_cycle))
    print("被回滚的事务 =", sorted(resolved.get("aborted", [])))
    print("重启后被回滚的集合 =", restored.get("aborted"))
    print("重启后剩余边 =", restored.get("edges"))
    print("重启后仍等待的事务 =", sorted(reborn.waited))
    print("环上最小 id =", min(first_cycle) if first_cycle else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
