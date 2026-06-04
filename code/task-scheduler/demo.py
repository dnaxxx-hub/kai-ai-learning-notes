"""
Demo: 分布式任务调度器
"""
import time
import sys
import os
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task import Task, task, list_tasks
from queue import TaskQueue
from worker import Worker
from backend import ResultBackend
from scheduler import Scheduler

DATA_DIR = 'ts_demo_data'


@task
def add(a, b):
    """加法任务"""
    return a + b


@task(name='greet')
def say_hello(name):
    """问候任务"""
    return f"Hello, {name}!"


@task(max_retries=2)
def flaky_task(success=True):
    """不稳定任务（用于演示重试）"""
    import random
    if not success and random.random() < 0.6:
        raise ValueError("Random failure!")
    return "Done"


def demo():
    print("=" * 60)
    print("  任务调度器 Demo")
    print("=" * 60)

    # Clean up old data
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)

    # 1. List registered tasks
    print("\n1. 已注册任务:")
    for name in list_tasks():
        print(f"   - {name}")

    # 2. Initialize components
    print("\n2. 初始化组件...")
    q = TaskQueue(data_path=f"{DATA_DIR}/queue")
    b = ResultBackend(data_path=f"{DATA_DIR}/backend")
    w = Worker('demo-worker', concurrency=4)
    s = Scheduler(q)

    w.start(q, b)
    s.start()
    print("   Worker + Scheduler 已启动")

    # 3. Submit tasks
    print("\n3. 提交异步任务...")
    tasks = []
    for i in range(5):
        t = Task('add', args=[i, i * 10], priority=i)
        q.put(t)
        tasks.append(t.task_id)
        print(f"   [{t.task_id[:8]}] add({i}, {i * 10})  priority={i}")

    t = Task('greet', args=['World'])
    q.put(t)
    tasks.append(t.task_id)
    print(f"   [{t.task_id[:8]}] greet('World')")

    # 4. Wait for results
    print("\n4. 等待执行结果...")
    time.sleep(1.5)

    print("\n5. 查询结果:")
    for tid in tasks:
        r = b.get_result(tid)
        if r:
            print(f"   [{tid[:8]}] {r['name']} -> {r['status']} result={r.get('result')}")

    # 6. Scheduled tasks
    print("\n6. 定时任务演示...")
    s.add_task('every_2s', 'greet', args=['Scheduler'], interval=1.0)
    time.sleep(2.2)

    scheduled = s.list_tasks()
    for st in scheduled:
        print(f"   {st['name']}: {st['task_name']} @ {st['interval']}s "
              f"ran={st['last_run'] > 0}")

    # 7. Recent results
    print("\n7. 最近结果:")
    results = b.list_results(limit=10)
    for r in results:
        print(f"   [{r['task_id'][:8]}] {r['name']} -> {r['status']} "
              f"result={r.get('result')}")

    # 8. Queue state
    print(f"\n8. 队列状态: size={q.size()}")

    # Cleanup
    s.stop()
    w.stop()
    print("\n9. 组件已停止")

    # Cleanup data
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)
    print("\n✅ Demo 完成!")


if __name__ == '__main__':
    demo()
