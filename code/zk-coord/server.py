import socket
import selectors
import json
from tree import ZNodeTree
from znode import ZNode
from watcher import WatcherManager
from session import SessionManager


# 简单文本协议
def encode(resp):
    return json.dumps(resp) + '\n'


def decode(line):
    parts = line.strip().split(maxsplit=1)
    cmd = parts[0].upper() if parts else ''
    args_str = parts[1] if len(parts) > 1 else ''
    try:
        args = json.loads(args_str) if args_str else {}
    except Exception:
        args = {'raw': args_str}
    return cmd, args


class ZKServer:
    def __init__(self, host='0.0.0.0', port=2181):
        self.host = host
        self.port = port
        self.tree = ZNodeTree()
        self.watcher = WatcherManager()
        self.sessions = SessionManager(self.tree, self.watcher)
        self.selector = selectors.DefaultSelector()
        self.buffers = {}
        self.connections = {}  # {fd: session_id}

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(50)
        sock.setblocking(False)
        self.selector.register(sock, selectors.EVENT_READ, self._accept)
        print(f"🟢 ZK Coordinator on {self.host}:{self.port}")

        try:
            while True:
                events = self.selector.select()
                for key, mask in events:
                    key.data(key.fileobj, mask)
        except KeyboardInterrupt:
            self.sessions.stop()

    def _accept(self, sock, mask):
        conn, addr = sock.accept()
        conn.setblocking(False)
        self.buffers[conn.fileno()] = b''
        self.connections[conn.fileno()] = self.sessions.create_session()
        self.selector.register(conn, selectors.EVENT_READ, self._read)

    def _read(self, conn, mask):
        try:
            data = conn.recv(65536)
            if not data:
                return self._disconnect(conn)
        except Exception:
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
        cmd, args = decode(line)
        sess_id = self.connections.get(conn.fileno(), '')

        try:
            if cmd == 'CREATE':
                path = args.get('path', '')
                data = args.get('data', b'')
                if isinstance(data, str):
                    data = data.encode()
                eph = args.get('ephemeral', False)
                seq = args.get('sequential', False)
                ntype = ZNode.PERSISTENT
                if eph and seq:
                    ntype = ZNode.EPHEMERAL_SEQUENTIAL
                elif eph:
                    ntype = ZNode.EPHEMERAL
                elif seq:
                    ntype = ZNode.PERSISTENT_SEQUENTIAL
                node = self.tree.create(path, data, ntype, sess_id)
                if node:
                    self.watcher.notify(path, 'created')
                    conn.sendall(encode({'ok': True, 'path': node.path}).encode())
                else:
                    conn.sendall(encode({'ok': False, 'error': 'create_failed'}).encode())

            elif cmd == 'DELETE':
                path = args.get('path', '')
                ver = args.get('version', -1)
                if self.tree.delete(path, ver):
                    self.watcher.notify(path, 'deleted')
                    conn.sendall(encode({'ok': True}).encode())
                else:
                    conn.sendall(encode({'ok': False, 'error': 'delete_failed'}).encode())

            elif cmd == 'SET':
                path = args.get('path', '')
                data = args.get('data', b'')
                if isinstance(data, str):
                    data = data.encode()
                ver = args.get('version', -1)
                node = self.tree.set_data(path, data, ver)
                if node:
                    self.watcher.notify(path, 'data_changed')
                    conn.sendall(encode({'ok': True, 'version': node.version}).encode())
                else:
                    conn.sendall(encode({'ok': False, 'error': 'not_found'}).encode())

            elif cmd == 'GET':
                path = args.get('path', '')
                data = self.tree.get_data(path)
                conn.sendall(
                    encode(
                        {'ok': data is not None, 'data': data.decode() if data else None}
                    ).encode()
                )

            elif cmd == 'CHILDREN':
                path = args.get('path', '')
                children = self.tree.get_children(path)
                conn.sendall(
                    encode(
                        {'ok': children is not None, 'children': children}
                    ).encode()
                )

            elif cmd == 'EXISTS':
                path = args.get('path', '')
                conn.sendall(encode({'ok': True, 'exists': self.tree.exists(path)}).encode())

            elif cmd == 'STAT':
                path = args.get('path', '')
                st = self.tree.stat(path)
                conn.sendall(encode({'ok': st is not None, 'stat': st}).encode())

            elif cmd == 'WATCH':
                path = args.get('path', '')
                event = args.get('event', 'data_changed')

                def callback(evt):
                    try:
                        conn.sendall(encode({'watch': evt}).encode())
                    except Exception:
                        pass

                self.watcher.watch(path, event, callback)
                conn.sendall(
                    encode({'ok': True, 'watching': path, 'event': event}).encode()
                )

            elif cmd == 'PING':
                self.sessions.keepalive(sess_id)
                conn.sendall(encode({'ok': True, 'pong': True}).encode())

            elif cmd == 'CLOSE':
                self.sessions.close_session(sess_id)
                conn.sendall(encode({'ok': True, 'closed': True}).encode())

            else:
                conn.sendall(encode({'ok': False, 'error': f'unknown: {cmd}'}).encode())

        except Exception as e:
            conn.sendall(encode({'ok': False, 'error': str(e)}).encode())

    def _disconnect(self, conn):
        sess_id = self.connections.pop(conn.fileno(), None)
        if sess_id:
            self.sessions.close_session(sess_id)
        self.buffers.pop(conn.fileno(), None)
        try:
            self.selector.unregister(conn)
            conn.close()
        except Exception:
            pass
