from lock import Lock, ReentrantLock, ReadWriteLock, FairLock
import threading
import time


class LockManager:
    def __init__(self):
        self.locks = {}  # {lock_name: LockInstance}
        self._lock = threading.Lock()

    def get_lock(self, name, lock_type='mutex'):
        with self._lock:
            if name not in self.locks:
                if lock_type == 'reentrant':
                    self.locks[name] = ReentrantLock(name, self)
                elif lock_type == 'readwrite':
                    self.locks[name] = ReadWriteLock(name, self)
                elif lock_type == 'fair':
                    self.locks[name] = FairLock(name, self)
                else:
                    self.locks[name] = Lock(name, self)
            return self.locks[name]

    def acquire(self, name, client_id, lock_type='mutex', timeout=None, blocking=True):
        lock = self.get_lock(name, lock_type)
        if lock_type == 'readwrite':
            return lock.acquire_read(client_id, timeout)
        return lock.acquire(client_id, timeout, blocking)

    def acquire_write(self, name, client_id, timeout=None):
        lock = self.get_lock(name, 'readwrite')
        return lock.acquire_write(client_id, timeout)

    def release(self, name, client_id, mode=None):
        lock = self.locks.get(name)
        if not lock:
            return {'released': False, 'reason': 'no_such_lock'}
        if mode == 'read':
            return lock.release_read(client_id)
        if mode == 'write':
            return lock.release_write(client_id)
        return lock.release(client_id)

    def status(self, name=None):
        if name:
            lock = self.locks.get(name)
            return lock.status() if lock else {'error': 'not_found'}
        return {name: l.status() for name, l in self.locks.items()}

    def list_locks(self):
        return list(self.locks.keys())
