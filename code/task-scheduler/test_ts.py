import unittest
import time
import json
import os
import threading
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task import Task, task, get_task_func, list_tasks, _tasks
from queue import TaskQueue
from worker import Worker
from backend import ResultBackend
from scheduler import Scheduler


# ==================== Test data dir cleanup ====================

TEST_DATA_DIR = 'ts_test_data'


def clean_test_data():
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR)


# ==================== Test: Task 创建 ====================

class TestTaskCreation(unittest.TestCase):
    def test_01_create_task_defaults(self):
        """Test 1: Task creation with default parameters"""
        t = Task('test_task')
        self.assertIsNotNone(t.task_id)
        self.assertEqual(t.name, 'test_task')
        self.assertEqual(t.args, [])
        self.assertEqual(t.kwargs, {})
        self.assertEqual(t.status, Task.PENDING)
        self.assertEqual(t.retries, 0)
        self.assertEqual(t.max_retries, 3)
        self.assertEqual(t.priority, 0)
        self.assertIsNone(t.started_at)
        self.assertIsNone(t.completed_at)

    def test_02_task_with_args(self):
        """Test 2: Task with args/kwargs"""
        t = Task('add', args=[1, 2], kwargs={'c': 3}, priority=5,
                 schedule_time=1234567890.0)
        self.assertEqual(t.args, [1, 2])
        self.assertEqual(t.kwargs, {'c': 3})
        self.assertEqual(t.priority, 5)
        self.assertEqual(t.schedule_time, 1234567890.0)

    def test_03_task_id_unique(self):
        """Test 3: Task IDs are unique"""
        t1 = Task('a')
        t2 = Task('a')
        self.assertNotEqual(t1.task_id, t2.task_id)

    def test_04_task_with_custom_id(self):
        """Test 4: Custom task ID"""
        t = Task('x', task_id='my-custom-id')
        self.assertEqual(t.task_id, 'my-custom-id')

    def test_05_task_max_retries(self):
        """Test 5: Custom max_retries"""
        t = Task('x', max_retries=5)
        self.assertEqual(t.max_retries, 5)


# ==================== Test: Task 状态转换 ====================

class TestTaskStatus(unittest.TestCase):
    def test_06_status_transitions(self):
        """Test 6: Status transitions"""
        t = Task('test')
        self.assertEqual(t.status, Task.PENDING)
        t.status = Task.RUNNING
        self.assertEqual(t.status, Task.RUNNING)
        t.status = Task.SUCCESS
        self.assertEqual(t.status, Task.SUCCESS)


# ==================== Test: Task 序列化 ====================

class TestTaskSerialization(unittest.TestCase):
    def test_07_to_dict(self):
        """Test 7: Task to_dict produces all keys"""
        t = Task('serialize', args=[1, 'hello'], priority=2)
        d = t.to_dict()
        self.assertEqual(d['name'], 'serialize')
        self.assertEqual(d['args'], [1, 'hello'])
        self.assertEqual(d['priority'], 2)
        self.assertEqual(d['status'], Task.PENDING)
        self.assertIn('task_id', d)
        self.assertIn('created_at', d)

    def test_08_roundtrip(self):
        """Test 8: Task to_dict -> from_dict roundtrip"""
        t1 = Task('rt', args=[42], kwargs={'opt': True}, priority=3)
        t1.status = Task.SUCCESS
        t1.result = 'done'
        d = t1.to_dict()
        t2 = Task('', task_id=d['task_id'])
        t2.__dict__.update(d)
        self.assertEqual(t2.task_id, t1.task_id)
        self.assertEqual(t2.name, t1.name)
        self.assertEqual(t2.args, t1.args)
        self.assertEqual(t2.kwargs, t1.kwargs)
        self.assertEqual(t2.priority, t1.priority)
        self.assertEqual(t2.status, t1.status)
        self.assertEqual(t2.result, t1.result)


# ==================== Test: 任务装饰器 ====================

class TestTaskDecorator(unittest.TestCase):
    def setUp(self):
        # Save and clear _tasks
        self.saved_tasks = dict(_tasks)
        _tasks.clear()

    def tearDown(self):
        _tasks.clear()
        _tasks.update(self.saved_tasks)

    def test_09_register_task(self):
        """Test 9: Register task via decorator"""
        @task
        def my_func():
            return 42
        self.assertIn('my_func', _tasks)
        info = get_task_func('my_func')
        self.assertIsNotNone(info)
        self.assertEqual(info['name'], 'my_func')

    def test_10_custom_task_name(self):
        """Test 10: Custom task name"""
        @task(name='custom_name')
        def another_func():
            return 'hello'
        self.assertIn('custom_name', _tasks)
        self.assertNotIn('another_func', _tasks)

    def test_11_task_execution(self):
        """Test 11: Task function execution"""
        @task
        def add(a, b):
            return a + b
        info = get_task_func('add')
        result = info['func'](3, 4)
        self.assertEqual(result, 7)

    def test_12_list_tasks(self):
        """Test 12: list_tasks returns registered names"""
        _tasks.clear()
        @task
        def fn_a():
            pass
        @task(name='fn_b')
        def fn_x():
            pass
        tl = list_tasks()
        self.assertIn('fn_a', tl)
        self.assertIn('fn_b', tl)


