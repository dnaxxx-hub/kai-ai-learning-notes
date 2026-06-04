import socket
import json


class ZKClient:
    """ZK 客户端"""

    def __init__(self, host='127.0.0.1', port=2181):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _send(self, cmd, args=None):
        if args is None:
            args = {}
        line = cmd
        if args:
            line += ' ' + json.dumps(args)
        self.sock.sendall((line + '\n').encode())

    def _recv(self):
        data = b''
        while True:
            chunk = self.sock.recv(65536)
            if not chunk:
                break
            data += chunk
            if b'\n' in data:
                line, rest = data.split(b'\n', 1)
                return json.loads(line.decode())
        return None

    def create(self, path, data=b'', ephemeral=False, sequential=False):
        self._send(
            'CREATE', {'path': path, 'data': data, 'ephemeral': ephemeral, 'sequential': sequential}
        )
        return self._recv()

    def delete(self, path, version=-1):
        self._send('DELETE', {'path': path, 'version': version})
        return self._recv()

    def set(self, path, data, version=-1):
        self._send('SET', {'path': path, 'data': data, 'version': version})
        return self._recv()

    def get(self, path):
        self._send('GET', {'path': path})
        return self._recv()

    def children(self, path):
        self._send('CHILDREN', {'path': path})
        return self._recv()

    def exists(self, path):
        self._send('EXISTS', {'path': path})
        return self._recv()

    def stat(self, path):
        self._send('STAT', {'path': path})
        return self._recv()

    def watch(self, path, event='data_changed'):
        self._send('WATCH', {'path': path, 'event': event})
        return self._recv()

    def ping(self):
        self._send('PING', {})
        return self._recv()

    def close_session(self):
        self._send('CLOSE', {})
        return self._recv()
