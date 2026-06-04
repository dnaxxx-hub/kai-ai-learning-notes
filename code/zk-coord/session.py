import threading
import time
import uuid


class Session:
    def __init__(self, session_id, timeout=10):
        self.session_id = session_id
        self.timeout = timeout
        self.last_heartbeat = time.time()
        self.active = True

    def is_expired(self):
        return self.active and (time.time() - self.last_heartbeat > self.timeout)

    def keepalive(self):
        self.last_heartbeat = time.time()
        self.active = True

    def close(self):
        self.active = False


class SessionManager:
    def __init__(self, tree, watcher_mgr):
        self.sessions = {}  # {session_id: Session}
        self.tree = tree
        self.watcher = watcher_mgr
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._expire_loop, daemon=True)
        self._thread.start()

    def create_session(self, timeout=10):
        session_id = str(uuid.uuid4())
        session = Session(session_id, timeout)
        with self._lock:
            self.sessions[session_id] = session
        return session_id

    def keepalive(self, session_id):
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.keepalive()
                return True
            return False

    def close_session(self, session_id):
        """关闭 session（外部调用，持有锁）"""
        with self._lock:
            session = self.sessions.pop(session_id, None)
            if session is None:
                return False
            session.close()
        # 释放锁后清理临时节点 + 通知
        removed = self.tree.clean_ephemeral(session_id)
        for path in removed:
            self.watcher.notify(path, 'deleted')
        return True

    def _expire_loop(self):
        while self._running:
            expired = self._get_expired()
            for sid in expired:
                self.close_session(sid)
            time.sleep(0.1)

    def _get_expired(self):
        with self._lock:
            return [sid for sid, s in list(self.sessions.items()) if s.is_expired()]

    def stop(self):
        self._running = False
