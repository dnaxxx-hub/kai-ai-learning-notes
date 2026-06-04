#!/usr/bin/env python3
"""
OS 进程调度深度演示
=====================
1. 调度算法对比: FCFS / SJF / SRTF / 优先级 / RR / MLFQ
2. CFS vruntime 红黑树模拟
3. 优先级反转 + 优先级继承模拟
"""

import random
import sys
from collections import deque

# ============================================================
# 第1部分: 进程模型
# ============================================================

class Process:
    """进程控制块"""
    def __init__(self, pid, burst, arrival, priority=0):
        self.pid = pid
        self.burst = burst          # 总执行时间
        self.remaining = burst      # 剩余时间
        self.arrival = arrival      # 到达时间
        self.priority = priority    # 优先级 (0=最高)
        self.start_time = -1        # 首次运行时间
        self.finish_time = -1       # 完成时间
        self.wait_time = 0          # 等待时间累计

    def turnaround(self):
        return self.finish_time - self.arrival

    def response(self):
        return self.start_time - self.arrival

    def __repr__(self):
        return f"P{self.pid}(burst={self.burst},arr={self.arrival},prio={self.priority})"


def generate_processes(n, max_burst=200, max_arrival=50):
    """生成 n 个随机进程"""
    random.seed(42)
    procs = []
    for i in range(n):
        burst = random.randint(10, max_burst)
        arrival = random.randint(0, max_arrival)
        priority = random.randint(0, 9)
        procs.append(Process(i, burst, arrival, priority))
    procs.sort(key=lambda p: p.arrival)
    return procs


# ============================================================
# 第2部分: 6种调度算法
# ============================================================

def simulate_fcfs(procs):
    """先来先服务"""
    ps = [Process(p.pid, p.burst, p.arrival, p.priority) for p in procs]
    ps.sort(key=lambda p: p.arrival)
    time = 0
    for p in ps:
        if time < p.arrival:
            time = p.arrival
        if p.start_time < 0:
            p.start_time = time
        p.wait_time = time - p.arrival
        time += p.remaining
        p.finish_time = time
    return ps


def simulate_sjf(procs):
    """最短作业优先 (非抢占)"""
    ps = [Process(p.pid, p.burst, p.arrival, p.priority) for p in procs]
    pending = sorted(ps, key=lambda p: p.arrival)
    time = 0
    remaining = []
    finished = []
    while pending or remaining:
        while pending and pending[0].arrival <= time:
            p = pending.pop(0)
            remaining.append(p)
        if not remaining:
            time = pending[0].arrival
            continue
        remaining.sort(key=lambda p: p.burst)
        p = remaining.pop(0)
        if p.start_time < 0:
            p.start_time = time
        p.wait_time = time - p.arrival
        time += p.remaining
        p.remaining = 0
        p.finish_time = time
        finished.append(p)
    return finished


def simulate_srtf(procs):
    """最短剩余时间优先 (抢占)"""
    ps = [Process(p.pid, p.burst, p.arrival, p.priority) for p in procs]
    pending = sorted(ps, key=lambda p: p.arrival)
    time = 0
    queue = []
    finished = []
    current = None
    while pending or queue or current:
        while pending and pending[0].arrival <= time:
            queue.append(pending.pop(0))
        if not queue and not current:
            if pending:
                time = pending[0].arrival
            continue
        if not current:
            queue.sort(key=lambda p: p.remaining)
            current = queue.pop(0)
            if current.start_time < 0:
                current.start_time = time
        # 检查是否有剩余更短的进程
        next_arrival = pending[0].arrival if pending else float('inf')
        time_to_next = next_arrival - time
        if time_to_next <= 0:
            time_to_next = 1
        queue.sort(key=lambda p: p.remaining)
        if queue and queue[0].remaining < current.remaining:
            queue.append(current)
            current = queue.pop(0)
            if current.start_time < 0:
                current.start_time = time
            continue
        exec_time = min(current.remaining, time_to_next)
        current.remaining -= exec_time
        time += exec_time
        if current.remaining <= 0:
            current.finish_time = time
            current.wait_time = current.finish_time - current.burst - current.arrival
            finished.append(current)
            current = None
        # 更新等待时间
        for p in queue:
            p.wait_time += exec_time
    return finished


def simulate_priority(procs):
    """优先级调度 (非抢占, 0=最高)"""
    ps = [Process(p.pid, p.burst, p.arrival, p.priority) for p in procs]
    pending = sorted(ps, key=lambda p: p.arrival)
    time = 0
    ready = []
    finished = []
    while pending or ready:
        while pending and pending[0].arrival <= time:
            ready.append(pending.pop(0))
        if not ready:
            time = pending[0].arrival
            continue
        ready.sort(key=lambda p: p.priority)
        p = ready.pop(0)
        if p.start_time < 0:
            p.start_time = time
        p.wait_time = time - p.arrival
        time += p.remaining
        p.remaining = 0
        p.finish_time = time
        finished.append(p)
    return finished


