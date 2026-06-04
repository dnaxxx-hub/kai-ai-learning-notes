import uuid
import time
import json


class Task:
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

    def __init__(self, func_name, args=None, kwargs=None, priority=0,
                 delay=0, max_retries=3, timeout=30):
        self.id = str(uuid.uuid4())
        self.func_name = func_name
        self.args = args or []
        self.kwargs = kwargs or {}
        self.priority = priority  # 数字越小优先级越高
        self.delay = delay  # 延迟秒数
        self.max_retries = max_retries
        self.timeout = timeout
        self.status = self.PENDING
        self.retries = 0
        self.created_at = time.time()
        self.scheduled_at = time.time() + delay if delay > 0 else time.time()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d):
        t = cls('')
        t.__dict__.update(d)
        return t

    def __lt__(self, other):
        # 优先级队列排序：先按调度时间，再按优先级
        if self.scheduled_at != other.scheduled_at:
            return self.scheduled_at < other.scheduled_at
        return self.priority < other.priority

    def __repr__(self):
        return (f"Task(id={self.id[:8]}, func={self.func_name}, "
                f"status={self.status}, priority={self.priority})")
