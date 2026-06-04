import threading
import time

from queue import TaskQueue


class Worker:
    def __init__(self, queue, handlers=None, num_workers=4):
        self.queue = queue
        self.handlers = handlers or {}
        self.num_workers = num_workers
        self.running = False
        self.threads = []

    def register(self, func_name, handler):
        self.handlers[func_name] = handler

    def start(self):
        self.running = True
        for i in range(self.num_workers):
            t = threading.Thread(
                target=self._work_loop, daemon=True, name=f'worker-{i}'
            )
            self.threads.append(t)
            t.start()

    def stop(self):
        self.running = False

    def _work_loop(self):
        while self.running:
            task = self.queue.dequeue(timeout=1.0)
            if task is None:
                continue

            handler = self.handlers.get(task.func_name)
            if handler is None:
                self.queue.fail(task, f"未知任务: {task.func_name}")
                continue

            try:
                result = handler(*task.args, **task.kwargs)
                self.queue.complete(task, result)
            except Exception as e:
                self.queue.fail(task, str(e))
