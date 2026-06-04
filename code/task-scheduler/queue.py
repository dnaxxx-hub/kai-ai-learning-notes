import threading
import time
import json
import os
import heapq
from task import Task


class TaskQueue:
    """任务队列（优先级队列）"""

    def __init__(self, data_path='ts_data'):
        self._queue = []  # 堆 [(priority, idx, task)]
        self._counter = 0
        self._lock = threading.Lock()
        self._not_empty = threading.Event()
        self.data_path = data_path
        os.makedirs(data_path, exist_ok=True)
        self._load()

    def put(self, task):
        with self._lock:
            heapq.heappush(self._queue, (-task.priority, self._counter, task))
            self._counter += 1
            self._not_empty.set()
        self._save()

    def get(self, timeout=None):
        deadline = time.time() + timeout if timeout else None
        while True:
            with self._lock:
                while self._queue:
                    _, _, task = heapq.heappop(self._queue)
                    if task.schedule_time and task.schedule_time > time.time():
                        # 定时任务未到时间，放回
                        heapq.heappush(self._queue, (-task.priority, self._counter, task))
                        self._counter += 1
                        break
                    return task

            if deadline and time.time() >= deadline:
                return None

            self._not_empty.wait(timeout=min(timeout or 1, 1))
            if self._not_empty.is_set():
                self._not_empty.clear()

    def peek(self):
        with self._lock:
            return self._queue[0][2] if self._queue else None

    def size(self):
        with self._lock:
            return len(self._queue)

    def _save(self):
        with open(os.path.join(self.data_path, 'queue.json'), 'w') as f:
            with self._lock:
                data = [(t.to_dict(), p, idx) for p, idx, t in self._queue]
            json.dump(data, f, indent=2)

    def _load(self):
        path = os.path.join(self.data_path, 'queue.json')
        if not os.path.exists(path):
            return
        with open(path) as f:
            data = json.load(f)
        for td, p, idx in data:
            t = Task(td['name'], td.get('args', []),
                     td.get('kwargs', {}), td.get('task_id'))
            t.__dict__.update(td)
            heapq.heappush(self._queue, (p, idx, t))
