import threading
import time
from task import Task, get_task_func


class Worker:
    def __init__(self, worker_id, concurrency=4):
        self.worker_id = worker_id
        self.concurrency = concurrency
        self._running = False
        self._threads = []
        self.task_queue = None
        self.backend = None

    def start(self, task_queue, backend):
        self.task_queue = task_queue
        self.backend = backend
        self._running = True
        print(f"Worker {self.worker_id} started (concurrency={self.concurrency})")
        for i in range(self.concurrency):
            t = threading.Thread(target=self._work_loop, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self):
        self._running = False

    def _work_loop(self):
        while self._running:
            try:
                task = self.task_queue.get(timeout=1)
            except Exception:
                continue
            if task is None:
                continue
            self._execute(task)

    def _execute(self, task):
        task.status = Task.RUNNING
        task.started_at = time.time()
        task.worker_id = self.worker_id

        if self.backend:
            self.backend.set_result(task)

        try:
            func_info = get_task_func(task.name)
            if func_info is None:
                raise ValueError(f"任务 {task.name} 未注册")

            func = func_info['func']
            result = func(*task.args, **task.kwargs)

            task.status = Task.SUCCESS
            task.result = result
            task.completed_at = time.time()
        except Exception as e:
            task.status = Task.FAILURE
            task.error = str(e)
            task.completed_at = time.time()

            # 重试
            if task.retries < task.max_retries:
                task.retries += 1
                task.status = Task.RETRY
                task.error = f"{e} (retry {task.retries}/{task.max_retries})"
                if self.task_queue:
                    self.task_queue.put(task)
                    print(f"  Retry {task.task_id} ({task.retries}/{task.max_retries})")

        if self.backend:
            self.backend.set_result(task)

        status_icon = 'OK' if task.status == Task.SUCCESS else 'FAIL'
        elapsed = time.time() - task.started_at
        print(f"  {status_icon} {task.name}[{task.task_id[:8]}] -> {task.status} ({elapsed:.2f}s)")
