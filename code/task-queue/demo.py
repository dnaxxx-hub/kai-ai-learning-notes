#!/usr/bin/env python
"""Task Queue — 完整演示脚本"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task import Task
from queue import TaskQueue
from worker import Worker
from scheduler import Scheduler
from storage import Storage


def add(a, b):
    print(f"  [Worker] add({a}, {b}) = {a + b}")
    return a + b


def greet(name):
    print(f"  [Worker] Hello, {name}!")
    return f"Hello, {name}!"


def failing_task():
    raise RuntimeError("模拟失败")


def main():
    print("=" * 60)
    print("Task Queue 演示")
    print("=" * 60)

    q = TaskQueue()
    storage = Storage()

    # ── 1. 基本入队出队 ──
    print("\n1️⃣  基本入队出队")
    t = Task('add', args=[3, 4])
    q.enqueue(t)
    out = q.dequeue(timeout=1.0)
    if out:
        print(f"   出队: {out.id[:8]} | {out.func_name}({out.args})")
    else:
        print("   出队超时")

    # ── 2. 优先级 ──
    print("\n2️⃣  优先级测试 (1 > 5 > 10)")
    q2 = TaskQueue()
    q2.enqueue(Task('add', args=[1, 1], priority=10))
    q2.enqueue(Task('add', args=[2, 2], priority=1))
    q2.enqueue(Task('add', args=[3, 3], priority=5))
    for _ in range(3):
        t = q2.dequeue(timeout=1.0)
        if t:
            print(f"   优先级 {t.priority}: {t.id[:8]}")

    # ── 3. 延迟执行 ──
    print("\n3️⃣  延迟执行 (0.5s)")
    t_delayed = Task('greet', args=['Alice'], delay=0.5)
    q3 = TaskQueue()
    q3.enqueue(t_delayed)
    start = time.time()
    out = q3.dequeue(timeout=1.0)
    elapsed = time.time() - start
    print(f"   延迟了 {elapsed:.2f}s 后出队")

    # ── 4. 任务取消 ──
    print("\n4️⃣  任务取消")
    t_cancel = Task('greet', args=['Bob'])
    q4 = TaskQueue()
    q4.enqueue(t_cancel)
    ok = q4.cancel(t_cancel.id)
    print(f"   取消{'成功' if ok else '失败'}")
    out = q4.dequeue(timeout=0.3)
    print(f"   取消后出队 = {'None (正确)' if out is None else '异常'}")

    # ── 5. 工作线程 + 持久化 ──
    print("\n5️⃣  工作线程池 (3 workers) + 持久化")
    q5 = TaskQueue()
    w = Worker(q5, {'add': add, 'greet': greet}, num_workers=3)
    w.start()

    for i in range(5):
        q5.enqueue(Task('add', args=[i, i * 10]))
    q5.enqueue(Task('greet', args=['World']))
    time.sleep(0.5)
    w.stop()

    storage.path = 'task_queue_data'
    storage.save(q5)
    print(f"   已持久化 {len(q5.get_all())} 个任务")

    # ── 6. 失败与重试 ──
    print("\n6️⃣  失败与重试")
    q6 = TaskQueue()
    w6 = Worker(q6, {'failing_task': failing_task}, num_workers=1)
    w6.start()
    t_fail = Task('failing_task', max_retries=2)
    q6.enqueue(t_fail)
    time.sleep(3)
    w6.stop()
    print(f"   状态: {t_fail.status}")
    print(f"   重试次数: {t_fail.retries}")
    if t_fail.error:
        print(f"   错误: {t_fail.error}")

    # ── 7. 调度器 ──
    print("\n7️⃣  调度器 (每 0.5s 执行 greet)")
    q7 = TaskQueue()
    sched = Scheduler(q7)
    sched.every('d', 'greet', interval=0.5, args=['Scheduled'])
    w7 = Worker(q7, {'greet': greet}, num_workers=2)
    sched.start()
    w7.start()
    time.sleep(1.2)
    sched.stop()
    w7.stop()
    print(f"   调度器产生 {len(q7.get_all())} 个任务")

    # ── 8. 从持久化加载 ──
    print("\n8️⃣  从持久化加载")
    storage.path = 'task_queue_data'
    q8 = TaskQueue()
    storage.load(q8)
    print(f"   已加载 {q8.size()} 个等待任务")

    print("\n" + "=" * 60)
    print("演示完成 ✅")
    print("=" * 60)


if __name__ == '__main__':
    main()