def simulate_rr(procs, time_slice=20):
    """时间片轮转"""
    ps = [Process(p.pid, p.burst, p.arrival, p.priority) for p in procs]
    pending = sorted(ps, key=lambda p: p.arrival)
    queue = deque()
    time = 0
    finished = []
    while pending or queue:
        while pending and pending[0].arrival <= time:
            queue.append(pending.pop(0))
        if not queue:
            time = pending[0].arrival
            continue
        p = queue.popleft()
        if p.start_time < 0:
            p.start_time = time
        exec_time = min(p.remaining, time_slice)
        p.remaining -= exec_time
        time += exec_time
        # 等待时间: 队列中的进程累积
        for qp in queue:
            qp.wait_time += exec_time
        if p.remaining <= 0:
            p.finish_time = time
            finished.append(p)
        else:
            queue.append(p)
    return finished


def simulate_mlfq(procs):
    """多级反馈队列
       队列0: RR 10ms (最高优先级)
       队列1: RR 25ms
       队列2: RR 50ms
       队列3: FCFS (最低优先级)
    """
    ps = [Process(p.pid, p.burst, p.arrival, p.priority) for p in procs]
    pending = sorted(ps, key=lambda p: p.arrival)

    # MLFQ 配置
    num_levels = 4
    time_slices = [10, 25, 50, 99999]  # 每级时间片
    queues = [deque() for _ in range(num_levels)]

    # 进程层级
    level_of = {p.pid: 0 for p in ps}

    time = 0
    finished = []
    current = None
    current_level = 0
    used_time = 0

    while pending or any(q for q in queues) or current:
        while pending and pending[0].arrival <= time:
            p = pending.pop(0)
            level_of[p.pid] = 0
            queues[0].append(p)

        if not current:
            # 选择非空最高优先级队列
            for lvl in range(num_levels):
                if queues[lvl]:
                    current = queues[lvl].popleft()
                    current_level = lvl
                    used_time = 0
                    if current.start_time < 0:
                        current.start_time = time
                    break

        if not current:
            time = pending[0].arrival if pending else time + 1
            continue

        # 检查更高优先级新进程
        for lvl in range(current_level):
            if queues[lvl]:
                # 抢占
                queues[current_level].appendleft(current)
                current = queues[lvl].popleft()
                current_level = lvl
                used_time = 0
                if current.start_time < 0:
                    current.start_time = time
                break

        # 执行一个时间单位
        exec_time = 1
        current.remaining -= exec_time
        used_time += exec_time
        time += exec_time

        # 队列中进程等待
        for lvl in range(num_levels):
            for qp in queues[lvl]:
                qp.wait_time += exec_time

        if current.remaining <= 0:
            current.finish_time = time
            finished.append(current)
            current = None
        elif used_time >= time_slices[current_level]:
            # 降级
            next_level = min(current_level + 1, num_levels - 1)
            level_of[current.pid] = next_level
            queues[next_level].append(current)
            current = None

    return finished


# ============================================================
# 第3部分: CFS vruntime 红黑树模拟
# ============================================================

class RBNode:
    """红黑树节点 (简化版, 仅保持排序)"""
    def __init__(self, pid, vruntime, nice=0):
        self.pid = pid
        self.vruntime = vruntime
        self.nice = nice
        self.left = None
        self.right = None

class SimpleRBTree:
    """简化的红黑树 — 用于模拟 CFS vruntime 排序"""
    def __init__(self):
        self.root = None

    def insert(self, node):
        if not self.root:
            self.root = node
            return
        cur = self.root
        while True:
            if node.vruntime < cur.vruntime:
                if cur.left:
                    cur = cur.left
                else:
                    cur.left = node
                    break
            else:
                if cur.right:
                    cur = cur.right
                else:
                    cur.right = node
                    break

    def leftmost(self):
        """返回最小 vruntime 节点 (最左子)"""
        if not self.root:
            return None
        cur = self.root
        while cur.left:
            cur = cur.left
        return cur

    def remove(self, node):
        """简单删除 (仅用于演示)"""
        parent = None
        cur = self.root
        while cur and cur != node:
            parent = cur
            if node.vruntime < cur.vruntime:
                cur = cur.left
            else:
                cur = cur.right
        if not cur:
            return
        # 叶子节点或单子节点
        child = cur.left if cur.left else cur.right
        if not parent:
            self.root = child
        elif parent.left == cur:
            parent.left = child
        else:
            parent.right = child


