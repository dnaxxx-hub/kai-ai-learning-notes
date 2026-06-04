import socket
import selectors
import json
import uuid
import threading
from lock_manager import LockManager
from protocol import encode_response, decode_request


class LockServer:
    def __init__(self, host='0.0.0.0', port=8600):
        self.host = host
        self.port = port
        self.lock_mgr = LockManager()
        self.clients = {}  # {conn_fileno: client_id}
        self.selector = selectors.DefaultSelector()
        self.buffers = {}

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(50)
        sock.setblocking(False)
        self.selector.register(sock, selectors.EVENT_READ, self._accept)
        print(f"🟢 Lock Server on {self.host}:{self.port}")
        self._run()

    def _accept(self, sock, mask):
        conn, addr = sock.accept()
        conn.setblocking(False)
        self.buffers[conn.fileno()] = b''
        self.clients[conn.fileno()] = str(uuid.uuid4())[:8]
        self.selector.register(conn, selectors.EVENT_READ, self._read)
        print(f"  🔗 Client {self.clients[conn.fileno()]} connected from {addr}")

    def _read(self, conn, mask):
        try:
            data = conn.recv(4096)
            if not data:
                self._disconnect(conn)
                return
        except:
            self._disconnect(conn)
            return

        buf = self.buffers[conn.fileno()]
        buf += data
        self.buffers[conn.fileno()] = buf

        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            self.buffers[conn.fileno()] = buf
            self._handle(conn, line.decode('utf-8', errors='ignore').strip())

    def _handle(self, conn, line):
        if not line:
            return
        cmd, args = decode_request(line)
        client_id = self.clients[conn.fileno()]

        if cmd == 'LOCK':
            name = args[0] if len(args) > 0 else 'default'
            lock_type = args[1] if len(args) > 1 else 'mutex'
            timeout = float(args[2]) if len(args) > 2 else None
            result = self.lock_mgr.acquire(name, client_id, lock_type, timeout)
            conn.sendall(encode_response(result['acquired'], result).encode())

        elif cmd == 'RLOCK':
            name = args[0] if len(args) > 0 else 'default'
            timeout = float(args[1]) if len(args) > 1 else None
            result = self.lock_mgr.acquire(name, client_id, 'readwrite', timeout)
            conn.sendall(encode_response(result['acquired'], result).encode())

        elif cmd == 'WLOCK':
            name = args[0] if len(args) > 0 else 'default'
            timeout = float(args[1]) if len(args) > 1 else None
            result = self.lock_mgr.acquire_write(name, client_id, timeout)
            conn.sendall(encode_response(result['acquired'], result).encode())

        elif cmd == 'UNLOCK':
            name = args[0] if len(args) > 0 else 'default'
            mode = args[1] if len(args) > 1 else None
            result = self.lock_mgr.release(name, client_id, mode)
            conn.sendall(encode_response(result['released'], result).encode())

        elif cmd == 'STATUS':
            name = args[0] if len(args) > 0 else None
            result = self.lock_mgr.status(name)
            conn.sendall(encode_response(True, result).encode())

        elif cmd == 'LIST':
            result = self.lock_mgr.list_locks()
            conn.sendall(encode_response(True, result).encode())

        elif cmd == 'HELP':
            help_text = """LOCK <name> [type] [timeout] — 获取互斥锁 (type: mutex/reentrant/fair/readwrite)
RLOCK <name> [timeout] — 获取读锁
WLOCK <name> [timeout] — 获取写锁
UNLOCK <name> [mode] — 释放锁 (mode: read/write)
STATUS [name] — 查看锁状态
LIST — 列出所有锁
HELP — 显示帮助"""
            conn.sendall(encode_response(True, {'help': help_text}).encode())

        else:
            conn.sendall(encode_response(False, error=f'Unknown command: {cmd}').encode())

    def _disconnect(self, conn):
        # 释放该连接持有的所有锁
        client_id = self.clients.pop(conn.fileno(), None)
        if client_id:
            for name in list(self.lock_mgr.list_locks()):
                self.lock_mgr.release(name, client_id)
        self.buffers.pop(conn.fileno(), None)
        try:
            self.selector.unregister(conn)
            conn.close()
        except:
            pass

    def _run(self):
        try:
            while True:
                events = self.selector.select()
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
        except KeyboardInterrupt:
            print("\n🛑 服务器关闭")
