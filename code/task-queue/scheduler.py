import time
import threading

from queue import TaskQueue
from task import Task


class ScheduledTask:
    def __init__(self, name, func_name, interval, args=None, kwargs=None,
                 start_delay=0):
        self.name = name
        self.func_name = func_name
        self.interval = interval
        self.args = args or []
        self.kwargs = kwargs or {}
        self.start_delay = start_delay
        self.enabled = True
        self.last_run = None
        self.next_run = time.time() + start_delay


class Scheduler:
    def __init__(self, queue):
        self.queue = queue
        self.scheduled = {}
        self.running = False
        self._thread = None

    def every(self, name, func_name, interval, args=None, kwargs=None):
        st = ScheduledTask(name, func_name, interval, args, kwargs)
        self.scheduled[name] = st
        return st

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def cancel_task(self, name):
        if name in self.scheduled:
            self.scheduled[name].enabled = False

    def _loop(self):
        while self.running:
            now = time.time()
            for st in list(self.scheduled.values()):
                if st.enabled and now >= st.next_run:
                    task = Task(st.func_name, st.args, st.kwargs)
                    self.queue.enqueue(task)
                    st.last_run = now
                    st.next_run = now + st.interval
            time.sleep(0.5)
