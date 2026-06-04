#!/usr/bin/env python
"""Task Queue — 单元测试"""
import time
import os
import sys
import unittest
import tempfile
import shutil
import threading

# 确保可以导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task import Task
from queue import TaskQueue
from worker import Worker
from scheduler import Scheduler
from storage import Storage


class TestTask(unittest.TestCase):
    """1. 任务创建与属性"""

    def test_task_creation_and_attributes(self):
        t = Task('echo', args=['hello'], kwargs={'name': 'world'},
                 priority=5, delay=10, max_retries=2, timeout=15)
        self.assertEqual(t.func_name, 'echo')
        self.assertEqual(t.args, ['hello'])
        self.assertEqual(t.kwargs, {'name': 'world'})
        self.assertEqual(t.priority, 5)
        self.assertEqual(t.delay, 10)
        self.assertEqual(t.max_retries, 2)
        self.assertEqual(t.timeout, 15)
        self.assertEqual(t.status, Task.PENDING)
        self.assertEqual(t.retries, 0)
        self.assertIsNotNone(t.id)
        self.assertIsNone(t.started_at)
        self.assertIsNone(t.completed_at)
        self.assertIsNone(t.result)
        self.assertIsNone(t.error)

    def test_task_scheduled_at_with_delay(self):
        now = time.time()
        t = Task('echo', delay=5)
        self.assertAlmostEqual(t.scheduled_at, now + 5, delta=0.01)

    def test_task_scheduled_at_no_delay(self):
        now = time.time()
        t = Task('echo', delay=0)
        self.assertAlmostEqual(t.scheduled_at, now, delta=0.01)

    def test_task_to_dict_and_from_dict(self):
        t = Task('compute', args=[1, 2], priority=3)
        d = t.to_dict()
        t2 = Task.from_dict(d)
        self.assertEqual(t.id, t2.id)
        self.assertEqual(t.func_name, t2.func_name)
        self.assertEqual(t.args, t2.args)
        self.assertEqual(t.priority, t2.priority)
        self.assertEqual(t.status, t2.status)

    def test_task_lt_by_time_then_priority(self):
        now = time.time()
        t1 = Task('a', priority=1)
        t1.scheduled_at = now + 10
        t2 = Task('b', priority=5)
        t2.scheduled_at = now + 5
        self.assertTrue(t2 < t1)  # 较早调度时间更高

        t3 = Task('c', priority=1)
        t3.scheduled_at = now + 5
        t4 = Task('d', priority=5)
        t4.scheduled_at = now + 5
        self.assertTrue(t3 < t4)  # 相同时间，低优先更高


