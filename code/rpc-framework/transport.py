"""transport.py — TCP 传输层（连接池 + 心跳）"""

import socket
import threading
import time
from codec import encode, decode, make_heartbeat, HEADER_SIZE


class Connection:
    """TCP 连接封装"""

    def __init__(self, host, port, timeout=5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock = None
        self._lock = threading.Lock()
        self._connected = False

    def connect(self):
        """建立 TCP 连接"""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect((self.host, self.port))
        self._connected = True
        return self

    def send(self, data):
        """发送数据，线程安全"""
        with self._lock:
            if not self._sock:
                raise ConnectionError("连接已关闭")
            self._sock.sendall(data)

    def recv(self, bufsize=65536):
        """接收数据"""
        if not self._sock:
            raise ConnectionError("连接已关闭")
        return self._sock.recv(bufsize)

    def close(self):
        """关闭连接"""
        with self._lock:
            self._connected = False
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None

    @property
    def is_connected(self):
        return self._connected and self._sock is not None


class ConnectionPool:
    """连接池

    管理到多个服务端口的连接，支持复用和自动清理。
    """

    def __init__(self, max_connections=10, idle_timeout=30):
        self._max_connections = max_connections
        self._idle_timeout = idle_timeout
        self._pool = {}     # {(host, port): [Connection, ...]}
        self._lock = threading.Lock()

    def get_connection(self, host, port, timeout=5):
        """从池中获取或创建连接"""
        key = (host, port)
        with self._lock:
            if key in self._pool and self._pool[key]:
                conn = self._pool[key].pop(0)
                if conn.is_connected:
                    return conn
                # 连接已断开，丢弃
                conn.close()

        # 创建新连接
        conn = Connection(host, port, timeout)
        conn.connect()
        return conn

    def release_connection(self, conn):
        """归还连接到池中"""
        if not conn.is_connected:
            conn.close()
            return
        key = (conn.host, conn.port)
        with self._lock:
            if key not in self._pool:
                self._pool[key] = []
            if len(self._pool[key]) < self._max_connections:
                self._pool[key].append(conn)
            else:
                conn.close()

    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for key, conns in self._pool.items():
                for conn in conns:
                    conn.close()
            self._pool.clear()


class HeartbeatManager:
    """心跳管理器

    定期发送心跳包保持连接活跃。
    """

    def __init__(self, interval=5):
        self.interval = interval
        self._connections = set()
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def start(self):
        """启动心跳线程"""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止心跳线程"""
        self._running = False

    def add_connection(self, conn):
        """添加需要心跳的连接"""
        with self._lock:
            self._connections.add(conn)

    def remove_connection(self, conn):
        """移除连接"""
        with self._lock:
            self._connections.discard(conn)

    def _loop(self):
        """心跳循环"""
        while self._running:
            time.sleep(self.interval)
            with self._lock:
                dead = []
                for conn in list(self._connections):
                    try:
                        conn.send(make_heartbeat())
                    except Exception:
                        dead.append(conn)
                for conn in dead:
                    self._connections.discard(conn)