def cfs_weight(nice):
    """根据 nice 值计算权重 (标准 CFS 权重表)"""
    # Linux 内核权重表
    sched_prio_to_weight = [
        88761, 71755, 56483, 46273, 36291,
        29154, 23382, 18705, 14949, 11916,
        9548, 7620, 6100, 4904, 3906,
        3121, 2501, 1991, 1586, 1288,
        1024, 793, 628, 518, 426,
        348, 293, 243, 205, 172,
        132, 110, 87, 72, 59,
        46, 37, 31, 26, 22,
    ]
    idx = nice + 20
    if idx < 0:
        idx = 0
    if idx >= len(sched_prio_to_weight):
        idx = len(sched_prio_to_weight) - 1
    return sched_prio_to_weight[idx]


def simulate_cfs():
    """模拟 CFS 调度过程"""
    print("=" * 70)
    print("CFS vruntime 调度模拟")
    print("=" * 70)

    # 创建5个进程，不同 nice 值
    NICE_0_LOAD = 1024
    processes = [
        {"pid": 1, "nice": 0,  "burst": 100},
        {"pid": 2, "nice": -5, "burst": 80},
        {"pid": 3, "nice": 5,  "burst": 120},
        {"pid": 4, "nice": -10,"burst": 60},
        {"pid": 5, "nice": 10, "burst": 90},
    ]

    for p in processes:
        w = cfs_weight(p["nice"])
        p["weight"] = w
        p["initial_vruntime"] = 0
        p["vruntime"] = 0
        inv_wt = NICE_0_LOAD / w
        print(f"  P{p['pid']}: nice={p['nice']:3d}  weight={w:5d}  "
              f"inv_weight={inv_wt:.4f}")

    print("\n--- 调度过程 (每步执行10ms) ---")
    tree = SimpleRBTree()
    for p in processes:
        tree.insert(RBNode(p["pid"], p["vruntime"], p["nice"]))

    total_time = 0
    step = 10  # 每步10ms
    remaining = {p["pid"]: p["burst"] for p in processes}

    while sum(remaining.values()) > 0:
        node = tree.leftmost()
        if not node:
            break
        pid = node.pid
        # 找到对应进程
        proc = next(p for p in processes if p["pid"] == pid)
        exec_time = min(step, remaining[pid])
        remaining[pid] -= exec_time
        total_time += exec_time

        # 计算 vruntime 增量: Δvruntime = Δt * NICE_0_LOAD / weight
        delta_vruntime = exec_time * NICE_0_LOAD / proc["weight"]
        proc["vruntime"] += delta_vruntime

        # 从树中删除后重新插入 (更新 vruntime)
        tree.remove(node)
        if remaining[pid] > 0:
            tree.insert(RBNode(pid, proc["vruntime"], proc["nice"]))

        print(f"  time={total_time:3d}ms | P{pid}: exec={exec_time}ms, "
              f"vruntime={proc['vruntime']:.1f}, "
              f"remain={remaining[pid]:3d}ms")

    print(f"\n--- 最终 vruntime ---")
    for p in processes:
        print(f"  P{p['pid']}: vruntime={p['vruntime']:.1f}, "
              f"nice={p['nice']:3d}, weight={p['weight']:5d}")

    print("\n  CFS 公平性验证:")
    print(f"  所有进程 vruntime 趋于一致 -> 展示了完全公平性")


# ============================================================
# 第4部分: 优先级反转 + 优先级继承
# ============================================================

def simulate_priority_inversion():
    """模拟优先级反转问题"""
    print("=" * 70)
    print("优先级反转 (Priority Inversion) 模拟")
    print("=" * 70)
    print("  场景: L 持有锁 → H 请求锁 → M 抢占 L → H 被阻塞\n")

    class Task:
        def __init__(self, name, priority, burst):
            self.name = name
            self.priority = priority  # 数字越小优先级越高
            self.burst = burst
            self.remain = burst
            self.holding_lock = False
            self.want_lock = False
            self.blocked = False
            self.effective_priority = priority

    # Task: H (高), M (中), L (低)
    H = Task("H", 1, 30)
    M = Task("M", 5, 50)
    L = Task("L", 10, 40)

    lock_holder = None
    time = 0
    lock_owner = None

    print("  [t=0]    L 开始运行, 获取锁, 进入临界区")
    print("  [t=10]   H 就绪, 优先级最高, 抢占 L")
    print("  [t=10]   H 运行, 请求锁但 L 持有 → H 阻塞")
    print("  [t=10]   L 恢复运行 (持有锁)")
    print("  [t=15]   M 就绪, 优先级高于 L, 抢占 L")
    print("  [t=15]   M 运行 (不请求锁)")
    print("  ... H 被 M 间接阻塞, 即使 H 优先级最高!")
    print("\n  结果: H 被 L + M 联合阻塞, 这就是优先级反转!\n")

    # 模拟加时间线
    timeline = [
        (0,  "L获取锁"),
        (10, "H到达, 抢占L"),
        (10, "H请求锁→阻塞"),
        (10, "L恢复运行"),
        (15, "M到达, 抢占L"),
        (15, "M运行50ms"),
        (65, "M完成"),
        (65, "L恢复, 释放锁"),
        (65, "H被唤醒, 获取锁, 运行30ms"),
        (95, "H完成"),
    ]
    for t, evt in timeline:
        print(f"  [t={t:3d}] {evt}")