class TestTaskQueue(unittest.TestCase):
    """队列核心测试"""

    def setUp(self):
        self.q = TaskQueue()

    def test_enqueue_dequeue(self):
        """2. 入队出队"""
        t = Task('echo', args=['hello'])
        tid = t.id
        self.q.enqueue(t)
        self.assertEqual(self.q.size(), 1)
        dequeued = self.q.dequeue(timeout=1.0)
        self.assertIsNotNone(dequeued)
        self.assertEqual(dequeued.id, tid)
        self.assertEqual(dequeued.status, Task.RUNNING)
        self.assertIsNotNone(dequeued.started_at)

    def test_priority_order(self):
        """3. 优先级排序（高优先先出）"""
        # 使用相同调度时间，确保按优先级排序
        same_time = time.time()
        low = Task('low', priority=10)
        low.scheduled_at = same_time
        high = Task('high', priority=1)
        high.scheduled_at = same_time
        # high 优先级更高（数字小），即使先入队 low，也应先出 high
        self.q.enqueue(low)
        self.q.enqueue(high)
        # 两个 ready 任务，高优先应先出
        t1 = self.q.dequeue(timeout=1.0)
        t2 = self.q.dequeue(timeout=1.0)
        self.assertEqual(t1.func_name, 'high')
        self.assertEqual(t2.func_name, 'low')

    def test_priority_with_same_time(self):
        """优先级在相同调度时间下生效"""
        # 按 priority 顺序入队，验证正确出队顺序
        t3 = Task('p3', priority=3)
        t1 = Task('p1', priority=1)
        t2 = Task('p2', priority=2)
        # 设置相同调度时间
        now = time.time()
        for t in [t1, t2, t3]:
            t.scheduled_at = now
        self.q.enqueue(t3)
        self.q.enqueue(t1)
        self.q.enqueue(t2)
        out1 = self.q.dequeue(timeout=1.0)
        out2 = self.q.dequeue(timeout=1.0)
        out3 = self.q.dequeue(timeout=1.0)
        self.assertEqual(out1.func_name, 'p1')
        self.assertEqual(out2.func_name, 'p2')
        self.assertEqual(out3.func_name, 'p3')

    def test_delay_execution(self):
        """4. 延迟执行"""
        t = Task('delayed', delay=0.3)
        self.q.enqueue(t)
        # 立即 dequeue 应返回 None
        start = time.time()
        result = self.q.dequeue(timeout=0.1)
        elapsed = time.time() - start
        self.assertIsNone(result)
        # 等待延迟后应取出
        time.sleep(0.4)
        result = self.q.dequeue(timeout=1.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.func_name, 'delayed')

    def test_cancel_task(self):
        """5. 任务取消"""
        t = Task('cancellable')
        self.q.enqueue(t)
        ok = self.q.cancel(t.id)
        self.assertTrue(ok)
        self.assertEqual(t.status, Task.CANCELLED)
        # 取消后不应出队
        result = self.q.dequeue(timeout=0.3)
        self.assertIsNone(result)

    def test_cancel_non_existent(self):
        t = Task('x')
        ok = self.q.cancel('non_existent')
        self.assertFalse(ok)

    def test_complete_status(self):
        """6. 完成状态"""
        t = Task('done')
        self.q.enqueue(t)
        self.q.dequeue(timeout=1.0)
        self.q.complete(t, 'ok')
        self.assertEqual(t.status, Task.COMPLETED)
        self.assertEqual(t.result, 'ok')
        self.assertIsNotNone(t.completed_at)

    def test_fail_and_retry(self):
        """7. 失败与重试（指数退避）"""
        t = Task('flaky', max_retries=3)
        self.q.enqueue(t)
        self.q.dequeue(timeout=1.0)
        # 第一次失败，应重试
        self.q.fail(t, 'error1')
        self.assertEqual(t.retries, 1)
        self.assertEqual(t.status, Task.PENDING)
        # 检查指数退避时间
        expected_delay = 2 ** 1  # 第一次重试 = 2^1 = 2s
        self.assertAlmostEqual(t.scheduled_at, time.time() + expected_delay, delta=0.1)

        # 模拟第二次失败
        t.scheduled_at = time.time()
        self.q.dequeue(timeout=0.1)
        self.q.fail(t, 'error2')
        self.assertEqual(t.retries, 2)
        expected_delay = 2 ** 2  # = 4s
        self.assertAlmostEqual(t.scheduled_at, time.time() + expected_delay, delta=0.1)

        # 模拟第三次失败 — 耗尽重试次数
        t.scheduled_at = time.time()
        self.q.dequeue(timeout=0.1)
        self.q.fail(t, 'error3')
        self.assertEqual(t.retries, 3)
        self.assertEqual(t.status, Task.FAILED)
        self.assertEqual(t.error, 'error3')

    def test_get_task(self):
        t = Task('findme')
        self.q.enqueue(t)
        found = self.q.get_task(t.id)
        self.assertEqual(found.id, t.id)
        not_found = self.q.get_task('nope')
        self.assertIsNone(not_found)

    def test_empty_queue(self):
        """14. 空队列"""
        result = self.q.dequeue(timeout=0.3)
        self.assertIsNone(result)
        self.assertEqual(self.q.size(), 0)
        self.assertEqual(len(self.q.get_all()), 0)


class TestWorker(unittest.TestCase):
    """工作线程测试"""

    def setUp(self):
        self.q = TaskQueue()
        self.results = []

    def handler_append(self, value):
        self.results.append(value)
        return value

    def handler_raise(self):
        raise ValueError("故意的错误")

    def test_worker_register_and_execute(self):
        """8. 工作线程注册与执行"""
        w = Worker(self.q, {'append': self.handler_append}, num_workers=1)
        w.start()

        t = Task('append', args=['hello'])
        self.q.enqueue(t)

        time.sleep(0.6)
        w.stop()

        self.assertEqual(len(self.results), 1)
        self.assertEqual(self.results[0], 'hello')
        self.assertEqual(t.status, Task.COMPLETED)
        self.assertEqual(t.result, 'hello')

    def test_worker_multi_task(self):
        """9. 工作线程池多任务"""
        w = Worker(self.q, {'append': self.handler_append}, num_workers=4)
        w.start()

        for i in range(10):
            t = Task('append', args=[i])
            self.q.enqueue(t)

        time.sleep(0.6)
        w.stop()

        self.assertEqual(len(self.results), 10)
        self.assertEqual(sorted(self.results), list(range(10)))

    def test_worker_unknown_handler(self):
        """未知处理器应标记为失败"""
        w = Worker(self.q, {}, num_workers=1)
        w.start()

        t = Task('unknown_func', max_retries=0)
        self.q.enqueue(t)

        time.sleep(1.5)
        w.stop()

        self.assertEqual(t.status, Task.FAILED)
        self.assertIn('未知任务', t.error)

    def test_worker_handler_error(self):
        """处理器抛出异常应重试并最终失败"""
        w = Worker(self.q, {'raise': self.handler_raise}, num_workers=1)
        w.start()

        t = Task('raise', max_retries=1)
        self.q.enqueue(t)

        time.sleep(3.5)
        w.stop()

        # max_retries=1，所以一次重试后应 FAILED（初始执行 + 1次重试）
        self.assertEqual(t.status, Task.FAILED)
        self.assertIn('故意的错误', str(t.error))