# ==================== Test: TaskQueue ====================

class TestTaskQueue(unittest.TestCase):
    def setUp(self):
        self.data_dir = os.path.join(TEST_DATA_DIR, 'queue')
        os.makedirs(self.data_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.data_dir):
            shutil.rmtree(self.data_dir)

    def test_13_put_get(self):
        """Test 13: TaskQueue put and get"""
        q = TaskQueue(data_path=self.data_dir)
        t = Task('test')
        q.put(t)
        self.assertEqual(q.size(), 1)
        got = q.get(timeout=1)
        self.assertIsNotNone(got)
        self.assertEqual(got.task_id, t.task_id)
        self.assertEqual(q.size(), 0)

    def test_14_get_empty(self):
        """Test 14: Get from empty queue with timeout"""
        q = TaskQueue(data_path=self.data_dir)
        result = q.get(timeout=0.5)
        self.assertIsNone(result)

    def test_15_priority(self):
        """Test 15: Priority ordering (higher priority first)"""
        q = TaskQueue(data_path=self.data_dir)
        t_high = Task('high', priority=10)
        t_low = Task('low', priority=0)
        q.put(t_low)
        q.put(t_high)
        # First get should be high priority
        first = q.get(timeout=1)
        self.assertEqual(first.name, 'high')
        second = q.get(timeout=1)
        self.assertEqual(second.name, 'low')

    def test_16_peek(self):
        """Test 16: Peek returns head without removing"""
        q = TaskQueue(data_path=self.data_dir)
        self.assertIsNone(q.peek())
        t = Task('peek_test')
        q.put(t)
        peeked = q.peek()
        self.assertIsNotNone(peeked)
        self.assertEqual(peeked.task_id, t.task_id)
        self.assertEqual(q.size(), 1)  # Not removed

    def test_17_scheduled_task_delayed(self):
        """Test 17: Scheduled task is delayed"""
        q = TaskQueue(data_path=self.data_dir)
        future = time.time() + 60
        t = Task('future', schedule_time=future)
        q.put(t)
        # Should not be returned immediately
        got = q.get(timeout=0.5)
        self.assertIsNone(got)

    def test_18_scheduled_task_now(self):
        """Test 18: Scheduled task in the past runs immediately"""
        q = TaskQueue(data_path=self.data_dir)
        past = time.time() - 10
        t = Task('past', schedule_time=past)
        q.put(t)
        got = q.get(timeout=0.5)
        self.assertIsNotNone(got)
        self.assertEqual(got.name, 'past')

    def test_19_queue_persistence(self):
        """Test 19: Queue persistence across instances"""
        q1 = TaskQueue(data_path=self.data_dir)
        t = Task('persist', priority=3)
        q1.put(t)
        q1_size = q1.size()
        del q1

        q2 = TaskQueue(data_path=self.data_dir)
        self.assertEqual(q2.size(), q1_size)
        got = q2.get(timeout=1)
        self.assertIsNotNone(got)
        self.assertEqual(got.name, 'persist')


# ==================== Test: Worker ====================

