#!/usr/bin/env python
"""Task Queue — CLI 入口"""
import argparse
import time
import json
import sys

from task import Task
from queue import TaskQueue
from worker import Worker
from scheduler import Scheduler
from storage import Storage


def demo_echo(*args, **kwargs):
    return f"echo: {args} {kwargs}"


def main():
    parser = argparse.ArgumentParser(description='Task Queue CLI')
    parser.add_argument('action', nargs='?', default='info',
                        choices=['info', 'enqueue', 'status', 'cancel',
                                 'worker', 'scheduler', 'save', 'load'])
    parser.add_argument('--func', '-f', default='echo',
                        help='任务函数名')
    parser.add_argument('--args', '-a', nargs='*', default=[],
                        help='任务参数')
    parser.add_argument('--priority', '-p', type=int, default=0,
                        help='优先级（越小越高）')
    parser.add_argument('--delay', '-d', type=int, default=0,
                        help='延迟秒数')
    parser.add_argument('--task-id', '-t', help='任务 ID')
    parser.add_argument('--max-retries', type=int, default=3,
                        help='最大重试次数')

    args = parser.parse_args()

    q = TaskQueue()
    storage = Storage()

    # 尝试加载持久化数据
    storage.load(q)

    if args.action == 'info':
        print(f"队列状态:")
        print(f"  等待任务: {q.size()}")
        print(f"  总任务数: {len(q.get_all())}")
        tasks = q.get_all()
        if tasks:
            print(f"\n任务列表:")
            for t in tasks:
                print(f"  [{t.status:^9}] {t.id[:8]} | {t.func_name} | "
                      f"prio={t.priority} | retry={t.retries}/{t.max_retries}"
                      f"{' | error=' + t.error if t.error else ''}")

    elif args.action == 'enqueue':
        task = Task(args.func, args.args, {},
                    priority=args.priority,
                    delay=args.delay,
                    max_retries=args.max_retries)
        q.enqueue(task)
        storage.save(q)
        print(f"任务已入队: {task.id} ({task.func_name})")

    elif args.action == 'status':
        if args.task_id:
            t = q.get_task(args.task_id)
            if t:
                print(json.dumps(t.to_dict(), indent=2, default=str))
            else:
                print(f"任务 {args.task_id} 不存在")
        else:
            print(f"队列任务数: {q.size()}")
            for t in q.get_all():
                print(f"  {t.id[:8]} | {t.func_name} | {t.status} "
                      f"| retry {t.retries}/{t.max_retries}")

    elif args.action == 'cancel':
        if args.task_id:
            ok = q.cancel(args.task_id)
            print(f"取消{'成功' if ok else '失败'}")
            storage.save(q)
        else:
            print("请指定 --task-id")

    elif args.action == 'worker':
        w = Worker(q, {'echo': demo_echo}, num_workers=2)
        w.start()
        print("工作线程已启动（按 Ctrl+C 停止）")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            w.stop()
            storage.save(q)
            print("\n已停止")

    elif args.action == 'scheduler':
        sched = Scheduler(q)
        sched.every('demo', 'echo', interval=5)
        sched.start()
        w = Worker(q, {'echo': demo_echo}, num_workers=2)
        w.start()
        print("调度器已启动（每 5 秒触发 demo，按 Ctrl+C 停止）")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sched.stop()
            w.stop()
            storage.save(q)
            print("\n已停止")

    elif args.action == 'save':
        storage.save(q)
        print("已持久化")

    elif args.action == 'load':
        storage.load(q)
        print(f"已加载 {q.size()} 个任务")


if __name__ == '__main__':
    main()