class TestScheduler(unittest.TestCase):
    """调度器测试"""

    def setUp(self):
        self.q = TaskQueue()
        self.results = []

    def handler_record(self, value):
        self.results.append(value)

    def test_scheduler_every(self):
        """10. 调度器定时任务"""
        sched = Scheduler(self.q)
        sched.every('test_job', 'record', interval=0.3,
                     args=['tick'], kwargs={})
        w = Worker(self.q, {'record': self.handler_record}, num_workers=2)

        sched.start()
        w.start()

        time.sleep(1.0)  # 大约触发 3 次（0s, 0.3s, 0.6s, 0.9s）
        sched.stop()
        w.stop()

        # 应该至少触发 2 次（可能有时间误差）
        self.assertGreaterEqual(len(self.results), 2)
        self.assertIn('tick', self.results)

    def test_scheduler_stop(self):
        """11. 调度器停止"""
        sched = Scheduler(self.q)
        sched.every('frequent', 'record', interval=0.1,
                     args=['x'], kwargs={})
        w = Worker(self.q, {'record': self.handler_record}, num_workers=2)

        sched.start()
        time.sleep(0.4)
        sched.stop()
        count_before = len(self.results)

        time.sleep(0.5)
        w.stop()

        # 停止后不应增加
        self.assertEqual(len(self.results), count_before)


class TestStorage(unittest.TestCase):
    """持久化测试"""

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.storage = Storage(self.tempdir)
        self.q = TaskQueue()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_save_and_load(self):
        """12. 持久化保存加载"""
        # 创建并保存一些任务
        t1 = Task('task1')
        t2 = Task('task2', delay=5)
        self.q.enqueue(t1)
        self.q.enqueue(t2)
        self.storage.save(self.q)

        # 检查文件存在
        self.assertTrue(os.path.exists(
            os.path.join(self.tempdir, 'tasks.json')))

        # 新建队列并加载
        q2 = TaskQueue()
        self.storage.load(q2)

        self.assertEqual(q2.size(), 2)
        # task1 应该立即可出队（scheduled_at 已过）
        loaded_t1 = q2.dequeue(timeout=0.1)
        self.assertIsNotNone(loaded_t1)
        self.assertEqual(loaded_t1.func_name, 'task1')

    def test_load_empty(self):
        """加载空文件不报错"""
        q2 = TaskQueue()
        # 没有文件，不应报错
        self.storage.load(q2)
        self.assertEqual(q2.size(), 0)

    def test_clear(self):
        self.storage.save(self.q)
        self.storage.clear()
        self.assertFalse(os.path.exists(
            os.path.join(self.tempdir, 'tasks.json')))


class TestExtra(unittest.TestCase):
    """额外测试"""

    def test_unique_ids(self):
        """15. 任务 ID 唯一"""
        ids = {Task('a').id for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_multiple_enqueue(self):
        """16. 多次入队"""
        q = TaskQueue()
        t = Task('multi')
        q.enqueue(t)
        # 不应抛出异常
        q.enqueue(Task('another'))
        self.assertEqual(q.size(), 2)

    def test_timeout_property(self):
        """13. 超时处理（属性检查）"""
        t = Task('timeout_test', timeout=5)
        self.assertEqual(t.timeout, 5)
        t2 = Task('default')
        self.assertEqual(t2.timeout, 30)

    def test_dequeue_multiple(self):
        """多个就绪任务依次出队"""
        q = TaskQueue()
        t1 = Task('a')
        t2 = Task('b')
        t3 = Task('c')
        q.enqueue(t1)
        q.enqueue(t2)
        q.enqueue(t3)

        out1 = q.dequeue(timeout=1.0)
        out2 = q.dequeue(timeout=1.0)
        out3 = q.dequeue(timeout=1.0)
        self.assertIsNotNone(out1)
        self.assertIsNotNone(out2)
        self.assertIsNotNone(out3)

    def test_get_all(self):
        q = TaskQueue()
        q.enqueue(Task('a'))
        q.enqueue(Task('b'))
        self.assertEqual(len(q.get_all()), 2)


if __name__ == '__main__':
    unittest.main()