class TestWorker(unittest.TestCase):
    def setUp(self):
        self.data_dir = os.path.join(TEST_DATA_DIR, 'worker')
        os.makedirs(self.data_dir, exist_ok=True)
        _tasks.clear()
        _tasks['echo'] = {
            'func': lambda *a, **kw: a[0] if a else 'ok',
            'name': 'echo',
            'max_retries': 3,
            'priority': 0,
        }
        _tasks['fail'] = {
            'func': lambda: (_ for _ in ()).throw(ValueError('boom')),
            'name': 'fail',
            'max_retries': 1,
            'priority': 0,
        }

    def tearDown(self):
        _tasks.clear()
        if os.path.exists(self.data_dir):
            shutil.rmtree(self.data_dir)

    def test_20_worker_execute_success(self):
        """Test 20: Worker executes task successfully"""
        q = TaskQueue(data_path=os.path.join(self.data_dir, 'q'))
        b = ResultBackend(data_path=os.path.join(self.data_dir, 'b'))
        w = Worker('test-w-1', concurrency=2)
        w.start(q, b)
        time.sleep(0.1)

        t = Task('echo', args=['hello'])
        q.put(t)
        time.sleep(0.5)

        result = b.get_result(t.task_id)
        self.assertIsNotNone(result)
        self.assertEqual(result['status'], Task.SUCCESS)

        w.stop()

    def test_21_worker_execute_failure(self):
        """Test 21: Worker handles task failure"""
        q = TaskQueue(data_path=os.path.join(self.data_dir, 'q2'))
        b = ResultBackend(data_path=os.path.join(self.data_dir, 'b2'))
        w = Worker('test-w-2', concurrency=2)
        w.start(q, b)
        time.sleep(0.1)

        t = Task('fail')
        q.put(t)
        time.sleep(1.0)

        result = b.get_result(t.task_id)
        self.assertIsNotNone(result)
        self.assertIn(result['status'], [Task.FAILURE, Task.RETRY])

        w.stop()

    def test_22_worker_retry(self):
        """Test 22: Worker retries on failure"""
        q = TaskQueue(data_path=os.path.join(self.data_dir, 'q3'))
        b = ResultBackend(data_path=os.path.join(self.data_dir, 'b3'))
        w = Worker('test-w-3', concurrency=2)
        w.start(q, b)
        time.sleep(0.1)

        t = Task('fail', max_retries=2)
        q.put(t)
        time.sleep(2.0)

        result = b.get_result(t.task_id)
        self.assertIsNotNone(result)
        self.assertTrue(result['retries'] >= 1)

        w.stop()


# ==================== Test: ResultBackend ====================

class TestResultBackend(unittest.TestCase):
    def setUp(self):
        self.data_dir = os.path.join(TEST_DATA_DIR, 'backend')
        os.makedirs(self.data_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.data_dir):
            shutil.rmtree(self.data_dir)

    def test_23_set_get(self):
        """Test 23: ResultBackend set and get"""
        b = ResultBackend(data_path=self.data_dir)
        t = Task('test', args=[1])
        t.status = Task.SUCCESS
        t.result = 'ok'
        b.set_result(t)

        result = b.get_result(t.task_id)
        self.assertIsNotNone(result)
        self.assertEqual(result['status'], Task.SUCCESS)
        self.assertEqual(result['result'], 'ok')

    def test_24_get_nonexistent(self):
        """Test 24: Get nonexistent task returns None"""
        b = ResultBackend(data_path=self.data_dir)
        result = b.get_result('nonexistent')
        self.assertIsNone(result)

    def test_25_filter_by_status(self):
        """Test 25: Filter results by status"""
        b = ResultBackend(data_path=self.data_dir)

        t1 = Task('a'); t1.status = Task.SUCCESS; t1.result = 1
        t2 = Task('b'); t2.status = Task.FAILURE; t2.error = 'err'
        t3 = Task('c'); t3.status = Task.SUCCESS; t3.result = 2

        b.set_result(t1)
        b.set_result(t2)
        b.set_result(t3)

        success = b.list_results(status=Task.SUCCESS)
        self.assertEqual(len(success), 2)

        failure = b.list_results(status=Task.FAILURE)
        self.assertEqual(len(failure), 1)

    def test_26_persistence(self):
        """Test 26: ResultBackend persistence across instances"""
        b1 = ResultBackend(data_path=self.data_dir)
        t = Task('persist', args=[42])
        t.status = Task.SUCCESS
        t.result = 42
        b1.set_result(t)
        del b1

        b2 = ResultBackend(data_path=self.data_dir)
        result = b2.get_result(t.task_id)
        self.assertIsNotNone(result)
        self.assertEqual(result['result'], 42)


# ==================== Test: Scheduler ====================

class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.data_dir = os.path.join(TEST_DATA_DIR, 'sched')
        os.makedirs(self.data_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.data_dir):
            shutil.rmtree(self.data_dir)

    def test_27_add_and_list(self):
        """Test 27: Scheduler add and list tasks"""
        q = TaskQueue(data_path=os.path.join(self.data_dir, 'q'))
        s = Scheduler(q)
        s.add_task('every_5s', 'echo', interval=5)
        tasks = s.list_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['name'], 'every_5s')
        self.assertEqual(tasks[0]['interval'], 5)

    def test_28_remove_scheduled(self):
        """Test 28: Scheduler remove task"""
        q = TaskQueue(data_path=os.path.join(self.data_dir, 'q2'))
        s = Scheduler(q)
        s.add_task('t1', 'echo', interval=10)
        s.add_task('t2', 'echo', interval=20)
        self.assertEqual(len(s.list_tasks()), 2)
        s.remove_task('t1')
        self.assertEqual(len(s.list_tasks()), 1)

    def test_29_scheduler_fires(self):
        """Test 29: Scheduler fires task into queue"""
        q = TaskQueue(data_path=os.path.join(self.data_dir, 'q3'))
        s = Scheduler(q)
        s.add_task('fast', 'echo', interval=0.5)
        s.start()
        time.sleep(1.5)
        s.stop()
        size = q.size()
        # Should have fired at least 2-3 times
        self.assertGreaterEqual(size, 1)


