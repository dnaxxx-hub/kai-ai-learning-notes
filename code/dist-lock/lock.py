import uuid
import time
import threading


class Lock:
    """分布式互斥锁"""

    def __init__(self, name, manager):
        self.name = name
        self.manager = manager
        self.owner = None  # 当前持有者 ID
        self.queue = []  # 等待队列 [client_id, ...]
        self.waiters = {}  # {client_id: event}
        self.lock = threading.Lock()

    def acquire(self, client_id, timeout=None, blocking=True):
        """尝试获取锁
        timeout: 获取锁的超时（秒）
        blocking: 是否阻塞等待
        """
        with self.lock:
            if self.owner is None:
                self.owner = client_id
                return {'acquired': True, 'owner': client_id}

            if not blocking:
                return {'acquired': False, 'reason': 'locked'}

            # 阻塞模式：加入等待队列
            event = threading.Event()
            self.queue.append(client_id)
            self.waiters[client_id] = event

        acquired = event.wait(timeout=timeout)
        with self.lock:
            if acquired:
                self.owner = client_id
                self.queue.remove(client_id)
                del self.waiters[client_id]
                return {'acquired': True, 'owner': client_id}
            else:
                # 超时
                self.queue.remove(client_id)
                del self.waiters[client_id]
                return {'acquired': False, 'reason': 'timeout'}

    def release(self, client_id):
        """释放锁"""
        with self.lock:
            if self.owner != client_id:
                return {'released': False, 'reason': 'not_owner'}
            self.owner = None

            # 通知下一个等待者
            if self.queue:
                next_client = self.queue[0]
                self.waiters[next_client].set()

            return {'released': True}

    def is_locked(self):
        with self.lock:
            return self.owner is not None

    def status(self):
        with self.lock:
            return {
                'name': self.name,
                'owner': self.owner,
                'queue_length': len(self.queue),
                'waiters': list(self.queue),
            }


class ReentrantLock(Lock):
    """可重入锁 — 同一个客户端可多次 acquire"""

    def __init__(self, name, manager):
        super().__init__(name, manager)
        self._reentrant_count = 0

    def acquire(self, client_id, timeout=None, blocking=True):
        with self.lock:
            if self.owner == client_id:
                self._reentrant_count += 1
                return {'acquired': True, 'owner': client_id, 'reentrant': True}

        result = super().acquire(client_id, timeout, blocking)
        if result['acquired']:
            with self.lock:
                self._reentrant_count = 1
        return result

    def release(self, client_id):
        need_full_release = False
        with self.lock:
            if self.owner == client_id and self._reentrant_count > 0:
                self._reentrant_count -= 1
                if self._reentrant_count == 0:
                    need_full_release = True
                else:
                    return {'released': True, 'reentrant': True}

        if need_full_release:
            return super().release(client_id)
        return super().release(client_id)


class ReadWriteLock:
    """读写锁 — 读读共享，读写互斥，写写互斥"""

    def __init__(self, name, manager):
        self.name = name
        self.manager = manager
        self._readers = set()
        self._writer = None
        self._write_waiters = []
        self._reader_events = {}
        self._writer_event = None
        self._reader_lock = threading.Lock()
        self._write_lock = threading.Lock()

    def acquire_read(self, client_id, timeout=None):
        with self._write_lock:
            if self._writer is None:
                with self._reader_lock:
                    self._readers.add(client_id)
                    return {'acquired': True, 'mode': 'read'}

            if timeout is not None and timeout <= 0:
                return {'acquired': False, 'reason': 'writing'}

        event = threading.Event()
        self._reader_events[client_id] = event
        acquired = event.wait(timeout)
        if acquired:
            with self._reader_lock:
                self._readers.add(client_id)
            return {'acquired': True, 'mode': 'read'}
        return {'acquired': False, 'reason': 'timeout'}

    def acquire_write(self, client_id, timeout=None):
        with self._write_lock:
            if self._writer is None and len(self._readers) == 0:
                self._writer = client_id
                return {'acquired': True, 'mode': 'write'}

        event = threading.Event()
        self._writer_event = event
        self._write_waiters.append(client_id)
        acquired = event.wait(timeout)
        if acquired:
            self._writer = client_id
            return {'acquired': True, 'mode': 'write'}
        return {'acquired': False, 'reason': 'timeout'}

    def release_read(self, client_id):
        with self._reader_lock:
            if client_id not in self._readers:
                return {'released': False, 'reason': 'not_reader'}
            self._readers.remove(client_id)

            if len(self._readers) == 0 and self._writer_event is not None and self._write_waiters:
                self._writer_event.set()
                self._writer_event = None
                self._write_waiters.pop(0)

            return {'released': True}

    def release_write(self, client_id):
        with self._write_lock:
            if self._writer != client_id:
                return {'released': False, 'reason': 'not_writer'}
            self._writer = None

            # 优先通知写等待者
            if self._write_waiters:
                self._writer_event.set()
                self._writer_event = None
                self._write_waiters.pop(0)
            elif self._reader_events:
                for cid, evt in list(self._reader_events.items()):
                    evt.set()
                self._reader_events.clear()

            return {'released': True}

    def release(self, client_id):
        if self._writer == client_id:
            return self.release_write(client_id)
        if client_id in self._readers:
            return self.release_read(client_id)
        return {'released': False, 'reason': 'not_owner'}

    def status(self):
        return {
            'name': self.name,
            'type': 'readwrite',
            'readers': list(self._readers),
            'writer': self._writer,
        }


class FairLock(Lock):
    """公平锁 — 严格按请求顺序 (FIFO)"""

    def __init__(self, name, manager):
        super().__init__(name, manager)
        self._request_queue = []

    def acquire(self, client_id, timeout=None, blocking=True):
        with self.lock:
            self._request_queue.append(client_id)
            if self.owner is None and self._request_queue[0] == client_id:
                self.owner = client_id
                self._request_queue.pop(0)
                return {'acquired': True, 'owner': client_id}

        if not blocking:
            with self.lock:
                self._request_queue.remove(client_id)
            return {'acquired': False, 'reason': 'locked'}

        event = threading.Event()
        with self.lock:
            self.waiters[client_id] = event

        acquired = event.wait(timeout=timeout)
        with self.lock:
            if acquired:
                self.owner = client_id
                self._request_queue.pop(0)
                del self.waiters[client_id]
                return {'acquired': True, 'owner': client_id}
            self._request_queue.remove(client_id)
            del self.waiters[client_id]
            return {'acquired': False, 'reason': 'timeout'}

    def release(self, client_id):
        with self.lock:
            if self.owner != client_id:
                return {'released': False, 'reason': 'not_owner'}
            self.owner = None

            # notify next waiter in FIFO order (enforced by _request_queue)
            if self.queue:
                next_client = self.queue[0]
                self.waiters[next_client].set()
            # also check request_queue for any remaining waiters
            elif self._request_queue:
                for cid in list(self._request_queue):
                    if cid in self.waiters:
                        self.waiters[cid].set()
                        break

            return {'released': True}
