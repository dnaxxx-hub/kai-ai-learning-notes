import heapq
import time
import threading

from task import Task


class TaskQueue:
    def __init__(self):
        self._queue = []  # 优先级堆
        self._lock = threading.Lock()
        self._tasks = {}  # {task_id: Task}

    def enqueue(self, task):
        with self._lock:
            heapq.heappush(
                self._queue,
                (task.scheduled_at, task.priority, task.id, task),
            )
            self._tasks[task.id] = task
        return task.id

    def dequeue(self, timeout=0.1):
        """取出可执行的任务"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                while self._queue and self._queue[0][0] <= time.time():
                    _, _, tid, task = heapq.heappop(self._queue)
                    if task.status == Task.CANCELLED:
                        continue
                    task.status = Task.RUNNING
                    task.started_at = time.time()
                    return task
                # 检查是否还有等待中的任务
                if self._queue:
                    wait = max(0, self._queue[0][0] - time.time())
                    time.sleep(min(wait, 0.05))
                else:
                    time.sleep(0.05)
        return None

    def cancel(self, task_id):
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == Task.PENDING:
                task.status = Task.CANCELLED
                return True
        return False

    def complete(self, task, result=None):
        task.status = Task.COMPLETED
        task.completed_at = time.time()
        task.result = result

    def fail(self, task, error=None):
        task.retries += 1
        if task.retries >= task.max_retries:
            task.status = Task.FAILED
            task.error = error
        else:
            task.status = Task.PENDING
            task.scheduled_at = time.time() + 2 ** task.retries  # 指数退避
            with self._lock:
                heapq.heappush(
                    self._queue,
                    (task.scheduled_at, task.priority, task.id, task),
                )

    def size(self):
        with self._lock:
            return len(self._queue)

    def get_task(self, task_id):
        with self._lock:
            return self._tasks.get(task_id)

    def get_all(self):
        with self._lock:
            return list(self._tasks.values())