# ==================== Test: 协议 ====================

class TestProtocol(unittest.TestCase):
    def test_30_encode_decode(self):
        """Test 30: Protocol encode/decode"""
        from server import encode, decode
        resp = encode({'ok': True, 'task_id': 'abc'})
        self.assertTrue(resp.endswith('\n'))
        data = json.loads(resp.strip())
        self.assertTrue(data['ok'])
        self.assertEqual(data['task_id'], 'abc')

    def test_31_decode_submit(self):
        """Test 31: Decode submit command"""
        from server import decode
        cmd, args = decode('SUBMIT {"name": "add", "args": [1, 2]}')
        self.assertEqual(cmd, 'SUBMIT')
        self.assertEqual(args['name'], 'add')
        self.assertEqual(args['args'], [1, 2])

    def test_32_decode_empty_args(self):
        """Test 32: Decode command with no args"""
        from server import decode
        cmd, args = decode('QUEUE_SIZE')
        self.assertEqual(cmd, 'QUEUE_SIZE')
        self.assertEqual(args, {})

    def test_33_decode_invalid_json(self):
        """Test 33: Decode with invalid JSON"""
        from server import decode
        cmd, args = decode('RESULT {bad json}')
        self.assertEqual(cmd, 'RESULT')
        self.assertEqual(args, {})


# ==================== Test: 集成 ====================

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.data_dir = os.path.join(TEST_DATA_DIR, 'integ')
        os.makedirs(self.data_dir, exist_ok=True)
        _tasks.clear()
        _tasks['multiply'] = {
            'func': lambda a, b: a * b,
            'name': 'multiply',
            'max_retries': 3,
            'priority': 0,
        }
        _tasks['slow'] = {
            'func': lambda: time.sleep(0.3) or 'done',
            'name': 'slow',
            'max_retries': 3,
            'priority': 0,
        }

    def tearDown(self):
        _tasks.clear()
        if os.path.exists(self.data_dir):
            shutil.rmtree(self.data_dir)

    def test_34_submit_to_result(self):
        """Test 34: Integration: submit task, wait for result"""
        q = TaskQueue(data_path=os.path.join(self.data_dir, 'q'))
        b = ResultBackend(data_path=os.path.join(self.data_dir, 'b'))
        w = Worker('integ-w', concurrency=2)
        w.start(q, b)
        time.sleep(0.1)

        t = Task('multiply', args=[6, 7])
        q.put(t)
        time.sleep(0.5)

        result = b.get_result(t.task_id)
        self.assertIsNotNone(result)
        self.assertEqual(result['status'], Task.SUCCESS)
        self.assertEqual(result['result'], 42)

        w.stop()

    def test_35_scheduler_auto_execute(self):
        """Test 35: Integration: scheduled task auto-executes"""
        q = TaskQueue(data_path=os.path.join(self.data_dir, 'qs'))
        b = ResultBackend(data_path=os.path.join(self.data_dir, 'bs'))
        s = Scheduler(q)
        w = Worker('integ-s', concurrency=2)
        w.start(q, b)
        s.add_task('int_auto', 'slow', interval=0.3)
        s.start()
        time.sleep(1.5)
        s.stop()
        w.stop()

        results = b.list_results()
        self.assertGreaterEqual(len(results), 1)

    def test_36_worker_concurrency(self):
        """Test 36: Worker processes multiple tasks concurrently"""
        q = TaskQueue(data_path=os.path.join(self.data_dir, 'qc'))
        b = ResultBackend(data_path=os.path.join(self.data_dir, 'bc'))
        w = Worker('integ-c', concurrency=4)
        w.start(q, b)
        time.sleep(0.1)

        for i in range(10):
            t = Task('multiply', args=[i, i])
            q.put(t)

        time.sleep(2.0)

        results = b.list_results()
        success = [r for r in results if r['status'] == Task.SUCCESS]
        self.assertGreaterEqual(len(success), 10)

        w.stop()


# ==================== Run ====================

if __name__ == '__main__':
    clean_test_data()
    try:
        unittest.main(verbosity=2)
    finally:
        clean_test_data()