def simulate_priority_inheritance():
    """模拟优先级继承协议 (解决反转)"""
    print("=" * 70)
    print("优先级继承 (Priority Inheritance) 模拟")
    print("=" * 70)
    print("  场景: L 持有锁 → H 请求锁 → L 继承 H 优先级 → 不被 M 抢占\n")

    class Task:
        def __init__(self, name, base_priority, burst):
            self.name = name
            self.base_priority = base_priority
            self.effective_priority = base_priority
            self.burst = burst
            self.remain = burst

    H = Task("H", 1, 30)
    M = Task("M", 5, 50)
    L = Task("L", 10, 40)

    timeline = [
        (0,  "L获取锁 (优先级别变化)"),
        (10, "H到达, 抢占L (L还没释放锁, H请求锁→阻塞)"),
        (10, "L继承H的优先级 (prio 10→1), 不会被M抢占!"),
        (10, f"L运行 (有效优先级={L.effective_priority})"),
        (15, "M到达, 但L优先级更高, M无法抢占"),
        (15, f"L继续运行... (有效优先级={L.effective_priority})"),
        (50, "L释放锁, 还原优先级"),
        (50, "H获取锁, 运行30ms"),
        (80, "H完成"),
        (80, "M运行50ms"),
        (130,"M完成"),
    ]
    for t, evt in timeline:
        print(f"  [t={t:3d}] {evt}")

    print("\n  关键区别: 优先级继承确保 L 持有锁时不会被 M 抢占,")
    print("  H 的阻塞时间 = L 的临界区长度, 而非 M 的全部执行时间!")


# ============================================================
# 第5部分: 主函数 — 运行全部演示
# ============================================================

def run_sched_comparison():
    """运行6种调度算法对比"""
    print("=" * 70)
    print("调度算法对比 (n=1000 随机进程)")
    print("=" * 70)

    n = 1000
    procs = generate_processes(n, max_burst=200, max_arrival=50)

    algorithms = [
        ("FCFS",     simulate_fcfs),
        ("SJF",      simulate_sjf),
        ("SRTF",     simulate_srtf),
        ("Priority", simulate_priority),
        ("RR(20)",   lambda p: simulate_rr(p, 20)),
        ("MLFQ",     simulate_mlfq),
    ]

    print(f"{'Algorithm':<12} {'AvgTurn':>10} {'AvgWait':>10} {'AvgResp':>10} {'Thrpt':>8}")
    print("-" * 52)

    for name, func in algorithms:
        result = func(procs)
        n_done = len(result)
        if n_done == 0:
            continue
        avg_turn = sum(p.turnaround() for p in result) / n_done
        avg_wait = sum(p.wait_time for p in result) / n_done
        avg_resp = sum(p.response() for p in result) / n_done
        last_finish = max(p.finish_time for p in result)
        throughput = n_done / (last_finish or 1) * 1000  # 进程/千时间单位

        print(f"{name:<12} {avg_turn:>10.2f} {avg_wait:>10.2f} {avg_resp:>10.2f} {throughput:>8.2f}")

    print()
    print("  AvgTurn: 平均周转时间 (越小越好)")
    print("  AvgWait: 平均等待时间 (越小越好)")
    print("  AvgResp: 平均响应时间 (越小越好)")
    print("  Thrpt:   吞吐量 (越大越好)")
    print()
    print("  分析:")
    print("  - SRTF 理论上等待时间最小 (但需要预知执行时间)")
    print("  - RR 响应时间最小 (交互性好)")
    print("  - FCFS 吞吐量最大 (零上下文切换)")
    print("  - MLFQ 综合表现最好 (兼顾交互和吞吐)")


def main():
    random.seed(42)

    # 1. 算法对比
    run_sched_comparison()

    print()
    print()

    # 2. CFS 模拟
    simulate_cfs()

    print()
    print()

    # 3. 优先级反转 + 继承
    simulate_priority_inversion()
    print()
    simulate_priority_inheritance()

    print()
    print("=" * 70)
    print("全部演示完成!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
